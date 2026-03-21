import os
p = r'C:\NovaX\novax_core_v2.py'
with open(p, 'rb') as f:
    d = f.read()
# Replace the problematic backslash paths in docstring with forward slashes
old = b'--root "C:\\ProgramData\\NovaX\\app\\shell\\static"'
new = b'--root C:/ProgramData/NovaX/app/shell/static'
d = d.replace(old, new, 1)
with open(p, 'wb') as f:
    f.write(d)
print('Patched', len(d), 'bytes')
