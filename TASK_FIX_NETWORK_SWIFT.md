# タスク指示書: Swift通信アーキテクチャ修正（GPT-5.3-codex / 副脳）

## 目的
3者体制通信監査で検出されたSwift側のCritical+Moderate問題を修正し、通信アーキテクチャを堅牢化する。

## 背景
- iOS アプリ（VideoDirectorAgent）がFastAPI（Mac上）と通信
- 3つの接続経路: ローカルmDNS / Tailscale VPN / cloudflaredトンネル
- WiFi切断→復帰後にアプリが接続を回復しない問題があった
- NWPathMonitor追加済みだが、probe競合・ScenePhase未監視等の設計問題が残存
- 監査レポート: `~/AI開発10/AUDIT_NETWORK_SWIFT.md`, `~/AI開発10/AUDIT_NETWORK_DESIGN.md`

## 修正内容（優先順位順）

### Critical（即修正）
1. **probe競合防止（actor化）** — `probeAndConnect()` を `ConnectionOrchestrator` actor に集約。多重probe抑止
   - 対象: `APIClient.swift`
   - 設計レビューの推奨コード案を参考に

2. **ScenePhase監視追加** — `@Environment(\.scenePhase)` で BG→FG 復帰時に `probeAndConnect()` を呼ぶ
   - 対象: `VideoDirectorAgentApp.swift`

3. **ATS修正** — `Info.plist` の `NSAllowsArbitraryLoads = true` を撤廃。必要ドメインのみ `NSExceptionDomains` で許可
   - 対象: `Info.plist`
   - 許可が必要なドメイン: ローカル(.local)、Tailscale IP、video-api.legit-marc.com

### Moderate（修正推奨）
4. **並列probe** — 逐次probeを `TaskGroup` で並列化。最初に成功した候補を採用（ただし優先順位: local > tailscale > cloud）
   - 対象: `APIClient.swift` の `probeAndConnect()`

5. **手修正API 8メソッドの `performRequest` 統合** — 直接 `URLSession.shared.data(for:)` を使っている8メソッドを `performRequest` 経由に変更
   - 対象: `APIClient.swift:708-870`
   - `JSONSerialization` ベースの `performRequest` オーバーロードを作成するか、Codable型を定義

6. **VimeoReviewViewModel の APIClient 経由化** — 直接 URLSession を使っている `fetchVimeoComments()` を `APIClient` 経由に変更
   - 対象: `VimeoReviewViewModel.swift:139-151`

7. **probeエンドポイントを `/healthz` に変更** — `/api/projects` の代わりに軽量な `/healthz` を使用（Python側で追加される）
   - 対象: `APIClient.swift` の `isReachable()`

8. **connectionStatus の UI表示** — `RootTabView` またはヘッダーに接続ステータス表示。`.disconnected` 時に赤バナー + リトライボタン
   - 対象: Views配下

## 完了条件
- [ ] Xcodeビルド成功（error 0）
- [ ] probe競合が発生しないこと（actor化で排他制御）
- [ ] BG→FG復帰時に再接続が走ること
- [ ] ATS例外が必要ドメインのみに限定されていること
- [ ] 全APIメソッドが `performRequest` 経由であること（grep確認）
- [ ] VimeoReviewViewModelが直接URLSessionを使っていないこと
- [ ] 接続状態がUIに表示されること

## 注意事項
- このタスクは `APIClient.swift` を中心に修正する。**他のタスク（Python側修正）とファイル競合はない**
- actor化により既存の呼び出し元に `await` が必要になる場合がある。呼び出し元も修正すること
- ビルドが通ることを最終確認すること

## 出力先
修正は直接コードに適用。完了後 `~/AI開発10/FIX_REPORT_SWIFT.md` に修正箇所一覧を出力。
