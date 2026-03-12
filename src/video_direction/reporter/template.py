from __future__ import annotations
"""HTMLテンプレート — video-knowledge-pagesのCSS設計を踏襲"""

# インラインCSS（max-width: 820px、レスポンシブ対応）
CSS_STYLE = """
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Hiragino Kaku Gothic ProN', 'Noto Sans JP', sans-serif;
    max-width: 820px;
    margin: 0 auto;
    padding: 20px;
    color: #333;
    background: #fafbfc;
    line-height: 1.7;
}
h1 {
    font-size: 1.6em;
    border-bottom: 3px solid #1a73e8;
    padding-bottom: 10px;
    margin-bottom: 20px;
}
h2 {
    font-size: 1.3em;
    color: #1a73e8;
    border-left: 4px solid #1a73e8;
    padding-left: 12px;
    margin-top: 30px;
}
h3 {
    font-size: 1.1em;
    color: #555;
    margin-top: 20px;
}
.meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 8px;
    background: #fff;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
    padding: 16px;
    margin: 16px 0;
}
.meta-item {
    font-size: 0.9em;
}
.meta-label {
    color: #888;
    font-size: 0.8em;
}
.meta-value {
    font-weight: 600;
}
.section {
    background: #fff;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
    padding: 20px;
    margin: 16px 0;
}
.tier-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 16px;
    font-weight: 600;
    font-size: 0.9em;
}
.tier-a { background: #ffd700; color: #333; }
.tier-b { background: #e8f0fe; color: #1a73e8; }
.tier-c { background: #e8f5e9; color: #2e7d32; }
.emphasis-on {
    color: #d32f2f;
    font-weight: 700;
}
.emphasis-off {
    color: #888;
}
.timeline-entry {
    display: flex;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid #f0f0f0;
}
.timeline-ts {
    font-family: 'SF Mono', 'Consolas', monospace;
    color: #1a73e8;
    font-weight: 600;
    min-width: 50px;
    white-space: nowrap;
}
.timeline-type {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75em;
    font-weight: 600;
    min-width: 60px;
    text-align: center;
}
.type-telop { background: #fce4ec; color: #c62828; }
.type-camera { background: #e3f2fd; color: #1565c0; }
.type-color { background: #fff3e0; color: #e65100; }
.type-composite { background: #f3e5f5; color: #7b1fa2; }
.timeline-instruction {
    flex: 1;
}
.priority-high { border-left: 3px solid #d32f2f; padding-left: 8px; }
.priority-medium { border-left: 3px solid #ff9800; padding-left: 8px; }
.priority-low { border-left: 3px solid #4caf50; padding-left: 8px; }
.noun-entry {
    padding: 8px 12px;
    margin: 4px 0;
    border-radius: 6px;
}
.noun-show { background: #e8f5e9; }
.noun-hide { background: #fce4ec; }
.target-scene {
    padding: 8px 12px;
    margin: 4px 0;
    border-radius: 6px;
    border-left: 3px solid;
}
.target-tier1 { border-color: #1a73e8; background: #e8f0fe; }
.target-tier2 { border-color: #2e7d32; background: #e8f5e9; }
.target-both { border-color: #ff9800; background: #fff3e0; }
.balance-meter {
    display: flex;
    height: 24px;
    border-radius: 12px;
    overflow: hidden;
    margin: 8px 0;
}
.balance-tier1 { background: #1a73e8; }
.balance-tier2 { background: #2e7d32; }
.balance-both { background: #ff9800; }
.strength-card {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
}
.highlight-table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0;
}
.highlight-table th, .highlight-table td {
    padding: 8px;
    text-align: left;
    border-bottom: 1px solid #eee;
    font-size: 0.9em;
}
.highlight-table th {
    background: #f8f9fa;
    font-weight: 600;
    color: #555;
}
details {
    margin: 16px 0;
}
summary {
    cursor: pointer;
    font-weight: 600;
    color: #1a73e8;
    padding: 8px;
}
summary:hover { text-decoration: underline; }
.transcript {
    background: #f8f9fa;
    padding: 16px;
    border-radius: 8px;
    font-size: 0.85em;
    line-height: 1.8;
    white-space: pre-wrap;
    max-height: 600px;
    overflow-y: auto;
}
footer {
    text-align: center;
    color: #999;
    font-size: 0.8em;
    margin-top: 40px;
    padding: 20px 0;
    border-top: 1px solid #eee;
}
a { color: #1a73e8; text-decoration: none; }
a:hover { text-decoration: underline; }

/* === Z型サムネイル指示書 === */
.thumbnail-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin: 16px 0;
}
.thumbnail-zone {
    background: #f8f9fa;
    border: 2px solid #dee2e6;
    border-radius: 10px;
    padding: 16px;
    position: relative;
}
.thumbnail-zone .zone-label {
    position: absolute;
    top: -10px;
    left: 12px;
    background: #1a73e8;
    color: #fff;
    font-size: 0.7em;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 10px;
}
.thumbnail-zone .zone-role {
    font-size: 0.8em;
    color: #888;
    margin-bottom: 6px;
}
.thumbnail-zone .zone-content {
    font-weight: 600;
    font-size: 1em;
    margin-bottom: 6px;
}
.thumbnail-zone .zone-color {
    font-size: 0.8em;
    color: #666;
}
.thumbnail-zone .zone-notes {
    font-size: 0.8em;
    color: #999;
    font-style: italic;
    margin-top: 4px;
}
.zone-top-left { border-color: #d32f2f; }
.zone-top-left .zone-label { background: #d32f2f; }
.zone-top-right { border-color: #1565c0; }
.zone-top-right .zone-label { background: #1565c0; }
.zone-diagonal { border-color: #ff9800; }
.zone-diagonal .zone-label { background: #ff9800; }
.zone-bottom-right { border-color: #2e7d32; }
.zone-bottom-right .zone-label { background: #2e7d32; }
.thumbnail-concept {
    background: #e8f0fe;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 12px 0;
    font-weight: 600;
}
.thumbnail-meta {
    display: flex;
    gap: 16px;
    font-size: 0.85em;
    color: #666;
    margin: 8px 0;
}

/* === タイトル案 === */
.title-card {
    background: #fff;
    border: 1px solid #e8e8e8;
    border-radius: 10px;
    padding: 16px;
    margin: 10px 0;
    transition: box-shadow 0.2s;
}
.title-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.title-card.recommended {
    border: 2px solid #ffd700;
    background: #fffef5;
}
.title-card .title-badge {
    display: inline-block;
    background: #ffd700;
    color: #333;
    font-size: 0.7em;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
    margin-bottom: 6px;
}
.title-card .title-text {
    font-size: 1.15em;
    font-weight: 700;
    margin-bottom: 8px;
    color: #222;
}
.title-card .title-meta {
    display: flex;
    gap: 12px;
    font-size: 0.8em;
    color: #888;
    flex-wrap: wrap;
}
.title-card .title-meta span {
    background: #f0f0f0;
    padding: 2px 8px;
    border-radius: 4px;
}
.title-card .title-rationale {
    font-size: 0.85em;
    color: #666;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid #f0f0f0;
}

/* === 概要欄プレビュー === */
.description-preview {
    background: #1a1a1a;
    color: #e0e0e0;
    border-radius: 10px;
    padding: 20px;
    margin: 16px 0;
    font-family: 'SF Mono', 'Consolas', 'Roboto Mono', monospace;
    font-size: 0.85em;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-all;
    position: relative;
    max-height: 500px;
    overflow-y: auto;
}
.description-preview::before {
    content: 'YouTube\u6982\u8981\u6b04\u30d7\u30ec\u30d3\u30e5\u30fc';
    position: absolute;
    top: 0;
    right: 0;
    background: #d32f2f;
    color: #fff;
    font-size: 0.7em;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 0 10px 0 8px;
    font-family: -apple-system, sans-serif;
}
.copy-btn {
    display: inline-block;
    background: #1a73e8;
    color: #fff;
    border: none;
    padding: 8px 20px;
    border-radius: 6px;
    font-size: 0.85em;
    cursor: pointer;
    margin-top: 8px;
}
.copy-btn:hover { background: #1558b0; }
"""

# index.htmlテンプレート
INDEX_CSS = """
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Hiragino Kaku Gothic ProN', sans-serif;
    max-width: 700px;
    margin: 40px auto;
    padding: 0 20px;
    color: #333;
    background: #fafbfc;
}
h1 { font-size: 1.5em; border-bottom: 2px solid #1a73e8; padding-bottom: 8px; }
a { color: #1a73e8; text-decoration: none; }
a:hover { text-decoration: underline; }
.item { padding: 16px 0; border-bottom: 1px solid #eee; }
.date { color: #888; font-size: 0.85em; }
.tier { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: 600; margin-left: 8px; }
.tier-a { background: #ffd700; color: #333; }
.tier-b { background: #e8f0fe; color: #1a73e8; }
.tier-c { background: #e8f5e9; color: #2e7d32; }
.count { color: #888; font-size: 0.9em; margin-top: 20px; }
"""
