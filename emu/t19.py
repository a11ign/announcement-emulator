import sys; sys.path.insert(0,'.')
import boot, live, driver
d = live.LiveDoc('<p>Hello, world!</p><p>Предложение по-русски.</p><p>我不会说中文！</p><p>Bye-bye, world!</p>')
for s,e,t in driver.lines(d.b): print(s,e,repr(t))
d.close()
