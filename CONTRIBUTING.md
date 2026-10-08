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
