# 通信設計レビュー（APIClient.swift）

対象: `VideoDirectorAgent/VideoDirectorAgent/Services/APIClient.swift`

レビュー観点は実装詳細ではなく、通信アーキテクチャ設計としての妥当性・欠陥・エッジケース網羅性。

## 総評
現状は「候補URLを順次probeして activeBaseURL を切り替える」最小設計としては成立していますが、
モバイル環境で必須になる「ネットワーク変化時の確実な再収束」「並行アクセス下での状態一貫性」「オフラインUX」「公開経路の防御」に不足があります。

特に以下は設計上の重大リスクです。
- `probeAndConnect()` の同時実行制御がなく、状態競合で不安定化しうる
- `URLSession.shared` 依存で経路ごとの接続特性（キャッシュ・接続プール・待機制御）を制御できない
- cloudflared 公開前提で API 認証設計が見えず、攻撃面が広い

---

## 1) 問題一覧（Severity分類）

### Critical

1. **再接続処理の競合（Race condition）**
- 根拠: `probeAndConnect()` が `NWPathMonitor` 変化時と `URLError` 発生時の両方から起動され、排他制御なし。
- 影響: 2つ以上のprobeが同時進行し、最後に完了したタスクが `activeBaseURL` を上書き。実際の最適経路より劣化経路に戻る可能性。
- 症状例: WiFi復帰直後にローカルへ切替 → 少し遅れて別probeがクラウドへ戻す。

2. **クラウド公開経路の認証不在リスク（設計上）**
- 根拠: APIリクエストに認証ヘッダ付与設計がない（全request共通でAuthorization未設定）。
- 影響: cloudflared URL が露出した場合、第三者がAPIへ直接アクセス可能になる恐れ。
- 備考: サーバ側で別認証があるなら明示が必要。クライアント設計上は未担保。

3. **ATSが過度に緩い (`NSAllowsArbitraryLoads = true`)**
- 根拠: `Info.plist` に包括許可。
- 影響: 想定外ドメインへの平文/弱TLS通信も許容され、通信保護境界が崩れる。

### Moderate

4. **逐次probeのみで収束が遅い**
- 根拠: ローカル→Tailscale→クラウドを3秒タイムアウトで直列試行。
- 影響: 最悪9秒以上接続待ち。UI/UX悪化、復帰遅延。

5. **NWPathMonitorイベントの解釈が粗い**
- 根拠: `path.status` のみ主軸で、`isExpensive`, `isConstrained`, interface種別差分を設計に反映していない。
- 影響: WiFi↔CellularやVPN有無で最適経路選択が不十分。

6. **バックグラウンド復帰時の明示再評価がない**
- 根拠: 起動時 `.task` と pathUpdate依存。`scenePhase == .active` 復帰でのprobe設計が見えない。
- 影響: 復帰後に path change が発火しないケースで古い `activeBaseURL` を保持。

7. **URLSession.shared 固定により通信制御点が不足**
- 根拠: probe・本リクエスト・長時間リクエストすべて shared。
- 影響: DNS/接続プール/キャッシュ/待機方針を用途別に分離できず、障害切替時の挙動が読みにくい。

8. **手修正API extension が再接続経路を通らない**
- 根拠: extension内の複数メソッドが `request()` ラッパではなく直接 `URLSession.shared.data(for:)`。
- 影響: 一部APIだけフォールバック・自動再接続が効かず、体感的に「時々つながらない」が発生。

9. **接続経路のハードコード（`.local` / Tailscale IP）**
- 根拠: `candidateURLs` が固定文字列。
- 影響: IP/ホスト変更で即死。運用時の追従コスト高。

### Minor

10. **`connectionStatus` がUI利用されていない**
- 根拠: 参照が `APIClient.swift` 内のみ。
- 影響: 接続中/切断/復旧中の視覚フィードバックが欠落。

11. **オフライン時の読み取りキャッシュ設計が不足**
- 根拠: APIレスポンス永続キャッシュ層（DB/ファイル）不在。
- 影響: 一時オフラインで画面が空/エラーに寄る。

