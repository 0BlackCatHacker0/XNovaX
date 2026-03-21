"""NovaX NovaLang Python Wrapper — bridges python novalang.py to novalang.exe"""
import subprocess
import sys
import os

# Forward all arguments to the compiled Rust VM
args = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "novalang.exe")] + sys.argv[1:]

# Pass through environment and creationflags
kwargs = {}
if os.name == 'nt':
    kwargs['creationflags'] = 0x08000000  # CREATE_NO_WINDOW

try:
    result = subprocess.run(args, **kwargs)
    sys.exit(result.returncode)
except FileNotFoundError:
    print(f"Error: novalang.exe not found", file=sys.stderr)
    sys.exit(1)
except KeyboardInterrupt:
    sys.exit(0)
