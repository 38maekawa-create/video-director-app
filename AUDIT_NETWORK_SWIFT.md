# Swift通信ロジック監査結果

> 監査実施日: 2026-03-18
> 監査対象: VideoDirectorAgent iOS アプリ
> 監査者: バティ（Opus 4.6）

---

## Critical（即修正必須）

### C-1. ScenePhase未監視 — バックグラウンド復帰時の再接続なし
- **[VideoDirectorAgentApp.swift:全体]**
- `@Environment(\.scenePhase)` を一切使用していない。アプリがバックグラウンドから復帰した際に `probeAndConnect()` が呼ばれない
- NWPathMonitorはネットワーク**インターフェースの変化**を検知するが、アプリのライフサイクル変化（バックグラウンド→フォアグラウンド）は検知しない。同じWiFiに接続したまま30分バックグラウンドにいた場合、URLSession.sharedの内部状態が古くなる可能性がある
- → **修正案**: `VideoDirectorAgentApp` に `@Environment(\.scenePhase) var scenePhase` を追加し、`.onChange(of: scenePhase)` で `.active` 復帰時に `probeAndConnect()` を呼ぶ

### C-2. VimeoReviewViewModel の直接URLSession — フォールバック・再接続ロジック完全バイパス
- **[VimeoReviewViewModel.swift:139-151]** `fetchVimeoComments()` メソッド
- `URLSession.shared.data(from: url)` を直接使用。`APIClient.shared` の `performRequest` を経由していないため:
  - フォールバック候補URL（ローカル→Tailscale→クラウド）の自動切り替えが効かない
  - ネットワークエラー時の `reconnectIfNeeded()` が呼ばれない
  - タイムアウトが `URLSession.shared` のデフォルト60秒（APIClient側は12秒）
- `baseURL` プロパティは `APIClient.shared.baseURL` を参照しているので接続先は正しいが、切り替え後のフォールバックが機能しない
- → **修正案**: `APIClient` に `fetchVimeoComments(projectId:)` メソッドを追加し、`performRequest` 経由に統一する

### C-3. APIClient extension の8メソッドが `performRequest` を使わず直接 `URLSession.shared` を呼んでいる
- **[APIClient.swift:708-870]** 以下のメソッドが全て直接 `URLSession.shared.data(for: request)` を使用:
  1. `updateDirectionReport()` — L729
  2. `fetchDirectionEditHistory()` — L746
  3. `fetchDirectionEditDiff()` — L763
  4. `updateTitle()` — L783
  5. `updateDescription(editedContent:editedBy:)` — L803
  6. `updateThumbnailInstruction()` — L823
  7. `fetchAssetEditHistory()` — L842
  8. `fetchAssetEditDiff()` — L861
- これらはネットワークエラー時の `reconnectIfNeeded()` が呼ばれず、URLフォールバックも効かない
- `[String: Any]` / `[[String: Any]]` を返すためジェネリック `performRequest<T: Decodable>` が使えないことが原因と推定
- → **修正案**: `JSONSerialization` ベースの `performRequest` オーバーロードを作成するか、Codableな型を定義して既存の `performRequest` に統一する

---

## Moderate（修正推奨）

### M-1. URLSession.shared のデフォルトキャッシュがAPI応答を汚染するリスク
- **[APIClient.swift:全体]**
- `URLSession.shared` は `URLSessionConfiguration.default` を使用。デフォルトでは `URLCache.shared`（メモリ4MB/ディスク20MB）がGETリクエストのレスポンスをキャッシュする
- サーバー側のCache-Controlヘッダー設定次第では、古いデータがキャッシュから返される可能性がある
- 特にダッシュボードサマリーやフィードバック一覧など、リアルタイム性が求められるGETリクエストで問題になりうる
- DNSキャッシュについて: URLSession内部のDNSキャッシュが古い接続先を保持する可能性があるが、`probeAndConnect()` は `/api/projects` への実リクエストで到達性テストしているため、DNSキャッシュの影響は限定的
- → **修正案**: `URLSessionConfiguration` をカスタマイズし、`requestCachePolicy = .reloadIgnoringLocalCacheData` を設定するか、各リクエストに `Cache-Control: no-cache` ヘッダーを付与する。あるいは `.ephemeral` セッションを使用する

### M-2. probeAndConnect() の逐次実行 — 最悪9秒のブロッキング
- **[APIClient.swift:109-126]**
- 3候補URLを**逐次**にprobeしている（各3秒タイムアウト）
- 最悪ケース: ローカル3秒失敗 → Tailscale3秒失敗 → クラウド3秒失敗 = 合計9秒
- この9秒間、アプリ起動時の `.task` 内で実行されるため、他のAPI呼び出しが `activeBaseURL` の確定を待たずに走る可能性がある
- → **修正案**: `TaskGroup` で並列probeし、最初に成功した候補を採用する。レイテンシの低い順（ローカル→Tailscale→クラウド）の優先順位は、応答時間で自動判定する

