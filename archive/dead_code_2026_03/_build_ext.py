
import base64, os, json

d = "C:/NovaX/extension"
os.makedirs(d + "/icons", exist_ok=True)

# --- manifest.json (clean ASCII only) ---
m = {
  "manifest_version": 3,
  "name": "NovaX Control Panel",
  "version": "1.0.0",
  "description": "NovaX AI Desktop OS - service monitor, terminal, and section launcher",
  "permissions": ["tabs", "activeTab", "storage", "alarms"],
  "host_permissions": [
    "http://localhost:9999/*","http://localhost:9990/*","http://localhost:9991/*",
    "http://localhost:9997/*","http://localhost:9998/*","http://localhost:18789/*"
  ],
  "action": {
    "default_popup": "popup.html",
    "default_icon": {"16":"icons/icon16.png","48":"icons/icon48.png","128":"icons/icon128.png"}
  },
  "icons": {"16":"icons/icon16.png","48":"icons/icon48.png","128":"icons/icon128.png"},
  "background": {"service_worker": "background.js"}
}
with open(d+"/manifest.json","w",encoding="utf-8") as f:
    json.dump(m, f, indent=2)
print("1/5 manifest.json OK")

# --- Generate icons using struct/zlib (no PIL needed) ---
import struct, zlib

def make_png(size):
    pixels = []
    cx, cy = size//2, size//2
    r = size//2 - 1
    for y in range(size):
        row = []
        for x in range(size):
            dx, dy = x-cx, y-cy
            if dx*dx + dy*dy <= r*r:
                row.extend([74, 222, 128, 255])  # green circle
            else:
                row.extend([0, 0, 0, 0])  # transparent
        pixels.append(b"\x00" + bytes(row))
    raw = b"".join(pixels)
    
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")

for size in [16, 48, 128]:
    with open(f"{d}/icons/icon{size}.png", "wb") as f:
        f.write(make_png(size))
    print(f"2/5 icon{size}.png OK")

print("ALL ICONS DONE")
