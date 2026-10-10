#!/usr/bin/env python3
"""Build and exercise base wheel and sdist installs outside the source checkout."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

from create_demo_pdf import create_demo_pdf
from documentation_check import ignored_paths
from pydub.generators import Sine

ROOT = Path(__file__).resolve().parents[1]


def run(command, cwd, env=None):
    subprocess.run(list(map(str, command)), cwd=cwd, env=env, check=True, timeout=240)


def python_in(environment):
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def smoke(python, work):
    work.mkdir()
    run([python, "-m", "pip", "check"], work)
    cli = python.parent / ("pdf2mp3.exe" if os.name == "nt" else "pdf2mp3")
    pdf = work / "synthetic.pdf"
    create_demo_pdf(pdf, "en")
    original = pdf.read_bytes()
    Sine(440).to_audio_segment(duration=100).export(work / "tone.mp3", format="mp3").close()
    # A test-only provider boundary and network guard; no production test switch.
    shutil.copy2(ROOT / "scripts/network_guard.py", work / "network_guard.py")
    (work / "sitecustomize.py").write_text("""from network_guard import block_network
block_network()
import os
from pathlib import Path
import pdf2mp3.pdf2mp3 as app

async def synthetic(*args, **kwargs):
    if os.environ.get("PDF2MP3_SMOKE_INTERRUPT") == "speech":
        raise KeyboardInterrupt()
    return Path(__file__).with_name("tone.mp3").read_bytes()
app.tts_chunk = synthetic
if os.environ.get("PDF2MP3_SMOKE_INTERRUPT") == "export":
    def interrupted_export(self, destination, **kwargs):
        Path(destination).write_bytes(b"incomplete synthetic audio")
        raise KeyboardInterrupt()
    app.AudioSegment.export = interrupted_export
