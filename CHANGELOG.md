# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-10-08
### Changed
- Store manual demo inputs/results under ignored `local/inputs/` and
  `local/outputs/`; default sample generation to `local/inputs/demo.pdf`, create
  destination parents and retain overwrite refusal. Update documented demo paths.
- Complete interface docstrings and clarify that chunking may normalize paragraph
  separators; preserve text processing and exported Python callable behavior.
- Migrate the optional OpenAI adapter from Speech API to Realtime WebSocket
  responses with `gpt-realtime-2.1-mini`, retaining `alloy` and local MP3 output.
  Require the OpenAI SDK realtime extra >=3.26.1,<4; reject legacy model/voice
  settings. Validate completed PCM and narration transcripts, bound requests
  to 120 seconds and close resources without automatic retries. This is tested
  offline; real API access and native Windows remain separate validation.
- **Breaking:** replace the flat CLI with `convert` and `check` subcommands; unify
  `--voice`/OpenAI `--model`, reject irrelevant options and require `--overwrite`.
  Add `--version`, consistent help, quiet output and schema-versioned JSON results
  for people and automation. Support negative Edge percentages with space or `=`.
- Keep document snippets and raw exception values out of normal CLI diagnostics;
  structured failures retain their exit codes even with `--debug`.
- **Breaking:** require Python 3.10+ instead of 3.9 to use the corrected PDF parser.
  Release version 2 with the redesigned CLI and preserved Python helper API.
- Require pdfminer.six 20251230 or later within the existing 2025 release range;
  add audioop-lts only on Python 3.13+ for pydub compatibility.
- Make pyproject.toml the dependency source; expose gTTS, OpenAI and pyttsx3 as
  optional extras and scope PyObjC to macOS. Preserve the existing Edge defaults.
- Correct English README installation and CLI examples to use `pdf2mp3` and
  `python -m pdf2mp3`; explain privacy, languages, OCR limits and release status.
- Record the upstream withdrawal of the historical gTTS/Click advisory; preserve
  the dependency constraint and security review note without adding exceptions
  or changing dependency resolution.

### Fixed
- Use absolute release documentation links in the distributed README so they
  work on PyPI; validate their files and heading anchors against release source.
- Reject pyttsx3 WAV responses without audio samples as synthesis failures,
  preserving the input and previous destination instead of exporting only pauses.
- Pass macOS `say` document text through stdin so leading hyphens cannot become
  subprocess options; make Unicode documentation fixtures independent of the
  Windows locale encoding and local-provider failure fixtures independent of
  installed native speech engines.
- Keep the reviewed nonterminating mutation as a survivor even when a test
  deadline reports it as killed; never award score credit for that known loop.
- Preserve a destination created during conversion with an exclusive final
  reservation; clean owned reservations on failed commits. Reject explicitly
  missing local voices rather than selecting another voice silently.
- Exclude checkout-local development material from wheel and sdist, including
  builds with existing packaging caches.
- Reject header-only audio from macOS `say` as a synthesis failure, preserving
  input and existing output instead of reporting a silent conversion as success.
- Reject input/output collisions (including existing aliases) and nonpositive
  chunk sizes; report extraction/export failures with defined exit codes.
- Preserve input and existing destination files on failed or interrupted export
  by writing to a sibling temporary file before replacing the output.
- Retry empty speech responses and stop sleeping after the last failed attempt.
- Preserve literal paragraph-marker text during chunking; keep public helper
  imports compatible after separating deterministic text processing.

### Added
- Exported Python API reference and a shared documentation/Git hygiene gate for
  local links, heading anchors, API inventory, docstrings and private-file protection.
- Final version metadata and PyPI installation instructions; run branch CI,
  require green PR checks and validate tagged artifacts before publication.
- Contributor instructions and indexed CLI, contract, QA, support and
  release documentation.
- Synthetic unit/property/contract/PDF/audio/provider and installed-artifact tests,
  network blocking, typed production interfaces and local quality profiles.
- Enforced coverage, mutation, lint, typing, security, license and performance
  gates with per-run evidence; test the gate evaluators' failure behavior.
- Python 3.10–3.14 CI coverage with macOS/Windows smoke checks; require the gate
  and support matrix before publication of the exact tested wheel and sdist.
- Reproducible synthetic Portuguese/English demo PDF generation, exercised by
  offline CLI and installed-artifact checks; document local macOS speech checks
  and a separate Windows validation checklist.

## [1.0.0] - 2025-10-01
### Added
- Initial release of `pdf2mp3`.
- Command-line interface (CLI) to convert PDF files into MP3 audio.
- PDF text extraction with chunking for large documents.
- Text-to-Speech (TTS) integration with retry mechanism.
- Language normalization and text cleaning utilities for TTS compatibility.
- MIT License and full project documentation (README, CONTRIBUTING, SECURITY, CODE OF CONDUCT).
- Continuous Integration (CI) with automated tests via GitHub Actions.
- Release workflow for publishing to PyPI.
