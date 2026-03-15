# PROGRESS.md — 映像品質追求・自動ディレクションシステム（AI開発10）

## 最終更新日時
2026-03-15 20:25（TestFlight Build 8アップロード完了）
<!-- authored: T1/副官A/バティ/2026-03-15 [なおとさんとの対話セッション中] -->

## 現在の作業状態
**実用化進行中（TestFlight実機テスト Phase）**

iPhoneからAPIサーバー（100.110.206.6:8210）に接続して実データ29件を表示・操作できる状態。
Build 5→8を連続デプロイし、各ビルドでバグ検出→修正→再ビルドのイテレーションを回している。

---

## TestFlight Build 履歴

| Build | 内容 | 状態 |
|-------|------|------|
| 5 | 初回TestFlight配信成功 | ✅ |
| 6 | isSent Bool/Intデコード修正 → 品質タブ復活 | ✅ |
| 7 | ナビゲーション修正・レポートタブ分離・ATS修正 | ✅ |
| 8 | ホームタップ修正（Button化）・履歴タブURL修正・空状態UI | ✅ アップロード完了 |

## Build 8で修正した内容（2026-03-15 20:25）

### 1. ホーム画面のプロジェクトカードがタップに反応しない問題
- **原因**: 横ScrollView内の`onTapGesture`がスクロールジェスチャと競合
- **修正**: `onTapGesture` → `Button` + `.buttonStyle(.plain)` に変更
- **ファイル**: `Views/ProjectListView.swift`

### 2. 履歴タブ「APIに接続できません」エラー
- **原因**: `URL.appending(path:)` がクエリパラメータ `?limit=50` の `?` を `%3F` にエンコード
- **修正**: `buildURL(base:path:)` ヘルパー追加。文字列結合でURL構築
- **ファイル**: `Services/APIClient.swift`
- **補足**: feedbacksテーブルは現在0件。空の場合は空状態UIを表示

### 3. 履歴タブの空状態UI追加
- フィードバック0件時に「フィードバック履歴がありません」を表示
- **ファイル**: `Views/FeedbackHistoryView.swift`

---

## DB修正完了（2026-03-15）

### メンバー名・タイトル全件修正
スプシ（動画コンテンツ分析DB「TEKO対談動画」タブ）の正式名を正として、DB全29件を照合・修正完了。

**修正内容:**
- 重複削除: 60件 → 29件
- guest_name統一: MEMBER_MASTER.jsonのcanonical_name + さん付き
- タイトル内の文字起こし誤変換修正:
  - コスト氏 → kos、コテツ → コテ、メイジ → メンイチ、羽生氏 → ハオ
  - ゲスト氏（里芋、トーマス） → さといも・トーマス
  - pay → PAY、ryo → RYO（大文字統一）

**タイトル一括置換で発生した副作用バグ（修正済み）:**
- 「さといも・さといも・さといも・トーマスさん」（連鎖置換） → 正しく修正
- 「RYOすけさん」（部分マッチ「りょう」→「RYO」） → 正しく修正
- タイトル内「さん」消失（置換マップに「〇〇さん」→「〇〇」が含まれていた） → バックアップから復元

**教訓（DB一括置換）:**
- 短い文字列の部分マッチ置換は危険。長い文字列優先で置換するか、単語境界を意識する
- 連鎖置換（AをBに置換した結果、Bの一部がさらに置換される）を防ぐため、1レコードずつ個別UPDATEが安全
- 置換前に必ずバックアップ。`cp db db.bak_YYYYMMDD_HHMMSS`

---

## 18モデル3台体制の生産性評価（2026-03-15 なおとさん壁打ち）

### ✅ 良かった点
- Mac2（Web UI）とMac3（iOS）に同時タスク投入 → Mac2のWeb変更（+624行）は品質OK。2つの成果物が並列で出てきた
- CLIビルド→TestFlightアップロードの完全自動化 → 人間の操作ゼロでBuild 5→6→7→8を連続デプロイ
- バグ検出→修正→再ビルドのサイクルが速い — ATS問題発見→修正→ビルド→アップロードが数分

### ❌ 課題（Mac3の暴走）
- Mac3の兵隊が「既存コード削除禁止」ルールを無視して3,954行削除 → リバートが必要になった
- 原因: タスク投入時にCLAUDE.mdのルールが既にセッション開始済みの兵隊に届いてなかった
- 教訓: **ルールはCLAUDE.mdだけでなくタスク指示書に直接埋め込む必要がある**

### 📊 実感値
- 「1セッションで全部やる」よりは確実に速い
- 品質管理（監査フェーズ）がまだ回ってないから、暴走検知が遅れた
- 監査2名が機能し始めればスピード×品質の両立ができるはず

---

## 技術的な学び（オペレーション組み込み用）

### iOS開発のハマりポイント（TestFlight配信時に判明）

