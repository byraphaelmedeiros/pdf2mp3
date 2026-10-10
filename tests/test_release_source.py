"""Release tags must identify the checked-out commit already integrated into main."""

import subprocess

import pytest


@pytest.fixture
def repository(tmp_path):
    def git(*args):
        return subprocess.check_output(
            [
                "git",
                "-c",
                "user.name=Release test",
                "-c",
                "user.email=release-test@example.invalid",
                *args,
            ],
            cwd=tmp_path,
            text=True,
            stderr=subprocess.STDOUT,
            timeout=10,
        ).strip()

    git("init", "--initial-branch=main")
    git("commit", "--allow-empty", "-m", "Initial commit")
    return tmp_path, git


def test_release_accepts_tag_integrated_before_main_tip(repository):
    from scripts.release_check import validate_source

    root, git = repository
    git("tag", "-a", "v2.0.0", "-m", "Release")
    git("commit", "--allow-empty", "-m", "Later change")
    git("checkout", "v2.0.0")
    validate_source(root, "v2.0.0", "main")


def test_release_rejects_unmerged_tag(repository):
    from scripts.release_check import validate_source

    root, git = repository
    git("checkout", "-b", "unmerged")
    git("commit", "--allow-empty", "-m", "Unmerged change")
    git("tag", "v2.0.0")
    with pytest.raises(ValueError, match="integrated"):
        validate_source(root, "v2.0.0", "main")


def test_release_rejects_checkout_different_from_tag(repository):
    from scripts.release_check import validate_source

    root, git = repository
    git("tag", "v2.0.0")
    git("commit", "--allow-empty", "-m", "Different source")
    with pytest.raises(ValueError, match="checked-out"):
        validate_source(root, "v2.0.0", "main")


@pytest.mark.parametrize("tag,main", [("v2.0.0", "missing-main"), ("missing-tag", "main")])
def test_release_rejects_missing_refs(repository, tag, main):
    from scripts.release_check import validate_source

    root, git = repository
    git("tag", "v2.0.0")
    with pytest.raises(ValueError, match="resolve"):
        validate_source(root, tag, main)
