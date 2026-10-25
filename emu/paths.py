"""Where things are. CODE is this repository; DOWNLOADS holds what the repository does not (NVDA, Chromium and CLDR sources, the Chrome build,
the unpacked libraries and the Python virtualenv; see Reproduction in docs/announcement-emulator-spike.md). Set EMU_DOWNLOADS to relocate it."""
import os, pathlib
CODE = pathlib.Path(__file__).resolve().parent.parent
DOWNLOADS = pathlib.Path(os.environ.get('EMU_DOWNLOADS') or pathlib.Path.home() / 'spikes/announcement-emulator-5661')


def app_dir(downloads=DOWNLOADS):
    """NVDA's appDir: the overlay of its source whose locale/en/cldr.dic is the pinned one, which setup.sh builds as links so that the checkout stays unmodified. The runtime bundle has no second tree
    (A11-231): its nvda-src/source has the pinned names in place (NVDA's own checkout has no cldr.dic), and is the appDir. A layout with neither is not made to look like the bundle: the overlay's path is
    returned, and what NVDA reads from it fails where it is missing."""
    root = pathlib.Path(downloads)
    overlay, source = root / 'nvda-appdir', root / 'nvda-src' / 'source'
    return source if not overlay.is_dir() and (source / 'locale' / 'en' / 'cldr.dic').exists() else overlay
