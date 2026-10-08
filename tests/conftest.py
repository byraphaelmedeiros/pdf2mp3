"""Synthetic fixtures shared by CLI and audio integration tests."""

import socket
import sys

import pytest
from pydub import AudioSegment
from reportlab.pdfgen import canvas

import pdf2mp3.pdf2mp3 as app
from scripts.network_guard import local_socketpair


@pytest.fixture
def synthetic_pdf(tmp_path):
    path = tmp_path / "sample.pdf"
    document = canvas.Canvas(str(path))
    document.drawString(60, 750, "Synthetic first sentence. Synthetic second sentence.")
    document.save()
    return path


@pytest.fixture
def invoke(monkeypatch):
    def run(*args):
        monkeypatch.setattr(sys, "argv", ["pdf2mp3", *map(str, args)])
        try:
            app.main()
        except SystemExit as error:
            return error.code
        return 0

    return run


@pytest.fixture
def synthetic_speech(monkeypatch):
    async def speak(*args, **kwargs):
        return AudioSegment.silent(duration=100)

    monkeypatch.setattr(app, "synthesize_chunks", speak)


# pytest-socket must still deny all ordinary network sockets. Windows asyncio's
# TCP wakeup pair is the sole local exception, including plugin teardown loops.
_original_socketpair = socket.socketpair


def pytest_configure(config):
    if sys.platform == "win32":
        socket.socketpair = local_socketpair


def pytest_unconfigure(config):
    if sys.platform == "win32":
        socket.socketpair = _original_socketpair
