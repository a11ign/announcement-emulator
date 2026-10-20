import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livepage import LivePage
import driver, live
html = '''<header id=h1><a href=#>implicit page header</a></header>
<header id=h2 role="banner"><a href=#>explicit banner</a></header>
<div role="banner" id=h3><a href=#>div banner</a></div>
<article><header id=h4><h2>nested header</h2></header></article>
<main><p>m</p></main>
<footer id=f1><a href=#>implicit footer</a></footer>
<footer id=f2 role="contentinfo"><a href=#>explicit contentinfo</a></footer>
<div role="complementary" id=c1>c</div><aside id=a1>aside</aside>
<section aria-label="named" id=s1>sec</section><div role=region aria-label=reg id=r1>r</div><form aria-label=ff id=fo><input aria-label=x></form><div role=search id=se>s</div>'''
d = live.LiveDoc(html, port=8831)
for ix, pn in d.world.by_ix.items():
    r = pn.raw.get('role')
    if r not in ('inlineTextBox', 'staticText', 'rootWebArea', 'paragraph'): print(ix, r, pn.raw.get('htmlTag'), repr(pn.raw.get('htmlId')), repr(pn.raw.get('name')), pn.ia2_attrs().get('xml-roles'))
d.close()
