"""
Gerald Cloud Migration Setup
Validates local configuration and prints step-by-step deployment instructions
for moving gerald_bridge.py to DigitalOcean with HTTPS and Firebase notifications.

Usage:
    python cloud_migration/cloud_setup.py --check
    python cloud_migration/cloud_setup.py --plan
    python cloud_migration/cloud_setup.py --check --plan
"""
import os
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple

BASE = r"C:\CommuteCoder"
CLOUD_DIR = os.path.join(BASE, "cloud_migration")
CONFIG_EXAMPLE = os.path.join(CLOUD_DIR, "cloud_config.example.json")
CONFIG_FILE = os.path.join(BASE, "cloud_config.json")


# ── Prerequisite checks ────────────────────────────────────────────────────────

def _which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _run(cmd: List[str]) -> Tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return -1, str(e)


def check_prerequisites() -> List[Dict[str, Any]]:
    """Return a list of prerequisite check results."""
    checks = []

    # Docker
    has_docker = _which("docker")
    if has_docker:
        rc, out = _run(["docker", "--version"])
        checks.append({
            "name": "Docker",
            "ok": rc == 0,
            "detail": out.split("\n")[0] if rc == 0 else "docker found but not responding",
            "required": True,
        })
    else:
        checks.append({
            "name": "Docker",
            "ok": False,
            "detail": "Not installed. Download: https://docs.docker.com/get-docker/",
            "required": True,
        })

    # Python
    rc, out = _run(["python", "--version"])
    checks.append({
        "name": "Python",
        "ok": rc == 0,
        "detail": out.split("\n")[0],
        "required": True,
    })

    # Git
    has_git = _which("git")
    rc, out = _run(["git", "--version"]) if has_git else (-1, "not found")
    checks.append({
        "name": "Git",
        "ok": rc == 0,
        "detail": out.split("\n")[0],
        "required": False,
    })

    # cloud_config.json
    has_config = os.path.exists(CONFIG_FILE)
    checks.append({
        "name": "cloud_config.json",
        "ok": has_config,
        "detail": CONFIG_FILE if has_config else f"Missing. Copy {CONFIG_EXAMPLE} → {CONFIG_FILE} and fill in your values.",
        "required": True,
    })

    # Firebase service account
    fcm_path = os.path.join(BASE, "firebase-service-account.json")
    has_fcm = os.path.exists(fcm_path)
    checks.append({
        "name": "Firebase service account",
        "ok": has_fcm,
        "detail": fcm_path if has_fcm else "Missing — push notifications will be disabled until added.",
        "required": False,
    })

    # Validate config if present
    if has_config:
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
            ai = cfg.get("ai_providers", {})
            missing_keys = []
            if not ai.get("openai_api_key", "").startswith("sk-"):
                missing_keys.append("openai_api_key")
            if not ai.get("google_api_key", ""):
                missing_keys.append("google_api_key")
            if not cfg.get("auth", {}).get("api_token", "").strip():
                missing_keys.append("auth.api_token")
            if missing_keys:
                checks.append({
                    "name": "cloud_config.json content",
                    "ok": False,
                    "detail": f"Missing values: {', '.join(missing_keys)}",
                    "required": True,
                })
            else:
                checks.append({
                    "name": "cloud_config.json content",
                    "ok": True,
                    "detail": f"domain={cfg.get('server', {}).get('domain', '?')}",
                    "required": True,
                })
        except Exception as e:
            checks.append({
                "name": "cloud_config.json content",
                "ok": False,
                "detail": f"JSON parse error: {e}",
                "required": True,
            })

    return checks


def print_checks(checks: List[Dict[str, Any]]) -> bool:
    print("\n── Prerequisite Checks ──────────────────────────────────────")
    all_required_ok = True
    for c in checks:
        icon = "✅" if c["ok"] else ("❌" if c["required"] else "⚠️ ")
        req = "" if c["required"] else " (optional)"
        print(f"  {icon}  {c['name']}{req}")
        if not c["ok"] or True:  # always print detail
            print(f"       {c['detail']}")
        if not c["ok"] and c["required"]:
            all_required_ok = False
    print()
    return all_required_ok


# ── Deployment plan ─────────────────────────────────────────────────────────────

