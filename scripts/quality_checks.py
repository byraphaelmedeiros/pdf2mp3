"""Pure, fail-closed evaluators used by the local and CI quality runner."""

import re

# Canonical thresholds; documentation links here rather than redefining policy.
COVERAGE_FLOORS = {"global": (90, 80), "changed": (95, 85), "text": (95, 90)}
MUTATION_FLOORS = {"scope": 80, "text": 90}


def changed_lines(diff):
    result = {}
    path = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            result.setdefault(path, set())
        elif line.startswith("+++ /dev/null"):
            path = None
        elif path and (match := re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)):
            start, count = int(match[1]), int(match[2] or 1)
            result[path].update(range(start, start + count))
    return result


def check_coverage(data, changed):
    files = data.get("files", {})
    if not files or "pdf2mp3/text.py" not in files:
        raise ValueError("missing production coverage")
    unmeasured = set(changed) - set(files)
    if unmeasured:
        raise ValueError(f"unmeasured changed files: {sorted(unmeasured)}")
    counts = {scope: [0, 0, 0, 0] for scope in COVERAGE_FLOORS}
    for path, report in files.items():
        if not path.startswith("pdf2mp3/"):
            raise ValueError(f"unexpected coverage scope: {path}")
        executed, missing = set(report["executed_lines"]), set(report["missing_lines"])
        branches = {tuple(b) for b in report["executed_branches"]}
        missed = {tuple(b) for b in report["missing_branches"]}
        for scope in counts:
            if scope == "text" and path != "pdf2mp3/text.py":
                continue
            selected = changed.get(path, set()) if scope == "changed" else executed | missing
            good, bad = executed & selected, missing & selected
            good_b = {b for b in branches if b[0] in selected}
            bad_b = {b for b in missed if b[0] in selected}
            for i, value in enumerate(
                (len(good), len(good | bad), len(good_b), len(good_b | bad_b))
            ):
                counts[scope][i] += value
    result = {}
    for scope, (hit, total, branch_hit, branch_total) in counts.items():
        if not total and scope != "changed":
            raise ValueError(f"empty {scope} coverage")
        # An unchanged executable scope has no coverage obligation; record N/A.
        result[scope] = {
            "lines": 100 * hit / total if total else None,
            "branches": 100 * branch_hit / branch_total if branch_total else None,
            "statements": total,
            "branch_count": branch_total,
        }
        for metric, floor in zip(("lines", "branches"), COVERAGE_FLOORS[scope], strict=True):
            value = result[scope][metric]
            if value is not None and value < floor:
                raise ValueError(f"{scope} {metric}: {value:.2f}% < {floor}%")
    return result


def check_mutation(records, triaged_timeouts=frozenset()):
    scopes = {"scope": [], "text": []}
    for name, exit_code in records.items():
        if name.startswith("pdf2mp3.text.") or name.startswith(
            "pdf2mp3.pdf2mp3.x_tts_chunk_with_retry"
        ):
            # A test deadline may report assertion failure (1) for the known loop.
            # Its reviewed nontermination never earns credit, regardless of that label.
            if name in triaged_timeouts and exit_code in (1, -24, 24, 36, 152, 255):
                exit_code = 0
            if exit_code not in (0, 1):
                raise ValueError(f"unresolved mutant: {name}, exit={exit_code}")
            scopes["scope"].append(exit_code)
            if name.startswith("pdf2mp3.text."):
                scopes["text"].append(exit_code)
    result = {}
    if not any(name.startswith("pdf2mp3.pdf2mp3.x_tts_chunk_with_retry") for name in records):
        raise ValueError("missing retry mutation evidence")
    for scope, values in scopes.items():
        if not values:
            raise ValueError(f"missing {scope} mutation evidence")
        result[scope] = 100 * sum(values) / len(values)
        if result[scope] < MUTATION_FLOORS[scope]:
            raise ValueError(f"{scope} mutation: {result[scope]:.2f}% < {MUTATION_FLOORS[scope]}%")
    return result


def check_audit(data):
    dependencies = data.get("dependencies", [])
    if not dependencies:
        raise ValueError("missing dependency audit")
    for item in dependencies:
        if "version" not in item or "vulns" not in item or item.get("skip_reason") or item["vulns"]:
            raise ValueError(f"unresolved dependency audit: {item.get('name', 'unknown')}")
    return len(dependencies)


def check_licenses(data, approved, packages=None):
    if not data:
        raise ValueError("empty license report")
    for item in data:
        allowed = [*approved, *(packages or {}).get(item.get("Name", "").lower(), [])]
        if item.get("License") not in allowed:
            raise ValueError(f"license needs review: {item.get('Name')}: {item.get('License')}")
    return len(data)
