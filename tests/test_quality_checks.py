"""The gate must reject missing evidence, threshold misses and invalid tool results."""

import pytest

from scripts.quality_checks import (
    changed_lines,
    check_audit,
    check_coverage,
    check_licenses,
    check_mutation,
)


def file_report(executed=(1, 2), missing=(), branches=((1, 2),), missed=()):
    return {
        "executed_lines": list(executed),
        "missing_lines": list(missing),
        "executed_branches": list(branches),
        "missing_branches": list(missed),
    }


def test_coverage_separate_floors_and_new_file():
    data = {"files": {"pdf2mp3/text.py": file_report()}}
    result = check_coverage(data, {"pdf2mp3/text.py": {1, 2}})
    assert result["global"]["lines"] == 100
    assert result["changed"]["branches"] == 100
    data["files"]["pdf2mp3/text.py"] = file_report(branches=(), missed=((1, 2),))
    with pytest.raises(ValueError, match="branches"):
        check_coverage(data, {"pdf2mp3/text.py": {1}})


@pytest.mark.parametrize(
    "data", [{}, {"files": {}}, {"files": {"pdf2mp3/text.py": file_report((), (), (), ())}}]
)
def test_empty_coverage_is_not_a_pass(data):
    with pytest.raises(ValueError):
        check_coverage(data, {})


def test_changed_unmeasured_production_file_fails():
    with pytest.raises(ValueError, match="unmeasured"):
        check_coverage({"files": {"pdf2mp3/text.py": file_report()}}, {"pdf2mp3/new.py": {1}})


def test_changed_lines_fail_even_when_global_passes():
    data = {"files": {"pdf2mp3/text.py": file_report(range(1, 100), (100,))}}
    with pytest.raises(ValueError, match="changed lines"):
        check_coverage(data, {"pdf2mp3/text.py": {100}})


def test_diff_parser_handles_add_delete_and_context():
    diff = "diff --git a/pdf2mp3/a.py b/pdf2mp3/a.py\n--- a/pdf2mp3/a.py\n+++ b/pdf2mp3/a.py\n@@ -2,0 +3,2 @@\n+x\n+y\n@@ -8 +9,0 @@\n-z\n"
    assert changed_lines(diff) == {"pdf2mp3/a.py": {3, 4}}


def test_mutation_counts_only_assertion_failures_as_kills():
    records = {f"pdf2mp3.text.x_clean_text__mutmut_{i}": 1 for i in range(10)}
    records["pdf2mp3.pdf2mp3.x_tts_chunk_with_retry__mutmut_1"] = 0
    assert check_mutation(records)["scope"] > 90
    for status in [3, None, 36, 5, -9]:
        records["pdf2mp3.text.x_clean_text__mutmut_0"] = status
        with pytest.raises(ValueError, match="unresolved"):
            check_mutation(records)
    with pytest.raises(ValueError):
        check_mutation({})


def test_audit_rejects_vulnerabilities_and_skips():
    assert check_audit({"dependencies": [{"name": "safe", "version": "1", "vulns": []}]}) == 1
    for data in [
        {},
        {"dependencies": []},
        {"dependencies": [{"name": "x", "skip_reason": "local"}]},
        {"dependencies": [{"name": "x", "version": "1", "vulns": [{"id": "CVE-test"}]}]},
    ]:
        with pytest.raises(ValueError):
            check_audit(data)


def test_license_requires_every_runtime_distribution_to_be_reviewed():
    approved = ["MIT", "Apache-2.0"]
    assert check_licenses([{"Name": "sample", "Version": "1", "License": "MIT"}], approved) == 1
    for data in [
        [],
        [{"Name": "sample", "License": "UNKNOWN"}],
        [{"Name": "sample", "License": "GPL-3.0"}],
    ]:
        with pytest.raises(ValueError):
            check_licenses(data, approved)


def test_gate_records_failed_command_and_timeout(tmp_path, monkeypatch):
    import sys

    from scripts import quality

    monkeypatch.setattr(quality, "ROOT", tmp_path)
    gate = quality.Gate("fast", "v1.0.0")
    with pytest.raises(RuntimeError, match="failed"):
        gate.run("failed", [sys.executable, "-c", "raise SystemExit(7)"], cwd=tmp_path)
    assert gate.report["stages"][-1]["exit_code"] == 7
    with pytest.raises(RuntimeError, match="timed out"):
        gate.run(
            "timeout",
            [sys.executable, "-c", "import time; time.sleep(2)"],
            cwd=tmp_path,
            timeout=0.01,
        )
    assert gate.report["status"] == "FAIL"
    assert gate.report["stages"][-1]["reason"] == "timeout"


@pytest.mark.parametrize(
    "version,tag,dated,valid",
    [
        ("2.0.0.dev0", None, False, True),
        ("2.0.0.dev0", "v2.0.0.dev0", False, False),
        ("2.0.0", "v2.0.0", True, True),
        ("2.0.0", "v2.0.1", True, False),
        ("2.0.0", "v2.0.0", False, False),
        ("2.0.0rc1", "v2.0.0rc1", True, False),
    ],
)
def test_stable_release_requires_final_matching_version_and_dated_changelog(
    tmp_path, version, tag, dated, valid
):
    from scripts.release_check import validate

    (tmp_path / "pdf2mp3").mkdir()
    (tmp_path / "pyproject.toml").write_text(f'version = "{version}"\n')
    (tmp_path / "pdf2mp3/pdf2mp3.py").write_text(f'__version__ = "{version}"\n')
    (tmp_path / "CHANGELOG.md").write_text(
        f"## [{version}] - {'2026-10-06' if dated else 'Unreleased'}\n"
    )
    if valid:
        assert validate(tmp_path, tag) == version
    else:
        with pytest.raises(ValueError):
            validate(tmp_path, tag)


