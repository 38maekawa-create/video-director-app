# タスク指示書: 通信周り全面監査＆修正

## 目的
iOS アプリ（VideoDirectorAgent）の通信周りに複数の不具合がある。WiFi↔4G切り替え時にAPIエラーが発生し、WiFiに戻っても復帰しない。ユーザー体験を著しく損なう問題であり、徹底的に潰す。

## 背景
- アプリはAPIサーバー（FastAPI on Mac）と通信する iOS ネイティブアプリ
- 接続先候補: ローカル（mDNS）、Tailscale VPN、cloudflaredトンネル
- 前セッション（37時間）のコンテキスト圧縮により通信周りのコードに品質劣化の可能性
- WiFi切断→復帰後にアプリが接続を回復しない不具合が確認済み
- cloudflaredのDNS設定が壊れており、クラウドURL経由のアクセスが不可

## 全体工程における位置づけ
トリプル監査のPhase 1（コード品質監査）は完了。本タスクはPhase 2（修正実行）の通信特化版。
完了すれば、WiFi/4G/VPN環境を問わず安定したAPI通信が実現し、パグさんへのTestFlight配布が完成する。

## 監査対象ファイル
### Swift側（iOS）
- `VideoDirectorAgent/VideoDirectorAgent/Services/APIClient.swift` — メインAPI通信クラス
- `VideoDirectorAgent/VideoDirectorAgent/ViewModels/*.swift` — 各ViewModelのAPI呼び出し
- `VideoDirectorAgent/VideoDirectorAgent/Views/*.swift` — Viewからの直接URLSession呼び出し（VimeoReviewViewModelなど）
- `VideoDirectorAgent/VideoDirectorAgent/Info.plist` — ATS設定、APIBaseURL

### Python側（APIサーバー）
- `src/video_direction/integrations/api_server.py` — CORS設定、エラーハンドリング
- cloudflared設定（`~/.cloudflared/config.yml`）

## 監査観点
### 1. 接続復帰メカニズム
- [x] NWPathMonitor導入済み（WiFi↔4G切り替え検知）
- [ ] probeAndConnect()の呼び出しタイミングは適切か
- [ ] ScenePhaseの.active復帰時にもprobeを実行しているか
- [ ] URLSessionのキャッシュが接続復帰を妨げていないか
- [ ] DNS解決のキャッシュ（NSURLCache, URLCache）が問題を起こしていないか

### 2. タイムアウト設計
- [ ] probeのタイムアウト3秒は適切か（3候補で最大9秒待ち）
- [ ] 各APIリクエストのタイムアウト12秒は適切か
- [ ] クラウドURLが応答しない場合のフォールバック速度
- [ ] 並列probeで高速化できないか（逐次ではなく）

### 3. エラーハンドリング
- [ ] API呼び出し失敗時のユーザー通知（現状サイレント握りつぶしが13箇所）
- [ ] リトライ戦略（現状は1回だけ）
- [ ] オフライン状態の明示的なUI表示
- [ ] エラー時の部分データ表示（キャッシュがあれば表示）

### 4. ローカルネットワーク
- [ ] mDNS（mac-mini-m4.local）の解決が失敗するケース
- [ ] Bonjourの権限（Info.plist: NSLocalNetworkUsageDescription）
- [ ] ローカルネットワーク許可ダイアログが出ていないケース

### 5. Tailscale
- [ ] VPNがOFFの場合の挙動
- [ ] Tailscale IPが変わった場合の対応（現在ハードコード）

### 6. cloudflared
- [ ] DNS設定（legit-marc.com → cfargotunnel.com CNAME）
- [ ] SSL/TLS（Cloudflareプロキシ不在時の証明書問題）
- [ ] トンネル再起動時のURL変更への対応

### 7. CORS
- [ ] api_server.pyのCORS設定はワイルドカード（*）か
- [ ] cloudflaredトンネル経由時のOriginヘッダー

## 完了条件
1. WiFi → 4G → WiFi の切り替えでアプリが自動復帰すること
2. アプリ起動から2秒以内にAPI接続が確立すること
3. 接続エラー時にユーザーに明示的なUI通知があること
4. Tailscale OFF、WiFi OFF の完全オフライン時にクラッシュしないこと
5. 上記を自走修正3サイクル（実画面スクリーンショット含む）で検証すること

## 検証方法
- WiFi ON → アプリ起動 → データ表示確認
- WiFi OFF → APIエラー表示確認（クラッシュしないこと）
- WiFi ON → 自動復帰確認（再起動不要）
- Tailscale ON + WiFi OFF → 4G経由で接続確認
- Tailscale OFF + WiFi OFF → オフラインUI確認
