import driver, hashlib, extract_cases, run_cases, traceback
cs=[c for c in extract_cases.cases() if c['name']=='test_ariaRoleDescription_inline_browseMode'][0]
key=hashlib.sha1(cs['html'].encode()).hexdigest()[:12]
b=driver.load(run_cases.capture.CACHE / f'{key}.json')
driver.set_caret(b, run_cases.find_status_line(b))
print(driver.press(b,'downArrow'))
try: print(driver.press(b,'control+rightArrow'))
except BaseException: traceback.print_exc(limit=-8)
