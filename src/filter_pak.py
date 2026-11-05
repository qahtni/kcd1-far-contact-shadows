#!/usr/bin/env python3
"""Copy a CryEngine .pak (zip) leaving out named entries; every other entry keeps its name, data and compression.
usage: filter_pak.py SRC.pak DST.pak ENTRY [ENTRY...]   (entry names compared case-insensitively)"""
import sys, zipfile
src, dst, drop = sys.argv[1], sys.argv[2], {e.lower() for e in sys.argv[3:]}
dropped = []
with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, 'w') as zout:
    for info in zin.infolist():
        if info.filename.lower() in drop:
            dropped.append(info.filename); continue
        zout.writestr(info, zin.read(info))
print('dropped', dropped)
assert len(dropped) == len(drop), 'not every entry was found'
