"""Where things are. CODE is this repository; DOWNLOADS holds what the repository does not (NVDA, Chromium and CLDR sources, the Chrome build,
the unpacked libraries and the Python virtualenv; see Reproduction in docs/announcement-emulator-spike.md). Set EMU_DOWNLOADS to relocate it."""
import os, pathlib
CODE = pathlib.Path(__file__).resolve().parent.parent
DOWNLOADS = pathlib.Path(os.environ.get('EMU_DOWNLOADS') or pathlib.Path.home() / 'spikes/announcement-emulator-5661')
