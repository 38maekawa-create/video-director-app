from __future__ import annotations
"""J-2: スプシ統合 — 【インタビュー対談動画】管理タブとの連携"""

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
try:
    from google.oauth2.service_account import Credentials
    import gspread
except ImportError:  # pragma: no cover - 依存がない環境のテスト実行を許容
    Credentials = None
    gspread = None


# --- MEMBER_MASTER.json別名解決テーブル ---
# canonical_name / aliases / transcription_errors を一括で検索可能にする
_MEMBER_ALIAS_MAP: dict[str, str] | None = None


def _load_member_alias_map() -> dict[str, str]:
    """MEMBER_MASTER.jsonから別名→canonical_nameのマップを構築する（遅延ロード）"""
    global _MEMBER_ALIAS_MAP
    if _MEMBER_ALIAS_MAP is not None:
        return _MEMBER_ALIAS_MAP

    _MEMBER_ALIAS_MAP = {}
    master_path = Path.home() / "TEKO" / "knowledge" / "people" / "MEMBER_MASTER.json"
    if not master_path.exists():
        return _MEMBER_ALIAS_MAP

    try:
        data = json.loads(master_path.read_text(encoding="utf-8"))
        for m in data.get("members", []):
            canonical = m.get("canonical_name", "")
            if not canonical:
                continue
            # canonical_name自身
            _MEMBER_ALIAS_MAP[_normalize_name(canonical)] = canonical
            # aliases
            for alias in m.get("aliases", []):
                _MEMBER_ALIAS_MAP[_normalize_name(alias)] = canonical
            # transcription_errors（文字起こし誤変換）
            for te in m.get("transcription_errors", []):
                _MEMBER_ALIAS_MAP[_normalize_name(te)] = canonical
    except Exception:
        pass

    return _MEMBER_ALIAS_MAP


def _resolve_via_member_master(name: str) -> str | None:
    """MEMBER_MASTER.jsonの別名テーブルでcanonical_nameに解決する"""
    alias_map = _load_member_alias_map()
    normalized = _normalize_name(name)
    return alias_map.get(normalized)


SPREADSHEET_ID = "1bW_qb13p747xoa2yf7RHaccNVTFCMxV8a5CjGdNqI6I"
TAB_NAME = "【インタビュー対談動画】管理"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ヘッダー行はRow 2
HEADER_ROW = 2
# B列（タイトル）のインデックス（1-based）
TITLE_COL = 2


# A列「コンテンツ」値 → プロジェクトカテゴリのマッピング
CONTENT_TO_CATEGORY: dict[str, str] = {
    "対談": "teko_member",
    "オフ会インタビュー": "teko_member",
    "不動産対談": "teko_realestate",
}

# A列のカラムインデックス（1-based）
CONTENT_COL = 1