| # | 問題 | 原因 | 修正 | 今後のチェックリスト |
|---|------|------|------|-------------------|
| 1 | iPhoneからAPI接続不可 | ATS（App Transport Security）がHTTP通信をブロック | Info.plistに`NSAllowsArbitraryLoads=true` + IP例外追加 | 新しいIPアドレスへの接続時は必ずATS例外を確認 |
| 2 | 品質・履歴タブエラー | `is_sent: 0`(Int)をBoolでデコード失敗 | Bool/Int両対応のフレキシブルデコーダー | APIレスポンスの型をSwift側で柔軟に受ける |
| 3 | カルーセルタップ反応なし | 横ScrollView内のonTapGestureがスクロールと競合 | Button + .buttonStyle(.plain) に変更 | 横スクロール内のタップは常にButtonを使う |
| 4 | クエリパラメータ付きAPIエラー | `URL.appending(path:)`が`?`を`%3F`にエンコード | 文字列結合でURL構築するヘルパー追加 | SwiftのURL APIはクエリパラメータに注意 |
| 5 | レポートタブがホームと同じ | RootTabViewの.reportケースがProjectListViewを表示 | 専用ReportListView作成 | 新タブ追加時は必ずビューの割り当てを確認 |

### xcodebuild CLI ビルド手順（自動化済み）
```bash
# 1. バージョンバンプ
sed -i '' 's/CURRENT_PROJECT_VERSION = N;/CURRENT_PROJECT_VERSION = N+1;/g' *.xcodeproj/project.pbxproj

# 2. Archive
xcodebuild -project *.xcodeproj -scheme VideoDirectorAgent -sdk iphoneos \
  -configuration Release -archivePath ./build/*.xcarchive archive \
  DEVELOPMENT_TEAM=TT2DA7H5NJ CODE_SIGN_IDENTITY="Apple Development" \
  -allowProvisioningUpdates

# 3. Export & Upload
xcodebuild -exportArchive -archivePath ./build/*.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath ./build/export \
  -allowProvisioningUpdates
```

### MEMBER_MASTER.json 運用ルール
- `canonical_name`: 正式名（DB・UIで使用する名前）
- `transcription_errors`: 文字起こし誤変換リスト（メイジ→メンイチ等）
- `aliases`: 別名・旧名
- `merged_from`: 統合元（重複削除時に記録）
- **DB修正時は必ずMEMBER_MASTER.jsonのcanonical_nameを正とする**
- **タイトル一括置換は個別UPDATE文で行う（REPLACE関数の連鎖置換を防ぐ）**

---

## 次にやるべき作業（優先順位付き）

### [P1] Build 8 動作確認
- ホームのカルーセルタップ → 詳細画面に遷移するか
- 履歴タブ → 「フィードバック履歴がありません」が表示されるか（エラーではなく）
- レポートタブ → 引き続き縦リスト表示

### [P2] YouTube素材3機能UI完成（iOS版）
- タイトル案表示・コピー
- サムネ指示書表示
- 概要欄テキスト表示・コピー

### [P3] before/after差分UI
- 修正前後のディレクション比較画面

### [P4] 映像トラッキング+学習ループ
- FB学習ループの運用データ投入
- 評価ルール精度改善

---

## 既知の問題・課題

| # | 問題 | 状態 |
|---|------|------|
| 1 | YouTubeAssetsViewModel.swiftのbaseURLがlocalhost:8210ハードコード | 未修正（APIClient.sharedを使うべき） |
| 2 | feedbacksテーブルが空（0件） | 正常。録音機能からFB投入後にデータが蓄積される |
| 3 | xcodebuild署名: `CODE_SIGN_STYLE=Automatic`ではなく手動指定が必要 | TT2DA7H5NJ + "Apple Development" で解決済み |
| 4 | 層cの該当者0件: 現データセット29件に自営業家系なし | 追加データで検証必要 |

---

## 完了済み作業アーカイブ

### webapp YouTube素材UI追加（2026-03-15）
- YouTube素材タブ追加（サムネ指示書・タイトル案・概要欄）
- テスト524件全PASS

### TestFlight初回配信〜Build 8（2026-03-15）
- Build 5: 初回配信成功
- Build 6: isSentデコード修正
- Build 7: ATS修正・ナビゲーション修正・レポートタブ分離
- Build 8: ホームタップ修正・履歴URL修正・空状態UI

### DB クリーンアップ（2026-03-15）
- 重複削除60→29件、メンバー名統一、タイトル誤字修正

### Phase 5 実用化チューニング（2026-03-14）
- FBエラーハンドリング強化
- Mac側 relay adapter 実投稿運用化
- 音声FB/STT外部保存拡張
- API/Swift安定化

### Phase 3-4 全機能実装（2026-03-13）
- Python側10新規ファイル、14APIエンドポイント追加
- Swift側新画面5つ追加
- xcodebuild BUILD SUCCEEDED

### Phase 1-2 コアエンジン実装（2026-03-09〜10）
- 28機能実装、250+テスト全PASS
- E2Eテスト・GitHub Pages公開
