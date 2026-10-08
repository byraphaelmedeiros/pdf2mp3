#!/usr/bin/env python3
"""One entry point for reproducible local and CI quality evidence (Python 3.12)."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.documentation_check import check_local_files  # noqa: E402
from scripts.quality_checks import (  # noqa: E402
    changed_lines,
    check_audit,
    check_coverage,
    check_licenses,
    check_mutation,
)

PYTHON = sys.executable


def fingerprint(files):
    digest = hashlib.sha256()
    for path in sorted(set(files.split("\0")) - {"", ".DS_Store"}):
        candidate = ROOT / path
        if candidate.is_file():
            digest.update(path.encode() + b"\0" + candidate.read_bytes() + b"\0")
    return digest.hexdigest()


class Gate:
    def __init__(self, profile, base):
        self.profile = profile
        self.base = base
        self.output = (
            ROOT / ".quality" / "runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        )
        self.output.mkdir(parents=True)
        self.report = {
            "profile": profile,
            "base": base,
            "status": "FAIL",
            "stages": [],
            "failures": [],
            "python": sys.version,
            "platform": platform.platform(),
        }
        self.save()

    def save(self):
        (self.output / "summary.json").write_text(json.dumps(self.report, indent=2) + "\n")

    def run(self, name, command, *, timeout=180, cwd=ROOT, env=None):
        log = self.output / f"{name}.log"
        error_log = self.output / f"{name}.stderr.log"
        stage = {
            "name": name,
            "command": list(map(str, command)),
            "cwd": str(cwd),
            "status": "FAIL",
            "log": log.name,
            "stderr_log": error_log.name,
        }
        self.report["stages"].append(stage)
        start = time.monotonic()
        print(f"[{name}]", flush=True)
        try:
            with (
                log.open("w", encoding="utf-8") as stream,
                error_log.open("w", encoding="utf-8") as errors,
            ):
                result = subprocess.run(
                    command,
                    cwd=cwd,
                    env=env,
                    stdout=stream,
                    stderr=errors,
                    timeout=timeout,
                    check=False,
                )
            stage["exit_code"] = result.returncode
            if result.returncode:
                raise RuntimeError(f"{name} failed ({result.returncode}); see {log}")
            stage["status"] = "PASS"
        except subprocess.TimeoutExpired as error:
            stage["reason"] = "timeout"
            raise RuntimeError(f"{name} timed out; see {log}") from error
        finally:
            stage["seconds"] = round(time.monotonic() - start, 3)
            self.save()
        return log.read_text(encoding="utf-8")

    def evaluate(self, name, function):
        stage = {"name": name, "status": "FAIL"}
        self.report["stages"].append(stage)
        try:
            stage["result"] = function()
            stage["status"] = "PASS"
        finally:
            self.save()

    def attempt(self, name, function):
        try:
            return function()
        except Exception as error:
            self.report["failures"].append({"name": name, "reason": str(error)})
            self.save()
            print(f"FAIL [{name}]: {error}", file=sys.stderr)
            return None

    def preflight(self):
        self.report["commit"] = self.run("git-head", ["git", "rev-parse", "HEAD"]).strip()
        self.run("git-base", ["git", "rev-parse", "--verify", f"{self.base}^{{commit}}"])
        # Reject private index entries before fingerprinting or secret scanning reads files.
        tracked = self.run("tracked-files", ["git", "ls-files", "-z"]).split("\0")
        self.evaluate("local-files", lambda: check_local_files(tracked))
        files = self.run(
            "source-files", ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
        )
        self.report["source_sha256"] = fingerprint(files)
        self.report["tools"] = {
            item.metadata["Name"]: item.version for item in importlib.metadata.distributions()
        }
        self.report["ffmpeg"] = self.run("ffmpeg", ["ffmpeg", "-version"]).splitlines()[0]
        self.run("ffprobe", ["ffprobe", "-version"])
        self.run("whitespace", ["git", "diff", "--check"])

    def fast(self):
        self.run("lint", [PYTHON, "-m", "ruff", "check", "."])
        self.run("format", [PYTHON, "-m", "ruff", "format", "--check", "."])
        self.run("types", [PYTHON, "-m", "mypy"])
        self.run("documentation", [PYTHON, "scripts/documentation_check.py"])
        if self.profile == "fast":
            self.run("tests", [PYTHON, "-m", "pytest", "-q"], timeout=240)

    def coverage(self):
        environment = {**os.environ, "COVERAGE_FILE": str(self.output / ".coverage")}
        self.run(
            "tests",
            [PYTHON, "-m", "coverage", "run", "-m", "pytest", "-q"],
            timeout=240,
            env=environment,
        )
        self.run(
            "coverage-combine",
            [PYTHON, "-m", "coverage", "combine", str(self.output)],
            env=environment,
        )
        report_path = self.output / "coverage.json"
        self.run(
            "coverage-json",
            [PYTHON, "-m", "coverage", "json", "-o", str(report_path)],
            env=environment,
        )
        diff = self.run(
            "coverage-diff",
            ["git", "diff", "--no-ext-diff", "--unified=0", self.base, "--", "pdf2mp3"],
        )
        changed = changed_lines(diff)
        new = self.run(
            "coverage-new", ["git", "ls-files", "--others", "--exclude-standard", "pdf2mp3"]
        )
        for name in new.splitlines():
            if name.endswith(".py"):
                changed[name] = set(
                    range(1, len((ROOT / name).read_text(encoding="utf-8").splitlines()) + 1)
                )
        self.evaluate(
            "coverage-floors",
            lambda: check_coverage(json.loads(report_path.read_text(encoding="utf-8")), changed),
        )

    def packaging(self):
        self.run("packaging", [PYTHON, "scripts/package_check.py", str(self.output)], timeout=600)
        runtime = (
            self.output / "runtime" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        return runtime

    def security(self, runtime):
        self.run(
            "bandit",
            [
                PYTHON,
                "-m",
                "bandit",
                "-r",
                "pdf2mp3",
                "-f",
                "json",
                "-o",
                str(self.output / "bandit.json"),
            ],
        )
        self.run("secrets", [PYTHON, "scripts/scan_secrets.py", str(self.output / "secrets.json")])
        self.attempt("audit-base", lambda: self.audit(runtime, "base"))
        (wheel,) = (self.output / "dist").glob("*.whl")
        self.run(
            "optional-extras",
            [str(runtime), "-m", "pip", "install", f"{wheel}[gtts,openai,pyttsx3]"],
            timeout=300,
        )
        self.run("extras-consistency", [str(runtime), "-m", "pip", "check"])
        self.run("openai-contract", [str(runtime), "scripts/openai_check.py"], timeout=60)
        self.attempt("audit-extras", lambda: self.audit(runtime, "extras"))
        licenses = self.output / "licenses.json"
        self.run(
            "licenses",
            [
                PYTHON,
                "-m",
                "piplicenses",
                "--python",
                str(runtime),
                "--format=json",
                "--output-file",
                str(licenses),
            ],
        )
        approved = json.loads((ROOT / "scripts/approved-licenses.json").read_text(encoding="utf-8"))
        self.evaluate(
            "license-policy",
            lambda: check_licenses(
                json.loads(licenses.read_text(encoding="utf-8")),
                approved["licenses"],
                approved["packages"],
            ),
        )

    def audit(self, runtime, label):
        # Audit resolved dependencies; the project's source has separate security checks.
        frozen = self.run(f"{label}-freeze", [str(runtime), "-m", "pip", "freeze"])
        requirements = self.output / f"{label}-requirements.txt"
        requirements.write_text(
            "\n".join(
                line for line in frozen.splitlines() if not line.lower().startswith("pdf2mp3")
            )
            + "\n"
        )
        audit = self.output / f"audit-{label}.json"
        self.run(
            f"audit-{label}",
            [
                PYTHON,
                "-m",
                "pip_audit",
                "-r",
                str(requirements),
                "--no-deps",
                "--disable-pip",
                "--progress-spinner",
                "off",
                "--cache-dir",
                str(ROOT / ".quality" / "audit-cache"),
                "-f",
                "json",
                "-o",
                str(audit),
            ],
            timeout=240,
        )
        self.evaluate(
            f"audit-{label}-findings",
            lambda: check_audit(json.loads(audit.read_text(encoding="utf-8"))),
        )

    def mutation(self):
        # Discard only this tool's generated cache, never source or user data.
        if (ROOT / "mutants").exists():
            shutil.rmtree(ROOT / "mutants")
        self.run(
            "mutation",
            [
                PYTHON,
                "-m",
                "mutmut",
                "run",
                "pdf2mp3.text.*",
                "pdf2mp3.pdf2mp3.x_tts_chunk_with_retry*",
                "--max-children",
                "4",
            ],
            timeout=1200,
        )
        records = {}
        for path in (ROOT / "mutants/pdf2mp3").glob("*.meta"):
            records.update(json.loads(path.read_text(encoding="utf-8"))["exit_code_by_key"])
        (self.output / "mutation.json").write_text(json.dumps(records, indent=2) + "\n")
        triage = json.loads((ROOT / "scripts/mutation-triage.json").read_text(encoding="utf-8"))
        for name, entry in triage.items():
            if (
                entry["source_sha256"]
                != hashlib.sha256((ROOT / "pdf2mp3/text.py").read_bytes()).hexdigest()
            ):
                raise ValueError(f"stale mutation triage: {name}")
            if entry["status"] != "timeout-as-survivor" or name not in records:
                raise ValueError(f"invalid mutation triage: {name}")
        self.report["mutation_triage"] = triage
        self.evaluate("mutation-floors", lambda: check_mutation(records, set(triage)))

    def release(self):
        self.attempt("mutation", self.mutation)
        self.attempt(
            "performance",
            lambda: self.run(
                "performance",
                [PYTHON, "scripts/performance_check.py", str(self.output / "performance.json")],
                timeout=90,
            ),
        )
        self.attempt(
            "release-metadata",
            lambda: self.run("release-metadata", [PYTHON, "scripts/release_check.py"]),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=["fast", "standard", "release"])
    parser.add_argument(
        "--base", default="v1.0.0", help="Git comparison base for changed-code coverage"
    )
    args = parser.parse_args()
    gate = Gate(args.profile, args.base)
    try:
        gate.preflight()
        gate.attempt("fast", gate.fast)
        if args.profile != "fast":
            gate.attempt("coverage", gate.coverage)
            runtime = gate.attempt("packaging", gate.packaging)
            if runtime:
                gate.attempt("security", lambda: gate.security(runtime))
        if args.profile == "release":
            gate.release()
        final_files = gate.run(
            "source-files-final",
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        )
        if fingerprint(final_files) != gate.report["source_sha256"]:
            raise RuntimeError("source changed during the gate; rerun on a stable checkout")
        if not gate.report["failures"]:
            gate.report["status"] = "PASS"
    except (Exception, KeyboardInterrupt) as error:
        gate.report["error"] = str(error)
        print(f"FAIL: {error}", file=sys.stderr)
    finally:
        gate.save()
        print(f"Evidence: {gate.output}")
    return 0 if gate.report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
