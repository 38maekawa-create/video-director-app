#!/usr/bin/env python3
"""
Video Director Agent アプリアイコン生成スクリプト

デザイン: ダークネイビー背景 + カチンコ風アイコン + 赤アクセント (Netflix風)
Pillowのみで描画。外部画像ファイル不要。
"""

import json
import math
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow がインストールされていません。インストールします...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageDraw, ImageFont


# --- カラー定義 ---
BG_COLOR = (26, 26, 46)        # #1a1a2e ダークネイビー
ACCENT_RED = (229, 9, 20)      # #E50914 Netflix赤
WHITE = (255, 255, 255)
LIGHT_GRAY = (200, 200, 210)
DARK_GRAY = (40, 40, 60)
BOARD_COLOR = (45, 45, 70)     # カチンコ本体


def draw_rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    """角丸矩形を描画"""
    x0, y0, x1, y1 = xy
    r = radius
    # 四隅の円弧
    draw.pieslice([x0, y0, x0 + 2*r, y0 + 2*r], 180, 270, fill=fill, outline=outline, width=width)
    draw.pieslice([x1 - 2*r, y0, x1, y0 + 2*r], 270, 360, fill=fill, outline=outline, width=width)
    draw.pieslice([x0, y1 - 2*r, x0 + 2*r, y1], 90, 180, fill=fill, outline=outline, width=width)
    draw.pieslice([x1 - 2*r, y1 - 2*r, x1, y1], 0, 90, fill=fill, outline=outline, width=width)
    # 中央の矩形
    draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
    draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)


