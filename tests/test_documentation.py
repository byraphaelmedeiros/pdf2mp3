"""The documentation gate rejects broken references and undocumented interfaces."""

import re
import subprocess
from pathlib import Path

import pytest

from scripts import documentation_check as checker


def ignore_notes(root):
    subprocess.run(["git", "init", "--quiet"], cwd=root, check=True, timeout=10)
    (root / ".git/info/exclude").write_text("local-notes.md\n")


@pytest.fixture
def documented_project(tmp_path):
    ignore_notes(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "pdf2mp3").mkdir()
    (tmp_path / "README.md").write_text("# Synthetic project\n[API](docs/api.md#helper)\n")
    (tmp_path / "docs/api.md").write_text(
        "# Python API\n\n## `helper`\n\nReturns synthetic text.\n"
    )
    (tmp_path / "pdf2mp3/__init__.py").write_text('"""Synthetic API."""\n__all__ = ["helper"]\n')
    (tmp_path / "pdf2mp3/helpers.py").write_text(
        '"""Synthetic helpers."""\ndef helper():\n    """Return synthetic text."""\n'
        '    return "synthetic"\n'
    )
    return tmp_path


@pytest.mark.parametrize("default_encoding", ["utf-8", "cp1252"])
def test_valid_documentation_with_unicode_and_duplicate_headings(
    documented_project, monkeypatch, default_encoding
):
    original_open = Path.open

    def locale_open(path, mode="r", *args, **kwargs):
        if "b" not in mode and kwargs.get("encoding") is None:
            kwargs["encoding"] = default_encoding
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", locale_open)
    guide = documented_project / "docs/guide with spaces.md"
    guide.write_text("# Narração: `example`!\n# Narração: `example`!\n", encoding="utf-8")
    with (documented_project / "README.md").open("a", encoding="utf-8") as stream:
        stream.write("[Guide](<docs/guide with spaces.md#narração-example-1>)\n")
        stream.write("[External](https://example.invalid/unavailable)\n")
    result = checker.check_documentation(documented_project)
    assert result == {"documents": 3, "modules": 2, "api_exports": 1}


@pytest.mark.parametrize("target", ["missing.md", "docs/api.md#missing"])
def test_broken_local_reference_fails(documented_project, target):
    (documented_project / "README.md").write_text(f"[Broken]({target})\n")
    with pytest.raises(ValueError, match="reference"):
        checker.check_documentation(documented_project)


@pytest.mark.parametrize(
    "target,valid",
    [
        ("docs/api.md#helper", True),
        ("docs/api.md#missing", False),
        ("missing.md", False),
        ("local-notes.md", False),
        ("local/inputs/private.txt", False),
        ("../outside.md", False),
    ],
)
def test_release_repository_links_are_validated_locally(documented_project, target, valid):
    url = f"https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.0/{target}"
    (documented_project / "README.md").write_text(f"[Release reference]({url})\n")
    if valid:
        assert checker.check_documentation(documented_project)["documents"] == 2
    else:
        with pytest.raises(ValueError, match="reference"):
            checker.check_documentation(documented_project)


def test_distributed_readme_links_work_outside_github():
    root = Path(__file__).resolve().parents[1]
    targets = re.findall(
        r"\]\(([^\s)]+)\)", checker._prose((root / "README.md").read_text(encoding="utf-8"))
    )
    assert targets
    assert all(target.startswith(("https://", "#")) for target in targets)


def test_code_block_heading_is_not_a_link_anchor(documented_project):
    (documented_project / "README.md").write_text("[Fake](#fake)\n```markdown\n# Fake\n```\n")
    with pytest.raises(ValueError, match="reference"):
        checker.check_documentation(documented_project)


@pytest.mark.parametrize("target", ["local-notes.md", "local/inputs/private.txt", "../outside.md"])
def test_public_reference_cannot_point_to_private_or_external_checkout_files(
    documented_project, target
):
    if target == "local-notes.md":
        (documented_project / target).write_text("Synthetic private note\n")
    (documented_project / "README.md").write_text(f"[Private]({target})\n")
    with pytest.raises(ValueError, match="reference"):
        checker.check_documentation(documented_project)


def test_internal_notes_are_outside_public_documentation(documented_project):
    (documented_project / "local-notes.md").write_text("[Private](missing.md)\n")
    notes = documented_project / "docs/development"
    notes.mkdir()
    (notes / "notes.md").write_text("[Private](missing.md)\n")
    assert checker.check_documentation(documented_project)["documents"] == 2