""")
    environment = {**os.environ, "PYTHONPATH": str(work)}
    helps = []
    for command in ([cli], [python, "-m", "pdf2mp3"]):
        for flags in ([], ["--help"], ["--version"], ["convert", "--help"], ["check", "--help"]):
            result = subprocess.run(
                [*map(str, command), *flags],
                cwd=work,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
                timeout=20,
            )
            if result.stderr or not result.stdout.startswith(("usage: pdf2mp3", "pdf2mp3 2.")):
                raise RuntimeError("installed help/version presentation failed")
            helps.append(result.stdout)
    if helps[:5] != helps[5:] or helps[0] != helps[1]:
        raise RuntimeError("console and module help/version differ")
    for flag in ("--lang", "--voice", "--max-chars", "--engine", "--overwrite", "--json"):
        if flag not in helps[3]:
            raise RuntimeError(f"convert help missing {flag}")
    before = set(work.rglob("*"))
    check = subprocess.run(
        [str(cli), "--json", "check", str(pdf)],
        cwd=work,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    report = json.loads(check.stdout)
    if not report["ok"] or report["data"]["speech_verified"] or not report["data"]["chunks"]:
        raise RuntimeError("installed check contract failed")
    if set(work.rglob("*")) != before or pdf.read_bytes() != original:
        raise RuntimeError("installed check modified files")
    run(
        [
            python,
            "-c",
            "import pdf2mp3, pathlib, sys; assert pathlib.Path(pdf2mp3.__file__).is_relative_to(sys.prefix)",
        ],
        work,
        environment,
    )
    default = pdf.with_suffix(".mp3")
    custom = work / "audio" / "sample.mp3"
    examples = [
        ([cli], [], default),
        ([python, "-m", "pdf2mp3"], ["--lang", "en"], default),
        ([cli], ["--output", custom], custom),
        ([cli], ["--rate=+5%", "--volume=+0%", "--max-chars", "1200"], default),
        ([cli], ["--voice", "en-US-AriaNeural", "--max-chars", "25", "--rate=-5%"], default),
    ]
    for command, flags, output in examples:
        run([*command, "convert", pdf, *flags, "--overwrite"], work, environment)
        run(
            [
                python,
                "-c",
                "from pydub import AudioSegment; import sys; assert len(AudioSegment.from_mp3(sys.argv[1])) >= 220",
                output,
            ],
            work,
        )
        if pdf.read_bytes() != original:
            raise RuntimeError("installed conversion modified the PDF")
    for path, expected in ((work / "missing.pdf", 1), (pdf, 2)):
        result = subprocess.run(
            [str(cli), "convert", str(path), "-o", str(path), "--json"],
            cwd=work,
            env=environment,
            timeout=20,
            capture_output=True,
        )
        report = json.loads(result.stdout)
        if report["ok"] or report["error"]["exit_code"] != expected:
            raise RuntimeError("installed JSON failure contract failed")
        if result.returncode != expected:
            raise RuntimeError(
                f"installed failure contract: expected {expected}, got {result.returncode}"
            )

    for stage in ("speech", "export"):
        output = work / "interrupted.mp3"
        output.write_bytes(b"previous synthetic audio")
        before = set(work.rglob("*"))
        result = subprocess.run(
            [str(cli), "convert", str(pdf), "-o", str(output), "--overwrite", "--json"],
            cwd=work,
            env={**environment, "PDF2MP3_SMOKE_INTERRUPT": stage},
            capture_output=True,
            timeout=20,
        )
        report = json.loads(result.stdout)
        if report["ok"] or report["error"]["code"] != "interrupted":
            raise RuntimeError("installed cancellation JSON failed")
        if result.returncode != 130 or output.read_bytes() != b"previous synthetic audio":
            raise RuntimeError(f"installed {stage} cancellation failed: {result.returncode}")
        if pdf.read_bytes() != original or set(work.rglob("*")) != before:
            raise RuntimeError("installed cancellation changed input or left temporary output")


def check_public_contents(names):
    # Setuptools metadata is generated for the sdist even though ignored in Git.
    metadata = {"pdf2mp3.egg-info"} | {
        f"pdf2mp3.egg-info/{name}"
        for name in (
            "PKG-INFO",
            "SOURCES.txt",
            "dependency_links.txt",
            "entry_points.txt",
            "requires.txt",
            "top_level.txt",
        )
    }
    source_names = [name for name in names if name not in metadata]
    if any(
        Path(name).name == ".DS_Store" or "docs/development/" in name or "local" in Path(name).parts
        for name in names
    ) or ignored_paths(ROOT, source_names):
        raise RuntimeError("package contains checkout-local files, instructions or notes")


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    distribution = output / "dist"
    run([sys.executable, "-m", "build", "--outdir", distribution], ROOT)
    files = sorted(distribution.iterdir())
    run([sys.executable, "-m", "twine", "check", "--strict", *files], ROOT)
    (wheel,) = distribution.glob("*.whl")
    (sdist,) = distribution.glob("*.tar.gz")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        check_public_contents(names)
        if not {"pdf2mp3/text.py", "pdf2mp3/cli.py", "pdf2mp3/openai_tts.py"} <= set(names) or any(
            not (name.startswith("pdf2mp3/") or ".dist-info/" in name) for name in names
        ):
            raise RuntimeError("unexpected wheel contents")
    with tarfile.open(sdist) as archive:
        names = {name.split("/", 1)[-1] for name in archive.getnames()}
        check_public_contents(names)
        required = {
            "pdf2mp3/cli.py",
            "pdf2mp3/openai_tts.py",
            "scripts/openai_check.py",
            "docs/cli.md",
            "docs/api.md",
            "scripts/documentation_check.py",
            "pdf2mp3/text.py",
            "tests/conftest.py",
            "pytest.ini",
            "scripts/quality_checks.py",
            "docs/contracts.md",
            "CHANGELOG.md",
        }
        if not required <= names:
            raise RuntimeError(f"incomplete sdist: {required - names}")
    rebuilt = output / "rebuilt"
    with tempfile.TemporaryDirectory(prefix="pdf2mp3-package-") as temporary:
        outside = Path(temporary)
        run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", rebuilt, sdist],
            outside,
        )
        (rebuilt_wheel,) = rebuilt.glob("*.whl")
        for label, artifact in (("wheel", wheel), ("sdist", rebuilt_wheel)):
            environment = output / ("runtime" if label == "wheel" else "sdist-runtime")
            venv.EnvBuilder(with_pip=True).create(environment)
            python = python_in(environment)
            run([python, "-m", "pip", "install", "--upgrade", "pip>=26.2"], outside)
            run([python, "-m", "pip", "install", artifact], outside)
            smoke(python, outside / label)
    (output / "artifacts.json").write_text(
        json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, indent=2)
        + "\n"
    )


if __name__ == "__main__":
    main()
