import base64, sys, os

b64_file = r"C:\NovaX\bridge_v3.b64"
out_file = r"C:\NovaX\nova_bridge_v3.py"

# Read base64, decode, write
with open(b64_file, 'r') as f:
    b64 = f.read().strip()

data = base64.b64decode(b64)
with open(out_file, 'wb') as f:
    f.write(data)

print(f"Decoded {len(b64)} base64 chars -> {len(data)} bytes -> {out_file}")

# Verify syntax
import py_compile
try:
    py_compile.compile(out_file, doraise=True)
    print("SYNTAX OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")
