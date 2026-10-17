import driver
b = driver.load(driver.boot.R / 'q2/fix/simple-web.json')
gm = type(b)._gestureMap
ks = [k for k in gm if any(k.endswith(x) for x in (':h', ':t', ':e', ':p', ':2', ':3', ':x', ':NVDA+upArrow', ':control+rightArrow', ':shift+p', ':shift+h'))]
for k in sorted(ks): print(k, gm[k])
print(len(gm))
