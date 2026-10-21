"""Ask NVDA's own Python, booted as the emulator boots it for Q3 (the fleet's settings, voices and Windows language names), what it says. Run under the emulator's Python (q2/venv):

    python probe_nvda.py <request.json>      # prints JSON

The request: {"codes": ["cy", ...], "supported": ["en", ...], "sequences": [[{"lang": "cy"}, "text", ...], ...], "table": "<path>"}.
  descriptions  languageHandler.getLanguageDescription(code), NVDA's own function, over the stand-in
  supported     the synthesizer's languageIsSupported(code)
  speech        what NVDA's speak() sends the synthesizer for each sequence, joined, the language state reset before each
  report        the stand-in's record of the names it was asked about (q3/emulate.py keeps it in a page's record)"""
import json, os, sys

request = json.loads(open(sys.argv[1], encoding='utf-8').read())
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('EMU_NVDA_INI', os.path.join(HERE, '..', '..', 'q3', 'nvda-fleet.ini'))
os.environ.setdefault('EMU_FLEET_VOICES', '1')
if request.get('table'): os.environ['EMU_LANGUAGE_NAMES'] = request['table']
sys.path.insert(0, os.path.join(HERE, '..'))
import driver, languageHandler, speech
from speech.commands import LangChangeCommand

out = {'descriptions': {c: languageHandler.getLanguageDescription(c) for c in request.get('codes', [])},
       'supported': {c: driver._synth.languageIsSupported(c) for c in request.get('supported', [])}, 'speech': []}
for sequence in request.get('sequences', []):
    speech.speech._speechState.lastReportedLanguage = None
    first = len(driver.SPY.sequences)
    speech.speak([LangChangeCommand(item['lang']) if isinstance(item, dict) else item for item in sequence])
    out['speech'].append(' '.join(driver.SPY.text_since(first).split()))
out['report'] = driver.boot.kernel32_standin.report()
print(json.dumps(out, ensure_ascii=False))
