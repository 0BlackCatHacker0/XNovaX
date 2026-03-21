"""tsize.py - Ternary directory size calculator micro-tool
Usage: python tsize.py <path>
Returns total bytes to stdout
"""
import os, sys

path = sys.argv[1] if len(sys.argv) > 1 else "C:/NovaX"
total = 0
for root, dirs, files in os.walk(path):
    for f in files:
        try:
            total += os.path.getsize(os.path.join(root, f))
        except OSError:
            pass
print(total)
