
import base64, os
parts = []
for i in range(9):
    p = f'C:\\NovaX\\_gc{i}.txt'
    if os.path.exists(p):
        with open(p, 'r') as f:
            parts.append(f.read().strip())
b64 = ''.join(parts)
data = base64.b64decode(b64)
dest = 'C:\\ProgramData\\NovaX\\app\\shell\\static\\claude_ghost.html'
with open(dest, 'wb') as f:
    f.write(data)
# Cleanup
for i in range(9):
    p = f'C:\\NovaX\\_gc{i}.txt'
    if os.path.exists(p):
        os.remove(p)
os.remove('C:\\NovaX\\_deploy_ghost.py')
print(f'Deployed {len(data)} bytes to {dest}')
