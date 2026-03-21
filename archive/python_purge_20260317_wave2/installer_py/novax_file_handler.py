"""NovaX File Handler — opens files/folders via NovaX."""
import sys
import subprocess
import urllib.parse

def main():
    args = sys.argv[1:]
    if not args:
        return
    mode = "open"
    path = args[-1]
    if "--ask" in args:
        mode = "ask"
    elif "--dir" in args:
        mode = "dir"

    encoded = urllib.parse.quote(path, safe="")
    if mode == "ask":
        url = f"http://localhost:9999/nova_desktop.html#ask={encoded}"
    elif mode == "dir":
        url = f"http://localhost:9999/nova_desktop.html#files={encoded}"
    else:
        url = f"http://localhost:9999/nova_desktop.html#open={encoded}"

    subprocess.Popen(["cmd", "/c", "start", "", url],
                     creationflags=0x08000000)

if __name__ == "__main__":
    main()
