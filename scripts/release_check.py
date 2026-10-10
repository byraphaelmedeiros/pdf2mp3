"""Validate version/changelog consistency; --tag additionally forbids prereleases."""

import argparse
import ast
import re
import subprocess
from pathlib import Path

from packaging.version import Version


def validate_source(root: Path, tag: str, main_ref: str) -> None:
    """Require the release checkout/tag to identify a commit integrated into main."""

    def resolve(ref: str) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode:
            raise ValueError("cannot resolve release source; fetch main and tags first")
        return result.stdout.strip()

    source = resolve(f"refs/tags/{tag}")
    if resolve("HEAD") != source:
        raise ValueError("release tag differs from the checked-out commit")
    main = resolve(main_ref)
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source, main],
        cwd=root,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if result.returncode:
        raise ValueError("release source is not proven integrated into main")


def validate(root, tag=None):
    # QA uses 3.12, but this check also runs in the Python 3.10 support matrix.
    metadata = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', metadata, re.MULTILINE)
    if not match:
        raise ValueError("missing package version")
    version = match[1]
    module = ast.parse((root / "pdf2mp3/pdf2mp3.py").read_text(encoding="utf-8"))
    runtime = [
        node.value.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
    ]
    if runtime != [version]:
        raise ValueError("runtime and package versions disagree")
    if f"## [{version}]" not in (root / "CHANGELOG.md").read_text(encoding="utf-8"):
        raise ValueError("changelog lacks the package version")
    if tag:
        parsed = Version(version)
        if tag != f"v{version}" or parsed.is_prerelease or parsed.is_devrelease or parsed.local:
            raise ValueError("stable tag must match a final package version")
        section = (
            (root / "CHANGELOG.md")
            .read_text(encoding="utf-8")
            .split(f"## [{version}]", 1)[1]
            .split("\n## ", 1)[0]
        )
        if "Unreleased" in section or not re.match(r" - \d{4}-\d{2}-\d{2}", section):
            raise ValueError("stable release needs a dated changelog")
    return version


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--main-ref", help="Require the tag commit to be integrated into this ref")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if arguments.main_ref and not arguments.tag:
        parser.error("--main-ref requires --tag")
    version = validate(root, arguments.tag)
    if arguments.main_ref:
        validate_source(root, arguments.tag, arguments.main_ref)
    print(version)