12. **cloudflared URL変更への追従経路が弱い**
- 根拠: primaryURLはInfo.plist固定。
- 影響: トンネル再作成でURL変更時、アプリ更新まで復旧不能。

---

## 2) 接続戦略の評価（逐次 vs 並列）

### 現状評価
- 逐次probeは実装が単純でデバッグしやすい利点あり。
- ただしモバイル実運用では「最速回復」要件に弱く、遅延と競合リスクが目立つ。

### 推奨
- **ハイブリッド方式**
  - フェーズ1: 低遅延候補（ローカル/Tailscale）を**短タイムアウトで並列probe**
  - フェーズ2: 失敗時のみクラウドをprobe
- 採用ロジックは「最初に成功した候補」ではなく、**成功 + 優先度 + 安定スコア**で決定。
  - 例: 同時成功なら `local > tailscale > cloud`、ただし直近失敗履歴で減点。

### probe頻度/タイミング
- 起動時1回は妥当。
- 追加必須トリガ:
  - `scenePhase` が `.active` に戻るたび（デバウンス付き）
  - NWPathの実質変化（interface種別、expensive/constrained、VPN到達性）
  - 連続通信失敗時のバックオフ再probe（1s,2s,4s...最大30s）

---

## 3) 状態遷移網羅性（指定7パターン）

1. **WiFi ON → WiFi OFF → WiFi ON**
- 判定: **部分的にOK / 漏れあり**
- 理由: OFF時に `.disconnected` 化、ON時にprobe実行はある。
- 漏れ: path event競合時の多重probe、復帰時に経路安定前の誤判定。

2. **WiFi ON → WiFi OFF → 4G ON**
- 判定: **部分的にOK**
- 理由: `status == .satisfied` で再probeされるため切替自体は可能。
- 漏れ: 4Gではローカル候補が毎回無駄に先行試行され遅延。

3. **4G ON → WiFi ON**
- 判定: **部分的にOK**
- 理由: interface変更で再probe。
- 漏れ: VPN状態やローカル到達性を加味した経路再優先が弱い。

4. **Tailscale ON → Tailscale OFF**
- 判定: **要改善**
- 理由: OS path status は satisfied のままでも Tailscale到達不能になるケースあり。pathイベント非発火なら切替が遅れる。
- 補足: 現状は実リクエスト失敗時にのみ再probeされる受動設計。

5. **アプリ BG → FG復帰**
- 判定: **要改善**
- 理由: FG復帰を明示トリガにしていない。

6. **Macスリープ → 復帰（API一時停止）**
- 判定: **部分的にOK**
- 理由: 通信失敗時のURLErrorで再probeは働く。
- 漏れ: サーバ起動待ちの再試行戦略（指数バックオフ + UI表示）がない。

7. **cloudflaredトンネル再起動（URL変更）**
- 判定: **NG（設計漏れ）**
- 理由: primaryURL固定。動的ディスカバリ/設定配信なし。

---

## 4) キャッシュ戦略レビュー

### DNS/接続キャッシュ
- リスク: `URLSession.shared` の接続再利用により、経路切替直後に古い接続へ寄る可能性。
- 推奨:
  - `URLSessionConfiguration.ephemeral` を接続管理専用セッションとして分離
  - `waitsForConnectivity = false`（用途別に調整）
  - probe専用セッションと業務APIセッションを分ける

### URLCache
- 現状: 明示設定なし（shared既定依存）。
- 評価: APIクライアントとして戦略不明確。
- 推奨:
  - 動的データは `requestCachePolicy = .reloadIgnoringLocalCacheData`
  - 静的寄りエンドポイントのみ短TTLキャッシュ

### オフライン表示データ
- 現状: API結果永続層なし。
- 推奨:
  - 最低限 `lastKnownGood` を永続化（SwiftData/SQLite/JSON）
  - オフライン時は stale データ表示 + 「最終更新時刻」表示

---

## 5) UX設計レビュー

### 現状
- `connectionStatus` は存在するが、ビューで未使用。
- Pull-to-refresh は各Viewにあるが、再接続状態の統一表示がない。

