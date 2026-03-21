import base64,os
chunks=[]
for i in range(6):
    p=f"C:\\NovaX\\_u{i}.txt"
    with open(p,'r') as f:
        chunks.append(f.read().strip())
b64=''.join(chunks)
data=base64.b64decode(b64)
out="C:\\ProgramData\\NovaX\\app\\shell\\static\\nova_desktop.html"
with open(out,'wb') as f:
    f.write(data)
print(f"Deployed {len(data)} bytes to {out}")
for i in range(6):
    try: os.remove(f"C:\\NovaX\\_u{i}.txt")
    except: pass
try: os.remove("C:\\NovaX\\_deploy.py")
except: pass
print("Cleaned")