def generate_icon(size=1024):
    """アプリアイコンを生成する"""
    img = Image.new("RGBA", (size, size), BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)

    s = size  # ショートハンド
    margin = int(s * 0.12)

    # --- 背景のグラデーション風効果（微細な放射状グラデーション）---
    center_x, center_y = s // 2, int(s * 0.55)
    max_radius = int(s * 0.6)
    for r in range(max_radius, 0, -4):
        alpha = int(25 * (1 - r / max_radius))
        glow_color = (50, 50, 90, alpha)
        glow_img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_img)
        glow_draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            fill=glow_color
        )
        img = Image.alpha_composite(img, glow_img)
    draw = ImageDraw.Draw(img)

    # ===== カチンコ（クラッパーボード）の描画 =====

    # --- 各部分の座標計算 ---
    board_left = int(s * 0.18)
    board_right = int(s * 0.82)
    board_top = int(s * 0.32)
    board_bottom = int(s * 0.78)
    board_w = board_right - board_left
    board_h = board_bottom - board_top

    clapper_top = int(s * 0.18)
    clapper_height = int(s * 0.16)
    clapper_bottom = board_top + int(s * 0.02)

    # --- カチンコ上部（ヒンジ付きクラッパー部分）---
    # 下のバー（固定部分）
    bar_h = int(clapper_height * 0.45)
    bar_top = clapper_bottom - bar_h

    # 固定バー
    draw_rounded_rect(
        draw,
        [board_left, bar_top, board_right, clapper_bottom],
        radius=int(s * 0.015),
        fill=ACCENT_RED
    )

    # 上のバー（開いた状態 - 回転表現）
    top_bar_h = int(clapper_height * 0.45)
    # 開いた角度を表現 - 左端を軸にして少し開いた状態
    pivot_x = board_left
    pivot_y = bar_top
    angle_deg = 25  # 開き角度

    # 回転したバーを描画（ポリゴンで表現）
    angle_rad = math.radians(angle_deg)
    bar_len = board_w
    # 4つの角の座標
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    p1 = (pivot_x, pivot_y)
    p2 = (pivot_x + bar_len * cos_a, pivot_y - bar_len * sin_a)
    p3 = (pivot_x + bar_len * cos_a + top_bar_h * sin_a, pivot_y - bar_len * sin_a + top_bar_h * cos_a)
    p4 = (pivot_x + top_bar_h * sin_a, pivot_y + top_bar_h * cos_a)

    draw.polygon([p1, p2, p3, p4], fill=ACCENT_RED)

    # ストライプ（カチンコの縞模様 - 上バー）
    stripe_count = 5
    stripe_w = bar_len / (stripe_count * 2)
    for i in range(stripe_count):
        sx = stripe_w * (2 * i)
        sx2 = sx + stripe_w
        # ストライプの4点
        sp1 = (pivot_x + sx * cos_a, pivot_y - sx * sin_a)
        sp2 = (pivot_x + sx2 * cos_a, pivot_y - sx2 * sin_a)
        sp3 = (pivot_x + sx2 * cos_a + top_bar_h * sin_a, pivot_y - sx2 * sin_a + top_bar_h * cos_a)
        sp4 = (pivot_x + sx * cos_a + top_bar_h * sin_a, pivot_y - sx * sin_a + top_bar_h * cos_a)
        draw.polygon([sp1, sp2, sp3, sp4], fill=WHITE)

    # ストライプ（固定バー）
    for i in range(stripe_count):
        sx = board_left + stripe_w * (2 * i)
        sx2 = sx + stripe_w
        draw.rectangle([sx, bar_top, sx2, clapper_bottom], fill=WHITE)

    # --- カチンコ本体（ボード部分）---
    draw_rounded_rect(
        draw,
        [board_left, board_top, board_right, board_bottom],
        radius=int(s * 0.03),
        fill=BOARD_COLOR
    )

    # ボードの赤いトップバー
    draw.rectangle(
        [board_left, board_top, board_right, board_top + int(s * 0.04)],
        fill=ACCENT_RED
    )

    # --- ボード上のテキスト情報 ---
    # フォント設定（システムフォントを試行）
    font_sizes = {
        "title": int(s * 0.055),
        "label": int(s * 0.03),
        "value": int(s * 0.035),
    }

    fonts = {}
    for key, fsize in font_sizes.items():
        try:
            # macOS のシステムフォントを試行
            fonts[key] = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", fsize)
        except (OSError, IOError):
            try:
                fonts[key] = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", fsize)
            except (OSError, IOError):
                fonts[key] = ImageFont.load_default()

    # ボード内のテキストレイアウト
    text_left = board_left + int(s * 0.05)
    text_top = board_top + int(s * 0.07)
    line_h = int(s * 0.065)

    # PRODUCTION ラベル行
    draw.text((text_left, text_top), "PROD.", fill=LIGHT_GRAY, font=fonts["label"])
    draw.text((text_left + int(s * 0.12), text_top), "VIDEO DIRECTOR", fill=WHITE, font=fonts["value"])

    # 区切り線
    line_y = text_top + int(line_h * 0.8)
    draw.line(
        [(text_left, line_y), (board_right - int(s * 0.05), line_y)],
        fill=DARK_GRAY, width=max(1, int(s * 0.002))
    )

    # DIRECTOR ラベル行
    row2_y = text_top + line_h
    draw.text((text_left, row2_y), "DIR.", fill=LIGHT_GRAY, font=fonts["label"])
    draw.text((text_left + int(s * 0.12), row2_y), "AI AGENT", fill=WHITE, font=fonts["value"])

    # 区切り線
    line_y2 = row2_y + int(line_h * 0.8)
    draw.line(
        [(text_left, line_y2), (board_right - int(s * 0.05), line_y2)],
        fill=DARK_GRAY, width=max(1, int(s * 0.002))
    )

    # SCENE / TAKE 行
    row3_y = text_top + line_h * 2
    draw.text((text_left, row3_y), "SCENE", fill=LIGHT_GRAY, font=fonts["label"])
    draw.text((text_left + int(s * 0.12), row3_y), "001", fill=WHITE, font=fonts["value"])

    mid_x = board_left + board_w // 2
    draw.text((mid_x, row3_y), "TAKE", fill=LIGHT_GRAY, font=fonts["label"])
    draw.text((mid_x + int(s * 0.10), row3_y), "01", fill=WHITE, font=fonts["value"])

    # --- 再生ボタン風の三角マーク（右下に小さく）---
    play_cx = board_right - int(s * 0.08)
    play_cy = board_bottom - int(s * 0.07)
    play_r = int(s * 0.035)

    # 赤い円
    draw.ellipse(
        [play_cx - play_r, play_cy - play_r, play_cx + play_r, play_cy + play_r],
        fill=ACCENT_RED
    )
    # 三角（再生）
    tri_size = int(play_r * 0.6)
    tri_offset = int(tri_size * 0.15)
    draw.polygon(
        [
            (play_cx - tri_size // 2 + tri_offset, play_cy - tri_size),
            (play_cx - tri_size // 2 + tri_offset, play_cy + tri_size),
            (play_cx + tri_size + tri_offset, play_cy),
        ],
        fill=WHITE
    )

    # --- 下部のAIインジケーター ---
    ai_y = int(s * 0.84)
    # 小さなドット群（AIネットワーク風）
    dot_r = int(s * 0.008)
    dot_positions = [
        (int(s * 0.35), ai_y),
        (int(s * 0.42), ai_y - int(s * 0.02)),
        (int(s * 0.50), ai_y + int(s * 0.01)),
        (int(s * 0.58), ai_y - int(s * 0.015)),
        (int(s * 0.65), ai_y),
    ]
    # ドット間の線
    for i in range(len(dot_positions) - 1):
        draw.line(
            [dot_positions[i], dot_positions[i + 1]],
            fill=ACCENT_RED + (120,), width=max(1, int(s * 0.003))
        )
    # ドット
    for px, py in dot_positions:
        draw.ellipse(
            [px - dot_r, py - dot_r, px + dot_r, py + dot_r],
            fill=ACCENT_RED
        )

    return img.convert("RGB")


def main():
    # 出力先
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "VideoDirectorAgent", "VideoDirectorAgent", "Resources",
        "Assets.xcassets", "AppIcon.appiconset"
    )
    os.makedirs(output_dir, exist_ok=True)

    # 必要なサイズ一覧
    icon_sizes = [1024, 180, 120, 87, 80, 60, 58, 40, 29, 20]

    # 1024x1024 のマスター画像を生成
    print("マスターアイコン (1024x1024) を生成中...")
    master = generate_icon(1024)

    generated_files = []
    for sz in icon_sizes:
        filename = f"icon_{sz}x{sz}.png"
        filepath = os.path.join(output_dir, filename)
        if sz == 1024:
            master.save(filepath, "PNG")
        else:
            resized = master.resize((sz, sz), Image.LANCZOS)
            resized.save(filepath, "PNG")
        generated_files.append((filename, sz))
        print(f"  生成: {filename}")

    # Contents.json を生成
    # Xcode 15+ 形式: universalで1024x1024を指定 + 従来の個別サイズも含める
    images = [
        # App Store
        {"filename": "icon_1024x1024.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"},
        # iPhone アプリアイコン
        {"filename": "icon_60x60.png", "idiom": "iphone", "scale": "2x", "size": "60x60"},
        {"filename": "icon_180x180.png", "idiom": "iphone", "scale": "3x", "size": "60x60"},
        # iPhone 通知
        {"filename": "icon_40x40.png", "idiom": "iphone", "scale": "2x", "size": "20x20"},
        {"filename": "icon_60x60.png", "idiom": "iphone", "scale": "3x", "size": "20x20"},
        # iPhone 設定
        {"filename": "icon_58x58.png", "idiom": "iphone", "scale": "2x", "size": "29x29"},
        {"filename": "icon_87x87.png", "idiom": "iphone", "scale": "3x", "size": "29x29"},
        # iPhone Spotlight
        {"filename": "icon_80x80.png", "idiom": "iphone", "scale": "2x", "size": "40x40"},
        {"filename": "icon_120x120.png", "idiom": "iphone", "scale": "3x", "size": "40x40"},
    ]

    contents = {
        "images": images,
        "info": {
            "author": "xcode",
            "version": 1
        }
    }

    contents_path = os.path.join(output_dir, "Contents.json")
    with open(contents_path, "w", encoding="utf-8") as f:
        json.dump(contents, f, indent=2, ensure_ascii=False)
    print(f"  生成: Contents.json")

    print(f"\n完了! {len(generated_files)} サイズのアイコンを生成しました。")
    print(f"出力先: {output_dir}")


if __name__ == "__main__":
    main()