class SheetsManager:
    """スプレッドシート連携マネージャー"""

    def __init__(self, credentials_path: str | Path = None):
        if credentials_path is None:
            credentials_path = Path.home() / ".config" / "maekawa" / "google-credentials.json"
        self.credentials_path = Path(credentials_path)
        self._client = None
        self._worksheet = None

    def _connect(self):
        """スプレッドシートに接続（lazy）"""
        if self._worksheet is not None:
            return
        if Credentials is None or gspread is None:
            raise ImportError(
                "gspread/google-auth is required for SheetsManager. "
                "Install dependencies before using sheet integration."
            )

        credentials = Credentials.from_service_account_file(
            str(self.credentials_path),
            scopes=SCOPES,
        )
        self._client = gspread.authorize(credentials)
        spreadsheet = self._client.open_by_key(SPREADSHEET_ID)
        self._worksheet = spreadsheet.worksheet(TAB_NAME)

    def get_content_categories(self) -> dict[str, str | None]:
        """A列「コンテンツ」とB列「タイトル」を読み取り、ゲスト名→カテゴリのマッピング辞書を返す。

        Returns:
            dict: ゲスト名(canonical_name or 抽出名) → カテゴリ("teko_member" / "teko_realestate" / None)
        """
        self._connect()
        # A列（コンテンツ）とB列（タイトル）を一括取得
        content_cells = self._worksheet.col_values(CONTENT_COL)
        title_cells = self._worksheet.col_values(TITLE_COL)

        result: dict[str, str | None] = {}
        max_rows = max(len(content_cells), len(title_cells))

        for row_idx in range(HEADER_ROW, max_rows):  # 0-based index, HEADER_ROWは2なのでskip row 1,2
            # A列のコンテンツ値
            content_val = content_cells[row_idx].strip() if row_idx < len(content_cells) else ""
            # B列のタイトル値
            title_val = title_cells[row_idx].strip() if row_idx < len(title_cells) else ""

            if not title_val:
                continue

            # カテゴリを決定
            category = CONTENT_TO_CATEGORY.get(content_val)

            # タイトルからゲスト名を抽出
            guest_names = _extract_names_from_title(title_val)
            for name in guest_names:
                # MEMBER_MASTER.jsonでcanonical_nameに解決
                canonical = _resolve_via_member_master(name)
                key = canonical if canonical else name
                # カテゴリ値がある方を優先（同一ゲストが複数行にある場合）
                # 例: けーさんが「単独インタビュー」(None)と「対談」(teko_member)の両方に存在する場合、teko_memberを採用
                if key not in result or (result[key] is None and category is not None):
                    result[key] = category

        return result

    def find_direction_url_column(self) -> int:
        """ディレクションURL列のインデックス（1-based）を取得。なければ新規作成"""
        self._connect()
        header_row = self._worksheet.row_values(HEADER_ROW)

        # 既存のディレクションURL列を探す
        for i, cell in enumerate(header_row, start=1):
            if "ディレクション" in cell and "URL" in cell:
                return i

        # なければ末尾に新規作成
        new_col = len(header_row) + 1
        self._worksheet.update_cell(HEADER_ROW, new_col, "ディレクションURL")
        return new_col

    def write_direction_url(self, guest_name: str, url: str) -> bool:
        """ゲスト名でマッチングし、対応する行にディレクションURLを書き込む"""
        self._connect()
        url_col = self.find_direction_url_column()

        # B列（タイトル）の全データを取得
        title_cells = self._worksheet.col_values(TITLE_COL)

        # ゲスト名でマッチング
        matched_row = None
        for row_idx, title in enumerate(title_cells, start=1):
            if row_idx <= HEADER_ROW:
                continue
            if _match_guest_name(guest_name, title):
                matched_row = row_idx
                break

        if matched_row is None:
            return False

        # URLを書き込み（既存データは上書きしない → 空セルの場合のみ書き込み）
        existing = self._worksheet.cell(matched_row, url_col).value
        if existing and existing.strip():
            return True  # 既に書き込み済み

        self._worksheet.update_cell(matched_row, url_col, url)
        return True

    def get_all_titles(self) -> list[tuple[int, str]]:
        """全タイトルと行番号のリストを返す"""
        self._connect()
        title_cells = self._worksheet.col_values(TITLE_COL)
        return [
            (row_idx, title)
            for row_idx, title in enumerate(title_cells, start=1)
            if row_idx > HEADER_ROW and title.strip()
        ]


def _normalize_name(name: str) -> str:
    """名前を正規化（敬称除去・全角半角統一・括弧内情報除去・記号除去）"""
    if not name:
        return ""
    name = unicodedata.normalize("NFKC", name)
    # 括弧内の情報を除去（例: "ゲスト氏（里芋、トーマス）" → "ゲスト氏"）
    name = re.sub(r"[（(].+?[）)]", "", name)
    # 敬称を除去（末尾の「さん」「氏」「くん」「ちゃん」）
    name = re.sub(r"(さん|氏|くん|ちゃん|様|先生)$", "", name.strip())
    # よく混ざる接頭語・ノイズを除去
    name = re.sub(r"^(ゲスト|撮影[_\-\s]*)", "", name)
    # 記号を除去（ハイフン・アンダースコア・スペース等）
    name = re.sub(r"[_\-\s・：:]+", "", name)
    # 名前判定に不要な文字を除去
    name = re.sub(r"[^0-9a-zA-Zぁ-んァ-ヶ一-龯ー]", "", name)
    return name.strip().lower()


