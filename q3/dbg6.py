import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livepage import LivePage
d = LivePage(url='https://www.cqc.org.uk/about-us', port=8861)
print(d.s.eval("innerWidth+'x'+innerHeight+' outer '+outerWidth+'x'+outerHeight+' dpr '+devicePixelRatio+' client '+document.documentElement.clientWidth"))
d.close()
