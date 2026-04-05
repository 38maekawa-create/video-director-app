# cloudflared DNS根本解決 — 手順書

## 目的
`video-api.legit-marc.com` がWiFi外（4G/5G）から繋がらない問題を根本解決する。

## 背景
- cloudflaredトンネルのCNAME（`xxx.cfargotunnel.com`）は、Cloudflareプロキシを通してのみ解決される
- 現在legit-marc.comのネームサーバーがXserverのため、Cloudflareプロキシが介入できずトンネルに到達不能
- legit-marc.comのドメインで動かしてるサービスは現在ないため、切り替えリスクはなし

## 所要時間
操作自体: 10〜15分 / DNS浸透待ち: 数時間（最大48時間だが通常は1〜2時間）

---

## 手順

### Step 1: Cloudflareにドメインを追加

1. https://dash.cloudflare.com にログイン
2. 左メニューの「Websites」→「Add a site」をクリック
3. `legit-marc.com` を入力して「Continue」
4. プラン選択 → **Free（無料）** を選択して「Continue」
5. Cloudflareが自動的に既存のDNSレコードをスキャンする → 次のStepで確認

### Step 2: DNSレコードの確認・追加

Cloudflareが自動スキャンした結果を確認する。以下のレコードが全部あることを確認：

| タイプ | 名前 | 値 | プロキシ |
|--------|------|-----|---------|
| A | `legit-marc.com` | `202.210.8.118` | OFF（DNSのみ・灰色雲） |
| A | `www` | `202.210.8.118` | OFF（DNSのみ・灰色雲） |
| A | `mail` | `202.210.8.118` | OFF（DNSのみ・灰色雲） |
| MX | `legit-marc.com` | `legit-marc.com`（優先度: 0） | — |
| TXT | `legit-marc.com` | `v=spf1 +a:sv10597.xserver.jp +a:legit-marc.com +mx include:spf1.sender.xserver.jp ~all` | — |
| CNAME | `video-api` | `9ebb2159-77cc-446b-83f6-794ba7d0c8e3.cfargotunnel.com` | **ON（オレンジ雲）** ← ここだけプロキシON！ |

**重要ポイント:**
- `video-api` の CNAME だけ **プロキシON（オレンジ色の雲アイコン）** にする
- 他のレコードは **プロキシOFF（灰色の雲）** にする（メール等に影響しないように）
- 自動スキャンで `video-api` のCNAMEが出てこなかったら手動で追加する

「Continue」で次へ。

### Step 3: Cloudflareが表示するネームサーバーをメモする

画面に以下のような2つのネームサーバーが表示される（例）：
```
例: aria.ns.cloudflare.com
例: lloyd.ns.cloudflare.com
```

**この2つをメモまたはスクショする！** 次のステップで使う。

### Step 4: Xserverでネームサーバーを変更

1. https://secure.xserver.ne.jp/ にログイン
2. 「サーバー管理」→「ドメイン設定」→ `legit-marc.com` を選択
3. ※ Xserverの管理画面構成によっては：
   - Xserverアカウント（旧インフォパネル）→「ドメイン」→ `legit-marc.com` の「ネームサーバー設定」
4. ネームサーバーを以下に変更：
   - ネームサーバー1: `（Step 3でメモしたもの）`
   - ネームサーバー2: `（Step 3でメモしたもの）`
   - ネームサーバー3〜5: 空欄にする
5. 「確認」→「変更」

### Step 5: 浸透確認

変更後、以下のコマンドで確認できる（ターミナルまたはバティに頼む）：

```bash
# ネームサーバーが変わったか
dig legit-marc.com NS +short

# video-apiが解決されるか
curl -s https://video-api.legit-marc.com/api/health

# Cloudflareプロキシ経由か確認
curl -sI https://video-api.legit-marc.com | grep -i server
# → "server: cloudflare" と出ればOK
```

**浸透前**: `ns1.xserver.jp` 等が返る
**浸透後**: `xxx.ns.cloudflare.com` が返り、APIに接続できるようになる

---

## 完了条件
- [ ] `dig legit-marc.com NS` → Cloudflareのネームサーバーが返る
- [ ] `curl https://video-api.legit-marc.com/api/health` → 正常レスポンス
- [ ] WiFi OFF（4G/5G）+ Tailscale OFF の状態でアプリからAPIアクセス成功
- [ ] cloudflaredトンネルが稼働中であることを確認

## 注意事項
- cloudflaredデーモンがMac上で動いている必要がある（`launchctl list | grep cloudflared`で確認）
- DNS浸透中は新旧ネームサーバーが混在するため、端末によって繋がったり繋がらなかったりする → 正常
- 完全浸透後はTailscale不要で外部からAPI接続可能になる
