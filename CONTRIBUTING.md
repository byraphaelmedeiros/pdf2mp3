# Contributing

Use English for code, comments and documentation. Preserve the public Python
API and documented defaults. Version 2 intentionally changes CLI syntax; use
the [CLI contract](docs/cli.md) and [architecture contracts](docs/contracts.md).
The [Python API reference](docs/api.md) covers the exported callable interfaces.
Capture released behavior before changing contracts beyond that redesign.

## Development environment

Install Python 3.12, FFmpeg and ffprobe, then from the repository root:

```bash
python3.12 -m venv .venv-dev
source .venv-dev/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/quality.py fast --base v1.0.0
```

On Windows, create the environment with `py -3.12 -m venv .venv-dev` and activate
`.venv-dev\Scripts\Activate.ps1` in PowerShell. Keep any older `.venv` separate
from this development environment. Runtime metadata and optional extras
live in `pyproject.toml`; requirement files delegate to that single source.

For a reusable synthetic `local/inputs/demo.pdf`, real macOS speech checks and the Windows
manual checklist, see [the local demo guide](docs/local-demo.md). Speech checks
are opt-in and separate from the network-blocked automated suite.
Keep manual inputs/results in ignored `local/inputs/` and `local/outputs/`.
Automated fixtures belong in temporary directories, not that local storage.

## Before proposing a change

Run `python scripts/quality.py standard --base v1.0.0` and inspect its evidence.
For release candidates or text/retry changes, run the `release` profile too;
mutation requires Linux/macOS. See [quality gates](docs/quality-gates.md) for
scope, thresholds and failure handling, and [support](docs/support.md) for the
additional CI matrix. All PRs run the full release profile and matrix remotely.

Use only synthetic PDFs, text and audio in tests. Tests block network access;
keep provider doubles at the service boundary and real PDF/FFmpeg operations in
integration tests. Do not add private documents, credentials or recorded user
speech. Live speech tests require separate explicit authorization.
The standard profile also exercises the installed OpenAI SDK with a synthetic
WebSocket transport and blocked network; see [OpenAI narration](docs/openai.md).
This check uses an inert test credential and makes no paid API requests.

Keep changes focused, add regressions for defects and update CHANGELOG for
behavior, compatibility or dependency changes. Do not lower gate thresholds or
add exclusions to conceal a failure. Review the complete diff before requesting
review. Use Conventional Commits for authorized commits.

Open a pull request from your branch with the problem, resulting behavior,
commands actually run, outcomes and remaining limits. Report local checks, CI
and publication separately. Commit, push, tag and release are maintainer/user
actions requiring authorization when an agent is doing the work.

## Issues and security

For bugs, include the installed version, OS/Python/FFmpeg versions and minimal
synthetic reproduction. Do not attach confidential PDFs or document content.
Report vulnerabilities privately using [SECURITY.md](SECURITY.md).

## Collaboration and integration

Raphael Medeiros ([@byraphaelmedeiros](https://github.com/byraphaelmedeiros)) is
the sole maintainer with write access. Anyone can open an issue, fork the project,
propose a pull request or review a change. These activities do not grant merge
or release permissions. Discuss substantial API, dependency or design changes
in an issue before implementing them.

Create a focused branch in your fork and open a PR against `main`. Use a
Conventional Commit style PR title, such as `fix: handle empty documents`.
Keep the PR current with `main`, respond to review and resolve conversations.
The maintainer manually squash-merges after all required checks succeed;
automatic merging is disabled. Branches in this repository are deleted after
merge, while contributors manage their own fork branches. `main` is the only
permanent development branch.

Required approval count is zero while there is only one maintainer, because a
PR author cannot approve their own PR. Write permissions still limit merging to
the maintainer. `CODEOWNERS` requests their review and does not grant anyone
access. Revisit required approvals if another maintainer receives write access.

Release tags and PyPI publication are separate maintainer actions. The `pypi`
environment requires the maintainer's manual approval; see [releasing](docs/releasing.md).
Dependency bots propose changes through PRs and never merge or release them.
External fork workflows require maintainer approval before running. The
maintainer should inspect workflow and executable changes before approving a run.

For triage, use the existing bug, enhancement, documentation and question labels;
mark well-scoped newcomer tasks with `good first issue` only when guidance is
available. Link fixes to issues and credit contributions through Git history and
PR discussion. If a fix already shipped through another change, explain that
with links before closing the superseded PR.
