# Python API reference

This reference covers the seven callables exported by `pdf2mp3.__all__` in the
`2.0.0` package. Import them directly from `pdf2mp3`. Provider adapters
and `pdf2mp3.cli` are implementation modules, outside that exported contract.
The CLI intentionally changed in v2; these Python callable contracts remain.

Use the [CLI contract](cli.md) for commands, JSON and exit codes, and
[architecture contracts](contracts.md) for the complete conversion pipeline.
Library helpers propagate exceptions; the CLI's safe error presentation does
not automatically apply to a caller's own logging.

## `normalize_lang`

```text
normalize_lang(lang: str | None) -> str
```

Return `en` or `pt-br`. Matching is case-insensitive and strips surrounding
whitespace. English aliases: `en`, `en-us`, `english`. Portuguese aliases:
`pt`, `pt-br`, `ptbr`, `pt_br`, `portuguese`, `português`, `portugues`.
`None` and the empty string select `pt-br`; whitespace alone is invalid.
Unrecognized values raise `ValueError`. No translation, file or network access.

## `extract_text_from_pdf`

```text
extract_text_from_pdf(pdf_path: pathlib.Path) -> str
```

Read the PDF locally through pdfminer.six and return its extracted text, possibly
empty. Relative paths resolve from the working directory. The input is not
modified or transmitted. File and PDF parser exceptions propagate; scanned
image-only PDFs need separate OCR. Reading order depends on PDF structure.
This helper does not clean the text or validate an output destination.

## `clean_text`

```text
clean_text(raw: str) -> str
```

Return heuristically normalized text: remove carriage returns, repair
line-ending hyphenation, join wrapped lines, normalize spacing/paragraph breaks
and discard frequently repeated short lines. Empty input returns an empty string.
These heuristics may remove meaningful repetition; they do not reconstruct
complex layouts or perform OCR. No file, network or speech effects.

## `split_into_chunks`

```text
split_into_chunks(text: str, max_chars: int) -> list[str]
```

Prefer sentence boundaries; hard-split an overlong sentence when necessary.
Each returned chunk is nonempty and no longer than `max_chars` by Python `len()`;
this is a character-count limit, not a byte/token limit. Whitespace-only input
returns an empty list. Chunk preparation strips boundary whitespace and may
join paragraph separators with spaces. It does not promise exact paragraph
formatting or keep an overlong word intact. Zero/negative limits raise
`ValueError`. No file or network effects.

## `sanitize_for_tts`

```text
sanitize_for_tts(s: str) -> str
```

Replace nonbreaking spaces, remove zero-width spaces, normalize the supported
smart quotes and replace `&` with the English word `and`, including in Portuguese
text. This preserves the existing shared TTS preparation behavior. Sanitation
can increase string length after chunking; it is not an XML/SSML sanitizer for
arbitrary markup. No file, network or speech effects.

## `tts_chunk_with_retry`

```text
async tts_chunk_with_retry(
    text: str, voice: str, rate: str, volume: str,
    *, timeout_s: float = 120, retries: int = 4, base_backoff: float = 1.6
) -> bytes
```

Await this helper to synthesize one text chunk through the external Edge service.
`voice` is an Edge voice ID; `rate` and `volume` are signed percentages. This
helper does not perform the CLI's complete parameter validation. It returns raw
MP3 bytes without saving a file or assembling the complete document.

Each attempt has a `timeout_s` deadline. `retries` is the maximum total attempts;
ordinary provider failures, timeouts and empty audio are retried. Waits use
`base_backoff ** attempt` plus random jitter from 0 to 0.5 seconds; no wait follows
the final failure. Exhaustion raises `RuntimeError`; cancellation propagates.
Use positive timeout/attempt values. Credentials are not needed by this Edge
adapter, but Internet and service/voice availability are required. Only submit
text appropriate for external processing. Caller logs may expose exception data.

## `main`

```text
main() -> None
```

Invoke the v2 CLI using `sys.argv[1:]`. A successful command returns `None`;
no arguments prints help and returns `None`. Explicit help/version use argparse
and can raise `SystemExit(0)`. Failures raise `SystemExit` with the documented
exit code. Conversion can send text externally and write audio. `check` does
not contact speech services or write files.

For automation, prefer `pdf2mp3` or `python -m pdf2mp3` in a subprocess with JSON
rather than modifying process arguments or calling this wrapper concurrently.

## Synthetic text preparation example

This example is offline and uses no PDF or credentials:

```python
from pdf2mp3 import clean_text, normalize_lang, sanitize_for_tts, split_into_chunks

raw = "Synthetic word-\nwrap.\n\nSecond sentence."
language = normalize_lang("english")
cleaned = clean_text(raw)
chunks = [sanitize_for_tts(chunk) for chunk in split_into_chunks(cleaned, 40)]
assert language == "en"
assert chunks == ["Synthetic wordwrap. Second sentence."]
```

For PDF/MP3 demonstrations, use [the local demo guide](local-demo.md). It keeps
manual inputs in `local/inputs/` and outputs in `local/outputs/`, outside Git and
distributed artifacts. Automated tests generate synthetic inputs in temporary
directories and block network access. Only opt-in speech checks contact services.
