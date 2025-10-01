# PDF2MP3 – Convert PDFs into Audiobooks

[![PyPI version](https://badge.fury.io/py/pdf2mp3.svg)](https://pypi.org/project/pdf2mp3/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/byraphaelmedeiros/pdf2mp3/actions/workflows/ci.yml/badge.svg)](https://github.com/byraphaelmedeiros/pdf2mp3/actions)

A command-line utility (CLI) in **Python** to convert **PDF files** into **MP3 audiobooks** using high-quality, natural female neural voices.  
Supports **English (en)** and **Brazilian Portuguese (pt-br)**.

---

## Features

* Extracts text from PDFs using **pdfminer.six**.
* Converts text to speech using **edge-tts** (Microsoft Neural Voices).
* Default high-quality female voices:
  * **en-US-AriaNeural**
  * **pt-BR-ThalitaNeural**
* Smart chunk splitting for fluent narration (default: **1600 characters per chunk**).
* Generates a single **continuous MP3 file** (via **pydub + ffmpeg**).
* Configurable language, voice, speaking rate, volume, and chunk size.
* Built-in retry system with exponential backoff for long or unstable requests.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/byraphaelmedeiros/pdf2mp3.git
cd pdf2mp3
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install FFmpeg

`pydub` requires `ffmpeg` to export audio to MP3.

Windows (via winget):

```bash
winget install --id=Gyan.FFmpeg -e
```

macOS (via Homebrew):

```bash
brew install ffmpeg
```

Linux (Debian/Ubuntu):

```bash
sudo apt-get update && sudo apt-get install ffmpeg
```

Verify the installation:

```bash
ffmpeg -version
```

---

## Usage

Basic usage requires only the **input PDF**. Other parameters have defaults.

```bash
python pdf2mp3.py <input.pdf> [options]
```

### Parameters

* **Required**
  * `input` → Input PDF file
* **Optional**
  * `-o, --output` → Output MP3 file (default: same name as PDF with `.mp3`)
  * `-l, --lang` → Language (`en` or `pt-br`, default: `pt-br`)
  * `--voice` → Voice name (default: AriaNeural / ThalitaNeural)
  * `--rate` → Speaking rate (e.g., `+5%`, `-5%`, default: `+0%`)
  * `--volume` → Speaking volume (e.g., `+0%`, `+5%`, default: `+0%`)
  * `--max-chars` → Maximum characters per chunk (default: `1600`)

---

## Examples

Convert a PDF in Portuguese (minimal usage):

```bash
python pdf2mp3.py "document.pdf"
```

Output: `document.mp3` in **pt-br** using `pt-BR-ThalitaNeural`.

Convert a PDF in English:

```bash
python pdf2mp3.py "book.pdf" -l en
```

Specify a custom output file:

```bash
python pdf2mp3.py "document.pdf" -o "output.mp3"
```

Adjust speaking rate and volume:

```bash
python pdf2mp3.py "document.pdf" --rate +5% --volume +0%
```

Use smaller chunks:

```bash
python pdf2mp3.py "document.pdf" --max-chars 1200
```

---

## Notes

* This program **does not work with scanned PDFs (image-based)**.  
  Use OCR first, for example:

  ```bash
  pip install ocrmypdf
  ocrmypdf --force-ocr input.pdf output_ocr.pdf
  ```

* Audio quality depends on the text extraction results from `pdfminer.six`.
* An **active internet connection** is required (the `edge-tts` library uses Microsoft’s neural voices).

---

## Quick Checklist

1. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Install FFmpeg:

   ```bash
   winget install --id=Gyan.FFmpeg -e   # Windows
   ```

3. Run the program:

   ```bash
   python pdf2mp3.py input.pdf
   ```

You will get a **ready-to-play MP3 audiobook**.

---

## Contributing

Contributions are welcome!  
Please read the [Contributing Guidelines](CONTRIBUTING.md) for details.

---

## Code of Conduct

This project follows a [Code of Conduct](CODE_OF_CONDUCT.md).  
By participating, you are expected to uphold this standard.

---

## Security

If you discover a security vulnerability, please report it by emailing:  
**pdf2mp3@byraphaelmedeiros.com**  
See [SECURITY.md](SECURITY.md) for more details.

---

## License

This project is released under the terms of the **MIT License**.  
See the [LICENSE](LICENSE) file for details.

---

## Maintainer

**Raphael Medeiros**  
- GitHub: [@byraphaelmedeiros](https://github.com/byraphaelmedeiros)  
- Contact: **pdf2mp3@byraphaelmedeiros.com**