### M-3. connectionStatus がUI上のどこにも表示されていない
- **[Views/*全ファイル]**
- `APIClient.shared.connectionStatus` を参照しているViewが**1つもない**
- `.disconnected` 状態でもユーザーに通知されない。オフラインバナー、接続状態インジケーター、リトライボタンが一切ない
- → **修正案**: `RootTabView` またはヘッダーに接続ステータスバッジを追加。`.disconnected` 時に赤いバナーとリトライボタンを表示する

### M-4. APIClient extension メソッドで `JSONEncoder()` を毎回生成
- **[APIClient.swift:727, 781, 801, 821]**
- `updateDirectionReport()` 等で `JSONEncoder()` を毎回 `new` している。APIClient本体には `encoder`（`convertToSnakeCase`付き）が定義済みだが使われていない
- `convertToSnakeCase` が適用されないため、リクエストボディのキー名がcamelCaseのまま送信される（`DirectionEditBody` の `editedContent` が `edited_content` ではなく `editedContent` で送られる）
- ただし `DirectionEditBody` では `editedContent` 等のプロパティ名をそのまま使っているため、サーバー側がcamelCaseを受け入れている可能性がある
- → **修正案**: `self.encoder` を使用するか、サーバー側の期待するフォーマットに合わせる。一貫性がないとバグの温床になる

### M-5. isReachable() のprobeエンドポイントが `/api/projects` — 重すぎる
- **[APIClient.swift:129-143]**
- probe用に `/api/projects` を使用している。プロジェクト一覧を全件返すエンドポイントのため、不必要なデータ転送が発生する
- ヘルスチェック専用エンドポイント（`/health` や `/api/ping`）がサーバーに存在すればそちらを使うべき
- → **修正案**: サーバーに `/health` エンドポイントを追加し、probeではそちらを使用する

### M-6. エラー握りつぶし箇所の全件リスト
以下の箇所でエラーをcatchしているが、ユーザーに通知せず無視している:

| # | ファイル | 行 | 内容 | 深刻度 |
|---|---------|-----|------|--------|
| 1 | DirectionEditView.swift | 462-464 | `loadCurrentReport()` のcatch: コメントなし（「初回は空で開始」） | 中 |
| 2 | DirectionEditView.swift | 555-557 | `loadEditHistory()` のcatch: `editHistory = []` 代入のみ | 低 |
| 3 | TitleDescriptionEditView.swift | 340-341 | タイトルdiff取得: コメントなし（「初回は空で開始」） | 中 |
| 4 | TitleDescriptionEditView.swift | 349-351 | 概要欄diff取得: コメントなし（「初回は空で開始」） | 中 |
| 5 | ThumbnailEditView.swift | 577-579 | サムネdiff取得: コメントなし（「初回は空で開始」） | 中 |
| 6 | YouTubeAssetsView.swift | 524-526 | `pollForUpdates()` のcatch: コメントのみ（「ポーリング失敗は静かに無視」） | 低 |
| 7 | BeforeAfterView.swift | 694-696 | `reloadTranscriptDiff()` のcatch: コメントのみ（「エラー時は前のデータを維持」） | 低 |
| 8 | KnowledgePagesViewModel.swift | 56-58 | `search()` のcatch: `print()` のみ | 中 |
| 9 | KnowledgePagesViewModel.swift | 70-72 | `loadPageDetail()` のcatch: `print()` のみ | 中 |
| 10 | VideoTrackingViewModel.swift | 36-37 | `fetchLearningSummary()` のcatch: 完全無視 | 低 |
| 11 | BeforeAfterView.swift | 530-532 | FBトラッカー取得: `try?` で無視 | 低 |
| 12 | BeforeAfterView.swift | 634-643 | `updateFBTrackingStatus` + `fetchFBTracker`: `try?` で無視 | 中 |

- #1,3,4,5 は「初回は空で開始」として握りつぶしているが、ネットワーク切断時もユーザーに何も通知しない。データがロードされない理由が分からない
- → **修正案**: 初回ロード失敗時は「サーバーに接続できません」のインラインエラーを表示する。ポーリング失敗やキャッシュ未存在は無視して良い

---

## Minor（改善推奨）

### m-1. Pull-to-refresh で再接続トリガーされない
- **[ProjectListView.swift:99, ReportListView.swift:45, QualityDashboardView.swift:56, FeedbackHistoryView.swift:127]**
- `.refreshable` は各ViewModelの `load()` / `refresh()` を呼ぶが、`probeAndConnect()` を呼ばない
- `.disconnected` 状態でpull-to-refreshしても、同じ（到達不可能な）URLに対してリクエストが飛ぶだけで、フォールバックが効かない
- ただし `performRequest` 内の `reconnectIfNeeded` がURLErrorをキャッチして `probeAndConnect()` を呼ぶため、**結果的に再接続は試行される**。この点は部分的に機能している
- → **修正案**: pull-to-refresh時に明示的に `probeAndConnect()` → API呼び出しの順で実行すると、ユーザーの意図した再接続がより確実になる

### m-2. ATS設定で `NSAllowsArbitraryLoads = true` が不要に広い
- **[Info.plist:33]**
- `NSAllowsArbitraryLoads = true` は**全ドメイン**へのHTTP接続を許可する設定
- 実際にHTTP（非HTTPS）で接続するのは `mac-mini-m4.local`、`100.110.206.6`、`localhost` の3つのみ
- `NSExceptionDomains` で個別に設定済みなので、`NSAllowsArbitraryLoads` は不要
- App Store審査でリジェクトされるリスクは低い（Bonjourや開発用途として認められるケースが多い）が、セキュリティポリシーとしては不必要に広い
- → **修正案**: `NSAllowsArbitraryLoads` を `false` に変更（または削除）。`NSExceptionDomains` の3ドメインで十分

### m-3. performRequest のリトライが再帰1回に限定されない保証がない
- **[APIClient.swift:534-542, 572-578, 606-612]**
- URLError発生 → `reconnectIfNeeded()` → `probeAndConnect()` → `activeBaseURL` 変更 → 再帰呼び出し
- 再帰呼び出し先で再びURLErrorが発生した場合、`activeBaseURL` は変わらないため無限ループにはならないが、設計意図として明示的なリトライ回数制限がない
- → **修正案**: リトライカウンターを引数に追加するか、コメントで「1回限り」の設計意図を明記する

### m-4. 12秒タイムアウトの妥当性
- **[APIClient.swift:518, 554]**
- 通常APIリクエストのタイムアウトが12秒。モバイル回線（4G/LTE）では妥当だが、3Gやキャリアの混雑時にはタイムアウトしやすい
- E2Eパイプライン用の120秒は適切
- → **修正案**: 現状維持で問題ないが、ユーザーフィードバックを見て調整可能にする設計にしておくと良い

### m-5. buildURL の最終フォールバックで `URL.appending(path:)` がクエリ文字列を壊す
- **[APIClient.swift:630]**
- 最終フォールバック `base.appending(path: path)` は `?` を `%3F` にエンコードする。これはメソッド冒頭のコメントで「エンコードしてしまうため」と書かれている問題そのもの
- 実際にはこのフォールバックに到達するケースはほぼないが、到達した場合はクエリパラメータ付きのURLが壊れる
- → **修正案**: `fatalError` またはログ警告で明示的に失敗を報告する

---

## 統計

| 項目 | 数値 |
|------|------|
| 検査ファイル数 | 24ファイル（APIClient 1、ViewModel 11、View 12） |
| Critical | 3件 |
| Moderate | 6件 |
| Minor | 5件 |
| エラー握りつぶし箇所 | 12件 |
| 直接URLSession使用箇所（APIClient performRequest外） | 9箇所（extension 8 + VimeoReviewVM 1） |
| connectionStatus UI表示箇所 | 0箇所 |
| ScenePhase 使用箇所 | 0箇所 |
| Pull-to-refresh 設置箇所 | 4箇所（全てprobeAndConnect未連動） |

---

## 監査項目別サマリー

### 1. probeAndConnect() の呼び出しタイミング
- **アプリ起動時**: `VideoDirectorAgentApp.swift` の `.task` で呼ばれている **[OK]**
- **ScenePhase .active復帰時**: **呼ばれていない [Critical: C-1]**
- **NWPathMonitor**: `startNetworkMonitor()` で呼ばれている **[OK]**

### 2. URLSessionキャッシュ問題
- `URLSession.shared` のデフォルトキャッシュ（メモリ4MB/ディスク20MB）が有効 **[Moderate: M-1]**
- `.ephemeral` セッションは使われていない
- DNSキャッシュの影響は限定的（probeが実リクエストを使用するため）

### 3. タイムアウト設計
- probe: 3秒 × 3候補 = 最大9秒（逐次） **[Moderate: M-2]**
- 通常API: 12秒 **[Minor: m-4]** — 妥当
- E2Eパイプライン: 120秒 — 適切

### 4. エラーハンドリング
- エラー握りつぶし: 12件 **[Moderate: M-6]**
- エラー通知UIは一部あり（ProjectListView, DashboardView, FeedbackHistoryView等）
- connectionStatus `.disconnected` はUIに反映されていない **[Moderate: M-3]**

### 5. 接続状態のUI反映
- connectionStatusを表示しているView: **0件** **[Moderate: M-3]**
- オフラインバナー: **なし**
- リトライボタン: **なし**
- Pull-to-refresh: 4箇所あるが再接続は間接的のみ

### 6. VimeoReviewViewModel の直接URLSession
- `fetchVimeoComments()` が1箇所 **[Critical: C-2]**
- APIClient extension が8箇所 **[Critical: C-3]**

### 7. ScenePhase / AppLifecycle
- `@Environment(\.scenePhase)` の使用箇所: **0件** **[Critical: C-1]**

### 8. ATS設定
- `NSAllowsArbitraryLoads = true` が不要に広い **[Minor: m-2]**
- `NSAllowsLocalNetworking = true` は適切
- `NSExceptionDomains` の3ドメイン設定は適切
