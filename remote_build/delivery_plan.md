# Gerald Remote APK Build Delivery Plan

## Goal
Matt receives a fresh debug APK on his phone automatically after Gerald edits code,
without needing a laptop tethered to his Android device.

## Problem Statement
Current workflow requires:
1. Gerald edits code on local PC
2. Matt manually runs `flutter build apk --debug`
3. Matt manually copies APK to phone via USB or ADB

Target workflow:
1. Gerald edits code on local PC
2. Gerald auto-triggers `flutter build apk --debug` (via Autonomous Build Verification)
3. APK is uploaded to a delivery endpoint
4. Gerald app on Matt's phone polls for new APK → downloads + prompts to install

## Architecture

```
[Gerald Bridge PC]
  ├─ build_and_deliver.py
  │   ├─ flutter build apk --debug
  │   ├─ compute APK hash
  │   ├─ upload APK to /apk-latest endpoint (or cloud storage)
  │   └─ write apk_manifest.json
  │
  └─ /apk-status endpoint  ←── Gerald Flutter App polls every 5 min
       └─ Returns: {version, hash, timestamp, download_url}

[Gerald Flutter App]
  └─ ApkDeliveryService
      ├─ Poll /apk-status every 5 minutes
      ├─ Compare hash with last-installed hash
      ├─ If new: download APK to app cache dir
      └─ Show "New build available — tap to install" notification
```

## Delivery Methods

### Method A — Local Serve (LAN only)
- Bridge serves APK at `GET /apk-latest/download`
- Flutter app downloads over LAN
- Simplest; works at home

### Method B — Cloud Object Storage
- Build script uploads to S3 / R2 / GCS
- Flutter app downloads via signed URL
- Works anywhere (commute, travel)
- Recommended for V1.5+

### Method C — Firebase App Distribution
- `firebase appdistribution:distribute` CLI after each build
- Firebase handles delivery + OTA install
- Most polished UX; no custom download code needed

## Implementation Steps

### Step 1 — APK Manifest Endpoint (Backend)
```
GET /apk-status
→ {
    "available": true,
    "version": "1.4.0",
    "build_number": 42,
    "hash": "sha256:abc123...",
    "size_bytes": 18450000,
    "timestamp": "2026-06-16T10:00:00Z",
    "download_url": "http://LAN_IP:8000/apk-latest/download"
  }
```

### Step 2 — APK Download Endpoint (Backend)
```
GET /apk-latest/download
→ Binary APK file (application/vnd.android.package-archive)
```

### Step 3 — Flutter ApkDeliveryService
- Poll `/apk-status` every 5 minutes
- Store last-seen hash in `shared_preferences`
- On new hash: show `flutter_local_notifications` alert
- On tap: open download URL in browser (Android will prompt install)

### Step 4 — Enable Unknown Sources
- Android Settings → Install unknown apps → allow browser/Gerald
- One-time setup on Matt's phone

## Files
- `build_and_deliver.py` — build script (this directory)
- `gerald_bridge.py` — add `/apk-status` + `/apk-latest/download` endpoints
- `lib/services/apk_delivery_service.dart` — Flutter polling service (V1.5)

## Timeline
| Phase | Target |
|-------|--------|
| APK manifest endpoint | V1.4 (backend stub) |
| Flutter polling + notification | V1.5 |
| Cloud storage delivery | V1.5 |
| Firebase App Distribution | V2.0 |
