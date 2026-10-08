"""Fixed synthetic workloads with generous time/memory regression budgets."""

import asyncio
import hashlib
import json
import platform
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from unittest.mock import patch

from pydub import AudioSegment
from reportlab.pdfgen import canvas

# Scripts run from the checkout; import the package under test, not another install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pdf2mp3.pdf2mp3 as app  # noqa: E402
from pdf2mp3 import clean_text, extract_text_from_pdf, split_into_chunks  # noqa: E402


def measure(function, seconds, megabytes):
    tracemalloc.start()
    started = time.perf_counter()
    result = function()
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    data = {
        "seconds": elapsed,
        "peak_mib": peak / 1024**2,
        "budget_seconds": seconds,
        "budget_mib": megabytes,
        "result_size": len(result),
    }
    if not result or elapsed > seconds or data["peak_mib"] > megabytes:
        raise RuntimeError(f"performance budget failed: {data}")
    return data


def assembly_workload():
    async def synthetic(*args, **kwargs):
        return b"synthetic codec boundary"

    # Exercise the production loop and real AudioSegment concatenation while
    # excluding variable network/decoder latency from this allocation budget.
    part = AudioSegment.silent(duration=100)
    with (
        patch.object(app, "tts_chunk", synthetic),
        patch.object(app.AudioSegment, "from_file", return_value=part),
    ):
        return asyncio.run(app.synthesize_chunks(["Synthetic text."] * 200, "synthetic"))


def main():
    text = "Synthetic words form a sentence. Another sentence follows.\n\n" * 12000
    report = {
        "python": sys.version,
        "platform": platform.platform(),
        "corpus_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }
    report["text"] = measure(lambda: split_into_chunks(clean_text(text), 1600), 10, 96)
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "synthetic.pdf"
        document = canvas.Canvas(str(path), invariant=True)
        for page in range(100):
            document.drawString(
                50, 700, f"Synthetic page {page}: an extraction performance sample."
            )
            document.showPage()
        document.save()
        report["pdf"] = measure(lambda: extract_text_from_pdf(path), 10, 96)

    report["audio"] = measure(assembly_workload, 5, 96)
    Path(sys.argv[1]).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
