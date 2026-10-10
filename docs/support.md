# Python and platform support

Version `2.0.1` requires Python **3.10 or later**. The configured
matrix covers 3.10–3.14 on Linux, and 3.10/3.14 on macOS and Windows. Versions
beyond that matrix are not yet verified. Canonical quality tooling runs on 3.12.

The published 1.0.0 baseline declares >=3.9 but its pydub dependency cannot import
on Python 3.13+ without the removed audioop module. Use Python 3.12 for that
release. Version 2.0 adds conditional `audioop-lts` for >=3.13.
The Python floor change was explicitly accepted as a major-version change.

FFmpeg and ffprobe must be installed on PATH. Package installation does not
install these system executables. The base package supports the Edge adapter;
English and Brazilian Portuguese are the language presets, not translation.

| Engine | Installation | External requirements |
| --- | --- | --- |
| Edge (default) | `python -m pip install pdf2mp3==2.0.1` | Network and available Microsoft voices |
| gTTS | `python -m pip install 'pdf2mp3[gtts]==2.0.1'` | Network; Google speech endpoint |
| OpenAI | `python -m pip install 'pdf2mp3[openai]==2.0.1'` | SDK 3.26.1+ with WebSockets, Realtime model access, `OPENAI_API_KEY`, possible charges; see [OpenAI narration](openai.md) |
| pyttsx3 | `python -m pip install 'pdf2mp3[pyttsx3]==2.0.1'` | Working system speech engine/voices; PyObjC on macOS, eSpeak on Linux |
| macOS say | Base package | macOS `say` and installed voices |

Base wheel/sdist installation, command help and synthetic conversions are checked
separately from optional-extra resolution and adapter contracts. Real provider
and system voice smoke tests are opt-in, require explicit authorization and must
use synthetic text. No offline test proves remote availability or voice quality.

GitHub workflows define the desired matrix. A local macOS run cannot certify
Linux/Windows; check the actual CI results before a release. See each local run's
summary for the interpreter, OS, resolved versions and limits of its evidence.

The [local demo guide](local-demo.md) separates real Edge/macOS `say` conversions
from offline tests and provides a Windows checklist. Speech files can be decoded
and checked for signal locally; listening is still required to assess narration.
