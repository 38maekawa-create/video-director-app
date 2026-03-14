#!/bin/bash
# VideoDirectorAgent TestFlight配布スクリプト

set -euo pipefail

PROJECT_DIR="$HOME/AI開発10/VideoDirectorAgent"
SCHEME="VideoDirectorAgent"
ARCHIVE_PATH="$PROJECT_DIR/build/VideoDirectorAgent.xcarchive"
EXPORT_PATH="$PROJECT_DIR/build/export"
EXPORT_OPTIONS="$PROJECT_DIR/ExportOptions.plist"

echo "=== VideoDirectorAgent TestFlight配布 ==="
echo "1. クリーンビルド..."
xcodebuild clean -project "$PROJECT_DIR/VideoDirectorAgent.xcodeproj" -scheme "$SCHEME" -quiet

echo "2. Archive..."
xcodebuild archive \
  -project "$PROJECT_DIR/VideoDirectorAgent.xcodeproj" \
  -scheme "$SCHEME" \
  -archivePath "$ARCHIVE_PATH" \
  -destination 'generic/platform=iOS' \
  CODE_SIGN_IDENTITY="Apple Distribution" \
  -quiet

echo "3. IPA Export..."
xcodebuild -exportArchive \
  -archivePath "$ARCHIVE_PATH" \
  -exportPath "$EXPORT_PATH" \
  -exportOptionsPlist "$EXPORT_OPTIONS" \
  -quiet

echo "4. App Store Connect にアップロード..."
xcrun altool --upload-app \
  -f "$EXPORT_PATH/VideoDirectorAgent.ipa" \
  -t ios \
  --apiKey "${APP_STORE_API_KEY:-}" \
  --apiIssuer "${APP_STORE_API_ISSUER:-}"

echo "=== 完了! TestFlightで確認してください ==="
