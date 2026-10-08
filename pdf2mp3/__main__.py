"""
Module entry point for the pdf2mp3 CLI.

Allows the package to be executed as a module:

    python -m pdf2mp3 convert input.pdf --output output.mp3
    python -m pdf2mp3 check input.pdf --json

This delegates execution to the main() function defined
in pdf2mp3/pdf2mp3.py, which delegates to the shared v2 CLI.
"""

from .pdf2mp3 import main

if __name__ == "__main__":
    main()
