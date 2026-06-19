#!/bin/bash
set -e

APP_DIR="/opt/Gerald/gerald_app"
APK_SRC="$APP_DIR/build/app/outputs/flutter-apk/app-debug.apk"
APK_DEST="/opt/Gerald/apk_serve/gerald-latest.apk"

echo "=== Gerald APK Build ==="
cd "$APP_DIR"

flutter clean
flutter pub get
flutter build apk --debug

mkdir -p /opt/Gerald/apk_serve
cp "$APK_SRC" "$APK_DEST"

echo "✅ APK built and published:"
ls -lh "$APK_DEST"
echo "Download:"
echo "https://geraldai.com.au/apk-latest/download"
