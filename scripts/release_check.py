"""Validate version/changelog consistency; --tag additionally forbids prereleases."""

import argparse
import ast
import re
from pathlib import Path

from packaging.version import Version


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
    arguments = parser.parse_args()
    print(validate(Path(__file__).resolve().parents[1], arguments.tag))
