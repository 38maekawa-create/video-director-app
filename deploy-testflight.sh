#!/usr/bin/env bash
# ==============================================================================
# deploy-testflight.sh
# 映像ディレクターアプリ TestFlight 配布スクリプト
#
# 使い方:
#   ./deploy-testflight.sh
#
# 前提条件:
#   - Xcode がインストールされていること
#   - Xcode > Settings > Accounts に Apple ID (7010mae@gmail.com) が登録済みであること
#   - App Store Connect で "映像ディレクター" アプリが作成済みであること
#     (Bundle ID: com.maekawa.VideoDirectorAgent)
#   - Apple ID のパスワード (App-Specific Password) を ~/.config/maekawa/asc-password に保存済みであること
#     ※ App-Specific Password は https://appleid.apple.com で発行
# ==============================================================================

set -euo pipefail

# ── 設定 ──────────────────────────────────────────────────────────────────────
WORKSPACE_ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$WORKSPACE_ROOT/VideoDirectorAgent"
XCODE_PROJECT="$PROJECT_DIR/VideoDirectorAgent.xcodeproj"
SCHEME="VideoDirectorAgent"
CONFIGURATION="Release"
EXPORT_OPTIONS_PLIST="$PROJECT_DIR/ExportOptions.plist"
ARCHIVE_DIR="$WORKSPACE_ROOT/build/VideoDirectorAgent.xcarchive"
EXPORT_DIR="$WORKSPACE_ROOT/build/export"

APPLE_ID="7010mae@gmail.com"
TEAM_ID="TT2DA7H5NJ"
# App-Specific Password ファイルパス（なければ環境変数 ASC_PASSWORD を使用）
ASC_PASSWORD_FILE="$HOME/.config/maekawa/asc-password"

# ── カラー出力 ────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── 前提条件チェック ──────────────────────────────────────────────────────────
info "前提条件を確認しています..."

# Xcode チェック
if ! command -v xcodebuild &>/dev/null; then
    error "xcodebuild が見つかりません。Xcode をインストールしてください。"
fi
XCODE_VERSION=$(xcodebuild -version | head -1)
success "Xcode: $XCODE_VERSION"

# xcodeプロジェクト存在確認
if [[ ! -d "$XCODE_PROJECT" ]]; then
    error "Xcodeプロジェクトが見つかりません: $XCODE_PROJECT"
fi
success "プロジェクト: $XCODE_PROJECT"

# ExportOptions.plist 確認
if [[ ! -f "$EXPORT_OPTIONS_PLIST" ]]; then
    error "ExportOptions.plist が見つかりません: $EXPORT_OPTIONS_PLIST"
fi
success "ExportOptions.plist: 確認済み"

# App-Specific Password 取得
if [[ -f "$ASC_PASSWORD_FILE" ]]; then
    ASC_PASSWORD=$(cat "$ASC_PASSWORD_FILE" | tr -d '[:space:]')
    success "App-Specific Password: ファイルから読み込み ($ASC_PASSWORD_FILE)"
elif [[ -n "${ASC_PASSWORD:-}" ]]; then
    success "App-Specific Password: 環境変数から読み込み"
else
    warn "App-Specific Password が見つかりません。"
    warn "  1. https://appleid.apple.com でApp-Specific Passwordを発行"
    warn "  2. echo 'xxxx-xxxx-xxxx-xxxx' > ~/.config/maekawa/asc-password"
    warn "  または: export ASC_PASSWORD='xxxx-xxxx-xxxx-xxxx'"
    echo ""
    read -rp "App-Specific Password を入力してください（または Ctrl+C でキャンセル）: " ASC_PASSWORD
fi

# ── ビルドバージョンのインクリメント ──────────────────────────────────────────
info "ビルドバージョンを更新しています..."
CURRENT_BUILD=$(xcodebuild -project "$XCODE_PROJECT" \
    -target "$SCHEME" \
    -showBuildSettings \
    2>/dev/null | grep CURRENT_PROJECT_VERSION | awk '{print $3}')

NEW_BUILD=$((CURRENT_BUILD + 1))
info "  ビルド番号: $CURRENT_BUILD → $NEW_BUILD"

