"""
AIInvigilator - One-Click Server Starter
=========================================
Starts the Daphne ASGI server and optionally opens an ngrok tunnel.

Usage:
  python start_server.py              # LAN only (for same-WiFi demo)
  python start_server.py --ngrok      # LAN + public ngrok URL (for remote demo)
  python start_server.py --port 9000  # Custom port
"""
import os
import sys
import time
import socket
import subprocess
import argparse
import threading

# Ensure we're in the right directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')


def get_lan_ip():
    """Get the LAN IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def check_mysql():
    """Quick check if MySQL is accessible."""
    try:
        import django
        django.setup()
        from django.db import connection
        connection.ensure_connection()
        return True
    except Exception as e:
        print(f"  [!] MySQL connection failed: {e}")
        print(f"  [!] Make sure MySQL is running and .env credentials are correct.")
        return False


def run_migrations():
    """Run pending migrations."""
    print("  Checking migrations...")
    result = subprocess.run(
        [sys.executable, "manage.py", "migrate", "--run-syncdb"],
        capture_output=True, text=True, cwd=BASE_DIR
    )
    if result.returncode == 0:
        print("  Migrations OK.")
    else:
        print(f"  Migration warning: {result.stderr[:200]}")


def start_daphne(host, port):
    """Start the Daphne ASGI server."""
    cmd = [
        sys.executable, "-m", "daphne",
        "-b", host,
        "-p", str(port),
        "app.asgi:application"
    ]
    return subprocess.Popen(cmd, cwd=BASE_DIR)


def start_ngrok(port):
    """Start ngrok tunnel and return public URL."""
    try:
        from pyngrok import ngrok, conf
        # Set ngrok config
        conf.get_default().region = "in"  # India region for lower latency
        tunnel = ngrok.connect(port, "http")
        return tunnel.public_url
    except Exception as e:
        print(f"  [!] ngrok failed: {e}")
        print(f"  [!] You may need to run: ngrok config add-authtoken YOUR_TOKEN")
        print(f"  [!] Get a free token at: https://dashboard.ngrok.com/get-started/your-authtoken")
        return None


def print_banner(lan_ip, port, ngrok_url=None):
    """Print the access information banner."""
    print("\n" + "=" * 60)
    print("   AIInvigilator Server Running!")
    print("=" * 60)
    print(f"\n   LOCAL:    http://127.0.0.1:{port}")
    print(f"   LAN:      http://{lan_ip}:{port}")
    if ngrok_url:
        print(f"   PUBLIC:   {ngrok_url}")
    print(f"\n   Admin login:   /login/")
    print(f"   Teacher login: /login/")
    print(f"\n" + "-" * 60)
    print(f"   To stop: press Ctrl+C")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="AIInvigilator Server")
    parser.add_argument("--port", type=int, default=8000, help="Port number (default: 8000)")
    parser.add_argument("--ngrok", action="store_true", help="Enable ngrok public tunnel")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    args = parser.parse_args()

    print("\n[AIInvigilator] Starting up...\n")

    # Step 1: Check MySQL
    print("[1/4] Checking database...")
    if not check_mysql():
        sys.exit(1)
    print("  Database OK.\n")

    # Step 2: Run migrations
    print("[2/4] Running migrations...")
    run_migrations()
    print()

    # Step 3: Get LAN IP
    print("[3/4] Network setup...")
    lan_ip = get_lan_ip()
    print(f"  LAN IP: {lan_ip}")

    # Step 4: Start ngrok if requested
    ngrok_url = None
    if args.ngrok:
        print("\n[4/4] Starting ngrok tunnel...")
        ngrok_url = start_ngrok(args.port)
        if ngrok_url:
            print(f"  ngrok tunnel: {ngrok_url}")
    else:
        print("\n[4/4] Skipping ngrok (use --ngrok to enable)")

    # Print banner
    print_banner(lan_ip, args.port, ngrok_url)

    # Start Daphne
    daphne_proc = start_daphne(args.host, args.port)

    try:
        daphne_proc.wait()
    except KeyboardInterrupt:
        print("\n\n[AIInvigilator] Shutting down...")
        daphne_proc.terminate()
        if ngrok_url:
            from pyngrok import ngrok
            ngrok.kill()
        print("[AIInvigilator] Goodbye!\n")


if __name__ == "__main__":
    main()
