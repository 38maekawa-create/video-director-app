# タスク指示書: AI開発10 Phase 3 — OpenCV/FFmpeg実連携

## 目的
Phase 2 Tier 1で実装したテキスト中心機能を、実動画入力（mp4/mov）に接続する。
本フェーズでは OpenCV + FFmpeg を中核に、以下3機能を実運用可能な形で実装する。

- C-1: フレーム画像評価（代表フレーム抽出と品質指標化）
- C-2: テロップ自動チェック（OCR前処理を含む）
- C-3: 音声品質評価（ラウドネス・ノイズ・BGM/会話バランス）

## Phase 2完了状況の確認（PROGRESS.md反映）
- 2026-03-10時点で Phase 2 Tier 1（E-1改 / NEW-2 / NEW-3）は完了、全124テストパス。
- C-1/C-2/C-3は未実装で、`PROGRESS.md`上でも「opencv/ffmpeg依存」として後続扱い。
- `requirements.txt`にはOpenCV系依存が未導入（コメントのみ）。
- Python 3.9 EOL警告が既知課題。OpenCV系実装前に Python 3.11+ へ更新が前提。

## スコープ
### 対象
- 実動画ファイルを入力にした解析パイプライン（ローカル実行）
- `src/video_direction/evaluator/` 配下への実装
- テスト（ユニット + 小規模統合）

### 非対象
- Dropbox/Vimeoからの動画取得自動化（別タスク）
- GPU最適化
- 大規模分散処理

## 技術選定
### 1) 動画・音声処理基盤
- FFmpeg CLI（必須）
  - 理由: デコード安定性、メタデータ取得、音声解析フィルタが豊富
  - 利用: `ffprobe`で情報取得、`ffmpeg`で抽出/解析
- OpenCV (`opencv-python-headless`)
  - 理由: フレーム読取・画像前処理をPythonで完結
  - GUI不要のためheadlessを採用

### 2) OCR
- 第一候補: `pytesseract` + `tesseract`本体（ja + eng）
  - 理由: 実績が多く、導入難易度が低い
- 代替候補: EasyOCR（tesseract精度不足時）
  - 初期実装は採用しない（依存が重いため）

### 3) 数値演算・信号処理
- `numpy`（必須）
- `scipy`（任意、ノイズ指標の高度化時）

### 4) 依存関係（案）
- Python package:
  - `opencv-python-headless>=4.10`
  - `numpy>=1.26`
  - `pytesseract>=0.3.10`
- System package:
  - `ffmpeg`（6系以上推奨）
  - `tesseract` + 言語データ（`jpn`, `eng`）

## 実装方針
### 設計原則
- 「抽出」と「評価」を分離する。
  - 抽出層: フレーム列・音声特徴を生成
  - 評価層: スコア計算・FB文生成
- 外部コマンドは薄いラッパー経由で実行し、例外を握り潰さない。
- 失敗時は「理由付きで劣化実行」し、レポートに欠損を明記する。

### 追加モジュール
- `src/video_direction/evaluator/video_probe.py`
  - `ffprobe`でfps, duration, resolution, audio有無を取得
- `src/video_direction/evaluator/frame_evaluator.py`
  - 代表フレーム抽出（均等間隔 + シーン変化補正）
  - 画質指標（露出、ブレ、コントラスト、構図近似）
- `src/video_direction/evaluator/telop_checker.py`
  - テロップ領域候補抽出（下帯優先）
  - OCR前処理（2値化、ノイズ除去、拡大）
  - 誤字候補・統一性チェック（フォント/サイズは近似指標）
- `src/video_direction/evaluator/audio_evaluator.py`
  - LUFS/ピーク、無音率、ノイズ床、会話帯域エネルギー比を算出
- `src/video_direction/evaluator/quality_scorer.py`
  - C-1/C-2/C-3の結果を受け取り、B-1の映像・音声要素へ反映

