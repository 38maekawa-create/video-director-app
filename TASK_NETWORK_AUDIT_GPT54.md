# タスク指示書: 通信設計レビュー（GPT-5.4 / 副脳）

## 目的
iOS アプリの通信アーキテクチャを設計レベルでレビューし、エッジケース・設計上の欠陥を洗い出す。実装の詳細ではなく「設計として正しいか」を評価する。

## 背景
- iOS アプリ（Swift/SwiftUI）がAPIサーバー（FastAPI on Mac）と通信
- 3つの接続経路: ローカルmDNS / Tailscale VPN / cloudflaredトンネル
- 現在の問題: WiFi切断→復帰後にアプリが接続を回復しない
- NWPathMonitor（Network.framework）を追加済みだが、まだ検証されていない

## 全体工程における位置づけ
3者体制通信監査の1/3。Swift実装（右腕）、Python実装（左腕Codex）と並行実施。
本タスクは設計・アーキテクチャレベルのレビュー。

## レビュー対象
`~/AI開発10/VideoDirectorAgent/VideoDirectorAgent/Services/APIClient.swift` を読んだ上で、以下を評価:

## レビュー項目

### 1. 接続戦略の設計評価
- 3候補（ローカル→Tailscale→クラウド）の逐次probeは最適か
- 並列probeにすべきか（最初に応答した候補を採用）
- probeの頻度・タイミングは適切か

### 2. 状態遷移の網羅性
以下の全状態遷移パターンでアプリが正しく動作するか:
- WiFi ON → WiFi OFF → WiFi ON
- WiFi ON → WiFi OFF → 4G ON
- 4G ON → WiFi ON
- Tailscale ON → Tailscale OFF
- アプリがバックグラウンド → フォアグラウンド復帰
- Macスリープ → 復帰（APIサーバー一時停止）
- cloudflaredトンネル再起動（URL変更）

### 3. キャッシュ戦略
- URLSessionのDNSキャッシュがフォールバックを妨げる可能性
- URLCacheの設定は適切か
- オフライン時のデータキャッシュ（最後に取得したデータの表示）

### 4. UX設計
- 接続中・接続失敗・再接続中のUI表示
- エラー時のリトライボタンの有無
- Pull-to-refreshで手動再接続できるか
- オフラインバナーの表示

### 5. セキュリティ設計
- HTTP（非暗号化）通信のリスク（ローカル/Tailscale経路）
- APIに認証がない状態でのcloudflared公開リスク
- ATS（App Transport Security）の例外設定の妥当性

### 6. スケーラビリティ
- Tailscale IPのハードコード（IPが変わったら？）
- mDNSのホスト名ハードコード
- 新しい接続経路を追加する際の拡張性

## 完了条件
1. 上記全項目の設計レビュー結果を `AUDIT_NETWORK_DESIGN.md` に出力
2. 各問題を Critical / Moderate / Minor に分類
3. 推奨設計の具体案を含めること（コード例あれば尚良し）
4. 「こういうエッジケースが漏れている」という指摘を重視

## 出力先
`~/AI開発10/AUDIT_NETWORK_DESIGN.md`
