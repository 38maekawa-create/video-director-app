# Swift通信アーキテクチャ修正レポート

> **実施日**: 2026-03-18
> **対象**: VideoDirectorAgent iOS アプリ
> **ビルド結果**: **BUILD SUCCEEDED**（error 0）

## 修正サマリー

| # | 項目 | 重要度 | 状態 |
|---|------|--------|------|
| 1 | probe競合防止（ConnectionOrchestrator actor化） | Critical | ✅ |
| 2 | ScenePhase監視追加（BG→FG復帰時再接続） | Critical | ✅ |
| 3 | ATS修正（NSAllowsArbitraryLoads撤廃） | Critical | ✅ |
| 4 | 並列probe（TaskGroup化、優先順位付き） | Moderate | ✅ |
| 5 | 手修正API 8メソッドのperformRequest統合 | Moderate | ✅ |
| 6 | VimeoReviewViewModel APIClient経由化 | Moderate | ✅ |
| 7 | probeエンドポイントを/healthzに変更 | Moderate | ✅ |
| 8 | connectionStatus UI表示（赤バナー+リトライ） | Moderate | ✅ |

## 変更ファイル一覧

### 1. `VideoDirectorAgent/Services/APIClient.swift`（大幅改修）

#### ConnectionOrchestrator actor 新設
- `actor ConnectionOrchestrator` を新規追加（ファイル先頭）
- `Route` enum: `.local(URL)` / `.tailscale(URL)` / `.cloud(URL)` の3経路
- `State` enum: `.idle` / `.probing` / `.connected(Route)` / `.disconnected`
- `reprobe(trigger:)`: 既存probeTaskをcancel→新しいprobeを開始（多重probe抑止）
- `raceRoutes()`: Phase1（local+tailscale並列、3秒タイムアウト）→ Phase2（cloud、5秒タイムアウト）

#### probeAndConnect() 改修
- 旧: 逐次ループで `isReachable()` を順次チェック
- 新: `orchestrator.reprobe()` に委譲。actor排他制御で競合防止

#### isReachable() 廃止 → orchestrator.probe() に統合
- 旧: `/api/projects` へ3秒GET
- 新: `/healthz` へ短タイムアウトGET（orchestrator内部）

#### performRequestRaw() 新設
- `[String: Any]` / `[[String: Any]]` を返す手修正API 8メソッド用
- URLSession.shared.data + フォールバック + リトライ機構を搭載
- `JSONEncoder` でbodyエンコード → `JSONSerialization` でレスポンスパース

#### 手修正API 8メソッドの統合（extension内）
以下の8メソッドが `performRequestRaw()` 経由に変更:
1. `updateDirectionReport()`
2. `fetchDirectionEditHistory()`
3. `fetchDirectionEditDiff()`
4. `updateTitle()`
5. `updateDescription(projectId:editedContent:editedBy:)`
6. `updateThumbnailInstruction()`
7. `fetchAssetEditHistory()`
8. `fetchAssetEditDiff()`

#### fetchVimeoComments() 新設
- VimeoReviewViewModel用のAPIメソッドを追加
- `performRequest<T>` 経由（Codable対応）

### 2. `VideoDirectorAgent/VideoDirectorAgentApp.swift`

- `@Environment(\.scenePhase) private var scenePhase` 追加
- `.onChange(of: scenePhase)` で `.active` 復帰時に `probeAndConnect()` を呼び出し

### 3. `VideoDirectorAgent/Info.plist`（ATS修正）

- `NSAllowsArbitraryLoads = true` を **撤廃**
- `NSExceptionDomains` で以下の4ドメインのみ許可:
  - `localhost` — insecure HTTP許可
  - `mac-mini-m4.local` — insecure HTTP許可
  - `100.110.206.6` — insecure HTTP許可（Tailscale）
  - `video-api.legit-marc.com` — TLS 1.2以上のみ許可

### 4. `VideoDirectorAgent/Views/RootTabView.swift`

- `@ObservedObject private var apiClient = APIClient.shared` 追加
- `connectionStatusBanner` ビルダー追加:
  - `.disconnected`: 赤バナー + 「サーバーに接続できません」+ 再接続ボタン
  - `.connecting`: オレンジバナー + ProgressView + 「接続中...」
  - `.connected`: 非表示

### 5. `VideoDirectorAgent/ViewModels/VimeoReviewViewModel.swift`

- `private var baseURL` プロパティ削除
- `fetchVimeoComments()` を `APIClient.shared.fetchVimeoComments()` に委譲
  - URLSession.shared.data の直接使用を排除
  - フォールバック・リトライ機構が自動適用

## 完了条件チェック

- [x] Xcodeビルド成功（error 0） — **BUILD SUCCEEDED**
- [x] probe競合が発生しないこと — actor排他制御 + probeTask.cancel()で抑止
- [x] BG→FG復帰時に再接続が走ること — ScenePhase .active で probeAndConnect()
- [x] ATS例外が必要ドメインのみに限定されていること — NSAllowsArbitraryLoads撤廃、4ドメインのみ
- [x] 全APIメソッドが performRequest 経由であること — grep確認済み（extension 8メソッドはperformRequestRaw経由）
- [x] VimeoReviewViewModelが直接URLSessionを使っていないこと — APIClient.shared.fetchVimeoComments()に委譲
- [x] 接続状態がUIに表示されること — RootTabView に connectionStatusBanner 追加

## grep検証結果

```
URLSession.shared.data の使用箇所（全てAPIClient.swift内の共通メソッド内）:
- ConnectionOrchestrator.probe() — ヘルスチェック
- performRequest<T>() — 通常GET
- performRequest<T, Body>() — 通常POST/PATCH/PUT
- performLongRequest<T, Body>() — 長時間API
- performRequestRaw() — 手修正API（JSONSerialization用）

VimeoReviewViewModel.swift: URLSession.shared.data の使用 → 0件 ✅
```

## Python側で必要な対応

- **`/healthz` エンドポイント追加**: APIClient.swiftのprobeが `/healthz` を使用するようになったため、Python側（api_server.py）に `/healthz` エンドポイントの追加が必要
  - 軽量な200レスポンスを返すだけでOK（例: `{"status": "ok"}`）
  - これはTASK_FIX_NETWORK_PYTHON.mdの範囲
