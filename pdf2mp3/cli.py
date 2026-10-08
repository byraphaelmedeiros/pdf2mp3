"""Command parsing, local preflight and presentation for the v2 CLI."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess  # nosec B404 - fixed say voice inventory, no shell
import sys
import tempfile
import traceback
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any, NoReturn, cast

from pydub import AudioSegment

from . import pdf2mp3 as app


class Failure(Exception):
    """A safe, stable error suitable for both CLI presentations."""

    def __init__(self, code: str, message: str, exit_code: int, data: Any = None):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.data = data


class Parser(argparse.ArgumentParser):
    """Route parsing errors through the safe human/JSON failure contract."""

    def error(self, message: str) -> NoReturn:
        """Reject invalid syntax without echoing user-supplied argument values."""
        # argparse messages can echo arbitrary argument values, including secrets.
        raise Failure("invalid_arguments", f"Invalid arguments; see {self.prog} --help.", 2)


def parser() -> Parser:
    """Build both subcommands with shared defaults and unambiguous option names."""
    result = Parser(
        prog="pdf2mp3",
        allow_abbrev=False,
        description="Convert selectable PDF text to MP3, or check local readiness without speech.",
        epilog=(
            "Requires Python 3.10+ and FFmpeg/ffprobe on PATH. Languages: en, pt-br.\n"
            "Scanned PDFs need OCR first. Edge, gTTS and OpenAI send text to external\n"
            "services and need Internet access.\n\nExamples:\n"
            "  pdf2mp3 convert local/inputs/demo.pdf --output local/outputs/demo-edge.mp3\n"
            "  pdf2mp3 check local/inputs/demo.pdf --engine edge --json\n"
            "  python -m pdf2mp3 convert local/inputs/demo.pdf --rate -5% "
            "--output local/outputs/demo-slower.mp3"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    result.add_argument("--version", action="version", version=f"pdf2mp3 {app.__version__}")
    _presentation_options(result, suppress=False)
    commands = result.add_subparsers(dest="command", title="commands", parser_class=Parser)
    for name, description in (
        ("convert", "Extract text, synthesize speech and save an MP3."),
        ("check", "Check local dependencies and optionally prepare a PDF; no speech or writes."),
    ):
        command = commands.add_parser(
            name, help=description, description=description, allow_abbrev=False
        )
        command.add_argument(
            "input",
            metavar="INPUT",
            nargs="?" if name == "check" else None,
            help="PDF with selectable text (scans need OCR)",
        )
        config = command.add_argument_group("preparation and provider")
        config.add_argument("-l", "--lang", default="pt-br", help="en or pt-br (default: pt-br)")
        config.add_argument(
            "--engine",
            choices=app.ENGINE_CHOICES,
            default=app.DEFAULT_ENGINE,
            help="speech provider (default: edge)",
        )
        config.add_argument(
            "--voice",
            help="Edge/OpenAI voice, or exact local voice name/ID; "
            "defaults: pt-BR-ThalitaNeural, en-US-AriaNeural, alloy (OpenAI), system (local)",
        )
        config.add_argument(
            "--model", help=f"OpenAI Realtime only (default: {app.DEFAULT_OPENAI_MODEL})"
        )
        config.add_argument("--rate", help="Edge only, signed integer percent (default: +0%%)")
        config.add_argument("--volume", help="Edge only, signed integer percent (default: +0%%)")
        config.add_argument(
            "--max-chars",
            type=int,
            default=app.DEFAULT_MAX_CHARS,
            help="positive maximum characters per chunk (default: 1600)",
        )
        output = command.add_argument_group("destination")
        output.add_argument("-o", "--output", help="MP3 destination (default: <INPUT>.mp3)")
        output.add_argument(
            "--overwrite", action="store_true", help="allow replacement of an existing destination"
        )
        _presentation_options(command, suppress=True)
    return result


def _presentation_options(target: argparse.ArgumentParser, *, suppress: bool) -> None:
    group = target.add_argument_group("presentation")
    for flag, help_text in (
        ("json", "emit one schema-versioned JSON result (help/version remain text)"),
        ("quiet", "suppress progress; preserve result and errors"),
        ("debug", "include safe exception types and stack locations on stderr"),
    ):
        group.add_argument(
            f"--{flag}",
            action="store_true",
            default=argparse.SUPPRESS if suppress else False,
            help=help_text,
        )


def _percent_arguments(argv: list[str]) -> list[str]:
    """argparse treats '-5%' as an option; attach signed percentages to their flag."""
    result: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--":
            result.extend(argv[index:])
            break
        if (
            argument in {"--rate", "--volume"}
            and index + 1 < len(argv)
            and re.fullmatch(r"[+-][0-9]+%", argv[index + 1])
        ):
            result.append(f"{argument}={argv[index + 1]}")
            index += 2
        else:
            result.append(argument)
            index += 1
    return result


def _configure(args: argparse.Namespace) -> None:
    """Normalize configuration and reject incompatible options before processing."""
    if args.output is not None and not args.output.strip():
        raise Failure("invalid_arguments", "--output must be a nonempty path.", 2)
    if args.max_chars <= 0:
        raise Failure("invalid_arguments", "--max-chars must be a positive integer.", 2)
    try:
        args.lang = app.normalize_lang(args.lang)
    except ValueError:
        raise Failure("invalid_arguments", "--lang must select en or pt-br.", 2) from None
    for option in ("voice", "model"):
        value = getattr(args, option)
        if value is not None and (not value.strip() or any(ord(c) < 32 for c in value)):
            raise Failure("invalid_arguments", f"--{option} must be a nonempty name.", 2)
    if args.model is not None and args.engine != "openai":
        raise Failure("invalid_arguments", "--model is only supported by OpenAI.", 2)
    if args.voice is not None and args.engine == "gtts":
        raise Failure("invalid_arguments", "gTTS uses --lang and does not support --voice.", 2)
    for option in ("rate", "volume"):
        value = getattr(args, option)
        if value is not None and (args.engine != "edge" or not re.fullmatch(r"[+-][0-9]+%", value)):
            raise Failure(
                "invalid_arguments", f"--{option} requires Edge and a signed integer percent.", 2
            )
    args.rate = args.rate or "+0%"
    args.volume = args.volume or "+0%"
    if args.engine == "edge":
        args.voice = args.voice or app.VOICE_BY_LANG[args.lang]
        if not re.fullmatch(r"[a-z]{2,3}-[A-Z]{2}-.+Neural", args.voice):
            raise Failure("invalid_arguments", "Use an Edge voice ID such as en-US-AriaNeural.", 2)
    elif args.engine == "openai":
        args.voice = args.voice or app.DEFAULT_OPENAI_VOICE
        args.model = args.model or app.DEFAULT_OPENAI_MODEL
        from .openai_tts import validate_options

        try:
            validate_options(args.model, args.voice)
        except ValueError as exc:
            raise Failure("invalid_arguments", str(exc), 2) from None
    if args.input is None and (args.output or args.overwrite):
        raise Failure("invalid_arguments", "Destination options require an INPUT PDF.", 2)


def _paths(args: argparse.Namespace) -> tuple[Path | None, Path | None]:
    if args.input is None:
        return None, None
    source = Path(args.input).expanduser().resolve()
    if not source.is_file():
        raise Failure("input_missing", "Input PDF is missing or is not a regular file.", 1)
    output = Path(args.output).expanduser().resolve() if args.output else source.with_suffix(".mp3")
    if output == source or (output.exists() and output.samefile(source)):
        raise Failure("invalid_arguments", "Output must not refer to the input PDF.", 2)
    if output.exists() and (not args.overwrite or not output.is_file()):
        raise Failure(
            "output_exists", "Destination exists; choose another path or use --overwrite.", 2
        )
    return source, output


def _dependencies(args: argparse.Namespace) -> list[dict[str, Any]]:
    checks = [
        {"name": name, "ok": shutil.which(name) is not None} for name in ("ffmpeg", "ffprobe")
    ]
    if args.engine in {"gtts", "openai", "pyttsx3"}:
        checks.append(
            {"name": args.engine, "ok": importlib.util.find_spec(args.engine) is not None}
        )
    if args.engine == "openai":
        checks.append(
            {"name": "websockets", "ok": importlib.util.find_spec("websockets") is not None}
        )
        checks.append({"name": "OPENAI_API_KEY", "ok": bool(os.environ.get("OPENAI_API_KEY"))})
    if args.engine == "pyttsx3":
        if sys.platform == "darwin":
            checks.append({"name": "objc", "ok": importlib.util.find_spec("objc") is not None})
        elif sys.platform.startswith("linux"):
            checks.append(
                {"name": "espeak", "ok": bool(shutil.which("espeak") or shutil.which("espeak-ng"))}
            )
    if args.engine == "say":
        available = sys.platform == "darwin" and shutil.which("say") is not None
        checks.append({"name": "macOS say", "ok": available})
        if available and args.voice is not None:
            with _boundary("dependency_missing", "Unable to inspect local say voices.", 2):
                inventory = subprocess.run(
                    ["say", "-v", "?"], capture_output=True, text=True, check=True, timeout=5
                )  # nosec B603 B607 - fixed read-only command
            names = {
                line.split("#", 1)[0].rsplit(maxsplit=1)[0].strip()
                for line in inventory.stdout.splitlines()
                if line.strip()
            }
            if args.voice not in names:
                raise Failure("invalid_arguments", "Requested say voice is not installed.", 2)
    return checks


@contextmanager
def _boundary(code: str, message: str, exit_code: int) -> Iterator[None]:
    try:
        yield
    except (Failure, KeyboardInterrupt):
        raise
    except Exception as exc:
        raise Failure(code, message, exit_code) from exc


def _prepare(source: Path, max_chars: int) -> tuple[list[str], int]:
    app_logger = logging.getLogger("pdf2mp3")
    app_logger.info("Extracting PDF text")
    with _boundary(
        "pdf_failed", "Failed to extract PDF text; check the PDF format and encryption.", 6
    ):
        raw = app.extract_text_from_pdf(source)
        if not raw.strip():
            raise Failure("no_text", "No readable text; scanned PDFs require OCR first.", 3)
        cleaned = app.clean_text(raw)
        chunks = [
            app.sanitize_for_tts(chunk)
            for chunk in app.split_into_chunks(cleaned, max_chars=max_chars)
        ]
        if not chunks or not any(chunk.strip() for chunk in chunks):
            raise Failure("empty_text", "No content remains after text preparation.", 4)
    app_logger.info("Prepared %d chunks", len(chunks))
    return chunks, len(cleaned)


def _speech(chunks: list[str], args: argparse.Namespace) -> AudioSegment:
    if args.engine == "edge":
        return asyncio.run(
            app.synthesize_chunks(chunks, voice=args.voice, rate=args.rate, volume=args.volume)
        )
    if args.engine == "gtts":
        language = "pt" if args.lang == "pt-br" else "en"
        return app.synthesize_chunks_sync(
            chunks, lambda text: app.tts_chunk_gtts(text, lang=language)
        )
    if args.engine == "openai":
        return app.synthesize_chunks_sync(
            chunks, lambda text: app.tts_chunk_openai(text, model=args.model, voice=args.voice)
        )
    if args.engine == "pyttsx3":
        return app.synthesize_chunks_pyttsx3(chunks, voice=args.voice)
    return app.synthesize_chunks_say(chunks, voice=args.voice)


def _export(audio: AudioSegment, output: Path, overwrite: bool) -> None:
    """Commit fully encoded audio, reserving new destinations and cleaning owned files."""
    temporary: Path | None = None
    reservation: tuple[int, int] | None = None
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".mp3", delete=False) as stream:
            temporary = Path(stream.name)
        audio.export(temporary, format="mp3").close()
        if not overwrite:
            try:
                with output.open("xb") as stream:
                    stat = os.fstat(stream.fileno())
                    reservation = (stat.st_dev, stat.st_ino)
            except FileExistsError:
                raise Failure(
                    "output_exists",
                    "Destination was created during conversion; it was preserved.",
                    2,
                ) from None
        temporary.replace(output)
        reservation = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if reservation is not None and output.exists():
            stat = output.stat()
            if (stat.st_dev, stat.st_ino) == reservation:
                output.unlink()


def _execute(args: argparse.Namespace) -> dict[str, Any]:
    with _boundary("invalid_arguments", "Unable to validate input and destination paths.", 2):
        source, output = _paths(args)
    data: dict[str, Any] = {
        "input": str(source) if source is not None else None,
        "output": str(output) if output is not None else None,
        "engine": args.engine,
        "language": args.lang,
        "voice": args.voice,
        "model": args.model,
        "rate": args.rate if args.engine == "edge" else None,
        "volume": args.volume if args.engine == "edge" else None,
        "max_chars": args.max_chars,
        "external_processing": args.engine in {"edge", "gtts", "openai"},
        "chunks": 0,
        "characters": 0,
    }
    with _boundary("dependency_missing", "Unable to inspect local provider requirements.", 2):
        checks = _dependencies(args)
    if args.command == "check":
        data.update(checks=checks, speech_verified=False)
    if not all(item["ok"] for item in checks):
        missing = ", ".join(item["name"] for item in checks if not item["ok"])
        raise Failure("dependency_missing", f"Missing local requirements: {missing}.", 2, data)
    chunks: list[str] = []
    if source is not None:
        chunks, data["characters"] = _prepare(source, args.max_chars)
        data["chunks"] = len(chunks)
    if args.command == "convert":
        with _boundary(
            "speech_failed", "Speech synthesis failed; check provider setup and availability.", 5
        ):
            audio = _speech(chunks, args)
        with _boundary(
            "output_failed", "Failed to save MP3; check destination permissions and FFmpeg.", 7
        ):
            # convert requires INPUT, so path validation always provides a destination.
            _export(audio, cast(Path, output), args.overwrite)
        data["duration_seconds"] = len(audio) / 1000
    return data


@contextmanager
def _diagnostics(quiet: bool) -> Iterator[None]:
    logger = logging.getLogger("pdf2mp3")
    state = logger.handlers[:], logger.level, logger.propagate
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers = [handler]
    logger.setLevel(logging.WARNING if quiet else logging.INFO)
    logger.propagate = False
    try:
        yield
    finally:
        logger.handlers, logger.level, logger.propagate = state
        handler.close()


def main(argv: list[str] | None = None) -> int:
    """Present one CLI result and return its exit code; argparse help/version exit 0.

    Omitted argv uses sys.argv[1:]. Progress and safe diagnostics go to stderr;
    JSON results go to stdout. This internal entry point returns an integer,
    whereas the exported pdf2mp3.main wrapper exits only on nonzero results.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    options = argv[: argv.index("--")] if "--" in argv else argv
    machine = "--json" in options
    command = next((item for item in options if item in {"convert", "check"}), None)
    cli = parser()
    if not argv:
        cli.print_help()
        return 0
    failure: Failure | None = None
    data: Any = None
    try:
        args = cli.parse_args(_percent_arguments(argv))
        if args.command is None:
            raise Failure("invalid_arguments", "Choose convert or check; see pdf2mp3 --help.", 2)
        command = args.command
        _configure(args)
        with _diagnostics(args.quiet), redirect_stdout(sys.stderr):
            data = _execute(args)
    except KeyboardInterrupt as exc:
        failure = Failure("interrupted", "Operation cancelled.", 130)
        failure.__cause__ = exc
    except Failure as exc:
        failure = exc
    if failure is not None:
        data = failure.data
        if "--debug" in options and failure.__cause__ is not None:
            cause = failure.__cause__
            print(f"Diagnostic: {type(cause).__name__}", file=sys.stderr)
            for frame in traceback.extract_tb(cause.__traceback__):
                print(
                    f"  {Path(frame.filename).name}:{frame.lineno} in {frame.name}", file=sys.stderr
                )
    if machine:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "command": command,
                    "ok": failure is None,
                    "data": data,
                    "error": None
                    if failure is None
                    else {
                        "code": failure.code,
                        "message": str(failure),
                        "exit_code": failure.exit_code,
                    },
                },
                ensure_ascii=True,
            )
        )
    elif failure is not None:
        print(f"Error [{failure.code}]: {failure}", file=sys.stderr)
    elif command == "convert":
        print(f"Saved {data['output']} ({data['chunks']} chunks, {data['duration_seconds']:.3f}s)")
    else:
        print(f"Local checks passed for {data['engine']}; speech was not tested.")
        print(
            f"Prepared {data['chunks']} chunks, {data['characters']} characters. "
            f"External text processing: {'yes' if data['external_processing'] else 'no'}."
        )
    return failure.exit_code if failure is not None else 0
