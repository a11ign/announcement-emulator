import boot, config
v = config.conf["speech"]["unicodeNormalization"]
print(type(v), repr(v), bool(v))
