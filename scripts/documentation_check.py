"""Check public Markdown, Python API documentation and checkout-local Git hygiene."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote, urlsplit


def ignored_paths(root: Path, names: Iterable[str]) -> set[str]:
    """Resolve checkout exclusions without reading the excluded files."""
    names = [name for name in names if name]
    if not names or not (root / ".git").exists():
        return set()
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin", "-z"],
        input="\0".join(names) + "\0",
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise ValueError("cannot verify checkout-local exclusions")
    return set(result.stdout.split("\0")) - {""}


def check_local_files(files: Iterable[str], root: Path | None = None) -> None:
    """Reject protected paths from the Git index without opening their contents."""
    files = list(files)
    excluded = ignored_paths(root, files) if root is not None else set()
    for name in files:
        path = Path(name)
        if (
            path.parts[:1] == ("local",)
            or path.parts[:2] == ("docs", "development")
            or path.name == ".DS_Store"
            or name in excluded
        ):
            raise ValueError(f"checkout-local file is tracked: {name}")


def _prose(text: str) -> str:
    """Keep Markdown outside fenced examples for link and heading checks."""
    lines = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
        elif fence is None:
            lines.append(line)
    return "\n".join(lines)


def _anchors(text: str) -> set[str]:
    anchors = set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", _prose(text), re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        candidate = slug
        number = 0
        while candidate in anchors:
            number += 1
            candidate = f"{slug}-{number}"
        anchors.add(candidate)
    return anchors


def check_documentation(root: Path) -> dict[str, int]:
    """Validate public references and declared interfaces without services/imports."""
    root = root.resolve()
    documents = sorted(
        set(root.glob("*.md"))
        | {
            path
            for path in (root / "docs").rglob("*.md")
            if path.relative_to(root / "docs").parts[:1] != ("development",)
        }
    )
    excluded = ignored_paths(root, (path.relative_to(root).as_posix() for path in documents))
    documents = [path for path in documents if path.relative_to(root).as_posix() not in excluded]
    if not documents:
        raise ValueError("missing public documentation")
    for document in documents:
        for target in re.findall(
            r"!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)\n]+)\)", _prose(document.read_text(encoding="utf-8"))
        ):
            target = target.strip("<>")
            parsed = urlsplit(target)
            repository = "https://github.com/byraphaelmedeiros/pdf2mp3/blob/"
            if target.startswith(repository):
                # PyPI needs absolute URLs; validate our release links against this source.
                _, separator, filename = parsed.path.removeprefix(
                    "/byraphaelmedeiros/pdf2mp3/blob/"
                ).partition("/")
                if not separator:
                    raise ValueError(f"broken reference in {document.relative_to(root)}: {target}")
                anchor = parsed.fragment
                destination = (root / unquote(filename)).resolve()
            elif parsed.scheme or target.startswith("//"):
                continue
            else:
                filename, _, anchor = target.partition("#")
                destination = (
                    (document.parent / unquote(filename)).resolve() if filename else document
                )
            try:
                relative = destination.relative_to(root)
                check_local_files([relative.as_posix()], root=root)
            except ValueError:
                raise ValueError(
                    f"private/outside reference in {document.relative_to(root)}"
                ) from None
            if not destination.exists() or (
                anchor
                and destination.suffix == ".md"
                and unquote(anchor) not in _anchors(destination.read_text(encoding="utf-8"))
            ):
                raise ValueError(f"broken reference in {document.relative_to(root)}: {target}")

    modules = sorted((root / "pdf2mp3").glob("*.py"))
    exports = []
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        interfaces = [tree]
        for node in tree.body:
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ) and not node.name.startswith("_"):
                interfaces.append(node)
                if isinstance(node, ast.ClassDef):
                    interfaces.extend(
                        method
                        for method in node.body
                        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and not method.name.startswith("_")
                    )
            if (
                module.name == "__init__.py"
                and isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in node.targets
                )
            ):
                exports = ast.literal_eval(node.value)
        for interface in interfaces:
            if not ast.get_docstring(interface):
                raise ValueError(
                    f"missing docstring in {module.relative_to(root)}:{getattr(interface, 'lineno', 1)}"
                )
    reference = root / "docs/api.md"
    headings = (
        re.findall(r"^## `([a-zA-Z_]\w*)`\s*$", reference.read_text(encoding="utf-8"), re.MULTILINE)
        if reference.is_file()
        else []
    )
    if not exports or sorted(headings) != sorted(exports):
        raise ValueError("documented API inventory does not match __all__")
    return {"documents": len(documents), "modules": len(modules), "api_exports": len(exports)}


def main() -> None:
    """Check this checkout's index and documentation; failures exit nonzero."""
    root = Path(__file__).resolve().parents[1]
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=True, timeout=10
    ).stdout.split("\0")
    check_local_files(tracked, root=root)
    print(json.dumps(check_documentation(root)))


if __name__ == "__main__":
    main()
