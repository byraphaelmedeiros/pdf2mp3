#!/usr/bin/env python3
"""Create a small, text-based synthetic PDF for local demos and offline tests."""

import argparse
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

DEMO_LINES = {
    "pt-br": (
        "Olá! Este documento contém apenas texto sintético.",
        "Esta é uma demonstração curta da conversão de PDF para áudio.",
        "Primeiro, o programa extrai o texto. Depois, prepara a narração.",
        "No final, as partes são reunidas em um arquivo de áudio MP3.",
        "A amostra não contém dados pessoais nem informações confidenciais.",
    ),
    "en": (
        "Hello! This document contains only synthetic text.",
        "This is a short demonstration of converting PDF text into audio.",
        "First, the program extracts the text. Then, it prepares the narration.",
        "Finally, the parts are joined into a single MP3 audio file.",
        "The sample contains no personal data or confidential information.",
    ),
}


def create_demo_pdf(output: Path, lang: str = "pt-br") -> None:
    """Write an extractable, reproducible demo without replacing an existing file."""
    lines = DEMO_LINES[lang]
    with output.open("xb") as stream:
        document = canvas.Canvas(stream, pagesize=A4, invariant=1)
        document.setTitle("PDF2MP3 - Synthetic demo")
        document.setAuthor("pdf2mp3")
        document.setFont("Helvetica-Bold", 18)
        document.drawString(54, 780, "PDF2MP3 - Demo")
        document.setFont("Helvetica", 12)
        for index, line in enumerate(lines):
            document.drawString(54, 730 - index * 28, line)
        document.save()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("local/inputs/demo.pdf"),
        help="destination (default: local/inputs/demo.pdf); parent directories are created",
    )
    parser.add_argument("--lang", choices=tuple(DEMO_LINES), default="pt-br")
    args = parser.parse_args()
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        create_demo_pdf(args.output, args.lang)
    except OSError as error:
        parser.error(f"could not create {args.output}: {error}; choose a new output path")
    print(f"Created {args.output} ({args.lang}, synthetic text only).")


if __name__ == "__main__":
    main()
