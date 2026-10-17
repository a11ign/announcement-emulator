import driver, hashlib, extract_cases, run_cases, textInfos, controlTypes
cs=[c for c in extract_cases.cases() if c['name']=='test_ariaDescription_browseMode'][0]
key=hashlib.sha1(cs['html'].encode()).hexdigest()[:12]
b=driver.load(run_cases.capture.CACHE / f'{key}.json')
for s,e,t in driver.lines(b): print(s,e,repr(t))
s,e,t=[x for x in driver.lines(b) if 'An element' in x[2]][0]
ti=b.makeTextInfo(textInfos.offsets.Offsets(s,s)); ti.expand(textInfos.UNIT_LINE)
for c in ti.getTextWithFields({}):
    if isinstance(c, textInfos.FieldCommand):
        f=c.field; print(' ',c.command,{k:f.get(k) for k in ('role','name','description','_description-from','_startOfNode','_endOfNode','alwaysReportName','descriptionIsContent') if k in f})
    else: print('  text',repr(c))