### 推奨UX要件
- 接続中: 画面上部に `Reconnecting... (local/tailscale/cloud を探索中)`
- 切断中: 永続オフラインバナー + 最終成功時刻
- 失敗時: `再試行` ボタン（`probeAndConnect()` + 再フェッチ）
- Pull-to-refresh: 手動再接続フックを明示（単なる再取得ではなく経路再評価も実施）

---

## 6) セキュリティ設計レビュー

1. **HTTP通信（local/tailscale）**
- ローカル/VPN内でも盗聴・改ざんリスクはゼロではない。
- 推奨: 可能ならTLS化（自己署名+pinning、または内部CA）。最低でも署名付きトークン必須。

2. **cloudflared公開と認証**
- APIキー/短命JWT/OAuth2いずれかを必須化。
- 端末固有識別 + レート制限 + 監査ログを推奨。

3. **ATS例外**
- `NSAllowsArbitraryLoads = true` は撤廃。
- 必要ドメインのみ `NSExceptionDomains` で限定。

---

## 7) スケーラビリティ評価

### 問題
- 接続候補がコード固定で、経路追加時にAPIClient改修必須。

### 推奨
- `EndpointProvider` 抽象を導入し、候補を設定/リモート配信/ローカル検出から組み立てる。
- 経路ごとにメタ情報を持つ:
  - `id`, `baseURL`, `priority`, `requiresVPN`, `securityLevel`, `healthScore`

---

## 8) 推奨アーキテクチャ（具体案）

### A. Connection Orchestrator（状態機械）

```swift
actor ConnectionOrchestrator {
    enum State { case idle, probing, connected(Route), degraded(Route), offline }

    private(set) var state: State = .idle
    private var probeTask: Task<Route?, Never>?

    func reprobe(trigger: Trigger) async {
        probeTask?.cancel()                  // 多重probeを抑止
        state = .probing
        probeTask = Task { await raceRoutes() }
        if let route = await probeTask?.value {
            state = .connected(route)
        } else {
            state = .offline
        }
    }
}
```

ポイント:
- probeを単一タスク化し、競合を排除
- trigger（起動/FG復帰/path変化/連続失敗）を明示管理

### B. 並列probe（優先度付き）

```swift
func raceRoutes() async -> Route? {
    await withTaskGroup(of: Route?.self) { group in
        for route in fastRoutes { group.addTask { await probe(route) ? route : nil } }
        for await result in group {
            if let r = result { return r }   // 最初の成功
        }
        return await probe(cloudRoute) ? cloudRoute : nil
    }
}
```

### C. リクエスト失敗時の再収束
- 1回だけ即時retryではなく、`retry budget` と `exponential backoff` を導入。
- 429/5xx と URLError を分離し、ネットワーク起因のみ経路再評価。

---

## 9) 追加で漏れやすいエッジケース（重要）

- Captive Portal（WiFi接続済みだが外部到達不可）
- DNSだけ生きていてTCP不可、またはその逆
- IPv6-onlyネットワークで `.local`/固定IPv4 が失敗
- Low Data Mode時の大容量レスポンス
- 端末時刻ずれによるTLS失敗
- サーバ証明書ローテーション時の一時失敗
- 同時に複数画面が fetch している最中の `activeBaseURL` 切替

---

## 10) 優先対応ロードマップ

1. **Critical**: probe競合防止（actor化/単一オーケストレータ化）
2. **Critical**: cloud公開前提のAPI認証導入（短命トークン）
3. **Critical**: ATSの包括許可撤廃
4. **Moderate**: 並列probe + バックオフ再試行 + FG復帰トリガ
5. **Moderate**: 手修正APIを共通request経路に統合
6. **Minor**: オフラインバナー/最終成功時刻/手動再接続UI

---

## 結論
現状設計は「通常時に動く」水準は満たす一方、モバイル実運用で起きる状態遷移の揺れと公開経路の安全性に対して防御が薄いです。
特に **多重probe競合・認証不在・ATS緩和** は早期是正対象です。これらを先に修正し、その後に並列probeとUX改善を入れる順序が最も効果的です。
