# -*- coding: utf-8 -*-
"""폴더를 zip 으로 (한글 이름은 UTF-8 표시 → Windows 탐색기에서 안 깨짐)."""
import os
import sys
import zipfile

args = [a for a in sys.argv[1:] if a != "--contents"]
src, dst = args[0], args[1]
# --contents: 폴더 이름 없이 안의 내용만
base = os.path.abspath(src) if "--contents" in sys.argv else os.path.dirname(os.path.abspath(src))
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for root, dirs, files in os.walk(src):
        dirs.sort()
        for f in sorted(files):
            if f == ".DS_Store":
                continue
            full = os.path.join(root, f)
            z.write(full, os.path.relpath(full, base).replace(os.sep, "/"))
print("zip:", dst)
