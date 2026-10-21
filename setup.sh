#!/bin/sh
# Build what the repository does not hold, into $EMU_DOWNLOADS (default ~/spikes/announcement-emulator-5661), without root:
#
#   EMU_DOWNLOADS=/some/dir ./setup.sh
#
# Every address and revision below is the one the spike was measured with (docs/announcement-emulator-spike.md, Reproduction). Needs git, curl, python3, dpkg-deb,
# apt-get download (the Chrome libraries are fetched as .deb files and unpacked under libs/root; nothing is installed), and about 2.5 GB.
set -eu
D="${EMU_DOWNLOADS:-$HOME/spikes/announcement-emulator-5661}"
mkdir -p "$D" && cd "$D"

NVDA_REV=5d92106f17e461dac62aa48257bbbf4183e033d0          # tag release-2026.1.1 (2026-05-18), the release the fleet runs
CLDR_REV=6d3ba86c3963f023550a4b1aa8160945e77ca423          # nvaccess/nvda-cldr, the emoji and symbol names NVDA's tests are run with
ARIA_REV=84b921a0                                          # w3c/aria-practices as NVDA's include/ pins it (the tests load pages from it)
CHROME=155.0.8059.84                                       # Chrome for Testing, milestone 155 as the fleet's Edge 155.0.4283.x
UV_REL=https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz

# 1. NVDA's own source, unmodified
if [ ! -d nvda-src/.git ]; then git clone --filter=blob:none https://github.com/nvaccess/nvda nvda-src; git -C nvda-src checkout "$NVDA_REV"; fi
# 2. the CLDR names, and the overlay of NVDA's source/ whose locale/en/cldr.dic is the pinned one (the file scons builds)
if [ ! -d cldr-src/.git ]; then git clone --filter=blob:none https://github.com/nvaccess/nvda-cldr cldr-src; git -C cldr-src checkout "$CLDR_REV"; fi
rm -rf nvda-appdir && mkdir nvda-appdir
for f in nvda-src/source/*; do ln -s "$D/$f" "nvda-appdir/$(basename "$f")"; done
rm nvda-appdir/locale && mkdir nvda-appdir/locale
for f in nvda-src/source/locale/*; do ln -s "$D/$f" "nvda-appdir/locale/$(basename "$f")"; done
rm nvda-appdir/locale/en && mkdir nvda-appdir/locale/en
for f in nvda-src/source/locale/en/*; do ln -s "$D/$f" "nvda-appdir/locale/en/$(basename "$f")"; done
ln -sf "$D/cldr-src/locale/en/cldr.dic" nvda-appdir/locale/en/cldr.dic
# 3. the W3C ARIA examples the tests open
if [ ! -d aria-practices/.git ]; then git clone -q --filter=blob:none https://github.com/w3c/aria-practices aria-practices; git -C aria-practices checkout -q "$ARIA_REV"; fi
# 4. Chromium's Windows accessibility mapping, as read: the tables are generated from these (emu/gen_tables.py)
mkdir -p chromium-src
for p in ui/accessibility/platform/ax_platform_node_win.cc ui/accessibility/platform/ax_platform_node_base.cc ui/accessibility/platform/ax_platform_node_delegate.h \
         ui/accessibility/ax_role_properties.cc ui/accessibility/ax_node.cc third_party/iaccessible2/ia2_api_all.idl; do
  curl -fsSL "https://chromium.googlesource.com/chromium/src/+/refs/tags/$CHROME/$p?format=TEXT" | base64 -d > "chromium-src/$(basename "$p")"
done
# 5. the browser
if [ ! -x chrome155/chrome-linux64/chrome ]; then
  mkdir -p chrome155
  curl -fsSL -o chrome155/c.zip "https://storage.googleapis.com/chrome-for-testing-public/$CHROME/linux64/chrome-linux64.zip"
  python3 - <<'PY'      # unzip keeps the executable bits; python's zipfile does not, so they are set from the archive's own modes
import zipfile, os
z = zipfile.ZipFile('chrome155/c.zip')
for i in z.infolist():
    z.extract(i, 'chrome155')
    mode = i.external_attr >> 16
    if mode: os.chmod(os.path.join('chrome155', i.filename), mode & 0o777)
PY
  rm chrome155/c.zip
fi
# 6. the libraries Chrome needs that a minimal host lacks, unpacked without root
mkdir -p libs/debs libs/root
( cd libs/debs && apt-get download libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64 libavahi-client3 libavahi-common-data libavahi-common3 libcups2t64 libfontenc1 \
    libgl1-mesa-dri libunwind8 libxdamage1 libxfont2 libxkbfile1 libxres1 x11-xkb-utils xkb-data xvfb )
for f in libs/debs/*.deb; do dpkg-deb -x "$f" libs/root; done
# 7. Python 3.13 (NVDA's pyproject requires >=3.13,<3.14) and the packages NVDA's source imports that are not Windows-only
mkdir -p tools
if [ ! -x tools/uv ]; then curl -fsSL "$UV_REL" | tar -xz -C tools --strip-components=1; fi
tools/uv python install 3.13.16
[ -x q2/venv/bin/python ] || tools/uv venv --python 3.13.16 q2/venv
tools/uv pip install --python q2/venv/bin/python configobj==5.0.9 fast-diff-match-patch==2.1.0 nh3==0.3.2 pyserial==3.5 requests==2.32.5 rpyc==6.0.2 schedule==1.2.2 url-normalize==2.2.1 plumbum==2.0.2
echo "ready: EMU_DOWNLOADS=$D"