@pytest.mark.parametrize("status", [-24, 24, 36, 152, 255, 0, 1])
def test_triaged_timeout_stays_in_denominator_and_never_counts_as_killed(status):
    records = {f"pdf2mp3.text.x_text__mutmut_{i}": 1 for i in range(10)}
    records["pdf2mp3.pdf2mp3.x_tts_chunk_with_retry__mutmut_1"] = 1
    known = "pdf2mp3.text.x_text__mutmut_0"
    records[known] = status
    assert check_mutation(records, triaged_timeouts={known})["text"] == 90
    records[known] = 3
    with pytest.raises(ValueError):
        check_mutation(records, triaged_timeouts={known})


def test_copyleft_license_acceptance_is_package_scoped():
    package = {"edge-tts": ["LGPL-3.0-only"]}
    assert check_licenses([{"Name": "edge-tts", "License": "LGPL-3.0-only"}], ["MIT"], package) == 1
    with pytest.raises(ValueError):
        check_licenses([{"Name": "other", "License": "LGPL-3.0-only"}], ["MIT"], package)


def test_command_stdout_is_separate_from_warnings(tmp_path, monkeypatch):
    import sys

    from scripts import quality

    monkeypatch.setattr(quality, "ROOT", tmp_path)
    gate = quality.Gate("fast", "v1.0.0")
    stdout = gate.run(
        "data",
        [
            sys.executable,
            "-c",
            "import sys; print('package==1'); print('warning', file=sys.stderr)",
        ],
        cwd=tmp_path,
    )
    assert stdout == "package==1\n"
    assert "warning" in (gate.output / "data.stderr.log").read_text()


def test_independent_checks_continue_without_erasing_failure(tmp_path, monkeypatch):
    from scripts import quality

    monkeypatch.setattr(quality, "ROOT", tmp_path)
    gate = quality.Gate("release", "v1.0.0")

    def failed():
        raise ValueError("synthetic advisory")

    assert gate.attempt("audit", failed) is None
    assert gate.attempt("other", lambda: 42) == 42
    assert gate.report["status"] == "FAIL"
    assert gate.report["failures"] == [{"name": "audit", "reason": "synthetic advisory"}]


def test_audit_includes_installer_and_development_tools(tmp_path, monkeypatch):
    import json
    import sys

    from scripts import quality

    monkeypatch.setattr(quality, "ROOT", tmp_path)
    gate = quality.Gate("standard", "v1.0.0")

    def run(name, command, **kwargs):
        if name == "dev-freeze":
            assert command == [sys.executable, "-m", "pip", "list", "--format=freeze"]
            return "pip==26.2.1\npytest==9.1.1\npdf2mp3==2.0.1\npdf2mp3-helper==1.0\n"
        requirements = gate.output / "dev-requirements.txt"
        assert requirements.read_text() == "pip==26.2.1\npytest==9.1.1\npdf2mp3-helper==1.0\n"
        (gate.output / "audit-dev.json").write_text(
            json.dumps({"dependencies": [{"name": "pytest", "version": "9.1.1", "vulns": []}]})
        )

    monkeypatch.setattr(gate, "run", run)
    gate.audit(sys.executable, "dev")
    assert gate.report["stages"][-1]["name"] == "audit-dev-findings"


def test_standard_audits_development_even_when_packaging_fails(tmp_path, monkeypatch):
    import sys

    from scripts import quality

    monkeypatch.setattr(quality, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["quality.py", "standard"])
    calls = []
    monkeypatch.setattr(
        quality.Gate, "preflight", lambda self: self.report.update(source_sha256="x")
    )
    monkeypatch.setattr(quality.Gate, "fast", lambda self: None)
    monkeypatch.setattr(quality.Gate, "coverage", lambda self: None)
    monkeypatch.setattr(quality.Gate, "audit", lambda self, python, label: calls.append(label))

    def packaging(self):
        raise RuntimeError("synthetic build failure")

    monkeypatch.setattr(quality.Gate, "packaging", packaging)
    monkeypatch.setattr(quality.Gate, "run", lambda *args, **kwargs: "")
    monkeypatch.setattr(quality, "fingerprint", lambda files: "x")
    assert quality.main() == 1
    assert calls == ["dev"]


def test_performance_measurement_rejects_empty_results_and_over_budget():
    from scripts.performance_check import measure

    with pytest.raises(RuntimeError):
        measure(lambda: [], 10, 10)
    with pytest.raises(RuntimeError):
        measure(lambda: [1], -1, 10)
    with pytest.raises(RuntimeError):
        measure(lambda: [1], 10, -1)
    assert measure(lambda: [1], 10, 10)["result_size"] == 1


def test_performance_workload_calls_production_assembly(monkeypatch):
    from pydub import AudioSegment

    import pdf2mp3.pdf2mp3 as app
    from scripts import performance_check

    calls = []

    async def assembly(chunks, voice):
        calls.append((chunks, voice))
        return AudioSegment.silent(duration=200)

    monkeypatch.setattr(app, "synthesize_chunks", assembly)
    assert len(performance_check.assembly_workload()) == 200
    assert len(calls[0][0]) == 200
    assert calls[0][1] == "synthetic"
