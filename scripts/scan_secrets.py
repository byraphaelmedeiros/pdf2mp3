"""Scan tracked and new source files, rejecting any unreviewed secret finding."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings

root = Path(__file__).resolve().parents[1]
paths = (
    subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root
    )
    .decode()
    .split("\0")
)
secrets = SecretsCollection()
with default_settings():
    for name in sorted(set(paths) - {"", ".DS_Store"}):
        path = root / name
        if path.is_file():
            secrets.scan_file(str(path))
report = secrets.json()
reviewed = []
# An exact, recomputed source checksum is public evidence, not a credential.
# Do not exempt other strings, lines, files or entropy findings.
triage_path = str(root / "scripts/mutation-triage.json")
source_hash = hashlib.sha256((root / "pdf2mp3/text.py").read_bytes()).hexdigest()
checksum_hash = hashlib.sha1(source_hash.encode(), usedforsecurity=False).hexdigest()
if triage_path in report:
    findings = report[triage_path]
    reviewed = [
        item
        for item in findings
        if item["type"] == "Hex High Entropy String" and item["hashed_secret"] == checksum_hash
    ]
    remaining = [item for item in findings if item not in reviewed]
    if remaining:
        report[triage_path] = remaining
    else:
        del report[triage_path]
Path(sys.argv[1]).write_text(
    json.dumps({"results": report, "reviewed_source_checksums": reviewed}, indent=2) + "\n"
)
if report:
    raise SystemExit("Unreviewed secret findings; inspect the local report (values are hashed).")
