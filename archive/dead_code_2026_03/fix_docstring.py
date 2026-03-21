
with open('C:\\NovaX\\novax_core_v2.py', 'r', encoding='utf-8', errors='replace') as f:
    src = f.read()

# Fix the docstring path that has backslash issues
src = src.replace(
    'Run: python novax_core.py --root "C:\\ProgramData\\NovaX\\app\\shell\\static" --port 9999',
    'Run: python novax_core.py --root C:/ProgramData/NovaX/app/shell/static --port 9999'
)

with open('C:\\NovaX\\novax_core_v2.py', 'w', encoding='utf-8') as f:
    f.write(src)

import py_compile
try:
    py_compile.compile('C:\\NovaX\\novax_core_v2.py', doraise=True)
    print('SYNTAX OK - ' + str(len(src)) + ' bytes')
except Exception as e:
    print(f'STILL ERROR: {e}')