def _extract_names_from_title(title: str) -> list[str]:
    """スプシタイトルからゲスト名の候補を複数抽出する

    B列のフォーマット例:
    - "INT001_ブンさん"
    - "53.izuさん"
    - "62やーまんさん"  （番号直結・区切り文字なし）
    - "13 ないべいさん"  （番号+スペース）
    - "コテツさん：31歳製造業..."
    - "ゲスト氏（里芋、トーマス）さん：..."
    - "ハオさん：30代前半..."
    - "リール_001_タイトル..."  （リール系 → ゲスト名なし）
    """
    names = []
    title_clean = unicodedata.normalize("NFKC", title.strip())

    # リール系タイトルはゲスト名を含まない → 空で返す
    if re.match(r"^リール[_\-]", title_clean):
        return []

    # 「大阪オフ会」等のイベント名はゲスト名を含まない → 空で返す
    if re.match(r"^大阪オフ会", title_clean):
        return []

    # INT番号形式: "INT001_ブンさん"
    match = re.search(r"INT\d+[_\s]+(.+?)(?:さん|氏|くん|ちゃん)?(?:：|:|$)", title_clean)
    if match:
        names.append(match.group(1).strip())

    # 番号+区切り+名前形式: "53.izuさん", "53_izuさん", "25 けーさん"
    num_match = re.search(r"^\d+[._\s]\s*(.+?)(?:さん|氏|くん|ちゃん)?(?:：|:|$)", title_clean)
    if num_match:
        candidate = num_match.group(1).strip()
        # "y.yさん（2回目）" のようなケースで2回目等をクリーンアップ
        candidate = re.sub(r"[（(].+?[）)]", "", candidate).strip()
        if candidate:
            names.append(candidate)

    # 番号直結+日本語名前形式: "62やーまんさん", "15ソトマさん", "16りつさん"
    # 番号の後に区切り文字なしで日本語（ひらがな・カタカナ・漢字）が続くパターン
    direct_match = re.match(r"^\d+([ぁ-んァ-ヶ一-龯ー].+?)(?:さん|氏|くん|ちゃん|夫妻)?(?:：|:|$)", title_clean)
    if direct_match:
        candidate = direct_match.group(1).strip()
        candidate = re.sub(r"[（(].+?[）)]", "", candidate).strip()
        if candidate:
            names.append(candidate)

    # 番号直結+英語名前形式: 数字の後にアルファベットが続く場合（"14y.yさん"等）
    direct_alpha_match = re.match(r"^\d+([a-zA-Z].+?)(?:さん|氏|くん|ちゃん)?(?:：|:|$)", title_clean)
    if direct_alpha_match:
        candidate = direct_alpha_match.group(1).strip()
        candidate = re.sub(r"[（(].+?[）)]", "", candidate).strip()
        if candidate:
            names.append(candidate)

    # 先頭の名前抽出（括弧・敬称・属性の前まで）
    head_match = re.match(r"(?:INT\d+[_\s]+|\d+[._\s]\s*|\d+)?(.+?)(?:さん|氏)?(?:：|:|[\d０-９])", title_clean)
    if head_match:
        candidate = head_match.group(1).strip()
        if candidate and len(candidate) >= 1:
            names.append(candidate)

    # 「20251123撮影_りょうすけさん...」形式
    shot_match = re.search(r"(?:^|\D)\d{8}撮影[_\s]*([^\d：:]+?)(?:さん|氏|様|くん|ちゃん)?(?:[：:]|$|\d)", title_clean)
    if shot_match:
        names.append(shot_match.group(1).strip())

    # 括弧内の別名も候補に追加（例: "ゲスト氏（里芋、トーマス）"）
    paren_match = re.search(r"[（(](.+?)[）)]", title_clean)
    if paren_match:
        paren_content = paren_match.group(1)
        # 「2回目」等の回数表記は名前ではない
        if not re.match(r"^\d+回目$", paren_content.strip()):
            # カンマ・読点で分割して各名前を候補に
            for alias in re.split(r"[、,]", paren_content):
                alias = alias.strip()
                if alias and len(alias) >= 2:
                    names.append(alias)

    # タイトル先頭セグメントからフォールバック抽出
    first_segment = re.split(r"[：:|]", title_clean, maxsplit=1)[0].strip()
    first_segment = re.sub(r"^(?:INT\d+[_\s]+|\d+[._\s]\s*|\d+)", "", first_segment, flags=re.IGNORECASE)
    first_segment = re.sub(r"^\d{8}撮影[_\s]*", "", first_segment)
    first_segment = re.sub(r"(さん|氏|くん|ちゃん|様|先生|夫妻).*$", "", first_segment).strip()
    if first_segment:
        names.append(first_segment)

    deduped = []
    seen = set()
    for n in names:
        norm = _normalize_name(n)
        if not norm or norm in seen:
            continue
        # 数字だけのゴミエントリをフィルタリング（"1", "2", "62" 等）
        if re.fullmatch(r"\d+", norm):
            continue
        # 1文字だけのアルファベット（"h", "K", "N" 等）をフィルタリング
        if re.fullmatch(r"[a-z]", norm):
            continue
        # "INT" はスプシのINT番号プレフィックスの残骸で名前ではない
        if norm == "int":
            continue
        seen.add(norm)
        deduped.append(n.strip())
    return deduped


