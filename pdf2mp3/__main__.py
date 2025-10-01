"""
Module entry point for the pdf2mp3 CLI.

Allows the package to be executed as a module:

    python -m pdf2mp3 <options>

This delegates execution to the main() function defined
in pdf2mp3/pdf2mp3.py.
"""

from .pdf2mp3 import main


if __name__ == "__main__":
    main()
