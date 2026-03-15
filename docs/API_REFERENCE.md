# API リファレンス — 映像品質追求・自動ディレクションシステム

**最終更新**: 2026-03-15
**ベースURL**: `http://localhost:8210`
**実装ファイル**: `src/video_direction/integrations/api_server.py`
**フレームワーク**: FastAPI
**データベース**: SQLite (`~/.data/video_director.db`, WALモード)
**CORS**: 全オリジン・メソッド・ヘッダーを許可

---

## 目次

1. [ヘルスチェック](#1-ヘルスチェック)
2. [プロジェクト管理](#2-プロジェクト管理)
3. [YouTube素材管理](#3-youtube素材管理)
4. [フィードバック管理](#4-フィードバック管理)
5. [ダッシュボード](#5-ダッシュボード)
6. [編集者管理](#6-編集者管理)
7. [映像トラッキング](#7-映像トラッキング)
8. [学習・インサイト](#8-学習インサイト)
9. [巡回監査](#9-巡回監査)
10. [通知設定](#10-通知設定)
11. [PDCAループ](#11-pdcaループ)
12. [分散処理](#12-分散処理)
13. [フィードバック変換](#13-フィードバック変換)
14. [同期チェック](#14-同期チェック)
15. [Pydanticモデル一覧](#15-pydanticモデル一覧)
16. [データベーススキーマ](#16-データベーススキーマ)

---

## 1. ヘルスチェック

### GET `/api/health`

APIサーバーとDBの死活確認。

**パラメータ**: なし

**レスポンス例** (200 OK):
```json
{
  "status": "ok",
  "db": "connected"
}
```

**エラー例** (500):
```json
{
  "status": "error",
  "detail": "DB connection failed"
}
```

---

## 2. プロジェクト管理

### GET `/api/projects`

全プロジェクト一覧を `shoot_date` 降順で取得。

**パラメータ**: なし

**レスポンス例** (200 OK):
```json
[
  {
    "id": "INT_001_Izu",
    "guest_name": "Izu",
    "title": "月収3000万の秘密",
    "status": "directed",
    "shoot_date": "2026-03-01",
    "guest_age": 32,
    "guest_occupation": "投資家",
    "quality_score": 88,
    "has_unsent_feedback": false,
    "unreviewed_count": 0,
    "direction_report_url": "https://38maekawa-create.github.io/direction-pages/INT_001_Izu.html",
    "source_video": {"url": "https://vimeo.com/xxx", "status": "uploaded"},
    "edited_video": {"url": "https://vimeo.com/yyy", "status": "review"},
    "feedback_summary": {"count": 3, "latest": "テロップの誤字修正"},
    "knowledge": {"highlights": ["年収3000万", "投資戦略"]},
    "created_at": "2026-03-01T10:00:00",
    "updated_at": "2026-03-15T09:00:00"
  }
]
```

---

### GET `/api/projects/{project_id}`

特定プロジェクトを取得。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `project_id` | string | プロジェクトID（例: `INT_001_Izu`） |

**レスポンス例** (200 OK): プロジェクトオブジェクト（上記と同形式）

**エラー例** (404):
```json
{"detail": "Project not found"}
```

---

### POST `/api/projects`

新規プロジェクトを作成。

**リクエストボディ**: `ProjectCreate`

```json
{
  "id": "INT_002_PayPay",
  "guest_name": "PAY",
  "title": "PayPayで月商1000万の話",
  "status": "directed",
  "shoot_date": "2026-03-10",
  "guest_age": 28,
  "guest_occupation": "EC事業者",
  "quality_score": 82,
  "direction_report_url": null,
  "source_video": null,
  "edited_video": null,
  "feedback_summary": null,
  "knowledge": null
}
```

**レスポンス例** (200 OK):
```json
{"message": "created", "id": "INT_002_PayPay"}
```

**エラー例** (400):
```json
{"detail": "Project INT_002_PayPay already exists"}
```

---

### PUT `/api/projects/{project_id}`

既存プロジェクトを更新。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `project_id` | string | プロジェクトID |

**リクエストボディ**: `ProjectCreate`（`id` は無視される）

**レスポンス例** (200 OK):
```json
{"message": "updated"}
```

**エラー例** (404):
```json
{"detail": "Project not found"}
```

---

## 3. YouTube素材管理

### GET `/api/projects/{project_id}/youtube-assets`

YouTube公開用素材（サムネイル指示書・タイトル案・概要欄）を取得。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `project_id` | string | プロジェクトID |

**レスポンス例** (200 OK):
```json
{
  "project_id": "INT_001_Izu",
  "thumbnail_design": {
    "zone_a": "ゲスト顔アップ + 驚き表情",
    "zone_b": "月収3000万",
    "zone_c": "投資家の素顔",
    "zone_d": "TEKO ロゴ"
  },
  "title_proposals": {
    "candidates": [
      "月収3000万の投資家が語る「お金の真実」",
      "32歳で資産10億達成した思考法",
      "普通のサラリーマンが投資家になるまで"
    ]
  },
  "description_original": "今回のゲストはIzuさんです...",
  "description_edited": "【今回のゲスト】Izuさん（投資家）...",
  "description_finalized_at": null,
  "description_finalized_by": null,
  "selected_title_index": 0,
  "edited_title": "月収3000万の投資家が語る「お金の真実」【完全版】",
  "last_edited_by": "naoto",
  "generated_at": "2026-03-01T12:00:00",
  "updated_at": "2026-03-15T08:00:00"
}
```

**エラー例** (404):
```json
{"detail": "YouTube assets not found"}
```

---

### PUT `/api/projects/{project_id}/youtube-assets`

YouTube素材をUPSERT（存在すれば更新、なければ新規作成）。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `project_id` | string | プロジェクトID |

**リクエストボディ**: `YouTubeAssetsUpsert`

```json
{
  "thumbnail_design": {
    "zone_a": "ゲスト顔アップ",
    "zone_b": "衝撃の事実",
    "zone_c": "タイトル文字",
    "zone_d": "TEKO"
  },
  "title_proposals": {
    "candidates": ["タイトル案1", "タイトル案2", "タイトル案3"]
  },
  "description_original": "元の概要欄テキスト...",
  "description_edited": null,
  "selected_title_index": null,
  "edited_title": null,
  "last_edited_by": "naoto"
}
```

**レスポンス例** (200 OK):
```json
{"message": "upserted"}
```

---

### PATCH `/api/projects/{project_id}/youtube-assets/description`

概要欄の編集済みテキストを更新。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `project_id` | string | プロジェクトID |

**リクエストボディ**: `DescriptionUpdate`

```json
{
  "edited": "【今回のゲスト】Izuさん（投資家・32歳）\n月収3000万を達成した...",
  "by": "pagu"
}
```

**レスポンス例** (200 OK):
```json
{"message": "updated"}
```

---

### PATCH `/api/projects/{project_id}/youtube-assets/title`

タイトル案の選択・編集。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `project_id` | string | プロジェクトID |

**リクエストボディ**: `TitleSelect`

```json
{
  "index": 0,
  "edited_title": "月収3000万の投資家が語る「お金の真実」【完全版】",
  "by": "naoto"
}
```

**レスポンス例** (200 OK):
```json
{"message": "updated"}
```

---

## 4. フィードバック管理

### GET `/api/projects/{project_id}/feedbacks`

特定プロジェクトのフィードバック一覧を取得。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `project_id` | string | プロジェクトID |

**レスポンス例** (200 OK):
```json
[
  {
    "id": 1,
    "project_id": "INT_001_Izu",
    "timestamp_mark": "03:24",
    "raw_voice_text": "テロップのフォントがちょっと小さいかな",
    "converted_text": "3分24秒のテロップについて：フォントサイズを現状より2段階大きくし、視認性を改善してください。モバイル視聴時にも読めるよう、最小16pxを確保すること。",
    "category": "telop",
    "priority": "medium",
    "created_by": "naoto",
    "is_sent": true,
    "editor_status": "acknowledged",
    "learning_effect": null,
    "created_at": "2026-03-10T15:30:00"
  }
]
```

---

### POST `/api/projects/{project_id}/feedbacks`

フィードバックを新規作成し、学習ループに自動投入。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `project_id` | string | プロジェクトID |

**リクエストボディ**: `FeedbackCreate`

```json
{
  "timestamp_mark": "05:12",
  "raw_voice_text": "ここのBGMが大きすぎる",
  "converted_text": "5分12秒のBGMについて：現状より音量を20%下げてください。会話の明瞭度を優先してください。",
  "category": "audio",
  "priority": "high",
  "created_by": "naoto"
}
```

**レスポンス例** (200 OK):
```json
{
  "message": "created",
  "feedback_id": 42
}
```

> **注意**: 保存後、`FeedbackLearner` に学習データが自動投入されます。

---

### GET `/api/feedbacks`

全フィードバック一覧を取得。

**クエリパラメータ**:
| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `limit` | int | 100 | 取得件数上限 |

**レスポンス例** (200 OK): フィードバック配列（上記と同形式）

---

## 5. ダッシュボード

### GET `/api/dashboard/summary`

全体サマリーデータを取得。

**パラメータ**: なし

**レスポンス例** (200 OK):
```json
{
  "total_projects": 62,
  "projects_with_assets": 60,
  "average_quality_score": 78.3,
  "status_breakdown": {
    "directed": 50,
    "editing": 8,
    "review": 3,
    "published": 1
  },
  "recent_feedbacks": [
    {
      "id": 42,
      "project_id": "INT_001_Izu",
      "category": "audio",
      "priority": "high",
      "created_at": "2026-03-15T09:00:00"
    }
  ],
  "unsent_feedback_count": 3
}
```

---

### GET `/api/dashboard/quality-trend`

品質スコア推移を取得（グラフ描画用）。

**パラメータ**: なし

**レスポンス例** (200 OK):
```json
[
  {
    "guest_name": "Izu",
    "shoot_date": "2026-03-01",
    "quality_score": 88
  },
  {
    "guest_name": "PAY",
    "shoot_date": "2026-02-15",
    "quality_score": 75
  }
]
```

---

## 6. 編集者管理

### GET `/api/editors`

編集者一覧を取得。

**クエリパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `status` | string (optional) | `active` / `inactive` でフィルタ |

**レスポンス例** (200 OK):
```json
[
  {
    "id": 1,
    "name": "田中編集者",
    "contact_info": "tanaka@example.com",
    "status": "active",
    "contract_type": "freelance",
    "specialties": ["カット編集", "テロップ", "カラーグレーディング"],
    "capacity": 3,
    "current_load": 2,
    "notes": "対談動画が得意",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-03-01T00:00:00"
  }
]
```

---

### GET `/api/editors/{editor_id}`

特定編集者を取得。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `editor_id` | int | 編集者ID |

**レスポンス例** (200 OK): 編集者オブジェクト（上記と同形式）

**エラー例** (404):
```json
{"detail": "Editor not found"}
```

---

### POST `/api/editors`

編集者を新規登録。

**リクエストボディ**: `EditorCreate`

```json
{
  "name": "鈴木カメラマン",
  "contact_info": "suzuki@example.com",
  "contract_type": "freelance",
  "specialties": ["カット編集", "SE追加"],
  "capacity": 5,
  "notes": "納期厳守。週3稼働。"
}
```

**レスポンス例** (200 OK):
```json
{"message": "created", "id": 2}
```

---

### PUT `/api/editors/{editor_id}`

編集者情報を更新。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `editor_id` | int | 編集者ID |

**リクエストボディ**: `EditorUpdate`（全フィールドOptional）

```json
{
  "status": "inactive",
  "notes": "2026-03から一時休止"
}
```

**レスポンス例** (200 OK):
```json
{"message": "updated"}
```

---

### GET `/api/editors/{editor_id}/handover`

編集者引き継ぎパッケージ（F-3）を生成・取得。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `editor_id` | int | 編集者ID |

**レスポンス例** (200 OK):
```json
{
  "editor": {
    "id": 1,
    "name": "田中編集者",
    "specialties": ["カット編集", "テロップ"]
  },
  "assigned_projects": [
    {
      "project_id": "INT_001_Izu",
      "guest_name": "Izu",
      "status": "editing",
      "direction_report_url": "https://..."
    }
  ],
  "skill_summary": {
    "telop": 4.2,
    "cut": 3.8,
    "color": 3.0
  },
  "handover_notes": "現在2件担当中。INT_001は3/20締め切り。",
  "generated_at": "2026-03-15T10:00:00"
}
```

---

## 7. 映像トラッキング

### GET `/api/tracking/videos`

トラッキング対象映像の一覧を取得。

**クエリパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `status` | string (optional) | `pending` / `analyzed` / `error` でフィルタ |

**レスポンス例** (200 OK):
```json
[
  {
    "id": 1,
    "url": "https://www.youtube.com/watch?v=xxxx",
    "title": "参考動画：Aチャンネル対談",
    "tags": ["対談", "カット割り参考"],
    "status": "analyzed",
    "metadata": {
      "duration_seconds": 2340,
      "view_count": 152000,
      "like_count": 8700
    },
    "analysis_result": null,
    "added_at": "2026-03-10T12:00:00",
    "analyzed_at": "2026-03-10T12:05:00"
  }
]
```

---

### GET `/api/tracking/videos/{video_id}`

特定トラッキング映像を取得。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `video_id` | int | 映像ID |

**レスポンス例** (200 OK): 映像オブジェクト（上記と同形式）

---

### POST `/api/tracking/videos`

トラッキング映像を追加（yt-dlpでメタデータ取得）。

**リクエストボディ**: `TrackingVideoAdd`

```json
{
  "url": "https://www.youtube.com/watch?v=xxxx",
  "tags": ["対談", "カット割り参考", "高品質"]
}
```

**レスポンス例** (200 OK):
```json
{"message": "added", "id": 1}
```

---

### POST `/api/tracking/videos/{video_id}/analyze`

トラッキング映像の分析を実行。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `video_id` | int | 映像ID |

**パラメータ**: なし（リクエストボディ不要）

**レスポンス例** (200 OK):
```json
{
  "message": "analyzed",
  "result": {
    "cut_rhythm": "fast",
    "avg_cut_duration_sec": 4.2,
    "telop_density": "high",
    "color_grade": "warm",
    "quality_elements": ["カット割りのテンポが良い", "テロップが読みやすい"]
  }
}
```

---

### DELETE `/api/tracking/videos/{video_id}`

トラッキング映像を削除。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `video_id` | int | 映像ID |

**レスポンス例** (200 OK):
```json
{"message": "deleted"}
```

---

## 8. 学習・インサイト

### GET `/api/tracking/insights`

映像分析結果とフィードバック学習を統合したインサイト一覧を取得。

**パラメータ**: なし

**レスポンス例** (200 OK):
```json
{
  "video_insights": [
    {
      "pattern": "冒頭3秒以内にゲスト顔ドアップ",
      "frequency": 8,
      "quality_impact": "high",
      "source": "tracking"
    }
  ],
  "feedback_insights": [
    {
      "category": "telop",
      "pattern": "テロップが小さすぎる指摘",
      "frequency": 12,
      "applied_rule": "最小フォントサイズ16px"
    }
  ],
  "combined_recommendations": [
    "冒頭3秒以内にゲスト顔ドアップで視聴継続率UP",
    "テロップは16px以上でモバイル視認性確保"
  ]
}
```

---

### GET `/api/learning/feedback-patterns`

フィードバック学習パターン一覧を取得。

**クエリパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `category` | string (optional) | `telop` / `cut` / `audio` / `color` 等でフィルタ |

**レスポンス例** (200 OK):
```json
[
  {
    "id": 1,
    "category": "telop",
    "pattern": "フォントサイズ不足",
    "rule": "最小フォントサイズを16pxに設定する",
    "trigger_count": 12,
    "is_active": true,
    "created_at": "2026-03-05T00:00:00"
  }
]
```

---

### GET `/api/learning/summary`

学習状況の全体サマリーを取得。

**パラメータ**: なし

**レスポンス例** (200 OK):
```json
{
  "total_patterns": 24,
  "active_patterns": 20,
  "patterns_by_category": {
    "telop": 8,
    "cut": 6,
    "audio": 5,
    "color": 3,
    "other": 2
  },
  "most_triggered_pattern": "フォントサイズ不足",
  "last_updated": "2026-03-15T08:00:00"
}
```

---

## 9. 巡回監査

### GET `/api/audit/latest`

最新の監査レポートを取得。

**パラメータ**: なし

**レスポンス例** (200 OK):
```json
{
  "id": 5,
  "run_at": "2026-03-15T09:00:00",
  "status": "ok",
  "db_status": "connected",
  "api_status": "responding",
  "quality_warnings": [],
  "stale_projects": [
    {
      "project_id": "INT_010_RYO",
      "last_updated_days_ago": 14,
      "status": "editing"
    }
  ],
  "unsent_feedback_count": 3,
  "summary": "全体正常。1件の滞留案件あり。"
}
```

---

### POST `/api/audit/run`

手動で監査を実行。

**パラメータ**: なし（リクエストボディ不要）

**レスポンス例** (200 OK):
```json
{
  "message": "audit completed",
  "result": {
    "status": "ok",
    "warnings": 0,
    "stale_count": 1
  }
}
```

---

### GET `/api/audit/history`

監査履歴を取得。

**クエリパラメータ**:
| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `limit` | int | 10 | 取得件数 |

**レスポンス例** (200 OK):
```json
[
  {
    "id": 5,
    "run_at": "2026-03-15T09:00:00",
    "status": "ok",
    "quality_warnings": 0,
    "stale_projects": 1
  },
  {
    "id": 4,
    "run_at": "2026-03-14T09:00:00",
    "status": "warning",
    "quality_warnings": 2,
    "stale_projects": 0
  }
]
```

---

## 10. 通知設定

### GET `/api/notifications/config`

現在の通知設定を取得。

**パラメータ**: なし

**レスポンス例** (200 OK):
```json
{
  "telegram_enabled": true,
  "telegram_bot_token": "xxx...（マスク済み）",
  "telegram_chat_id": "123456789",
  "line_enabled": false,
  "line_channel_token": null,
  "line_user_id": null,
  "notify_on_report": true,
  "notify_on_quality_warning": true,
  "notify_on_feedback": false
}
```

---

### PUT `/api/notifications/config`

通知設定を更新。

**リクエストボディ**: `NotificationConfigUpdate`（全フィールドOptional）

```json
{
  "telegram_enabled": true,
  "telegram_bot_token": "1234567890:ABCDEFxxxxxx",
  "telegram_chat_id": "987654321",
  "notify_on_report": true,
  "notify_on_quality_warning": true,
  "notify_on_feedback": false
}
```

**レスポンス例** (200 OK):
```json
{"message": "updated"}
```

---

### POST `/api/notifications/test`

テスト通知を送信。

**パラメータ**: なし（リクエストボディ不要）

**レスポンス例** (200 OK):
```json
{
  "message": "test notification sent",
  "channels": {
    "telegram": "ok",
    "line": "disabled"
  }
}
```

**エラー例** (500):
```json
{
  "message": "test notification failed",
  "channels": {
    "telegram": "error: Bot token invalid"
  }
}
```

---

## 11. PDCAループ

### GET `/api/pdca/states`

PDCA状態一覧を取得。

**クエリパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `phase` | string (optional) | `plan` / `do` / `check` / `act` でフィルタ |

**レスポンス例** (200 OK):
```json
[
  {
    "project_id": "INT_001_Izu",
    "phase": "check",
    "plan_summary": "テロップサイズ改善、BGM調整",
    "do_summary": "修正版 v2 完成",
    "check_result": "テロップ改善確認。BGMは再修正必要。",
    "act_summary": null,
    "updated_at": "2026-03-14T15:00:00"
  }
]
```

---

### GET `/api/pdca/states/{project_id}`

特定プロジェクトのPDCA状態を取得。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `project_id` | string | プロジェクトID |

**レスポンス例** (200 OK): PDCA状態オブジェクト（上記と同形式）

---

### GET `/api/pdca/summary`

PDCA全体サマリーを取得。

**パラメータ**: なし

**レスポンス例** (200 OK):
```json
{
  "total": 62,
  "by_phase": {
    "plan": 5,
    "do": 8,
    "check": 3,
    "act": 2,
    "completed": 44
  },
  "average_cycle_days": 6.3,
  "bottleneck_phase": "do"
}
```

---

## 12. 分散処理

### GET `/api/distributed/macs`

登録済みリモートMac一覧を取得。

**パラメータ**: なし

**レスポンス例** (200 OK):
```json
[
  {
    "id": "mac-mini-m4",
    "hostname": "192.168.1.100",
    "status": "online",
    "last_seen": "2026-03-15T09:58:00",
    "capabilities": ["xcodebuild", "python3", "ffmpeg"]
  },
  {
    "id": "macbook-pro",
    "hostname": "192.168.1.101",
    "status": "offline",
    "last_seen": "2026-03-14T23:00:00",
    "capabilities": ["python3"]
  }
]
```

---

### POST `/api/distributed/macs/check`

全リモートMacの死活確認を実行（SSH経由）。

**パラメータ**: なし（リクエストボディ不要）

**レスポンス例** (200 OK):
```json
{
  "checked": 2,
  "online": 1,
  "offline": 1,
  "results": {
    "mac-mini-m4": "online",
    "macbook-pro": "offline"
  }
}
```

---

## 13. フィードバック変換

### POST `/api/feedback/convert`

音声フィードバックのテキストをプロのディレクション指示に変換（Claude API使用）。

**リクエストボディ**: `FeedbackConvertRequest`

```json
{
  "raw_text": "なんかここのカット、ちょっとテンポ悪い気がする",
  "project_id": "INT_001_Izu"
}
```

**レスポンス例** (200 OK):
```json
{
  "converted_text": "該当シーンのカット間隔を短縮し、テンポを改善してください。具体的には、各カットの冒頭0.3〜0.5秒をカットして間を詰め、映像のリズムを上げてください。視聴者がテンポの悪さを感じないよう、次のカットへの移行をスムーズにすることを意識してください。",
  "category": "cut",
  "priority": "medium",
  "model_used": "claude-sonnet-4"
}
```

**フォールバック動作**: Claude APIが利用不可の場合、`raw_text` をそのまま返す。

---

## 14. 同期チェック

### GET `/api/projects/{project_id}/sync-check`

クライアント側ポーリング用の同期チェック。プロジェクトの更新タイムスタンプを返す。

**パスパラメータ**:
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `project_id` | string | プロジェクトID |

**レスポンス例** (200 OK):
```json
{
  "project_id": "INT_001_Izu",
  "updated_at": "2026-03-15T09:30:00",
  "has_unsent_feedback": false,
  "unreviewed_count": 0
}
```

> **用途**: クライアントが15秒ごとにポーリングし、`updated_at` の変化を検知してデータを再取得する。

---

## 15. Pydanticモデル一覧

### ProjectCreate

| フィールド | 型 | 必須 | デフォルト | 説明 |
|-----------|-----|------|-----------|------|
| `id` | string | ✓ | - | プロジェクトID（例: `INT_001_Izu`） |
| `guest_name` | string | ✓ | - | ゲスト名 |
| `title` | string | ✓ | - | 動画タイトル |
| `status` | string | - | `"directed"` | ステータス |
| `shoot_date` | string | - | null | 撮影日（YYYY-MM-DD） |
| `guest_age` | int | - | null | ゲスト年齢 |
| `guest_occupation` | string | - | null | ゲスト職業 |
| `quality_score` | int | - | null | 品質スコア（0-100） |
| `direction_report_url` | string | - | null | ディレクションレポートURL |
| `source_video` | dict | - | null | 素材動画情報 |
| `edited_video` | dict | - | null | 編集後動画情報 |
| `feedback_summary` | dict | - | null | フィードバックサマリー |
| `knowledge` | dict | - | null | ナレッジデータ |

### YouTubeAssetsUpsert

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `thumbnail_design` | dict | - | Z型サムネイル指示書（zone_a〜d） |
| `title_proposals` | dict | - | タイトル案一覧（candidates配列） |
| `description_original` | string | - | AI生成の概要欄原文 |
| `description_edited` | string | - | 人間が編集した概要欄 |
| `selected_title_index` | int | - | 選択したタイトル案のインデックス |
| `edited_title` | string | - | 手動編集後のタイトル |
| `last_edited_by` | string | - | 最終編集者名 |

### DescriptionUpdate

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `edited` | string | ✓ | 編集済み概要欄テキスト |
| `by` | string | ✓ | 編集者名 |

### TitleSelect

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `index` | int | ✓ | 選択タイトル案のインデックス |
| `edited_title` | string | - | 手動編集後のタイトル |
| `by` | string | ✓ | 操作者名 |

### FeedbackCreate

| フィールド | 型 | 必須 | デフォルト | 説明 |
|-----------|-----|------|-----------|------|
| `timestamp_mark` | string | - | null | タイムスタンプ（例: `"03:24"`） |
| `raw_voice_text` | string | - | null | 音声認識テキスト（変換前） |
| `converted_text` | string | - | null | Claude変換後のディレクション指示 |
| `category` | string | - | null | カテゴリ（`telop`/`cut`/`audio`/`color`等） |
| `priority` | string | - | `"medium"` | 優先度（`low`/`medium`/`high`） |
| `created_by` | string | - | null | 作成者名 |

### EditorCreate

| フィールド | 型 | 必須 | デフォルト | 説明 |
|-----------|-----|------|-----------|------|
| `name` | string | ✓ | - | 編集者名 |
| `contact_info` | string | - | `""` | 連絡先 |
| `contract_type` | string | - | `"freelance"` | 契約形態 |
| `specialties` | list | - | `[]` | 専門スキル一覧 |
| `capacity` | int | - | 3 | 最大同時担当案件数 |
| `notes` | string | - | `""` | 備考 |

### EditorUpdate

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `name` | string (Optional) | 編集者名 |
| `contact_info` | string (Optional) | 連絡先 |
| `status` | string (Optional) | `active` / `inactive` |
| `contract_type` | string (Optional) | 契約形態 |
| `specialties` | list (Optional) | 専門スキル一覧 |
| `capacity` | int (Optional) | 最大同時担当件数 |
| `notes` | string (Optional) | 備考 |

### TrackingVideoAdd

| フィールド | 型 | 必須 | デフォルト | 説明 |
|-----------|-----|------|-----------|------|
| `url` | string | ✓ | - | YouTubeまたはVimeo URL |
| `tags` | list | - | `[]` | タグ一覧 |

### NotificationConfigUpdate

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `telegram_enabled` | bool (Optional) | Telegram通知を有効化 |
| `telegram_bot_token` | string (Optional) | Telegram Bot Token |
| `telegram_chat_id` | string (Optional) | Telegram Chat ID |
| `line_enabled` | bool (Optional) | LINE通知を有効化 |
| `line_channel_token` | string (Optional) | LINE Channel Access Token |
| `line_user_id` | string (Optional) | LINE User ID |
| `notify_on_report` | bool (Optional) | レポート生成時に通知 |
| `notify_on_quality_warning` | bool (Optional) | 品質警告時に通知 |
| `notify_on_feedback` | bool (Optional) | FB受信時に通知 |

### FeedbackConvertRequest

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `raw_text` | string | ✓ | 変換対象の音声フィードバックテキスト |
| `project_id` | string | ✓ | 対象プロジェクトID |

---

## 16. データベーススキーマ

### projects テーブル

| カラム | 型 | 説明 |
|--------|-----|------|
| `id` | TEXT (PK) | プロジェクトID |
| `guest_name` | TEXT | ゲスト名 |
| `title` | TEXT | 動画タイトル |
| `status` | TEXT | ステータス |
| `shoot_date` | TEXT | 撮影日 |
| `guest_age` | INTEGER | ゲスト年齢 |
| `guest_occupation` | TEXT | ゲスト職業 |
| `quality_score` | INTEGER | 品質スコア（0-100） |
| `has_unsent_feedback` | INTEGER | 未送信FBあり（0/1） |
| `unreviewed_count` | INTEGER | 未確認FB件数 |
| `direction_report_url` | TEXT | ディレクションレポートURL |
| `source_video` | TEXT (JSON) | 素材動画情報 |
| `edited_video` | TEXT (JSON) | 編集後動画情報 |
| `feedback_summary` | TEXT (JSON) | フィードバックサマリー |
| `knowledge` | TEXT (JSON) | ナレッジデータ |
| `created_at` | TEXT | 作成日時 (ISO 8601) |
| `updated_at` | TEXT | 更新日時 (ISO 8601) |

### youtube_assets テーブル

| カラム | 型 | 説明 |
|--------|-----|------|
| `project_id` | TEXT (FK→projects) | プロジェクトID |
| `thumbnail_design` | TEXT (JSON) | Z型サムネイル指示書 |
| `title_proposals` | TEXT (JSON) | タイトル案一覧 |
| `description_original` | TEXT | AI生成概要欄原文 |
| `description_edited` | TEXT | 編集済み概要欄 |
| `description_finalized_at` | TEXT | 概要欄確定日時 |
| `description_finalized_by` | TEXT | 概要欄確定者 |
| `selected_title_index` | INTEGER | 選択タイトル案インデックス |
| `edited_title` | TEXT | 手動編集後タイトル |
| `last_edited_by` | TEXT | 最終編集者名 |
| `generated_at` | TEXT | 生成日時 |
| `updated_at` | TEXT | 更新日時 |

### feedbacks テーブル

| カラム | 型 | 説明 |
|--------|-----|------|
| `id` | INTEGER (PK, AI) | フィードバックID |
| `project_id` | TEXT (FK→projects) | プロジェクトID |
| `timestamp_mark` | TEXT | タイムスタンプ（例: `"03:24"`） |
| `raw_voice_text` | TEXT | 音声認識テキスト（変換前） |
| `converted_text` | TEXT | Claude変換後のディレクション指示 |
| `category` | TEXT | カテゴリ（telop/cut/audio/color等） |
| `priority` | TEXT | 優先度（low/medium/high） |
| `created_by` | TEXT | 作成者名 |
| `is_sent` | INTEGER | 送信済みフラグ（0/1） |
| `editor_status` | TEXT | 編集者確認状態 |
| `learning_effect` | TEXT | 学習効果メモ |
| `created_at` | TEXT | 作成日時 (ISO 8601) |

---

## エンドポイント一覧（早見表）

| # | メソッド | パス | 説明 |
|---|---------|------|------|
| 1 | GET | `/api/health` | ヘルスチェック |
| 2 | GET | `/api/projects` | プロジェクト一覧 |
| 3 | GET | `/api/projects/{project_id}` | プロジェクト取得 |
| 4 | POST | `/api/projects` | プロジェクト作成 |
| 5 | PUT | `/api/projects/{project_id}` | プロジェクト更新 |
| 6 | GET | `/api/projects/{project_id}/youtube-assets` | YouTube素材取得 |
| 7 | PUT | `/api/projects/{project_id}/youtube-assets` | YouTube素材UPSERT |
| 8 | PATCH | `/api/projects/{project_id}/youtube-assets/description` | 概要欄更新 |
| 9 | PATCH | `/api/projects/{project_id}/youtube-assets/title` | タイトル選択 |
| 10 | GET | `/api/projects/{project_id}/feedbacks` | プロジェクト別FB一覧 |
| 11 | POST | `/api/projects/{project_id}/feedbacks` | FB作成+学習投入 |
| 12 | GET | `/api/feedbacks` | 全FB一覧 |
| 13 | GET | `/api/dashboard/summary` | ダッシュボードサマリー |
| 14 | GET | `/api/dashboard/quality-trend` | 品質スコア推移 |
| 15 | GET | `/api/editors` | 編集者一覧 |
| 16 | GET | `/api/editors/{editor_id}` | 編集者取得 |
| 17 | POST | `/api/editors` | 編集者作成 |
| 18 | PUT | `/api/editors/{editor_id}` | 編集者更新 |
| 19 | GET | `/api/editors/{editor_id}/handover` | 引き継ぎパッケージ |
| 20 | GET | `/api/tracking/videos` | トラッキング映像一覧 |
| 21 | GET | `/api/tracking/videos/{video_id}` | トラッキング映像取得 |
| 22 | POST | `/api/tracking/videos` | トラッキング映像追加 |
| 23 | POST | `/api/tracking/videos/{video_id}/analyze` | 映像分析実行 |
| 24 | DELETE | `/api/tracking/videos/{video_id}` | トラッキング映像削除 |
| 25 | GET | `/api/tracking/insights` | 統合インサイト一覧 |
| 26 | GET | `/api/learning/feedback-patterns` | FBパターン一覧 |
| 27 | GET | `/api/learning/summary` | 学習状況サマリー |
| 28 | GET | `/api/audit/latest` | 最新監査レポート |
| 29 | POST | `/api/audit/run` | 手動監査実行 |
| 30 | GET | `/api/audit/history` | 監査履歴 |
| 31 | GET | `/api/notifications/config` | 通知設定取得 |
| 32 | PUT | `/api/notifications/config` | 通知設定更新 |
| 33 | POST | `/api/notifications/test` | テスト通知送信 |
| 34 | GET | `/api/pdca/states` | PDCA状態一覧 |
| 35 | GET | `/api/pdca/states/{project_id}` | プロジェクト別PDCA状態 |
| 36 | GET | `/api/pdca/summary` | PDCAサマリー |
| 37 | GET | `/api/distributed/macs` | リモートMac一覧 |
| 38 | POST | `/api/distributed/macs/check` | リモートMac死活確認 |
| 39 | POST | `/api/feedback/convert` | FB音声→ディレクション変換 |
| 40 | GET | `/api/projects/{project_id}/sync-check` | ポーリング同期チェック |

**合計: 40エンドポイント**