def _match_guest_name(guest_name: str, sheet_title: str) -> bool:
    """ゲスト名がスプシのタイトル（B列）とマッチするか判定

    B列の例: "INT001_ブンさん", "INT015_Izuさん"
    guest_name: "Izu", "ブン", etc.

    マッチング戦略:
    1. 正規化後の完全一致
    2. スプシタイトルから複数名前候補を抽出 → 完全一致
    3. 正規化後の部分一致（2文字以上）
    4. ひらがな/カタカナ変換後のマッチ
    """
    if not sheet_title or not guest_name:
        return False

    name_normalized = _normalize_name(guest_name)
    if not name_normalized:
        return False

    # スプシタイトルから名前候補を抽出
    title_names = _extract_names_from_title(sheet_title)

    # 戦略0: MEMBER_MASTER.jsonの別名解決によるマッチング
    # ゲスト名とタイトル内名前候補の両方をcanonical_nameに解決して比較
    guest_canonical = _resolve_via_member_master(guest_name)
    if guest_canonical:
        for title_name in title_names:
            title_canonical = _resolve_via_member_master(title_name)
            if title_canonical and _normalize_name(guest_canonical) == _normalize_name(title_canonical):
                return True

    # 戦略1: 正規化後の完全一致
    for title_name in title_names:
        if _normalize_name(title_name) == name_normalized:
            return True

    # 戦略2: ひらがな↔カタカナ変換後の完全一致
    name_hiragana = _to_hiragana(name_normalized)
    name_katakana = _to_katakana(name_normalized)
    for title_name in title_names:
        tn = _normalize_name(title_name)
        tn_hira = _to_hiragana(tn)
        tn_kata = _to_katakana(tn)
        if name_hiragana and (name_hiragana == tn_hira or name_hiragana == tn_kata):
            return True
        if name_katakana and (name_katakana == tn_hira or name_katakana == tn_kata):
            return True

    # 戦略3: 候補名同士の部分一致（2文字以上）
    for title_name in title_names:
        tn = _normalize_name(title_name)
        if _is_partial_match(name_normalized, tn):
            return True

    # 戦略4: 正規化後の部分一致（タイトル全体）
    title_normalized = _normalize_name(sheet_title)
    if _is_partial_match(name_normalized, title_normalized):
        return True

    # ひらがな/カタカナ変換後の部分一致
    title_hira = _to_hiragana(title_normalized)
    if _is_partial_match(name_hiragana, title_hira):
        return True

    # 戦略5: ローマ字↔ひらがな変換によるマッチング
    # ゲスト名がローマ字の場合 → ひらがなに変換してマッチ
    name_from_romaji = _romaji_to_hiragana(name_normalized)
    if name_from_romaji:
        for title_name in title_names:
            tn = _normalize_name(title_name)
            tn_hira = _to_hiragana(tn)
            if name_from_romaji == tn_hira or _is_partial_match(name_from_romaji, tn_hira):
                return True
        if _is_partial_match(name_from_romaji, title_hira):
            return True

    # タイトルから抽出した名前がローマ字の場合 → ひらがなに変換してゲスト名とマッチ
    for title_name in title_names:
        tn = _normalize_name(title_name)
        tn_from_romaji = _romaji_to_hiragana(tn)
        if tn_from_romaji:
            if name_hiragana and (name_hiragana == tn_from_romaji or _is_partial_match(name_hiragana, tn_from_romaji)):
                return True
            if name_katakana and _to_katakana(tn_from_romaji) == name_katakana:
                return True

    return False