# CURRENT_PROJECT_VERSION を pbxproj で更新
sed -i '' "s/CURRENT_PROJECT_VERSION = ${CURRENT_BUILD};/CURRENT_PROJECT_VERSION = ${NEW_BUILD};/g" \
    "$XCODE_PROJECT/project.pbxproj"
success "ビルド番号を $NEW_BUILD に更新しました"

# ── Archive ────────────────────────────────────────────────────────────────────
info "Archive を実行しています..."
mkdir -p "$WORKSPACE_ROOT/build"

xcodebuild archive \
    -project "$XCODE_PROJECT" \
    -scheme "$SCHEME" \
    -configuration "$CONFIGURATION" \
    -archivePath "$ARCHIVE_DIR" \
    -destination "generic/platform=iOS" \
    CODE_SIGN_STYLE=Automatic \
    DEVELOPMENT_TEAM="$TEAM_ID" \
    | tee "$WORKSPACE_ROOT/build/archive.log" \
    | grep -E "(error:|warning:|Archive Succeeded|BUILD)"

if [[ ! -d "$ARCHIVE_DIR" ]]; then
    error "Archive 失敗。ログを確認してください: $WORKSPACE_ROOT/build/archive.log"
fi
success "Archive 成功: $ARCHIVE_DIR"

# ── Export (.ipa) ──────────────────────────────────────────────────────────────
info ".ipa をエクスポートしています..."
rm -rf "$EXPORT_DIR"

xcodebuild -exportArchive \
    -archivePath "$ARCHIVE_DIR" \
    -exportOptionsPlist "$EXPORT_OPTIONS_PLIST" \
    -exportPath "$EXPORT_DIR" \
    | tee "$WORKSPACE_ROOT/build/export.log" \
    | grep -E "(error:|warning:|Export Succeeded|INFO)"

IPA_PATH=$(find "$EXPORT_DIR" -name "*.ipa" | head -1)
if [[ -z "$IPA_PATH" ]]; then
    error "IPA が見つかりません。ログを確認してください: $WORKSPACE_ROOT/build/export.log"
fi
success "エクスポート成功: $IPA_PATH"

# ── App Store Connect へアップロード ───────────────────────────────────────────
info "App Store Connect へアップロードしています..."
info "  Apple ID: $APPLE_ID"
info "  Team ID:  $TEAM_ID"

xcrun altool \
    --upload-app \
    --type ios \
    --file "$IPA_PATH" \
    --username "$APPLE_ID" \
    --password "$ASC_PASSWORD" \
    --output-format xml \
    2>&1 | tee "$WORKSPACE_ROOT/build/upload.log"

if grep -q "No errors uploading" "$WORKSPACE_ROOT/build/upload.log" || \
   grep -q "success" "$WORKSPACE_ROOT/build/upload.log"; then
    success "アップロード成功！"
else
    # altool の代わりに xcrun notarytool / xcrun altool の終了コードで判定
    UPLOAD_EXIT=${PIPESTATUS[0]}
    if [[ $UPLOAD_EXIT -eq 0 ]]; then
        success "アップロード成功！"
    else
        warn "アップロードの結果を確認してください: $WORKSPACE_ROOT/build/upload.log"
    fi
fi

# ── 完了メッセージ ─────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  映像ディレクターアプリ — TestFlight 配布完了${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  アプリ名 : 映像ディレクター"
echo "  Bundle ID: com.maekawa.VideoDirectorAgent"
echo "  バージョン: 1.0.0 (build $NEW_BUILD)"
echo "  Team ID  : $TEAM_ID"
echo ""
echo "  次のステップ:"
echo "  1. https://appstoreconnect.apple.com を開く"
echo "  2. マイ App → 映像ディレクター → TestFlight"
echo "  3. ビルドが処理完了後（5〜15分）、テスターを追加"
echo "  4. テスターにTestFlightの招待メールが送信される"
echo ""
echo "  ログファイル:"
echo "    Archive : $WORKSPACE_ROOT/build/archive.log"
echo "    Export  : $WORKSPACE_ROOT/build/export.log"
echo "    Upload  : $WORKSPACE_ROOT/build/upload.log"
echo ""
