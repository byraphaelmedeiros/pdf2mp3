"""The documentation gate rejects broken references and undocumented interfaces."""

from pathlib import Path

import pytest

from scripts import documentation_check as checker


@pytest.fixture
def documented_project(tmp_path):
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


def test_code_block_heading_is_not_a_link_anchor(documented_project):
    (documented_project / "README.md").write_text("[Fake](#fake)\n```markdown\n# Fake\n```\n")
    with pytest.raises(ValueError, match="reference"):
        checker.check_documentation(documented_project)


@pytest.mark.parametrize("target", ["AGENTS.md", "local/inputs/private.txt", "../outside.md"])
def test_public_reference_cannot_point_to_private_or_external_checkout_files(
    documented_project, target
):
    (documented_project / "README.md").write_text(f"[Private]({target})\n")
    with pytest.raises(ValueError, match="reference"):
        checker.check_documentation(documented_project)


def test_internal_notes_are_outside_public_documentation(documented_project):
    (documented_project / "AGENTS.md").write_text("[Private](missing.md)\n")
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
        "AGENTS.md",
        "docs/development/note.md",
        ".DS_Store",
    ],
)
def test_tracked_private_file_fails_without_reading_it(path):
    with pytest.raises(ValueError, match="checkout-local"):
        checker.check_local_files([path])
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
