import os
import sys
import subprocess
import time
import re
import threading

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

def install_cloudflared():
    """Installs cloudflared binary if not present."""
    cf_check = subprocess.run(["which", "cloudflared"], capture_output=True, text=True)
    if cf_check.returncode == 0 and cf_check.stdout.strip():
        return True

    print("[INFO] Installing cloudflared tunnel client...")
    try:
        # Check platform
        import platform
        if platform.system() == "Linux":
            subprocess.run(
                "wget -q -nc https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && dpkg -i cloudflared-linux-amd64.deb",
                shell=True,
                check=True
            )
            return True
        elif platform.system() == "Darwin":
            subprocess.run("brew install cloudflared", shell=True, check=True)
            return True
    except Exception as e:
        print(f"[WARN] Failed to install cloudflared: {e}")
    return False

def start_tunnel_and_server():
    print("=" * 75)
    print("  🚀 BANE LIVE GPU SERVER LAUNCHER (FastAPI + Public Tunnel)")
    print("=" * 75)

    # 1. Start Tunnel
    tunnel_proc = None
    public_url = None

    # Check if ngrok authtoken is present
    ngrok_token = os.environ.get("NGROK_AUTHTOKEN")
    if ngrok_token:
        try:
            from pyngrok import ngrok
            ngrok.set_auth_token(ngrok_token)
            tunnel = ngrok.connect(8000)
            public_url = tunnel.public_url
            print(f"[INFO] ngrok tunnel established: {public_url}")
        except Exception as e:
            print(f"[WARN] ngrok failed: {e}. Falling back to cloudflared...")

    if not public_url:
        has_cf = install_cloudflared()
        if has_cf:
            tunnel_log = os.path.join(repo_root, "tunnel.log")
            if os.path.exists(tunnel_log):
                os.remove(tunnel_log)

            print("[INFO] Launching Cloudflare quick tunnel to http://127.0.0.1:8000...")
            tunnel_proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", "http://127.0.0.1:8000", "--logfile", tunnel_log],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Poll for public URL
            for _ in range(35):
                time.sleep(1)
                if os.path.exists(tunnel_log):
                    with open(tunnel_log, "r") as f:
                        content = f.read()
                        matches = re.findall(r"https://[a-zA-Z0-9\-\.]+\.trycloudflare\.com", content)
                        if matches:
                            public_url = matches[0]
                            break

    if not public_url:
        print("[WARN] Could not acquire public tunnel URL. Serving locally on port 8000.")
        public_url = "http://localhost:8000"

    print("\n" + "=" * 75)
    print("  🎉 BANE GPU API SERVER IS LIVE & READY FOR INFERENCE!")
    print("=" * 75)
    print(f"  🌐 Public API URL:  {public_url}")
    print("\n  👉 On your local Mac, run this in your terminal:")
    print(f'     export BANE_API_URL="{public_url}"')
    print("\n  👉 Then run queries with your Bane CLI:")
    print('     bane health')
    print('     bane query "Rank accounts by settled spend volume" -d enterprise_nexus.sqlite')
    print("=" * 75 + "\n")

    # 2. Run Uvicorn in current process
    import uvicorn
    try:
        uvicorn.run("src.api:app", host="0.0.0.0", port=8000, log_level="info")
    finally:
        if tunnel_proc:
            tunnel_proc.terminate()

if __name__ == "__main__":
    start_tunnel_and_server()