def _is_partial_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True

    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    min_len = 2 if re.search(r"[ぁ-んァ-ヶ一-龯]", shorter) else 3
    if len(shorter) < min_len:
        return False

    if shorter in longer or longer in shorter:
        return True

    # スペルゆれ向けの緩やかな類似判定（短すぎる名前には適用しない）
    if len(shorter) >= 4:
        ratio = SequenceMatcher(None, shorter, longer).ratio()
        if ratio >= 0.82:
            return True
    return False


def _to_hiragana(text: str) -> str:
    """カタカナをひらがなに変換"""
    return "".join(
        chr(ord(c) - 0x60) if "\u30A1" <= c <= "\u30F6" else c
        for c in text
    )


def _to_katakana(text: str) -> str:
    """ひらがなをカタカナに変換"""
    return "".join(
        chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c
        for c in text
    )


# ローマ字→ひらがな変換テーブル（ヘボン式ベース + よくある綴り）
_ROMAJI_TO_HIRAGANA = {
    "sha": "しゃ", "shi": "し", "shu": "しゅ", "sho": "しょ",
    "cha": "ちゃ", "chi": "ち", "chu": "ちゅ", "cho": "ちょ",
    "tsu": "つ", "fu": "ふ",
    "kya": "きゃ", "kyu": "きゅ", "kyo": "きょ",
    "nya": "にゃ", "nyu": "にゅ", "nyo": "にょ",
    "hya": "ひゃ", "hyu": "ひゅ", "hyo": "ひょ",
    "mya": "みゃ", "myu": "みゅ", "myo": "みょ",
    "rya": "りゃ", "ryu": "りゅ", "ryo": "りょ",
    "gya": "ぎゃ", "gyu": "ぎゅ", "gyo": "ぎょ",
    "bya": "びゃ", "byu": "びゅ", "byo": "びょ",
    "pya": "ぴゃ", "pyu": "ぴゅ", "pyo": "ぴょ",
    "ja": "じゃ", "ji": "じ", "ju": "じゅ", "jo": "じょ",
    "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ",
    "sa": "さ", "si": "し", "su": "す", "se": "せ", "so": "そ",
    "ta": "た", "ti": "ち", "tu": "つ", "te": "て", "to": "と",
    "na": "な", "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の",
    "ha": "は", "hi": "ひ", "hu": "ふ", "he": "へ", "ho": "ほ",
    "ma": "ま", "mi": "み", "mu": "む", "me": "め", "mo": "も",
    "ya": "や", "yu": "ゆ", "yo": "よ",
    "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ",
    "wa": "わ", "wi": "ゐ", "we": "ゑ", "wo": "を",
    "ga": "が", "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご",
    "za": "ざ", "zi": "じ", "zu": "ず", "ze": "ぜ", "zo": "ぞ",
    "da": "だ", "di": "ぢ", "du": "づ", "de": "で", "do": "ど",
    "ba": "ば", "bi": "び", "bu": "ぶ", "be": "べ", "bo": "ぼ",
    "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ",
    "a": "あ", "i": "い", "u": "う", "e": "え", "o": "お",
    "n": "ん",
}


def _romaji_to_hiragana(text: str) -> str:
    """ローマ字文字列をひらがなに変換する（ベストエフォート）

    完全な変換は不要。マッチング用途なので「hirai」→「ひらい」レベルで十分。
    促音（っ）、長音（ー）にも対応。
    """
    if not text:
        return ""
    text = text.lower().strip()
    # 全角英数を半角に
    text = unicodedata.normalize("NFKC", text)

    # 英字のみの文字列でなければ変換不要（既にひらがな/カタカナを含む場合）
    if not re.fullmatch(r"[a-z\-]+", text):
        return ""

    result = []
    i = 0
    while i < len(text):
        # 促音: 子音の連続（nn以外）
        if i + 1 < len(text) and text[i] == text[i + 1] and text[i] not in "aeioun":
            result.append("っ")
            i += 1
            continue

        matched = False
        # 長いパターンから優先マッチ（3文字 → 2文字 → 1文字）
        for length in (3, 2, 1):
            chunk = text[i:i + length]
            if chunk in _ROMAJI_TO_HIRAGANA:
                result.append(_ROMAJI_TO_HIRAGANA[chunk])
                i += length
                matched = True
                break

        if not matched:
            # 変換できない文字はスキップ（ハイフン等）
            i += 1

    return "".join(result)
