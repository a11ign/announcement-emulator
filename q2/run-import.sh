#!/bin/bash
# Q2 stage 1: import NVDA 2026.1.1's own Python on Linux (CPython 3.13), stubbing only Windows-bound modules.
cd "$(dirname "$0")"
export STUB=winBindings,winUser,winKernel,easeOfAccess,NVDAHelper,louisHelper,objidl,oleacc,oleTypes,IAccessibleHandler,UIAHandler,JABHandler,braille,gui,tones,nvwave,ui,vision,bdDetect,brailleInput,brailleViewer,wasapi,mouseHandler,comInterfaces,eventHandler,api,review,NVDAObjects,appModuleHandler,winreg,winsound,comtypes,wx
exec venv/bin/python probe1.py "$@"
