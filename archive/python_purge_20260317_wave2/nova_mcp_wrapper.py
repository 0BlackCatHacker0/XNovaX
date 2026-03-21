"""NovaX MCP Server — Python stdin/stdout wrapper for novalang.exe"""
import sys
import subprocess
import threading
import os

def main():
    proc = subprocess.Popen(
        [r"C:\NovaX\novalang.exe", r"C:\NovaX\nova_mcp_stdio.nova"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    # Forward stdout from novalang to our stdout
    def forward_stdout():
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()

    t = threading.Thread(target=forward_stdout, daemon=True)
    t.start()

    # Forward stdin to novalang
    try:
        for line in sys.stdin.buffer:
            proc.stdin.write(line)
            proc.stdin.flush()
    except Exception:
        pass
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.wait()

if __name__ == "__main__":
    main()