## 実装順序
1. **Step 0: 実行基盤整備（最優先）**
- Python 3.11+環境の確認
- `ffmpeg -version`, `ffprobe -version`, `tesseract --version`をCI/ローカルで検証
- 依存追加とimport健全性テスト作成

2. **Step 1: `video_probe.py`（全機能の土台）**
- メタデータ取得APIを実装
- 破損ファイル/音声なし動画のエラーハンドリング定義

3. **Step 2: `audio_evaluator.py`（C-3先行）**
- FFmpegフィルタで数値抽出（例: loudnorm, astats, silencedetect）
- ノイズ・音量・会話バランスの基礎スコア実装
- NEW-3へ連携できる出力スキーマを固定

4. **Step 3: `frame_evaluator.py`（C-1）**
- OpenCVで代表フレーム抽出
- 露出・ブレ・画面密度等の画質指標を実装
- LLM評価連携はオプション化（APIキーなしでもスコア計算継続）

5. **Step 4: `telop_checker.py`（C-2）**
- OCR前処理 + OCR実行
- 文字起こし/想定テキストとの差分検出
- 誤字候補、表記揺れ、表示時間不足を指摘

6. **Step 5: `quality_scorer.py`統合（B-1拡張）**
- 既存のテキスト評価に映像/音声評価を統合
- 7要素スコアの最終版に更新

7. **Step 6: `post_edit_feedback.py`統合**
- NEW-3のFB文生成にC-1/C-2/C-3結果を反映
- HTML出力項目を最小限拡張

## 検証方法
### 1) ユニットテスト
- `tests/test_video_probe.py`
  - 正常動画/音声なし/破損ファイルでの挙動
- `tests/test_audio_evaluator.py`
  - 音量極端ケース、無音区間、ノイズ混入ケース
- `tests/test_frame_evaluator.py`
  - フレーム抽出件数、指標範囲、例外処理
- `tests/test_telop_checker.py`
  - OCR前処理、誤字検出、閾値判定
- `tests/test_quality_scorer.py`
  - 7要素統合後の重み反映

### 2) 統合テスト
- `tests/test_integration_video_pipeline.py` を追加し、1動画を入力にC-1/C-2/C-3を一気通貫で実行
- 生成JSON/レポートのスキーマ検証

### 3) 回帰テスト
- 既存124テストが全て通ること
- Phase 2 Tier 1機能（clip/highlight/post_edit）の出力互換性確認

### 4) 実データ検証
- 最低3本（短尺1, 中尺1, ノイズ多め1）で手動評価と自動評価の乖離を確認
- 乖離が大きい指標は閾値・重みを調整

## 完了条件（DoD）
1. C-1/C-2/C-3が実動画ファイル入力で動作する
2. `quality_scorer.py`が映像/音声要素を含む7要素を出力する
3. NEW-3レポートに映像/音声由来の改善提案が含まれる
4. 新規テスト + 既存テストがすべてパスする
5. 失敗ケース（ffmpeg不在、OCR失敗、音声なし）で明示的エラーまたは劣化実行が行われる

## リスクと対策
1. **Pythonバージョン不整合**
- 対策: Phase 3開始前に3.11+固定、CIも同一化

2. **OCR精度不足（日本語テロップ）**
- 対策: 前処理を強化し、必要時のみEasyOCRを追加

3. **動画入力品質のばらつき**
- 対策: `video_probe`で解像度/FPSに応じて閾値を動的調整

4. **実行時間増大**
- 対策: 代表フレーム数上限、音声解析サンプリング間引き

## 実装開始時チェックリスト
- [ ] Python 3.11+ で `pytest` 実行可能
- [ ] `ffmpeg`, `ffprobe`, `tesseract` がPATH上に存在
- [ ] サンプル動画3本を `tests/fixtures/video/` に配置
- [ ] 失敗系テスト（依存欠落・破損動画）を先に作成

