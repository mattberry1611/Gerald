"""
Gerald Remote APK Build & Deliver Script
Builds the Flutter APK, copies to serve dir, writes manifest, and optionally
uploads to a cloud endpoint and notifies Matt via push notification.

Usage:
    python remote_build/build_and_deliver.py
    python remote_build/build_and_deliver.py --cloud-url http://my-vps:8000
    python remote_build/build_and_deliver.py --notify
"""
import os
import sys
import json
import shutil
import hashlib
import argparse
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

BASE = "/opt/Gerald"
GERALD_APP = os.path.join(BASE, "gerald_app")
APK_OUTPUT = os.path.join(GERALD_APP, "build/app/outputs/flutter-apk/app-debug.apk")
APK_MANIFEST = os.path.join(BASE, "apk_manifest.json")
APK_SERVE_DIR = os.path.join(BASE, "apk_serve")
DEVICES_FILE = os.path.join(BASE, "gerald_devices.json")


# ── Helpers ────────────────────────────────────────────────────────────────────

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def read_pubspec_version(app_dir: str) -> tuple[str, int]:
    pubspec = os.path.join(app_dir, "pubspec.yaml")
    version = "1.0.0"
    build_number = 1
    if os.path.exists(pubspec):
        with open(pubspec, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("version:"):
                    raw = line.split(":", 1)[1].strip()
                    if "+" in raw:
                        version, bn = raw.split("+", 1)
                        try:
                            build_number = int(bn.strip())
                        except ValueError:
                            pass
                    else:
                        version = raw
                    break
    return version.strip(), build_number


# ── Build ──────────────────────────────────────────────────────────────────────

def build_apk(app_dir: str, flavor: str = "debug") -> bool:
    """Run flutter build apk. Returns True on success."""
    print(f"[build_and_deliver] Running: flutter build apk --{flavor}")
    result = subprocess.run(
        ["flutter", "build", "apk", f"--{flavor}"],
        cwd=app_dir,
        timeout=600,
    )
    return result.returncode == 0


# ── Manifest ───────────────────────────────────────────────────────────────────

def write_manifest(
    apk_path: str,
    version: str,
    build_number: int,
    base_url: str = "",
) -> dict:
    size = os.path.getsize(apk_path)
    apk_hash = sha256_file(apk_path)
    ts = datetime.now(timezone.utc).isoformat()

    download_url = (
        f"{base_url}/apk-latest/download" if base_url else "/apk-latest/download"
    )

    manifest = {
        "available": True,
        "version": version,
        "build_number": build_number,
        "hash": apk_hash,
        "size_bytes": size,
        "timestamp": ts,
        "flavor": "debug",
        "apk_path": apk_path,
        "download_url": download_url,
    }

    with open(APK_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"[build_and_deliver] Manifest written: {APK_MANIFEST}")
    print(f"  version={version}+{build_number}  size={size // 1024}KB  hash={apk_hash[:20]}...")
    return manifest


# ── Local serve copy ───────────────────────────────────────────────────────────

def copy_apk_to_serve_dir(apk_path: str) -> str:
    """Copy APK to stable serve directory so the endpoint URL stays constant."""
    os.makedirs(APK_SERVE_DIR, exist_ok=True)
    dest = os.path.join(APK_SERVE_DIR, "gerald-latest.apk")
    shutil.copy2(apk_path, dest)
    print(f"[build_and_deliver] APK copied to: {dest}")
    return dest


# ── Cloud upload ───────────────────────────────────────────────────────────────

def upload_apk_to_cloud(apk_path: str, cloud_url: str, token: str = "") -> dict:
    """
    Upload the APK binary to the cloud bridge /apk-upload endpoint.
    The cloud bridge stores it and updates its own manifest so remote devices
    can download over HTTPS without needing LAN access.

    Returns {"ok": True, "download_url": "..."} on success.
    """
    upload_url = f"{cloud_url.rstrip('/')}/apk-upload"
    print(f"[build_and_deliver] Uploading APK to: {upload_url}")

    with open(apk_path, "rb") as f:
        apk_bytes = f.read()

    headers: dict = {"Content-Type": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        upload_url,
        data=apk_bytes,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[build_and_deliver] Cloud upload OK: {data}")
            return data
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            pass
        print(f"[build_and_deliver] Cloud upload HTTP error {e.code}: {body[:300]}")
        return {"ok": False, "error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        print(f"[build_and_deliver] Cloud upload error: {e}")
        return {"ok": False, "error": str(e)}


# ── Notification ───────────────────────────────────────────────────────────────

def notify_matt_via_bridge(manifest: dict, bridge_url: str, token: str = "") -> bool:
    """
    POST a notification to the Gerald bridge /notify endpoint.
    The bridge forwards it to Matt's device via FCM.
    """
    notify_url = f"{bridge_url.rstrip('/')}/notify"
    payload = json.dumps({
        "title": "Gerald: New APK Ready",
        "body": (
            f"v{manifest['version']}+{manifest['build_number']} "
            f"({manifest['size_bytes'] // 1024} KB) — tap to install"
        ),
        "data": {
            "type": "apk_ready",
            "version": manifest["version"],
            "build_number": str(manifest["build_number"]),
            "download_url": manifest.get("download_url", ""),
            "hash": manifest["hash"],
        },
    }).encode("utf-8")

    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(notify_url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"[build_and_deliver] Notification sent: {result}")
            return True
    except Exception as e:
        print(f"[build_and_deliver] Notification failed (non-fatal): {e}")
        return False


def write_local_notification(manifest: dict) -> None:
    """
    Write a pending-notification file that the Gerald bridge picks up on next poll.
    Used when cloud bridge is not available.
    """
    notif_path = os.path.join(BASE, "pending_notification.json")
    with open(notif_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "type": "apk_ready",
                "title": "Gerald: New APK Ready",
                "body": (
                    f"v{manifest['version']}+{manifest['build_number']} "
                    f"({manifest['size_bytes'] // 1024} KB)"
                ),
                "manifest": manifest,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            f,
            indent=2,
        )
    print(f"[build_and_deliver] Local notification queued: {notif_path}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gerald APK Build & Deliver")
    parser.add_argument(
        "--cloud-url",
        default="",
        help="Cloud bridge base URL for remote upload (e.g. http://my-vps:8000)",
    )
    parser.add_argument(
        "--token",
        default="",
        help="Bearer token for cloud bridge authentication",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send push notification after successful build",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("Gerald APK Build & Deliver")
    print("=" * 50)

    version, build_number = read_pubspec_version(GERALD_APP)
    print(f"Version: {version}+{build_number}")

    # Step 1 — Build
    success = build_apk(GERALD_APP)
    if not success:
        print("[build_and_deliver] BUILD FAILED — aborting delivery")
        return 1

    if not os.path.exists(APK_OUTPUT):
        print(f"[build_and_deliver] APK not found at: {APK_OUTPUT}")
        return 1

    # Step 2 — Copy to local serve dir
    copy_apk_to_serve_dir(APK_OUTPUT)

    # Step 3 — Write manifest (local URL by default)
    base_url = args.cloud_url or ""
    manifest = write_manifest(APK_OUTPUT, version, build_number, base_url)

    # Step 4 — Cloud upload (if --cloud-url provided)
    if args.cloud_url:
        upload_result = upload_apk_to_cloud(APK_OUTPUT, args.cloud_url, args.token)
        if upload_result.get("ok"):
            cloud_download_url = upload_result.get("download_url", "")
            if cloud_download_url:
                manifest["download_url"] = cloud_download_url
                # Re-write manifest with updated cloud download URL
                with open(APK_MANIFEST, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)
                print(f"[build_and_deliver] Cloud download URL: {cloud_download_url}")
        else:
            print(f"[build_and_deliver] Cloud upload failed: {upload_result.get('error')}")

    # Step 5 — Notify Matt
    if args.notify or args.cloud_url:
        if args.cloud_url:
            notify_matt_via_bridge(manifest, args.cloud_url, args.token)
        else:
            write_local_notification(manifest)

    print("\n✅ Build & delivery complete")
    print(f"   Version: {version}+{build_number}")
    print(f"   Hash: {manifest['hash'][:30]}...")
    print(f"   Size: {manifest['size_bytes'] // 1024} KB")
    print(f"   Download: {manifest['download_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
