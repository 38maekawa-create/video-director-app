# Vimeo Relay Adapter Spec

> 最終更新: 2026-03-11
> 対象: AI開発10 映像エージェント root正本

## 1. 目的

スマホ音声FBから生成されたレビューコメントを、Mac側中継API経由で Vimeo レビューモードの該当タイムコードへ投稿するための受け口仕様を定義する。

この仕様の責務は次の3つ。
- 映像エージェントUIが生成した relay request の形式を固定する
- Mac側 relay adapter が受ける HTTP 入力を固定する
- relay adapter が返す最小レスポンスを固定する

## 2. 全体フロー

1. 映像エージェント詳細ページで音声FBをレビュー文へ変換する
2. UI上で relay request JSON または curl を生成する
3. Mac側 relay adapter が `/api/vimeo/review-comments` で受け取る
4. relay adapter が Vimeo 側へコメント投稿を実行する
5. 投稿結果を映像エージェントへ返し、アプリ内の sync 状態に反映する

## 3. HTTP エンドポイント

- Method: `POST`
- Path: `/api/vimeo/review-comments`
- Content-Type: `application/json`
- Auth: `Authorization: Bearer <relay_token>`

## 4. Request Body

```json
{
  "projectId": "proj-001",
  "projectName": "ブンさん対談",
  "videoId": "video-001",
  "endpoint": "http://mac-relay.local/api/vimeo/review-comments",
  "authMode": "relay_token",
  "targetVideoId": "vimeo-839201",
  "body": {
    "videoId": "video-001",
    "projectName": "ブンさん対談",
    "targetVideoId": "vimeo-839201",
    "comments": [
      {
        "feedbackId": "fb-001",
        "timestamp": "03:12",
        "timestampSeconds": 192,
        "rawVoiceText": "3分12秒のここがくそ",
        "convertedText": "3分12秒付近は結論の強さが落ちるので、最初の一言を残しつつ余白を詰めて温度感を上げたいです。",
        "referenceExample": {
          "title": "参考: Netflix風インタビューのテンポ",
          "url": "https://example.com/reference/netflix-interview",
          "note": "入り3秒で結論を立てる構成を参考にする"
        },
        "syncState": "pending",
        "reviewMode": "transformed"
      }
    ]
  }
}
```

## 5. リクエストバリデーション

relay adapter 側では最低限次を検証する。
- `projectId` が空でない
- `videoId` が空でない
- `targetVideoId` が空でない
- `body.comments` が配列である
- 各 comment に `feedbackId`, `timestampSeconds`, `convertedText` がある
- `Authorization` ヘッダが期待トークンと一致する

## 6. 期待レスポンス

成功時:

```json
{
  "ok": true,
  "projectId": "proj-001",
  "videoId": "video-001",
  "targetVideoId": "vimeo-839201",
  "postedCount": 2,
  "results": [
    {
      "feedbackId": "fb-001",
      "status": "posted",
      "vimeoCommentId": "comment-123",
      "timestampSeconds": 192
    }
  ],
  "receivedAt": "2026-03-11T16:40:00+09:00"
}
```

部分成功時:

```json
{
  "ok": false,
  "projectId": "proj-001",
  "postedCount": 1,
  "results": [
    {"feedbackId": "fb-001", "status": "posted"},
    {"feedbackId": "fb-002", "status": "failed", "error": "timestamp out of range"}
  ]
}
```

## 7. relay adapter の責務

Mac側 relay adapter は次を担う。
- Bearer token 検証
- request body 検証
- Vimeo API へのコメント投稿
- 投稿結果の集約
- ローカルログ保存

担わないもの。
- 音声文字起こし
- レビュー文への変換
- 参考事例の検索
- UIの状態更新

## 8. ローカルログ

relay adapter は最低限次を保存する。
- request 受信時刻
- projectId / videoId
- 各 feedbackId の投稿結果
- 失敗時の原因

推奨保存先。
- `runs/relay_logs/YYYYMMDD/`
- または relay server 側の `logs/relay/`

## 9. Vimeo 投稿マッピング

各 comment は次のように投稿する。
- 本文: `convertedText`
- タイムコード: `timestampSeconds`
- 補助情報: `referenceExample.url` と `referenceExample.note` は本文末尾に整形して付与可

推奨整形例。

```text
3分12秒付近は結論の強さが落ちるので、最初の一言を残しつつ余白を詰めて温度感を上げたいです。

参考事例: https://example.com/reference/netflix-interview
補足: 入り3秒で結論を立てる構成を参考にする
```

## 10. 現時点の実装境界

2026-03-11 時点では、映像エージェント root 正本で次まで実装済み。
- relay request JSON 生成
- relay curl 生成
- relay 送信シミュレーション

未実装。
- Mac側 relay HTTP server 本体
- Vimeo API 認証と実コメント投稿
- 投稿成功レスポンスを UI へ戻す本線

## 11. 次の実装順

1. relay adapter をローカル HTTP server として起動
2. `send_vimeo_relay_package.py` から POST できるようにする
3. Vimeo API adapter を差し込む
4. 成功/失敗レスポンスを映像エージェントUIへ戻す