DEPLOYMENT_PLAN = """
── Gerald Cloud Migration Deployment Plan ──────────────────────────────────────

GOAL: Move gerald_bridge.py to DigitalOcean so Gerald works over the internet.

ARCHITECTURE:
  [Flutter App] → HTTPS → [DigitalOcean Droplet: nginx + gerald_bridge + uvicorn]
                                            ↓ (optional relay)
                              [Matt's PC: claude.cmd]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1 — DigitalOcean Droplet Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Create a Droplet (digitalocean.com → Create → Droplet)
   - Image: Ubuntu 22.04 LTS
   - Size: Basic, $6/mo (1 GB RAM, 1 vCPU) — sufficient for FastAPI
   - Datacenter: Choose closest region
   - Authentication: SSH Key (add your public key)

2. SSH into the droplet:
   ssh root@YOUR_DROPLET_IP

3. Install dependencies:
   apt update && apt upgrade -y
   apt install -y python3 python3-pip nginx certbot python3-certbot-nginx
   pip3 install fastapi uvicorn[standard]

4. Transfer files:
   scp gerald_bridge.py build_verifier.py multi_ai_router.py root@YOUR_DROPLET_IP:/app/
   scp cloud_config.json root@YOUR_DROPLET_IP:/app/
   # Optional: scp firebase-service-account.json root@YOUR_DROPLET_IP:/app/

5. Create a systemd service (/etc/systemd/system/gerald.service):
   [Unit]
   Description=Gerald Bridge
   After=network.target

   [Service]
   WorkingDirectory=/app
   ExecStart=/usr/bin/python3 -m uvicorn gerald_bridge:app --host 0.0.0.0 --port 8000
   Restart=always
   Environment=GERALD_DATA_DIR=/app/data

   [Install]
   WantedBy=multi-user.target

   systemctl enable gerald && systemctl start gerald

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2 — Domain + HTTPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Register or use an existing domain (e.g. mattberry.dev)
   Add an A record: gerald.mattberry.dev → YOUR_DROPLET_IP

2. Configure nginx (/etc/nginx/sites-available/gerald):
   server {
       server_name gerald.mattberry.dev;
       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ln -s /etc/nginx/sites-available/gerald /etc/nginx/sites-enabled/
   nginx -t && systemctl reload nginx

3. Get free HTTPS cert via Let's Encrypt:
   certbot --nginx -d gerald.mattberry.dev
   # Certbot auto-renews every 90 days

4. Update Flutter app Settings → Base URL:
   https://gerald.mattberry.dev

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3 — Firebase Push Notifications
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Create Firebase project: console.firebase.google.com
2. Add Android app → download google-services.json → place in gerald_app/android/app/
3. Enable Cloud Messaging (FCM)
4. Download service account key → place at /app/firebase-service-account.json on server
5. Install google-auth on server:
   pip3 install google-auth requests
6. Restart gerald: systemctl restart gerald

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4 — OpenAI Integration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Get OpenAI API key: platform.openai.com
2. Add to cloud_config.json → ai_providers.openai_api_key
3. Upload updated config: scp cloud_config.json root@YOUR_DROPLET_IP:/app/
4. Restart gerald: systemctl restart gerald
5. In Gerald app Settings → AI Provider → switch to ChatGPT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ESTIMATED COSTS (monthly)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DigitalOcean Droplet (1GB):  $6/mo
  Domain (.dev):               ~$12/yr → $1/mo
  Let's Encrypt SSL:           FREE
  Firebase FCM:                FREE (generous free tier)
  OpenAI API:                  ~$0.01 per task (GPT-4o mini available for less)
  ─────────────────────────────────────────
  TOTAL:                       ~$7-8/mo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCKER ALTERNATIVE (simpler deployment)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # From C:\\CommuteCoder:
  docker build -f cloud_migration/Dockerfile -t gerald-bridge .
  docker run -d -p 8000:8000 --name gerald gerald-bridge

  # Or with docker-compose:
  docker-compose -f cloud_migration/docker-compose.yml up -d
"""


def print_plan() -> None:
    print(DEPLOYMENT_PLAN)


# ── Docker build helper ─────────────────────────────────────────────────────────

def build_docker_image() -> bool:
    """Build the Gerald Docker image locally for testing."""
    dockerfile = os.path.join(CLOUD_DIR, "Dockerfile")
    print(f"[cloud_setup] Building Docker image from {dockerfile}...")
    rc, out = _run([
        "docker", "build",
        "-f", dockerfile,
        "-t", "gerald-bridge:latest",
        BASE,
    ])
    if rc == 0:
        print("[cloud_setup] Docker build SUCCESS — run with:")
        print("  docker run -d -p 8000:8000 --name gerald gerald-bridge:latest")
    else:
        print(f"[cloud_setup] Docker build FAILED:\n{out}")
    return rc == 0


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gerald Cloud Migration Setup")
    parser.add_argument("--check", action="store_true", help="Run prerequisite checks")
    parser.add_argument("--plan", action="store_true", help="Print deployment plan")
    parser.add_argument("--docker", action="store_true", help="Build Docker image locally")
    args = parser.parse_args()

    if not any([args.check, args.plan, args.docker]):
        parser.print_help()
        return 0

    if args.check:
        checks = check_prerequisites()
        all_ok = print_checks(checks)
        if all_ok:
            print("✅ All required prerequisites satisfied — ready to deploy.")
        else:
            print("❌ Fix the above issues before deploying.")

    if args.plan:
        print_plan()

    if args.docker:
        build_docker_image()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