def test_checkout_parent_named_development_does_not_hide_public_docs(documented_project):
    relocated = documented_project / "development/project"
    relocated.mkdir(parents=True)
    for name in ("README.md", "docs", "pdf2mp3"):
        (documented_project / name).rename(relocated / name)
    with (relocated / "docs/api.md").open("a") as stream:
        stream.write("[Broken](missing.md)\n")
    with pytest.raises(ValueError, match="reference"):
        checker.check_documentation(relocated)


@pytest.mark.parametrize(
    "source",
    [
        'def helper():\n    """Documented function."""\n',
        '"""Module."""\ndef helper():\n    pass\n',
        '"""Module."""\nclass Interface:\n    pass\n',
        '"""Module."""\nclass Interface:\n    """Class."""\n    def call(self):\n        pass\n',
    ],
)
def test_missing_module_or_interface_docstring_fails(documented_project, source):
    (documented_project / "pdf2mp3/helpers.py").write_text(source)
    with pytest.raises(ValueError, match="docstring"):
        checker.check_documentation(documented_project)


@pytest.mark.parametrize("headings", ["", "## `another`\n", "## `helper`\n## `helper`\n"])
def test_api_inventory_must_match_exports(documented_project, headings):
    (documented_project / "README.md").write_text("[API](docs/api.md)\n")
    (documented_project / "docs/api.md").write_text(f"# API\n{headings}")
    with pytest.raises(ValueError, match="API inventory"):
        checker.check_documentation(documented_project)


@pytest.mark.parametrize(
    "path",
    [
        "local/inputs/sample.txt",
        "local/outputs/audio.wav",
        "local-notes.md",
        "docs/development/note.md",
        ".DS_Store",
    ],
)
def test_tracked_private_file_fails_without_reading_it(path, tmp_path):
    ignore_notes(tmp_path)
    with pytest.raises(ValueError, match="checkout-local"):
        checker.check_local_files([path], root=tmp_path)
    checker.check_local_files(["docs/local-demo.md", "tests/test_demo.py"])


@pytest.mark.parametrize(
    "path", ["local/inputs/sample.txt", "pdf2mp3-2.0.0/local/audio.aiff", ".DS_Store"]
)
def test_package_contents_reject_manual_test_files(path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from package_check import check_public_contents

    with pytest.raises(RuntimeError, match="checkout-local"):
        check_public_contents(["pdf2mp3/__init__.py", path])


def test_quality_preflight_rejects_private_index_before_fingerprinting(tmp_path, monkeypatch):
    from scripts import quality

    monkeypatch.setattr(quality, "ROOT", tmp_path)
    gate = quality.Gate("fast", "v1.0.0")
    responses = {
        "git-head": "synthetic-head",
        "git-base": "synthetic-base",
        "tracked-files": "local/inputs/private.txt\0",
        "source-files": "local/inputs/private.txt\0",
    }
    monkeypatch.setattr(gate, "run", lambda name, command: responses.get(name, ""))
    monkeypatch.setattr(quality, "fingerprint", lambda files: pytest.fail("read private input"))
    with pytest.raises(ValueError, match="checkout-local"):
        gate.preflight()


def test_force_added_local_exclusion_is_rejected_without_reading(tmp_path, monkeypatch):
    ignore_notes(tmp_path)
    notes = tmp_path / "local-notes.md"
    notes.write_text("Synthetic private note")
    subprocess.run(["git", "add", "--force", notes.name], cwd=tmp_path, check=True, timeout=10)
    original = Path.read_text

    def guarded_read(path, *args, **kwargs):
        if path == notes:
            pytest.fail("read local note")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read)
    with pytest.raises(ValueError, match="checkout-local"):
        checker.check_local_files([notes.name], root=tmp_path)


@pytest.mark.parametrize(
    "name",
    ["local-notes.md", "docs/review.egg-info/local-notes.md", "pdf2mp3.egg-info/local-notes.md"],
)
def test_package_rejects_checkout_specific_exclusions(tmp_path, monkeypatch, name):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import package_check

    ignore_notes(tmp_path)
    monkeypatch.setattr(package_check, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="checkout-local"):
        package_check.check_public_contents([name])
