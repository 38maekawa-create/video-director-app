# 映像エージェント部署（AI開発10）

## 部署概要

TEKO対談動画29件のディレクションレポート・タイトル・概要欄・サムネ指示書を自動生成する映像エージェント部署。
Python APIサーバー（FastAPI）+ iOS SwiftUIアプリ（TestFlight配布）で構成。

> 🔴 **二層構造で運用（2026-04-15確定）**
> - **層1（Python）**: 29件一括バッチ・launchd常駐API・ルールベース分類・DB/API/iOS連携
> - **層2（Claude Code兵隊）**: 個別QC・概要欄修正・バグ修正・品質パターン発見
> - 詳細: SYSTEM_SPEC.md

## .claude/ 品質基準・ワークフロー

品質基準と開発ルールは `.claude/` に一元化。兵隊もPythonバッチも同じ正本を参照する。

```
.claude/
├── rules/                          ← 自動ロード（常に参照される）
│   ├── quality-judgment-guide.md   ← symlink → docs/QUALITY_JUDGMENT_GUIDE.md（品質基準の正本）
│   ├── codebase-rules.md           ← LLM呼び出し・FB承認・設計確定事項
│   └── naming-rules.md             ← Drive素材C番号ルール・出力先ルール
└── skills/
    └── video-qc/SKILL.md           ← /video-qc で個別動画の品質チェック+修正
```

## AI開発5（動画ナレッジシステム）との連携
- AI開発5はカメラマンがGoogleドライブにアップした動画を自動処理（文字起こし → LLM整形 → スプシ更新）
- 本システムはAI開発5の処理済みデータを受け取り、ディレクションレポートを生成
- ナレッジパス: `~/TEKO/knowledge/raw-data/video_transcripts/`

## 言語ルール
- 常に日本語で応答すること
- コード内のコメントも日本語で書くこと
- 変数名・関数名は英語のままでOK

## セキュリティ
- 外部APIのレート制限を遵守すること
- 取得したデータは `~/TEKO/knowledge/raw-data/video-direction/` に格納（生データ格納プロトコル準拠）
- 外部サービスの認証情報は `.env` で管理し、gitには含めない
- スクレイピングは行わない。公式APIのみを使用すること

## 生データ格納先
`~/TEKO/knowledge/raw-data/video-direction/`
