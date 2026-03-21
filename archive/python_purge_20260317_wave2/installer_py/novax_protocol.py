"""NovaX Protocol Handler — opens novax:// URLs in browser."""
import sys
import subprocess
import urllib.parse

def main():
    if len(sys.argv) < 2:
        return
    url = sys.argv[1]  # novax://chat or novax://files/path
    # Strip protocol prefix
    path = url.replace("novax://", "").replace("novax:", "").strip("/")
    if not path:
        path = "nova_desktop.html"
    target = f"http://localhost:9999/{path}"
    # Open in default browser
    subprocess.Popen(["cmd", "/c", "start", "", target],
                     creationflags=0x08000000)

if __name__ == "__main__":
    main()
