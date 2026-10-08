# Quality gates

Use Python 3.12 and FFmpeg/ffprobe for the canonical QA environment. Install the
pinned developer tools with `python -m pip install -r requirements-dev.txt`.
Runtime dependencies have compatible ranges in `pyproject.toml`; each gate
records the exact resolution. There is no committed transitive lockfile.

```bash
python scripts/quality.py fast --base v1.0.0
python scripts/quality.py standard --base v1.0.0
python scripts/quality.py release --base v1.0.0
```

The base must exist locally. Fetch tags/history before comparing a different
base; do not choose a newer base to hide changed code. Deleted lines have no
execution obligation. New Python files in the production package are measured
in full. If a change has no executable lines/branches, that metric is reported
as null (not applicable), not invented execution coverage.

| Profile | Checks |
| --- | --- |
| fast | Git/base/FFmpeg and private-file preflight, whitespace, Ruff lint/format, strict production mypy, documentation, full deterministic pytest suite |
| standard | Fast checks, subprocess-aware line and branch coverage, changed-code floors, wheel/sdist build and non-editable installs, real synthetic PDF/FFmpeg conversions, static security, secrets, resolved runtime plus optional-extra audit and licenses |
| release | Standard plus scoped mutation, synthetic performance budgets, version/changelog consistency |

CI also runs the [support matrix](support.md). A local release profile does not
prove that remote matrix or live voice services passed. Stable publication has a
separate final-tag check and consumes the gate's exact checksummed artifacts.

## Tests and thresholds

`pytest.ini` blocks network sockets (Unix sockets remain available for the event
loop) and sets a per-test deadline. Windows gets a test-only, connected TCP
loopback socketpair for asyncio wakeup, while ordinary AF_INET creation and
external connections remain blocked. The installed harness uses the same guard. Installed conversion probes block network in
the child process and replace only the speech boundary with synthetic MP3 bytes.
No ordinary test reads personal documents, uses credentials or sends text to TTS.

Tests cover units, properties, released contracts, real PDF/codec integration,
CLI error paths and optional provider boundaries. Installed smoke runs both CLI
entry points outside the source tree for a wheel and a wheel rebuilt from sdist.

The canonical thresholds are `COVERAGE_FLOORS` and `MUTATION_FLOORS` in
[`scripts/quality_checks.py`](../scripts/quality_checks.py). Coverage checks line
and branch ratios separately: global 90/80%, changed code 95/85%, text core
95/90%. The production scope is the complete `pdf2mp3` package, without blanket
coverage exclusions.

`scripts/documentation_check.py` checks inline public Markdown links and ATX heading
anchors, the API reference against `__all__`, and module/public interface
docstrings. It excludes local development notes and does not check external URL
availability or mechanically certify prose accuracy. The runner also rejects
tracked checkout-local files before fingerprinting or scanning their contents.
Human review still checks contracts, examples and limits against code/evidence.

Mutation targets deterministic text functions and `tts_chunk_with_retry`; IO and
provider adapters and CLI validation/presentation rely on integration/contract
tests. The CLI module is copied into the mutation environment so entry-point
tests exercise the v2 interface. Required scores are 80%
for the combined scope and 90% for text. Only assertion-failure exit code 1
counts as killed. Internal errors, missing tests and unreviewed timeouts block
the gate. The exact nonterminating marker-loop mutation in
`scripts/mutation-triage.json` is tied to the source hash and counted as a
**survivor**, with no score credit. Surviving mutants remain visible in the raw
report; a test deadline may make the tool label that known loop as killed, but
the evaluator still counts it as surviving. Passing a score is not a claim that
every mutation was detected.

Performance checks use a fixed ~700 KB text corpus, a 100-page synthetic PDF and
200 local audio segments through the production assembly loop (speech/decoder
boundaries fixed; real AudioSegment concatenation). Time and traced Python allocation budgets live in
`scripts/performance_check.py`. These guard gross regressions, not a throughput
SLA. Tracemalloc does not include all native/FFmpeg allocations. Reports include
Python/platform and corpus hash; compare like environments.

## Security and license policy

Bandit covers production code. Inline suppressions are limited to non-security
random jitter, fixed executable argument arrays without a shell, and existing
optional-bridge/cleanup handling; each has a local reason. Secret scanning covers
tracked and new nonignored files. A reviewed checksum is not a credential.

`pip-audit` checks the actual installed base and gTTS/OpenAI/pyttsx3 dependencies
for the current platform. The project distribution itself is excluded from
the public advisory lookup, not its dependencies. **Any** advisory or unavailable
required report fails; there are no vulnerability exemptions. Advisory services
and package indexes require network. Other platforms need their own audit if
their dependency resolution differs.

After installing extras, the standard/release profiles run
`scripts/openai_check.py` with the installed runtime. It blocks network, replaces
only the SDK's WebSocket transport with synthetic events, and exercises real SDK
serialization/parsing plus PCM-to-MP3 encode/decode. Its credential is an inert
test value. It does not establish real API access or narration fidelity.

Licenses are accepted only by exact metadata value in
`scripts/approved-licenses.json`: MIT, Apache, BSD, ISC and Python/PSF families
and the listed dual-license expressions. Existing dependencies with other
licenses have package-specific entries: Edge TTS (LGPLv3), certifi and pyttsx3
(MPL 2.0), and tqdm (MPL 2.0 AND MIT). They are installed as separate, unmodified
Python distributions; PDF2MP3 does not relicense or vendor them. Preserve their
notices and review obligations before modifying/bundling those dependencies.
This records acceptance of the existing dependency model, not a blanket
allowance for additional copyleft dependencies. Unknown licenses, new packages
outside the permissive set or new expressions fail for review. This covers Python distributions; FFmpeg/system voice licensing
must be considered separately when redistributing binaries. The package does
not bundle them.

## Evidence and failures

Each invocation writes `.quality/runs/<UTC timestamp>/summary.json`, command logs,
versions, source fingerprint, coverage, dependency/security/license reports and
artifact hashes. Generated environments and mutation files are ignored by Git.
A failed command, timeout, missing report or unmet threshold returns nonzero;
never treat an old report as proof for a changed checkout. Preserve evidence for
review, fix the cause, then rerun the affected profile. No gate commits, pushes,
creates tags, contacts TTS or publishes the package.

The [gTTS/Click security note](../SECURITY.md#known-development-dependency-finding)
records why current audits differ from earlier failing runs: the upstream
advisory was withdrawn, with no local exemption or dependency override.
Independent checks continue after a failure; any required failure keeps the
aggregate result FAIL.
