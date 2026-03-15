// VideoDirectorAgent WebApp MVP
// HTML + CSS + JS のみ。フレームワーク不使用。

(function() {
  'use strict';

  // ===== 状態管理 =====
  let currentTab = 'home';
  let currentProject = null;
  let historyFilter = 'all';
  let isRecording = false;

  // ===== 初期化 =====
  document.addEventListener('DOMContentLoaded', init);

  function init() {
    renderHome();
    renderHistoryPage();
    renderQualityDashboard();
    setupTabBar();
    setupSearchHandlers();
    createRecordingModal();
  }

  // トラッキングページは遅延初期化（タブ選択時に読み込み）

  // ===== スコア色判定 =====
  function scoreColor(score) {
    if (score >= 85) return 'var(--status-complete)';
    if (score >= 70) return 'var(--status-editing)';
    return 'var(--accent)';
  }

  function scoreClass(score) {
    if (score >= 85) return 'score-green';
    if (score >= 70) return 'score-yellow';
    return 'score-red';
  }

  // ステータス色をグラデーション背景に変換
  function statusGradient(status) {
    const colors = {
      directed: 'rgba(74,144,217,0.2)',
      editing: 'rgba(245,166,35,0.2)',
      reviewPending: 'rgba(229,9,20,0.2)',
      published: 'rgba(70,211,105,0.2)'
    };
    return colors[status] || 'rgba(255,255,255,0.05)';
  }

  // ===== 画面1: ホーム =====
  function renderHome() {
    const projects = MockData.projects;
    const hero = projects[0];

    // ヒーローバナー
    const heroBanner = document.getElementById('hero-banner');
    heroBanner.innerHTML = `
      <div class="hero-bg">
        <span class="hero-icon">${hero.icon}</span>
      </div>
      <div class="hero-gradient"></div>
      <div class="hero-text">
        <div class="hero-brand">VIDEO DIRECTOR</div>
        <div class="hero-label">最新プロジェクト</div>
        <div class="hero-guest-name">${hero.guestName}</div>
        <div class="hero-title">${hero.title}</div>
        <div class="hero-meta">
          <span>${hero.shootDate}</span>
          ${hero.qualityScore ? `<span>Score ${hero.qualityScore}</span>` : ''}
        </div>
        <div class="hero-badges">
          <span class="badge badge-status" data-status="${hero.status}">${hero.statusLabel}</span>
          ${hero.unreviewedCount > 0 ? `<span class="badge badge-unreviewed">未レビュー ${hero.unreviewedCount}</span>` : ''}
        </div>
      </div>
    `;
    // ヒーローバナーのクリックでレポート詳細に遷移
    heroBanner.style.cursor = 'pointer';
    heroBanner.addEventListener('click', () => openReport(hero));

    // カルーセル: 最近のフィードバック（未送信FBがあるもの）
    const recentFB = projects.filter(p => p.hasUnsentFeedback);
    renderCarousel('carousel-recent', '最近のフィードバック', 'FB', recentFB);

    // カルーセル: 要対応（未レビューがあるもの）
    const actionRequired = projects.filter(p => p.unreviewedCount > 0);
    renderCarousel('carousel-action', '要対応', '!', actionRequired);

    // カルーセル: 全プロジェクト
    renderCarousel('carousel-all', '全プロジェクト', 'ALL', projects);
  }

  function renderCarousel(containerId, title, icon, projects) {
    const container = document.getElementById(containerId);
    if (!projects.length) {
      container.style.display = 'none';
      return;
    }

    container.innerHTML = `
      <div class="carousel-header">
        <span class="section-icon">${icon}</span>
        <span class="section-title">${title}</span>
        <span class="section-chevron">›</span>
      </div>
      <div class="carousel-scroll">
        ${projects.map(p => projectCardHTML(p)).join('')}
      </div>
    `;

    // カードクリックイベント
    container.querySelectorAll('.project-card').forEach(card => {
      card.addEventListener('click', () => {
        const projectId = card.dataset.id;
        const project = MockData.projects.find(p => p.id === projectId);
        if (project) openReport(project);
      });
    });
  }

  function projectCardHTML(p) {
    const gradient = `linear-gradient(135deg, var(--card), ${statusGradient(p.status)})`;
    return `
      <div class="project-card" data-id="${p.id}">
        <div class="card-thumbnail">
          <div class="thumb-bg" style="background: ${gradient}">
            <span class="thumb-icon">${p.icon}</span>
          </div>
          ${p.qualityScore ? `<div class="progress-bar" style="width: ${p.qualityScore}%"></div>` : ''}
          ${p.hasUnsentFeedback ? '<div class="unsent-dot"></div>' : ''}
        </div>
        <div class="card-guest">${p.guestName}</div>
        <div class="card-date">${p.shootDate}</div>
      </div>
    `;
  }

  // ===== 検索 =====
  function setupSearchHandlers() {
    // ホーム検索
    const searchInput = document.getElementById('search-input');
    searchInput.addEventListener('input', () => {
      const query = searchInput.value.toLowerCase();
      filterHomeProjects(query);
    });

    // 履歴検索
    const historySearch = document.getElementById('history-search');
    historySearch.addEventListener('input', () => {
      renderHistoryList();
    });
  }

  function filterHomeProjects(query) {
    const all = MockData.projects;
    const filtered = query
      ? all.filter(p =>
          p.guestName.toLowerCase().includes(query) ||
          p.title.toLowerCase().includes(query) ||
          p.shootDate.includes(query)
        )
      : all;

    // 全プロジェクトカルーセルのみ更新
    renderCarousel('carousel-all', '全プロジェクト', 'ALL', filtered);
  }

  // ===== 画面2: レポート詳細 =====
  function openReport(project) {
    currentProject = project;
    navigateTo('report');
    renderReport(project);
  }

  function renderReport(p) {
    const content = document.getElementById('report-content');
    const gradient = `linear-gradient(135deg, ${statusGradient(p.status)}, var(--card))`;

    content.innerHTML = `
      <button class="back-btn" id="report-back">← 戻る</button>
      <div class="report-cover">
        <div class="cover-bg" style="background: ${gradient}">
          <span class="cover-icon">${p.icon}</span>
        </div>
        <div class="cover-gradient"></div>
      </div>
      <div style="padding: 0 20px;">
        <div class="report-guest-name">${p.guestName}</div>
        <div class="report-title">${p.title}</div>
        <div class="report-meta">
          ${p.guestAge ? `<span>${p.guestAge}歳</span>` : ''}
          ${p.guestOccupation ? `<span>${p.guestOccupation}</span>` : ''}
          <span>${p.shootDate}</span>
        </div>
        <div class="report-actions">
          <button class="btn-vimeo">▶ Vimeoレビューを開く</button>
          ${p.qualityScore ? `
            <div class="score-display">
              <div class="score-value ${scoreClass(p.qualityScore)}" style="color: ${scoreColor(p.qualityScore)}">${p.qualityScore}</div>
              <div class="score-label">品質スコア</div>
            </div>
          ` : ''}
        </div>
      </div>
      <div class="tab-selector" id="report-tabs"></div>
      <div id="report-sections"></div>
    `;

    // 戻るボタン
    document.getElementById('report-back').addEventListener('click', () => {
      navigateTo('home');
    });

    // Vimeoレビューボタン
    const vimeoBtn = content.querySelector('.btn-vimeo');
    if (vimeoBtn) {
      vimeoBtn.addEventListener('click', () => {
        openVimeoReview(p);
      });
    }

    // タブ
    renderReportTabs();
    renderReportSection(0);

    // 下部アクションバー表示
    showBottomActionBar(true);
  }

  function renderReportTabs() {
    // ナレッジページの有無を確認
    const knowledgePage = (typeof findKnowledgePage === 'function' && currentProject)
      ? findKnowledgePage(currentProject.guestName)
      : null;

    const tabs = ['演出', 'テロップ', 'カメラ', '音声FB'];
    if (knowledgePage) {
      tabs.push('ナレッジ');
    }
    // YouTube素材タブ（追加: 2026-03-15）
    tabs.push('YouTube素材');
    // 編集FB / Vimeoレビュータブ（追加: 2026-03-16）
    tabs.push('編集FB');
    tabs.push('レビュー');
    // フレーム評価タブ（追加: C-1）
    tabs.push('フレーム評価');

    const container = document.getElementById('report-tabs');
    container.innerHTML = tabs.map((t, i) => `
      <button class="tab-selector-btn ${i === 0 ? 'active' : ''}" data-index="${i}" data-tab-name="${t}">
        <span class="tab-label">${t}</span>
        <div class="tab-indicator"></div>
      </button>
    `).join('');

    container.querySelectorAll('.tab-selector-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        container.querySelectorAll('.tab-selector-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tabName = btn.dataset.tabName;
        if (tabName === 'ナレッジ') {
          renderKnowledgePage(knowledgePage);
        } else if (tabName === 'YouTube素材') {
          // YouTube素材タブ（追加: 2026-03-15）
          renderYouTubeAssets(currentProject);
        } else if (tabName === '編集FB') {
          // 編集FBタブ（追加: 2026-03-16）
          openEditFeedback(currentProject);
        } else if (tabName === 'レビュー') {
          // Vimeoレビュータブ（追加: 2026-03-16）
          openVimeoReview(currentProject);
        } else if (tabName === 'フレーム評価') {
          // フレーム評価タブ（C-1）
          renderFrameEvaluation(currentProject);
        } else {
          renderReportSection(parseInt(btn.dataset.index));
        }
      });
    });
  }

  function renderReportSection(index) {
    const container = document.getElementById('report-sections');
    const section = MockData.reportSections[index];
    if (!section) {
      container.innerHTML = '';
      return;
    }

    container.innerHTML = `
      <div class="expandable-section" id="section-${section.id}">
        <div class="expandable-header">
          <span class="section-icon">${section.icon}</span>
          <span class="section-title">${section.title}</span>
          <span class="chevron">▼</span>
        </div>
        <div class="expandable-body">
          ${section.items.map(item => `
            <div class="fb-item">
              <div class="fb-dot"></div>
              <div class="fb-text">${item}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    // 折りたたみ動作
    container.querySelectorAll('.expandable-header').forEach(header => {
      header.addEventListener('click', () => {
        const section = header.closest('.expandable-section');
        section.classList.toggle('collapsed');
      });
    });
  }

  // ===== ナレッジページ表示 =====
  function renderKnowledgePage(filename) {
    const container = document.getElementById('report-sections');
    if (!filename) {
      container.innerHTML = `
        <div class="knowledge-empty">
          <div class="knowledge-empty-icon">--</div>
          <div class="knowledge-empty-text">ナレッジページ未生成</div>
          <div class="knowledge-empty-sub">この対談動画のナレッジページはまだ作成されていません</div>
        </div>
      `;
      return;
    }

    const encodedFilename = encodeURIComponent(filename);
    container.innerHTML = `
      <div class="knowledge-viewer">
        <div class="knowledge-header">
          <span class="knowledge-header-icon">KN</span>
          <span class="knowledge-header-title">動画ナレッジページ</span>
        </div>
        <div class="knowledge-iframe-wrap">
          <iframe
            src="knowledge-pages/${encodedFilename}"
            class="knowledge-iframe"
            sandbox="allow-same-origin"
            title="動画ナレッジページ"
          ></iframe>
        </div>
        <a href="knowledge-pages/${encodedFilename}" target="_blank" class="knowledge-open-btn">
          別タブで開く ↗
        </a>
      </div>
    `;
  }

  // ===== 下部固定アクションバー =====
  function showBottomActionBar(show) {
    let bar = document.querySelector('.bottom-action-bar');
    if (!bar) {
      bar = document.createElement('div');
      bar.className = 'bottom-action-bar';
      bar.innerHTML = `
        <button class="btn-voice-fb">
          + 音声フィードバックを追加
        </button>
      `;
      bar.querySelector('.btn-voice-fb').addEventListener('click', () => {
        showRecordingModal(true);
      });
      document.body.appendChild(bar);
    }
    bar.classList.toggle('visible', show);
  }

  // ===== 画面3: 履歴 =====
  function renderHistoryPage() {
    // フィルターボタン
    const filterBar = document.getElementById('history-filters');
    const filters = [
      { key: 'all', label: 'すべて' },
      { key: 'unsent', label: '未送信のみ' }
    ];
    filterBar.innerHTML = filters.map(f => `
      <button class="filter-btn ${f.key === historyFilter ? 'active' : ''}" data-filter="${f.key}">${f.label}</button>
    `).join('');

    filterBar.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        historyFilter = btn.dataset.filter;
        filterBar.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderHistoryList();
      });
    });

    renderHistoryList();
  }

  function renderHistoryList() {
    const container = document.getElementById('history-list');
    const searchQuery = (document.getElementById('history-search')?.value || '').toLowerCase();

    let items = MockData.historyItems;

    // フィルタ
    if (historyFilter === 'unsent') {
      items = items.filter(i => !i.isSent);
    }

    // 検索
    if (searchQuery) {
      items = items.filter(i =>
        i.projectTitle.toLowerCase().includes(searchQuery) ||
        i.guestName.toLowerCase().includes(searchQuery) ||
        i.rawVoiceText.toLowerCase().includes(searchQuery)
      );
    }

    // 日付グループ化
    const grouped = {};
    items.forEach(item => {
      if (!grouped[item.date]) grouped[item.date] = [];
      grouped[item.date].push(item);
    });

    const dates = Object.keys(grouped).sort().reverse();

    container.innerHTML = dates.map(date => `
      <div class="history-date-header">${date}</div>
      ${grouped[date].map(item => historyCardHTML(item)).join('')}
    `).join('');
  }

  function historyCardHTML(item) {
    return `
      <div class="history-card">
        <div class="history-card-header">
          <div>
            <div class="history-guest">${item.guestName}</div>
            <div class="history-project">${item.projectTitle}</div>
          </div>
          <span class="history-timestamp">${item.timestamp}</span>
        </div>
        <div class="history-voice-row">
          <div class="voice-icon play">▶</div>
          <div>
            <div class="voice-label">音声</div>
            <div class="voice-text">${item.rawVoiceText}</div>
          </div>
        </div>
        <div class="history-converted-row">
          <div class="voice-icon convert">→</div>
          <div>
            <div class="voice-label converted">変換後</div>
            <div class="voice-text converted">${item.convertedText}</div>
          </div>
        </div>
        <div class="history-status-row">
          <span class="sent-badge ${item.isSent ? 'sent' : 'unsent'}">
            ${item.isSent ? '✓ 送信済み' : '⏱ 未送信'}
          </span>
          <span style="color: var(--text-muted)">・</span>
          <span class="editor-status">${item.editorStatus}</span>
          ${item.learningEffect ? `<span class="learning-effect">${item.learningEffect}</span>` : ''}
        </div>
      </div>
    `;
  }

  // ===== 画面4: 品質ダッシュボード =====
  function renderQualityDashboard() {
    const container = document.getElementById('quality-content');
    const trend = MockData.qualityTrend;
    const latestScore = trend[trend.length - 1].score;
    const prevScore = trend[trend.length - 2].score;
    const delta = latestScore - prevScore;

    container.innerHTML = `
      <div class="quality-content">
        <!-- メインスコア -->
        <div class="main-score-card">
          <div class="main-score-label">映像品質スコア</div>
          <div class="main-score-value" style="color: ${scoreColor(latestScore)}">${latestScore}</div>
          <span class="score-delta ${delta >= 0 ? 'positive' : 'negative'}">
            ${delta >= 0 ? '↗' : '↘'} ${delta >= 0 ? '+' : ''}${delta} 前回比
          </span>
        </div>

        <!-- スコア推移グラフ -->
        <div class="trend-card">
          <div class="card-title-row">
            <span class="card-title-icon">^</span>
            <span class="card-title">スコア推移（過去10回）</span>
          </div>
          <canvas id="trend-chart"></canvas>
          <div class="trend-labels" id="trend-labels"></div>
        </div>

        <!-- カテゴリ別スコア -->
        <div class="category-card">
          <div class="card-title-row">
            <span class="card-title-icon">#</span>
            <span class="card-title">カテゴリ別スコア</span>
          </div>
          <div class="category-grid">
            ${MockData.categoryScores.map(cat => `
              <div class="category-item">
                <div class="category-icon">${cat.icon}</div>
                <div class="category-score" style="color: ${scoreColor(cat.score)}">${cat.score}</div>
                <div class="category-name">${cat.category}</div>
                <div class="category-bar">
                  <div class="category-bar-fill" style="width: ${cat.score}%; background: ${scoreColor(cat.score)}"></div>
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- 改善提案 -->
        <div class="suggestions-card">
          <div class="card-title-row">
            <span class="card-title-icon">*</span>
            <span class="card-title">AIからの改善提案</span>
          </div>
          ${MockData.improvementSuggestions.map(s => `
            <div class="suggestion-item">
              <div class="priority-badge ${s.priority}">${s.priority === 'high' ? '高' : s.priority === 'medium' ? '中' : '低'}</div>
              <div>
                <div class="suggestion-category">${s.category}</div>
                <div class="suggestion-text">${s.suggestion}</div>
              </div>
            </div>
          `).join('')}
        </div>

        <!-- アラート -->
        <div class="alerts-card">
          <div class="card-title-row">
            <span class="card-title-icon" style="color: var(--accent)">!</span>
            <span class="card-title">品質アラート</span>
          </div>
          ${MockData.alerts.map(a => `
            <div class="alert-item">
              <div class="alert-dot ${a.level}"></div>
              <div class="alert-text">${a.message}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    // グラフ描画
    requestAnimationFrame(() => drawTrendChart());

    // ラベル
    const labelsContainer = document.getElementById('trend-labels');
    if (labelsContainer) {
      labelsContainer.innerHTML = trend.map((p, i) => {
        // 偶数番目か最後のみ表示
        if (i % 2 === 0 || i === trend.length - 1) {
          return `<span class="trend-label">${p.label}</span>`;
        }
        return '<span class="trend-label"></span>';
      }).join('');
    }
  }

  function drawTrendChart() {
    const canvas = document.getElementById('trend-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const points = MockData.qualityTrend;
    const scores = points.map(p => p.score);
    const maxScore = Math.max(...scores);
    const minScore = Math.min(...scores);
    const range = Math.max(maxScore - minScore, 1);
    const padding = 4;

    // グリッド線
    ctx.strokeStyle = 'rgba(128, 128, 128, 0.15)';
    ctx.lineWidth = 1;
    for (let i = 0; i < 4; i++) {
      const y = (height - padding * 2) * i / 3 + padding;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // ポイント座標計算
    const coords = points.map((p, i) => ({
      x: width * i / Math.max(points.length - 1, 1),
      y: padding + (height - padding * 2) - ((height - padding * 2) * (p.score - minScore) / range)
    }));

    // グラデーション塗り
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, 'rgba(229, 9, 20, 0.3)');
    gradient.addColorStop(1, 'rgba(229, 9, 20, 0.0)');

    ctx.beginPath();
    coords.forEach((c, i) => {
      if (i === 0) ctx.moveTo(c.x, c.y);
      else ctx.lineTo(c.x, c.y);
    });
    ctx.lineTo(coords[coords.length - 1].x, height);
    ctx.lineTo(coords[0].x, height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // 折れ線
    ctx.beginPath();
    ctx.strokeStyle = '#E50914';
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    coords.forEach((c, i) => {
      if (i === 0) ctx.moveTo(c.x, c.y);
      else ctx.lineTo(c.x, c.y);
    });
    ctx.stroke();

    // ドット
    coords.forEach(c => {
      ctx.beginPath();
      ctx.arc(c.x, c.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#E50914';
      ctx.fill();
      ctx.beginPath();
      ctx.arc(c.x, c.y, 2, 0, Math.PI * 2);
      ctx.fillStyle = '#fff';
      ctx.fill();
    });
  }

  // ===== タブバー =====
  function setupTabBar() {
    const buttons = document.querySelectorAll('#tab-bar .tab-btn');
    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        if (tab === 'record') {
          showRecordingModal(true);
          return;
        }
        if (tab === 'tools') {
          renderToolsMenu();
          return;
        }
        navigateTo(tab);
      });
    });
  }

  function navigateTo(tab) {
    currentTab = tab;

    // ページ切替
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const targetPage = document.getElementById(`page-${tab}`);
    if (targetPage) targetPage.classList.add('active');

    // タブバーのアクティブ状態
    document.querySelectorAll('#tab-bar .tab-btn').forEach(b => b.classList.remove('active'));
    const activeBtn = document.querySelector(`#tab-bar .tab-btn[data-tab="${tab}"]`);
    if (activeBtn) activeBtn.classList.add('active');

    // レポート画面以外では下部アクションバーを非表示
    showBottomActionBar(tab === 'report');

    // スクロールトップ
    document.getElementById('app').scrollTop = 0;

    // レポートタブでデフォルトプロジェクトを表示
    if (tab === 'report' && !currentProject) {
      openReport(MockData.projects[0]);
    }

    // トラッキングタブ: 遅延初期化（タブ選択時にAPI呼び出し）
    if (tab === 'tracking') {
      renderTrackingPage();
    }

    // 各ツール画面の遅延初期化
    if (tab === 'e2e-pipeline') {
      renderE2EPipelinePage();
    }
    if (tab === 'telop-check') {
      renderTelopCheckPage();
    }
    if (tab === 'audio-eval') {
      renderAudioEvalPage();
    }
    if (tab === 'knowledge-browse') {
      renderKnowledgeBrowsePage();
    }
    if (tab === 'fb-learning') {
      renderFBLearningPage();
    }
    if (tab === 'frame-eval-detail') {
      renderFrameEvalDetailPage();
    }
    if (tab === 'pdca') {
      renderPDCAPage();
    }
    if (tab === 'audit') {
      renderAuditPage();
    }
    if (tab === 'editors') {
      renderEditorsPage();
    }
    if (tab === 'notifications') {
      renderNotificationsPage();
    }
  }

  // ===== 録音モーダル（MediaRecorder API + Vimeo連携） =====
  let mediaRecorder = null;
  let audioChunks = [];
  let recordingStartTime = 0;
  let recordingTimer = null;

  function createRecordingModal() {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'recording-modal';
    modal.innerHTML = `
      <div class="modal-content rec-modal-content">
        <div class="modal-text">音声フィードバック</div>
        <div class="modal-subtext" id="rec-subtext">タップして録音を開始</div>
        <div class="rec-timer" id="rec-timer">00:00</div>
        <button class="modal-record-btn" id="modal-record-btn">
          <svg viewBox="0 0 24 24"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg>
        </button>
        <!-- 録音完了後のフロー -->
        <div class="rec-result-area" id="rec-result-area" style="display:none;">
          <div class="rec-result-label">録音完了</div>
          <div class="rec-convert-section">
            <button class="rec-convert-btn" id="rec-convert-btn">LLMで変換する</button>
            <div class="rec-converting" id="rec-converting" style="display:none;">変換中...</div>
          </div>
          <div class="rec-converted-text" id="rec-converted-text" style="display:none;"></div>
          <div class="rec-post-section" id="rec-post-section" style="display:none;">
            <div class="rec-dryrun-toggle">
              <label class="rec-toggle-label">
                <input type="checkbox" id="rec-dryrun-check" checked>
                <span class="rec-toggle-text">Dry Run（テスト送信）</span>
              </label>
            </div>
            <button class="rec-post-btn" id="rec-post-btn">Vimeoレビューに投稿</button>
            <div class="rec-post-status" id="rec-post-status" style="display:none;"></div>
          </div>
        </div>
        <button class="modal-close" id="modal-close">閉じる</button>
      </div>
    `;
    document.body.appendChild(modal);

    document.getElementById('modal-close').addEventListener('click', function() {
      showRecordingModal(false);
    });

    document.getElementById('modal-record-btn').addEventListener('click', function() {
      if (!isRecording) {
        startRecording();
      } else {
        stopRecording();
      }
    });

    document.getElementById('rec-convert-btn').addEventListener('click', function() {
      convertRecordedAudio();
    });

    document.getElementById('rec-post-btn').addEventListener('click', function() {
      postToVimeoReview();
    });

    // 背景クリックで閉じる
    modal.addEventListener('click', function(e) {
      if (e.target === modal) showRecordingModal(false);
    });
  }

  function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      document.getElementById('rec-subtext').textContent = 'このブラウザはマイク録音に対応していません';
      return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function(stream) {
        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = function(e) {
          if (e.data.size > 0) audioChunks.push(e.data);
        };
        mediaRecorder.onstop = function() {
          stream.getTracks().forEach(function(t) { t.stop(); });
        };
        mediaRecorder.start();
        isRecording = true;
        recordingStartTime = Date.now();

        var btn = document.getElementById('modal-record-btn');
        btn.classList.add('recording');
        document.getElementById('rec-subtext').textContent = '録音中... タップして停止';
        document.getElementById('rec-result-area').style.display = 'none';

        // タイマー更新
        recordingTimer = setInterval(function() {
          var elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
          var m = Math.floor(elapsed / 60);
          var s = elapsed % 60;
          document.getElementById('rec-timer').textContent =
            (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
        }, 1000);
      })
      .catch(function(err) {
        document.getElementById('rec-subtext').textContent = 'マイクへのアクセスが拒否されました';
      });
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    isRecording = false;
    clearInterval(recordingTimer);

    var btn = document.getElementById('modal-record-btn');
    btn.classList.remove('recording');
    document.getElementById('rec-subtext').textContent = '録音完了';
    document.getElementById('rec-result-area').style.display = 'block';
    document.getElementById('rec-converted-text').style.display = 'none';
    document.getElementById('rec-post-section').style.display = 'none';
    document.getElementById('rec-post-status').style.display = 'none';
  }

  function convertRecordedAudio() {
    if (audioChunks.length === 0) return;

    var blob = new Blob(audioChunks, { type: 'audio/webm' });
    var formData = new FormData();
    formData.append('audio', blob, 'feedback.webm');
    if (currentProject) {
      formData.append('project_id', currentProject.id);
    }

    document.getElementById('rec-convert-btn').style.display = 'none';
    document.getElementById('rec-converting').style.display = 'block';

    fetch('http://localhost:8210/api/v1/feedback/convert', {
      method: 'POST',
      body: formData
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        document.getElementById('rec-converting').style.display = 'none';
        var converted = data.converted_text || data.convertedText || data.text || '';
        var rawText = data.raw_text || data.rawText || '';
        var html = '';
        if (rawText) {
          html += '<div class="rec-raw-label">音声認識結果:</div>' +
                  '<div class="rec-raw-text">' + escapeHTML(rawText) + '</div>';
        }
        html += '<div class="rec-conv-label">LLM変換結果:</div>' +
                '<div class="rec-conv-text">' + escapeHTML(converted) + '</div>';
        document.getElementById('rec-converted-text').innerHTML = html;
        document.getElementById('rec-converted-text').style.display = 'block';
        document.getElementById('rec-post-section').style.display = 'block';
        // 変換結果をdata属性に保持
        document.getElementById('rec-post-btn').dataset.convertedText = converted;
      })
      .catch(function() {
        document.getElementById('rec-converting').style.display = 'none';
        document.getElementById('rec-convert-btn').style.display = 'block';
        document.getElementById('rec-converted-text').innerHTML =
          '<div class="rec-error">変換に失敗しました。サーバーが起動しているか確認してください。</div>';
        document.getElementById('rec-converted-text').style.display = 'block';
      });
  }

  function postToVimeoReview() {
    var postBtn = document.getElementById('rec-post-btn');
    var convertedText = postBtn.dataset.convertedText || '';
    var dryRun = document.getElementById('rec-dryrun-check').checked;
    var statusEl = document.getElementById('rec-post-status');

    if (!convertedText) return;

    postBtn.disabled = true;
    statusEl.style.display = 'block';
    statusEl.className = 'rec-post-status';
    statusEl.textContent = '投稿中...';

    var url = 'http://localhost:8210/api/v1/vimeo/post-review' + (dryRun ? '?dry_run=true' : '');

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: currentProject ? currentProject.id : '',
        feedback_text: convertedText
      })
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        postBtn.disabled = false;
        statusEl.className = 'rec-post-status rec-post-success';
        if (dryRun) {
          statusEl.textContent = 'Dry Run成功: レビューコメントは送信されていません（テストモード）';
        } else {
          statusEl.textContent = '投稿完了: Vimeoレビューにコメントが追加されました';
        }
      })
      .catch(function() {
        postBtn.disabled = false;
        statusEl.className = 'rec-post-status rec-post-error';
        statusEl.textContent = '投稿に失敗しました。サーバー接続を確認してください。';
      });
  }

  function showRecordingModal(show) {
    const modal = document.getElementById('recording-modal');
    if (modal) {
      modal.classList.toggle('visible', show);
      if (!show) {
        // 録音中なら停止
        if (isRecording) {
          stopRecording();
        }
        isRecording = false;
        var btn = document.getElementById('modal-record-btn');
        if (btn) btn.classList.remove('recording');
        // UI初期化
        document.getElementById('rec-timer').textContent = '00:00';
        document.getElementById('rec-subtext').textContent = 'タップして録音を開始';
        document.getElementById('rec-result-area').style.display = 'none';
        document.getElementById('rec-convert-btn').style.display = 'block';
        document.getElementById('rec-converting').style.display = 'none';
      }
    }
  }

  // ===== リサイズ対応（Canvas再描画） =====
  window.addEventListener('resize', () => {
    if (currentTab === 'quality') {
      drawTrendChart();
    }
  });

  // ===================================================================
  // 画面5: 編集後動画FB表示（NEW-3）
  // ===================================================================

  function openEditFeedback(project) {
    currentProject = project;
    navigateTo('edit-feedback');
    renderEditFeedback(project);
  }

  function renderEditFeedback(p) {
    var content = document.getElementById('edit-feedback-content');
    content.innerHTML = '<button class="back-btn" id="ef-back">\u2190 \u623b\u308b</button>' +
      '<div class="ef-loading"><div class="yt-loading-text">\u7de8\u96c6\u5f8cFB\u3092\u8aad\u307f\u8fbc\u307f\u4e2d...</div></div>';

    document.getElementById('ef-back').addEventListener('click', function() {
      navigateTo('report');
      if (currentProject) renderReport(currentProject);
    });

    // APIからプロジェクト詳細を取得（edited_video フィールドを確認）
    fetch('http://localhost:8210/api/projects/' + encodeURIComponent(p.id))
      .then(function(r) { return r.json(); })
      .then(function(data) {
        renderEditFeedbackContent(content, p, data);
      })
      .catch(function() {
        // APIなしの場合のフォールバック
        renderEditFeedbackContent(content, p, null);
      });
  }

  function renderEditFeedbackContent(container, p, apiData) {
    var vimeoUrl = '';
    var editedVideo = null;
    var feedbackComments = [];

    if (apiData) {
      editedVideo = apiData.edited_video || apiData.editedVideo || null;
      if (editedVideo) {
        vimeoUrl = editedVideo.vimeo_url || editedVideo.vimeoUrl || '';
      }
      feedbackComments = apiData.edit_feedback || apiData.editFeedback || [];
    }

    var vimeoId = extractVimeoId(vimeoUrl);

    var html = '<button class="back-btn" id="ef-back2">\u2190 \u623b\u308b</button>';

    // ヒーロー部分（グレード + スコア）
    var grade = 'B';
    var gradeScore = 7.2;
    if (apiData && apiData.quality_score) {
      gradeScore = apiData.quality_score / 10;
      if (gradeScore >= 8.5) grade = 'S';
      else if (gradeScore >= 7.5) grade = 'A';
      else if (gradeScore >= 6.0) grade = 'B';
      else grade = 'C';
    }
    var gradeColor = grade === 'S' ? 'var(--status-complete)' :
                     grade === 'A' ? 'var(--status-directed)' :
                     grade === 'B' ? 'var(--status-editing)' : 'var(--accent)';

    html += '<div class="ef-hero">' +
      '<div class="ef-grade-circle" style="border-color: ' + gradeColor + '; color: ' + gradeColor + '">' + grade + '</div>' +
      '<div class="ef-score-row">' +
        '<span class="ef-score-value">' + gradeScore.toFixed(1) + '</span>' +
        '<span class="ef-score-label"> / 10.0</span>' +
      '</div>' +
      '<div class="ef-score-bar"><div class="ef-score-bar-fill" style="width: ' + (gradeScore * 10) + '%; background: ' + gradeColor + '"></div></div>' +
    '</div>';

    // Vimeo埋め込みプレーヤー
    if (vimeoId) {
      html += '<div class="ef-section">' +
        '<div class="ef-section-header"><span class="ef-section-icon">VD</span>\u7de8\u96c6\u6e08\u307f\u52d5\u753b</div>' +
        '<div class="vimeo-player-wrap">' +
          '<iframe src="https://player.vimeo.com/video/' + vimeoId + '?title=0&byline=0&portrait=0" ' +
            'class="vimeo-iframe" frameborder="0" allow="autoplay; fullscreen" allowfullscreen></iframe>' +
        '</div>' +
      '</div>';
    } else {
      html += '<div class="ef-section">' +
        '<div class="ef-section-header"><span class="ef-section-icon">VD</span>\u7de8\u96c6\u6e08\u307f\u52d5\u753b</div>' +
        '<div class="ef-empty">\u7de8\u96c6\u6e08\u307f\u52d5\u753b\u304c\u307e\u3060\u30a2\u30c3\u30d7\u30ed\u30fc\u30c9\u3055\u308c\u3066\u3044\u307e\u305b\u3093</div>' +
      '</div>';
    }

    // FBコメント一覧
    html += '<div class="ef-section">' +
      '<div class="ef-section-header"><span class="ef-section-icon" style="background: var(--status-editing)">FB</span>\u30d5\u30a3\u30fc\u30c9\u30d0\u30c3\u30af\u30b3\u30e1\u30f3\u30c8</div>';

    if (feedbackComments.length > 0) {
      feedbackComments.forEach(function(fb) {
        var severity = fb.severity || fb.priority || 'info';
        var sevColor = severity === 'high' || severity === 'critical' ? 'var(--accent)' :
                       severity === 'medium' || severity === 'warning' ? 'var(--status-editing)' :
                       'var(--status-directed)';
        var catLabel = fb.category || fb.area || '\u5168\u822c';
        html += '<div class="ef-fb-item">' +
          '<div class="ef-fb-bar" style="background: ' + sevColor + '"></div>' +
          '<div class="ef-fb-body">' +
            '<div class="ef-fb-meta">' +
              '<span class="ef-fb-cat" style="color: ' + sevColor + '; background: ' + sevColor.replace(')', ', 0.15)').replace('var(', 'rgba(229,9,20,') + '">' + escapeHTML(catLabel) + '</span>' +
              (fb.area ? '<span class="ef-fb-area">' + escapeHTML(fb.area) + '</span>' : '') +
            '</div>' +
            '<div class="ef-fb-msg">' + escapeHTML(fb.message || fb.note || fb.text || '') + '</div>' +
          '</div>' +
        '</div>';
      });
    } else {
      // フォールバック: プロジェクトのreportSectionsから生成
      var section = MockData.reportSections[3]; // 音声FB履歴
      if (section) {
        section.items.forEach(function(item) {
          html += '<div class="ef-fb-item">' +
            '<div class="ef-fb-bar" style="background: var(--status-directed)"></div>' +
            '<div class="ef-fb-body">' +
              '<div class="ef-fb-msg">' + escapeHTML(item) + '</div>' +
            '</div>' +
          '</div>';
        });
      } else {
        html += '<div class="ef-empty">\u30d5\u30a3\u30fc\u30c9\u30d0\u30c3\u30af\u304c\u307e\u3060\u3042\u308a\u307e\u305b\u3093</div>';
      }
    }

    html += '</div>';

    // メタ情報
    html += '<div class="ef-section ef-meta-section">' +
      '<div class="ef-meta-row"><span class="ef-meta-label">\u30b2\u30b9\u30c8</span><span class="ef-meta-val">' + escapeHTML(p.guestName) + '</span></div>' +
      '<div class="ef-meta-row"><span class="ef-meta-label">\u64ae\u5f71\u65e5</span><span class="ef-meta-val">' + escapeHTML(p.shootDate) + '</span></div>' +
      (editedVideo && editedVideo.editor_name ? '<div class="ef-meta-row"><span class="ef-meta-label">\u7de8\u96c6\u8005</span><span class="ef-meta-val">' + escapeHTML(editedVideo.editor_name) + '</span></div>' : '') +
      (editedVideo && editedVideo.stage ? '<div class="ef-meta-row"><span class="ef-meta-label">\u7de8\u96c6\u6bb5\u968e</span><span class="ef-meta-val">' + escapeHTML(stageLabel(editedVideo.stage)) + '</span></div>' : '') +
    '</div>';

    container.innerHTML = html;

    document.getElementById('ef-back2').addEventListener('click', function() {
      navigateTo('report');
      if (currentProject) renderReport(currentProject);
    });
  }

  function stageLabel(stage) {
    var labels = { draft: '\u521d\u7a3f', revision_1: '\u4fee\u6b631', revision_2: '\u4fee\u6b632', final: '\u6700\u7d42\u7a3f' };
    return labels[stage] || stage || '';
  }

  // ===================================================================
  // 画面6: Vimeoレビュー表示
  // ===================================================================

  function openVimeoReview(project) {
    currentProject = project;
    navigateTo('vimeo-review');
    renderVimeoReview(project);
  }

  function renderVimeoReview(p) {
    var content = document.getElementById('vimeo-review-content');
    content.innerHTML = '<button class="back-btn" id="vr-back">\u2190 \u623b\u308b</button>' +
      '<div class="ef-loading"><div class="yt-loading-text">Vimeo\u30ec\u30d3\u30e5\u30fc\u3092\u8aad\u307f\u8fbc\u307f\u4e2d...</div></div>';

    document.getElementById('vr-back').addEventListener('click', function() {
      navigateTo('report');
      if (currentProject) renderReport(currentProject);
    });

    // API: POST /api/v1/vimeo/post-review?dry_run=true
    fetch('http://localhost:8210/api/v1/vimeo/post-review?dry_run=true', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: p.id })
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        renderVimeoReviewContent(content, p, data);
      })
      .catch(function() {
        // APIなしフォールバック: プロジェクト詳細から取得
        fetch('http://localhost:8210/api/projects/' + encodeURIComponent(p.id))
          .then(function(r) { return r.json(); })
          .then(function(data) {
            renderVimeoReviewContent(content, p, data);
          })
          .catch(function() {
            renderVimeoReviewContent(content, p, null);
          });
      });
  }

  function renderVimeoReviewContent(container, p, data) {
    var vimeoUrl = '';
    var feedbacks = [];
    var duration = 0;

    if (data) {
      // post-review APIレスポンス
      vimeoUrl = data.vimeo_url || data.vimeoUrl || '';
      feedbacks = data.feedbacks || data.timeline_feedbacks || data.timelineFeedbacks || [];
      duration = data.duration || data.video_duration || 0;

      // プロジェクト詳細から取得
      if (!vimeoUrl && data.edited_video) {
        vimeoUrl = data.edited_video.vimeo_url || data.edited_video.vimeoUrl || '';
      }
      if (!feedbacks.length && data.vimeo_feedbacks) {
        feedbacks = data.vimeo_feedbacks;
      }
    }

    var vimeoId = extractVimeoId(vimeoUrl);

    var html = '<button class="back-btn" id="vr-back2">\u2190 \u623b\u308b</button>';

    // ヘッダー
    html += '<div class="vr-header">' +
      '<div class="vr-title">Vimeo\u30ec\u30d3\u30e5\u30fc</div>' +
      '<div class="vr-subtitle">' + escapeHTML(p.guestName) + ' - ' + escapeHTML(p.title) + '</div>' +
    '</div>';

    // Vimeoプレーヤー
    if (vimeoId) {
      html += '<div class="vr-player-section">' +
        '<div class="vimeo-player-wrap">' +
          '<iframe id="vimeo-player-iframe" src="https://player.vimeo.com/video/' + vimeoId + '?title=0&byline=0&portrait=0" ' +
            'class="vimeo-iframe" frameborder="0" allow="autoplay; fullscreen" allowfullscreen></iframe>' +
        '</div>' +
      '</div>';
    } else {
      html += '<div class="vr-player-section">' +
        '<div class="ef-empty">Vimeo\u52d5\u753b\u304c\u307e\u3060\u767b\u9332\u3055\u308c\u3066\u3044\u307e\u305b\u3093</div>' +
      '</div>';
    }

    // タイムラインバー（FBマーカー付き）
    if (feedbacks.length > 0 && duration > 0) {
      html += '<div class="vr-timeline-section">' +
        '<div class="vr-timeline-label">\u30bf\u30a4\u30e0\u30e9\u30a4\u30f3 FB\u30de\u30fc\u30ab\u30fc</div>' +
        '<div class="vr-timeline-bar">' +
          '<div class="vr-timeline-track"></div>';

      feedbacks.forEach(function(fb, i) {
        var ts = fb.timestamp_seconds || fb.timestampMark || fb.timestamp || 0;
        var pos = (ts / duration) * 100;
        var priority = fb.priority || 'medium';
        var pColor = priority === 'high' || priority === 'critical' ? 'var(--accent)' :
                     priority === 'medium' ? 'var(--status-editing)' :
                     'var(--status-directed)';
        html += '<div class="vr-marker" style="left: ' + pos + '%; background: ' + pColor + '" data-fb-index="' + i + '" title="' + escapeAttr(fb.note || fb.text || '') + '"></div>';
      });

      html += '</div></div>';
    }

    // FB一覧
    html += '<div class="vr-fb-list">';

    if (feedbacks.length > 0) {
      feedbacks.forEach(function(fb) {
        var ts = fb.timestamp_seconds || fb.timestampMark || fb.timestamp || 0;
        var tsStr = formatTimestamp(ts);
        var priority = fb.priority || 'medium';
        var pColor = priority === 'high' || priority === 'critical' ? 'var(--accent)' :
                     priority === 'medium' ? 'var(--status-editing)' :
                     'var(--status-directed)';
        var element = fb.element || fb.category || '';
        var note = fb.note || fb.text || fb.message || '';

        html += '<div class="vr-fb-card">' +
          '<div class="vr-fb-left">' +
            '<div class="vr-fb-ts" style="color: var(--accent)">' + tsStr + '</div>' +
            '<div class="vr-fb-dot" style="background: ' + pColor + '"></div>' +
          '</div>' +
          '<div class="vr-fb-right">' +
            '<div class="vr-fb-element">' + escapeHTML(element) + '</div>' +
            '<div class="vr-fb-note">' + escapeHTML(note) + '</div>' +
            '<span class="vr-fb-priority" style="color: ' + pColor + '; background: ' + pColor.replace(')', ', 0.15)').replace('var(', 'rgba(229,9,20,') + '">' + escapeHTML(priority) + '</span>' +
          '</div>' +
        '</div>';
      });
    } else {
      html += '<div class="ef-empty">\u30bf\u30a4\u30e0\u30b3\u30fc\u30c9\u4ed8\u304dFB\u304c\u3042\u308a\u307e\u305b\u3093</div>';
    }

    html += '</div>';

    container.innerHTML = html;

    document.getElementById('vr-back2').addEventListener('click', function() {
      navigateTo('report');
      if (currentProject) renderReport(currentProject);
    });
  }

  // ===================================================================
  // 画面7: 映像トラッキング表示（NEW-4〜7）
  // ===================================================================

  function renderTrackingPage() {
    var content = document.getElementById('tracking-content');
    content.innerHTML = '<div class="ef-loading"><div class="yt-loading-text">\u30c8\u30e9\u30c3\u30ad\u30f3\u30b0\u30c7\u30fc\u30bf\u3092\u8aad\u307f\u8fbc\u307f\u4e2d...</div></div>';

    // 並列でAPI呼び出し
    var videosPromise = fetch('http://localhost:8210/api/tracking/videos')
      .then(function(r) { return r.ok ? r.json() : []; })
      .catch(function() { return []; });

    var summaryPromise = fetch('http://localhost:8210/api/v1/learning/summary')
      .then(function(r) { return r.ok ? r.json() : null; })
      .catch(function() { return null; });

    Promise.all([videosPromise, summaryPromise]).then(function(results) {
      var videos = results[0];
      var summary = results[1];
      // 配列でない場合（オブジェクト内にvideosキーがある場合）
      if (videos && !Array.isArray(videos) && videos.videos) {
        videos = videos.videos;
      }
      if (!Array.isArray(videos)) videos = [];
      renderTrackingContent(content, videos, summary);
    });
  }

  function tkStatCard(title, patterns, rules, videos) {
    var html = '<div class="tk-stat-card">' +
      '<div class="tk-stat-title">' + title + '</div>' +
      '<div class="tk-stat-nums">' +
        '<div class="tk-stat-num"><span class="tk-stat-big">' + patterns + '</span><span class="tk-stat-sub">\u30d1\u30bf\u30fc\u30f3</span></div>' +
        '<div class="tk-stat-num"><span class="tk-stat-big" style="color: var(--status-complete)">' + rules + '</span><span class="tk-stat-sub">\u30eb\u30fc\u30eb</span></div>';
    if (videos !== null && videos !== undefined) {
      html += '<div class="tk-stat-num"><span class="tk-stat-big" style="color: var(--status-directed)">' + videos + '</span><span class="tk-stat-sub">\u6620\u50cf</span></div>';
    }
    html += '</div></div>';
    return html;
  }

  // ===================================================================
  // ユーティリティ
  // ===================================================================

  function extractVimeoId(url) {
    if (!url) return '';
    var match = url.match(/vimeo\.com\/(?:video\/)?(\d+)/);
    return match ? match[1] : '';
  }

  function formatTimestamp(seconds) {
    var m = Math.floor(seconds / 60);
    var s = Math.floor(seconds % 60);
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }

  // ===== YouTube素材3機能（追加: 2026-03-15） =====

  // YouTube素材タブのメイン描画
  function renderYouTubeAssets(project) {
    const container = document.getElementById('report-sections');
    if (!project) {
      container.innerHTML = '<div class="yt-empty">プロジェクトが選択されていません</div>';
      return;
    }

    // ローディング表示
    container.innerHTML = '<div class="yt-loading"><div class="yt-loading-text">YouTube素材を読み込み中...</div></div>';

    // APIからfetch（失敗時はローカル生成でフォールバック）
    fetch('http://localhost:8210/api/projects/' + encodeURIComponent(project.id) + '/youtube-assets')
      .then(function(r) {
        if (!r.ok) throw new Error('not found');
        return r.json();
      })
      .then(function(data) {
        container.innerHTML = buildYouTubeAssetsHTML(data);
        setupYouTubeCopyHandlers(container);
      })
      .catch(function() {
        // APIなし or データなし: プロジェクト情報からローカル生成
        var localData = buildLocalYouTubeAssets(project);
        container.innerHTML = buildYouTubeAssetsHTML(localData);
        setupYouTubeCopyHandlers(container);
      });
  }

  // プロジェクト情報からYouTube素材をローカル生成（フォールバック）
  function buildLocalYouTubeAssets(project) {
    var name = project.guestName || 'ゲスト';
    var age = project.guestAge;
    var occ = project.guestOccupation || '会社員';
    var ageLabel = age ? (age + '歳') : '';

    return {
      thumbnail_design: {
        overall_concept: name + 'さんの対談動画 — ' + occ + 'が不動産投資を選んだ理由',
        font_suggestion: 'ヒラギノ角ゴ Pro W6 / Noto Sans JP Bold — 視認性重視',
        background_suggestion: 'ダークグラデーション（#1a1a2e → #16213e）+ ゲスト写真右配置',
        top_left: {
          role: 'フック（数字 or パンチライン）',
          content: ageLabel ? (ageLabel + ' ' + occ) : occ,
          color_suggestion: '白文字 + 黄色アクセント（年収部分）',
          notes: 'Z型の起点。最も目を引くゾーン。文字サイズ最大'
        },
        top_right: {
          role: '人物シルエット＋属性',
          content: ageLabel ? (name + 'さん（' + ageLabel + '）') : (name + 'さん'),
          color_suggestion: '写真 + 白テキストオーバーレイ',
          notes: 'ゲスト写真を配置。名前と属性を重ねる'
        },
        diagonal: {
          role: 'コンテンツ要素（対談のテーマ）',
          content: '本業×不動産投資の両立法',
          color_suggestion: '薄い青系バッジ',
          notes: 'Z型の対角線。視線誘導の中継点'
        },
        bottom_right: {
          role: 'ベネフィット（視聴者への約束）',
          content: '不動産投資のリアルが分かる',
          color_suggestion: '赤 or オレンジのCTAカラー',
          notes: 'Z型の終点。次のアクション（再生）を促す'
        }
      },
      title_proposals: {
        candidates: [
          {
            title: (ageLabel ? '【' + ageLabel + '】' : '') + occ + 'が語る「会社員×不動産投資」のリアル',
            appeal_type: 'ストーリー系',
            target_segment: '本業を持ちながら投資を検討している層',
            rationale: 'リアルなストーリーへの期待感を醸成'
          },
          {
            title: 'なぜ' + occ + 'は不動産投資を選んだのか？' + name + 'さんの決断',
            appeal_type: '問いかけ系',
            target_segment: '投資手法を比較検討中の層',
            rationale: '「なぜ」で視聴者の知的好奇心を刺激'
          },
          {
            title: name + 'さん対談 — ' + occ + 'の不動産投資ジャーニー【TEKO】',
            appeal_type: 'ブランド系',
            target_segment: 'TEKOチャンネル視聴者全般',
            rationale: 'チャンネルブランドと紐付けた信頼訴求'
          }
        ],
        recommended_index: 0
      },
      description_original: (ageLabel ? ageLabel + '、' : '') + occ + 'の' + name + 'さんが語る不動産投資のリアル。\n本業を持ちながら不動産投資に挑戦する' + name + 'さんの考え方や決断の背景に迫ります。\n\n▼ ゲストプロフィール\n・名前: ' + name + 'さん\n' + (age ? '・年齢: ' + ageLabel + '\n' : '') + (occ ? '・職業: ' + occ + '\n' : '') + '\n▼ チャプター\n0:00 オープニング・自己紹介\n※ 編集完了後にタイムスタンプを追加\n\n▼ TEKOについて\n不動産投資コミュニティ「TEKO」の対談シリーズです。\nメンバーのリアルな声をお届けしています。\n\n#不動産投資 #TEKO #対談 #サラリーマン投資家'
    };
  }

  // YouTube素材HTMLを組み立てる
  function buildYouTubeAssetsHTML(data) {
    var td = data.thumbnail_design || {};
    var tp = data.title_proposals || {};
    var desc = data.description_edited || data.description_original || '';
    var candidates = tp.candidates || [];
    var recommendedIdx = tp.recommended_index || 0;

    // Z型4ゾーン定義（左上→右上→対角→右下）
    var zones = [
      { key: 'top_left',     num: '①', pos: '左上',    colorClass: 'yt-zone-1', arrow: '→' },
      { key: 'top_right',    num: '②', pos: '右上',    colorClass: 'yt-zone-2', arrow: '↙' },
      { key: 'diagonal',     num: '③', pos: '中央対角', colorClass: 'yt-zone-3', arrow: '→' },
      { key: 'bottom_right', num: '④', pos: '右下',    colorClass: 'yt-zone-4', arrow: '' }
    ];

    // ゾーンカードHTML
    var zonesHTML = zones.map(function(z, i) {
      var zd = td[z.key] || {};
      return '<div class="yt-zone-card ' + z.colorClass + '">' +
        '<div class="yt-zone-header">' +
          '<span class="yt-zone-num">' + z.num + '</span>' +
          '<span class="yt-zone-pos">' + z.pos + '</span>' +
          (z.arrow ? '<span class="yt-zone-arrow">' + z.arrow + '</span>' : '') +
        '</div>' +
        '<div class="yt-zone-role">' + (zd.role || '') + '</div>' +
        '<div class="yt-zone-content">' + (zd.content || '') + '</div>' +
        (zd.color_suggestion ? '<div class="yt-zone-color"><span class="yt-zone-color-dot"></span>' + zd.color_suggestion + '</div>' : '') +
        (zd.notes ? '<div class="yt-zone-notes">' + zd.notes + '</div>' : '') +
      '</div>';
    }).join('');

    // タイトル案HTML
    var titlesHTML = candidates.map(function(c, i) {
      var isRec = (i === recommendedIdx);
      return '<div class="yt-title-item' + (isRec ? ' yt-title-rec' : '') + '" data-copy-text="' + escapeAttr(c.title) + '">' +
        '<div class="yt-title-badges">' +
          (isRec ? '<span class="yt-badge yt-badge-rec">推薦</span>' : '') +
          '<span class="yt-badge yt-badge-type">' + (c.appeal_type || '') + '</span>' +
        '</div>' +
        '<div class="yt-title-text">' + escapeHTML(c.title) + '</div>' +
        (c.target_segment ? '<div class="yt-title-segment">' + escapeHTML(c.target_segment) + '</div>' : '') +
        '<div class="yt-title-copy-hint">タップでコピー</div>' +
      '</div>';
    }).join('');

    // 概要欄HTML（pre要素でテキスト整形を保持）
    var descText = escapeHTML(desc);

    return '<div class="yt-assets-wrap">' +

      // 1. サムネイル指示書
      '<div class="yt-section">' +
        '<div class="yt-section-header">' +
          '<span class="yt-section-icon yt-icon-thumb">YT</span>' +
          '<span class="yt-section-title">サムネ生成ディレクション</span>' +
        '</div>' +
        (td.overall_concept ? '<div class="yt-concept">' + escapeHTML(td.overall_concept) + '</div>' : '') +
        '<div class="yt-meta-rows">' +
          (td.font_suggestion ? '<div class="yt-meta-row"><span class="yt-meta-label">フォント</span><span class="yt-meta-val">' + escapeHTML(td.font_suggestion) + '</span></div>' : '') +
          (td.background_suggestion ? '<div class="yt-meta-row"><span class="yt-meta-label">背景</span><span class="yt-meta-val">' + escapeHTML(td.background_suggestion) + '</span></div>' : '') +
        '</div>' +
        '<div class="yt-z-label">Z型視線誘導レイアウト</div>' +
        '<div class="yt-zones-grid">' + zonesHTML + '</div>' +
      '</div>' +

      // 2. タイトル案
      '<div class="yt-section">' +
        '<div class="yt-section-header">' +
          '<span class="yt-section-icon yt-icon-title">T</span>' +
          '<span class="yt-section-title">タイトル案</span>' +
          '<span class="yt-section-sub">タップでコピー</span>' +
        '</div>' +
        '<div class="yt-titles-list">' + titlesHTML + '</div>' +
      '</div>' +

      // 3. 概要欄
      '<div class="yt-section">' +
        '<div class="yt-section-header">' +
          '<span class="yt-section-icon yt-icon-desc">D</span>' +
          '<span class="yt-section-title">概要欄テキスト</span>' +
          '<button class="yt-copy-btn" data-copy-desc="1">コピー</button>' +
        '</div>' +
        '<pre class="yt-desc-pre" id="yt-desc-content">' + descText + '</pre>' +
      '</div>' +

    '</div>';
  }

  // コピー機能のセットアップ
  function setupYouTubeCopyHandlers(container) {
    // タイトルアイテムのタップコピー
    container.querySelectorAll('.yt-title-item[data-copy-text]').forEach(function(item) {
      item.addEventListener('click', function() {
        var text = item.getAttribute('data-copy-text');
        var hint = item.querySelector('.yt-title-copy-hint');
        ytCopyToClipboard(text, function(ok) {
          if (ok) {
            item.classList.add('yt-copied');
            if (hint) hint.textContent = '✓ コピー完了！';
            setTimeout(function() {
              item.classList.remove('yt-copied');
              if (hint) hint.textContent = 'タップでコピー';
            }, 2000);
          }
        });
      });
    });

    // 概要欄コピーボタン
    container.querySelectorAll('.yt-copy-btn[data-copy-desc]').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var target = document.getElementById('yt-desc-content');
        if (!target) return;
        var text = target.textContent;
        ytCopyToClipboard(text, function(ok) {
          if (ok) {
            btn.textContent = '✓ コピー完了！';
            btn.classList.add('yt-btn-copied');
            setTimeout(function() {
              btn.textContent = 'コピー';
              btn.classList.remove('yt-btn-copied');
            }, 2000);
          }
        });
      });
    });
  }

  // クリップボードコピーのユーティリティ
  function ytCopyToClipboard(text, callback) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text)
        .then(function() { callback(true); })
        .catch(function() { ytCopyFallback(text, callback); });
    } else {
      ytCopyFallback(text, callback);
    }
  }

  // クリップボードコピーのフォールバック（古いブラウザ向け）
  function ytCopyFallback(text, callback) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
    callback(ok);
  }

  // ===================================================================
  // トラッキングページ: 学習詳細表示（NEW-6: FB学習, NEW-7: 映像学習）
  // ===================================================================

  // トラッキングページを詳細版に拡張
  function renderTrackingContent(container, videos, summary) {
    var html = '';

    // 学習状況サマリー（既存を維持）
    if (summary) {
      var fbLearning = summary.feedback_learning || summary.feedbackLearning || {};
      var vidLearning = summary.video_learning || summary.videoLearning || {};

      html += '<div class="tk-section">' +
        '<div class="tk-section-title">\u5b66\u7fd2\u72b6\u6cc1</div>' +
        '<div class="tk-stats-row">' +
          tkStatCard('FB\u5b66\u7fd2', fbLearning.total_patterns || fbLearning.totalPatterns || 0, fbLearning.active_rules || fbLearning.activeRules || 0, null) +
          tkStatCard('\u6620\u50cf\u5b66\u7fd2', vidLearning.total_patterns || vidLearning.totalPatterns || 0, vidLearning.active_rules || vidLearning.activeRules || 0, vidLearning.total_source_videos || vidLearning.totalSourceVideos || null) +
        '</div>';

      // カテゴリ分布
      var catDist = (vidLearning.category_distribution || vidLearning.categoryDistribution);
      if (catDist && Object.keys(catDist).length > 0) {
        html += '<div class="tk-cat-dist">' +
          '<div class="tk-cat-label">\u30ab\u30c6\u30b4\u30ea\u5206\u5e03</div>' +
          '<div class="tk-cat-tags">';

        var catLabels = { cutting: '\u30ab\u30c3\u30c8', color: '\u8272\u5f69', tempo: '\u30c6\u30f3\u30dd', technique: '\u30c6\u30af\u30cb\u30c3\u30af', composition: '\u69cb\u56f3', telop: '\u30c6\u30ed\u30c3\u30d7', bgm: 'BGM', camera: '\u30ab\u30e1\u30e9', general: '\u5168\u822c' };
        var catColors = { cutting: '#E50914', color: '#F5A623', tempo: '#4A90D9', technique: '#46D369', composition: '#9B59B6' };

        var sorted = Object.entries(catDist).sort(function(a, b) { return b[1] - a[1]; });
        sorted.forEach(function(entry) {
          var key = entry[0], val = entry[1];
          var lbl = catLabels[key] || key;
          var clr = catColors[key] || '#808080';
          html += '<span class="tk-cat-tag" style="background: ' + clr + '">' + lbl + ' ' + val + '</span>';
        });

        html += '</div></div>';
      }

      html += '</div>';

      // ===== NEW-6: FB学習ルール詳細 =====
      var fbRules = fbLearning.rules || fbLearning.learned_rules || [];
      var fbPatterns = fbLearning.patterns || fbLearning.detected_patterns || [];

      html += '<div class="tk-section">' +
        '<div class="tk-section-title">FB\u5b66\u7fd2\u30eb\u30fc\u30eb\u8a73\u7d30</div>';

      if (fbRules.length > 0) {
        html += '<div class="learn-rules-list">';
        fbRules.forEach(function(rule) {
          var conf = rule.confidence || rule.score || 0;
          var confPct = Math.round(conf * 100);
          var applyCount = rule.apply_count || rule.applyCount || rule.applications || 0;
          var ruleText = rule.text || rule.rule || rule.description || '';
          var confColor = confPct >= 80 ? 'var(--status-complete)' : confPct >= 50 ? 'var(--status-editing)' : 'var(--accent)';

          html += '<div class="learn-rule-card">' +
            '<div class="learn-rule-text">' + escapeHTML(ruleText) + '</div>' +
            '<div class="learn-rule-meta">' +
              '<div class="learn-conf-bar-wrap">' +
                '<div class="learn-conf-label">\u78ba\u4fe1\u5ea6 ' + confPct + '%</div>' +
                '<div class="learn-conf-bar"><div class="learn-conf-fill" style="width:' + confPct + '%;background:' + confColor + '"></div></div>' +
              '</div>' +
              '<div class="learn-apply-count">\u9069\u7528 ' + applyCount + '\u56de</div>' +
            '</div>' +
          '</div>';
        });
        html += '</div>';
      } else {
        html += '<div class="ef-empty">FB\u5b66\u7fd2\u30eb\u30fc\u30eb\u304c\u307e\u3060\u3042\u308a\u307e\u305b\u3093</div>';
      }

      // FB学習パターン一覧
      if (fbPatterns.length > 0) {
        html += '<div class="learn-patterns-header">\u691c\u51fa\u30d1\u30bf\u30fc\u30f3</div>' +
          '<div class="learn-patterns-list">';
        fbPatterns.forEach(function(pat) {
          var freq = pat.frequency || pat.count || 0;
          var catTag = pat.category || pat.type || '\u5168\u822c';
          var patText = pat.pattern || pat.text || pat.description || '';

          html += '<div class="learn-pattern-item">' +
            '<div class="learn-pattern-text">' + escapeHTML(patText) + '</div>' +
            '<div class="learn-pattern-meta">' +
              '<span class="learn-pattern-freq">\u51fa\u73fe ' + freq + '\u56de</span>' +
              '<span class="learn-pattern-cat">' + escapeHTML(catTag) + '</span>' +
            '</div>' +
          '</div>';
        });
        html += '</div>';
      }

      // FB学習→ディレクション反映ビジュアライゼーション
      var fbImpact = fbLearning.direction_impact || fbLearning.directionImpact || null;
      if (fbImpact) {
        html += '<div class="learn-impact-section">' +
          '<div class="learn-impact-title">\u5b66\u7fd2\u306e\u30c7\u30a3\u30ec\u30af\u30b7\u30e7\u30f3\u53cd\u6620</div>' +
          renderImpactVisualization(fbImpact) +
        '</div>';
      }

      html += '</div>';

      // ===== NEW-7: VideoLearner 映像学習ルール詳細 =====
      var vidRules = vidLearning.rules || vidLearning.learned_rules || [];
      var vidTechniques = vidLearning.extracted_techniques || vidLearning.extractedTechniques || [];

      html += '<div class="tk-section">' +
        '<div class="tk-section-title">\u6620\u50cf\u5b66\u7fd2\u30eb\u30fc\u30eb\u8a73\u7d30</div>';

      if (vidRules.length > 0) {
        html += '<div class="learn-rules-list">';
        vidRules.forEach(function(rule) {
          var conf = rule.confidence || rule.score || 0;
          var confPct = Math.round(conf * 100);
          var cat = rule.category || '\u5168\u822c';
          var ruleText = rule.text || rule.rule || rule.description || '';
          var confColor = confPct >= 80 ? 'var(--status-complete)' : confPct >= 50 ? 'var(--status-editing)' : 'var(--accent)';

          html += '<div class="learn-rule-card">' +
            '<div class="learn-rule-head">' +
              '<span class="learn-rule-cat-tag">' + escapeHTML(cat) + '</span>' +
            '</div>' +
            '<div class="learn-rule-text">' + escapeHTML(ruleText) + '</div>' +
            '<div class="learn-rule-meta">' +
              '<div class="learn-conf-bar-wrap">' +
                '<div class="learn-conf-label">\u78ba\u4fe1\u5ea6 ' + confPct + '%</div>' +
                '<div class="learn-conf-bar"><div class="learn-conf-fill" style="width:' + confPct + '%;background:' + confColor + '"></div></div>' +
              '</div>' +
            '</div>' +
          '</div>';
        });
        html += '</div>';
      } else {
        html += '<div class="ef-empty">\u6620\u50cf\u5b66\u7fd2\u30eb\u30fc\u30eb\u304c\u307e\u3060\u3042\u308a\u307e\u305b\u3093</div>';
      }

      // 外部映像テクニック一覧
      if (vidTechniques.length > 0) {
        html += '<div class="learn-techniques-header">\u62bd\u51fa\u30c6\u30af\u30cb\u30c3\u30af\u4e00\u89a7</div>' +
          '<div class="learn-techniques-list">';
        vidTechniques.forEach(function(tech) {
          var techName = tech.name || tech.technique || '';
          var source = tech.source_video || tech.sourceVideo || '';
          var timestamp = tech.timestamp || tech.time || '';
          var desc = tech.description || '';

          html += '<div class="learn-tech-card">' +
            '<div class="learn-tech-name">' + escapeHTML(techName) + '</div>' +
            (desc ? '<div class="learn-tech-desc">' + escapeHTML(desc) + '</div>' : '') +
            (source ? '<div class="learn-tech-source">' +
              '<span class="learn-tech-source-icon">VD</span>' +
              '<span class="learn-tech-source-text">' + escapeHTML(source) +
                (timestamp ? ' (' + escapeHTML(timestamp) + ')' : '') +
              '</span>' +
            '</div>' : '') +
          '</div>';
        });
        html += '</div>';
      }

      html += '</div>';
    }

    // トラッキング動画一覧（既存と同じ構造を維持）
    html += '<div class="tk-section">' +
      '<div class="tk-section-title">\u30c8\u30e9\u30c3\u30ad\u30f3\u30b0\u4e2d\u306e\u52d5\u753b</div>';

    if (videos.length > 0) {
      videos.forEach(function(video) {
        var title = video.title || '\u7121\u984c';
        var channel = video.channel_name || video.channelName || '\u30c1\u30e3\u30f3\u30cd\u30eb\u672a\u8a2d\u5b9a';
        var status = video.analysis_status || video.analysisStatus || 'pending';
        var statusLbl = status === 'completed' ? '\u5206\u6790\u5b8c\u4e86' : status === 'analyzing' ? '\u5206\u6790\u4e2d' : '\u5f85\u6a5f\u4e2d';
        var statusClr = status === 'completed' ? 'var(--status-complete)' : status === 'analyzing' ? 'var(--status-editing)' : 'var(--text-muted)';

        var analysis = video.analysis_result || video.analysisResult || null;

        html += '<div class="tk-video-card">' +
          '<div class="tk-video-header">' +
            '<div class="tk-video-info">' +
              '<div class="tk-video-title">' + escapeHTML(title) + '</div>' +
              '<div class="tk-video-channel">' + escapeHTML(channel) + '</div>' +
            '</div>' +
            '<span class="tk-video-status" style="background: ' + statusClr + '">' + statusLbl + '</span>' +
          '</div>';

        if (analysis) {
          var details = [
            ['\u7dcf\u5408', analysis.overall_score || analysis.overallScore ? (analysis.overall_score || analysis.overallScore).toFixed(0) : '-'],
            ['\u69cb\u56f3', analysis.composition || '-'],
            ['\u30c6\u30f3\u30dd', analysis.tempo || '-'],
            ['\u30ab\u30c3\u30c8', analysis.cutting_style || analysis.cuttingStyle || '-'],
            ['\u8272\u5f69', analysis.color_grading || analysis.colorGrading || '-']
          ];
          details.forEach(function(d) {
            html += '<div class="tk-detail-row"><span class="tk-detail-label">' + d[0] + '</span><span class="tk-detail-val">' + escapeHTML(String(d[1])) + '</span></div>';
          });

          var techniques = analysis.key_techniques || analysis.keyTechniques || [];
          if (techniques.length > 0) {
            html += '<div class="tk-techniques">' +
              '<div class="tk-techniques-label">\u62bd\u51fa\u30c6\u30af\u30cb\u30c3\u30af</div>';
            techniques.forEach(function(t) {
              html += '<div class="tk-technique-item">\u30fb' + escapeHTML(t) + '</div>';
            });
            html += '</div>';
          }
        }

        html += '</div>';
      });
    } else {
      html += '<div class="ef-empty">\u30c8\u30e9\u30c3\u30ad\u30f3\u30b0\u4e2d\u306e\u52d5\u753b\u306f\u3042\u308a\u307e\u305b\u3093</div>';
    }

    html += '</div>';

    container.innerHTML = html;
  }

  // FB学習→ディレクション反映のビジュアライゼーション
  function renderImpactVisualization(impact) {
    var areas = impact.areas || impact.categories || [];
    if (!areas.length && typeof impact === 'object') {
      // オブジェクト形式の場合
      areas = Object.entries(impact).map(function(e) {
        return { name: e[0], score: e[1] };
      });
    }
    if (!areas.length) return '<div class="ef-empty">\u53cd\u6620\u30c7\u30fc\u30bf\u306a\u3057</div>';

    var maxScore = Math.max.apply(null, areas.map(function(a) { return a.score || a.value || 0; }));
    if (maxScore === 0) maxScore = 1;

    var html = '<div class="learn-impact-bars">';
    areas.forEach(function(area) {
      var name = area.name || area.category || '';
      var score = area.score || area.value || 0;
      var pct = Math.round((score / maxScore) * 100);
      html += '<div class="learn-impact-row">' +
        '<span class="learn-impact-name">' + escapeHTML(name) + '</span>' +
        '<div class="learn-impact-bar"><div class="learn-impact-fill" style="width:' + pct + '%"></div></div>' +
        '<span class="learn-impact-val">' + score + '</span>' +
      '</div>';
    });
    html += '</div>';
    return html;
  }

  // ===================================================================
  // フレーム画像マルチモデル評価（C-1）
  // ===================================================================

  function renderFrameEvaluation(project) {
    var container = document.getElementById('report-sections');
    if (!project) {
      container.innerHTML = '<div class="ef-empty">\u30d7\u30ed\u30b8\u30a7\u30af\u30c8\u304c\u9078\u629e\u3055\u308c\u3066\u3044\u307e\u305b\u3093</div>';
      return;
    }

    container.innerHTML = '<div class="ef-loading"><div class="yt-loading-text">\u30d5\u30ec\u30fc\u30e0\u8a55\u4fa1\u30c7\u30fc\u30bf\u3092\u8aad\u307f\u8fbc\u307f\u4e2d...</div></div>';

    fetch('http://localhost:8210/api/v1/projects/' + encodeURIComponent(project.id) + '/frame-evaluation')
      .then(function(r) {
        if (!r.ok) throw new Error('not found');
        return r.json();
      })
      .then(function(data) {
        container.innerHTML = buildFrameEvaluationHTML(data);
      })
      .catch(function() {
        container.innerHTML = '<div class="frame-eval-fallback">' +
          '<div class="frame-eval-empty-icon">FE</div>' +
          '<div class="frame-eval-empty-title">\u30d5\u30ec\u30fc\u30e0\u8a55\u4fa1\u672a\u5b9f\u65bd</div>' +
          '<div class="frame-eval-empty-sub">\u3053\u306e\u30d7\u30ed\u30b8\u30a7\u30af\u30c8\u306e\u30d5\u30ec\u30fc\u30e0\u8a55\u4fa1\u306f\u307e\u3060\u5b9f\u884c\u3055\u308c\u3066\u3044\u307e\u305b\u3093\u3002<br>\u54c1\u8cea\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u304b\u3089\u8a55\u4fa1\u3092\u958b\u59cb\u3067\u304d\u307e\u3059\u3002</div>' +
        '</div>';
      });
  }

  function buildFrameEvaluationHTML(data) {
    var frames = data.frames || data.evaluations || [];
    var overallScore = data.overall_score || data.overallScore || null;
    var summary = data.summary || '';

    var html = '<div class="frame-eval-wrap">';

    // 総合スコア
    if (overallScore !== null) {
      var sColor = scoreColor(overallScore);
      var sClass = scoreClass(overallScore);
      html += '<div class="frame-eval-overall">' +
        '<div class="frame-eval-overall-label">\u30d5\u30ec\u30fc\u30e0\u7dcf\u5408\u8a55\u4fa1</div>' +
        '<div class="frame-eval-overall-score ' + sClass + '" style="color:' + sColor + '">' + overallScore + '</div>' +
        (summary ? '<div class="frame-eval-summary">' + escapeHTML(summary) + '</div>' : '') +
      '</div>';
    }

    // 各フレーム評価
    if (frames.length > 0) {
      frames.forEach(function(frame, idx) {
        var frameScore = frame.score || frame.overall_score || 0;
        var fColor = scoreColor(frameScore);
        var fClass = scoreClass(frameScore);
        var timestamp = frame.timestamp || frame.time || '';
        var tsStr = typeof timestamp === 'number' ? formatTimestamp(timestamp) : (timestamp || '');
        var issues = frame.issues || frame.findings || [];
        var suggestions = frame.suggestions || frame.improvements || [];
        var models = frame.models || frame.model_scores || [];

        html += '<div class="frame-eval-card">' +
          '<div class="frame-eval-card-header">' +
            '<div class="frame-eval-frame-num">\u30d5\u30ec\u30fc\u30e0 #' + (idx + 1) + (tsStr ? ' (' + tsStr + ')' : '') + '</div>' +
            '<div class="frame-eval-frame-score ' + fClass + '" style="color:' + fColor + '">' + frameScore + '</div>' +
          '</div>';

        // モデル別スコア
        if (models.length > 0) {
          html += '<div class="frame-eval-models">';
          models.forEach(function(m) {
            var mName = m.model || m.name || '';
            var mScore = m.score || 0;
            var mColor = scoreColor(mScore);
            html += '<div class="frame-eval-model-item">' +
              '<span class="frame-eval-model-name">' + escapeHTML(mName) + '</span>' +
              '<span class="frame-eval-model-score" style="color:' + mColor + '">' + mScore + '</span>' +
            '</div>';
          });
          html += '</div>';
        }

        // 指摘事項
        if (issues.length > 0) {
          html += '<div class="frame-eval-issues">' +
            '<div class="frame-eval-sub-label">\u6307\u6458\u4e8b\u9805</div>';
          issues.forEach(function(issue) {
            var issueText = typeof issue === 'string' ? issue : (issue.text || issue.message || issue.description || '');
            var severity = typeof issue === 'object' ? (issue.severity || 'info') : 'info';
            var sevColor = severity === 'high' || severity === 'critical' ? 'var(--accent)' :
                           severity === 'medium' ? 'var(--status-editing)' : 'var(--status-directed)';
            html += '<div class="frame-eval-issue-item">' +
              '<div class="frame-eval-issue-dot" style="background:' + sevColor + '"></div>' +
              '<div class="frame-eval-issue-text">' + escapeHTML(issueText) + '</div>' +
            '</div>';
          });
          html += '</div>';
        }

        // 改善提案
        if (suggestions.length > 0) {
          html += '<div class="frame-eval-suggestions">' +
            '<div class="frame-eval-sub-label">\u6539\u5584\u63d0\u6848</div>';
          suggestions.forEach(function(sug) {
            var sugText = typeof sug === 'string' ? sug : (sug.text || sug.suggestion || sug.description || '');
            html += '<div class="frame-eval-sug-item">' +
              '<span class="frame-eval-sug-arrow">\u2192</span>' +
              '<span class="frame-eval-sug-text">' + escapeHTML(sugText) + '</span>' +
            '</div>';
          });
          html += '</div>';
        }

        html += '</div>';
      });
    } else {
      html += '<div class="ef-empty">\u30d5\u30ec\u30fc\u30e0\u8a55\u4fa1\u30c7\u30fc\u30bf\u304c\u3042\u308a\u307e\u305b\u3093</div>';
    }

    html += '</div>';
    return html;
  }

  // ===================================================================
  // ツールメニュー画面
  // ===================================================================

  function renderToolsMenu() {
    // ツールページ用のコンテナを探すか、page-tracking の構造と同様にコンテナに描画
    var page = document.getElementById('page-e2e-pipeline');
    // ツールタブは専用ページがないので、既存ページを全部非表示にして
    // ツールメニューをオーバーレイ的に表示する
    // → 実際にはnavigateToでpage-toolsが探されるがHTMLにないので
    // 代わりにモーダル風のツールメニューを生成する
    var existing = document.getElementById('tools-menu-overlay');
    if (existing) {
      existing.classList.add('visible');
      return;
    }

    var overlay = document.createElement('div');
    overlay.className = 'tools-menu-overlay visible';
    overlay.id = 'tools-menu-overlay';

    var tools = [
      { id: 'e2e-pipeline', icon: 'E2E', label: 'E2Eパイプライン', desc: '全工程一括実行' },
      { id: 'telop-check', icon: 'TC', label: 'テロップチェック', desc: '誤字脱字・フォント検証' },
      { id: 'audio-eval', icon: 'AE', label: '音声品質評価', desc: 'LUFS・ピーク・無音検出' },
      { id: 'knowledge-browse', icon: 'KN', label: 'ナレッジページ', desc: '166ページ全文検索' },
      { id: 'fb-learning', icon: 'FL', label: 'FB学習詳細', desc: 'パターン・ルール一覧' },
      { id: 'frame-eval-detail', icon: 'FE', label: 'フレーム評価詳細', desc: '評価履歴・カテゴリ別' },
      { id: 'pdca', icon: 'PD', label: 'PDCA品質改善', desc: 'Plan→Do→Check→Act' },
      { id: 'audit', icon: 'AU', label: '監査ループ', desc: '自動監査・履歴確認' },
      { id: 'editors', icon: 'ED', label: '編集者管理', desc: '編集者・引き継ぎ管理' },
      { id: 'notifications', icon: 'NT', label: '通知設定', desc: '通知チャネル設定' }
    ];

    overlay.innerHTML = '<div class="tools-menu-content">' +
      '<div class="tools-menu-header">' +
        '<span class="tools-menu-title">ツール</span>' +
        '<button class="tools-menu-close" id="tools-menu-close">\u2715</button>' +
      '</div>' +
      '<div class="tools-menu-grid">' +
        tools.map(function(t) {
          return '<button class="tools-menu-item" data-tool="' + t.id + '">' +
            '<div class="tools-menu-icon">' + t.icon + '</div>' +
            '<div class="tools-menu-label">' + t.label + '</div>' +
            '<div class="tools-menu-desc">' + t.desc + '</div>' +
          '</button>';
        }).join('') +
      '</div>' +
    '</div>';

    document.body.appendChild(overlay);

    // 閉じるボタン
    document.getElementById('tools-menu-close').addEventListener('click', function() {
      overlay.classList.remove('visible');
      navigateTo('home');
    });

    // 背景クリックで閉じる
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) {
        overlay.classList.remove('visible');
        navigateTo('home');
      }
    });

    // 各ツールボタン
    overlay.querySelectorAll('.tools-menu-item').forEach(function(btn) {
      btn.addEventListener('click', function() {
        overlay.classList.remove('visible');
        navigateTo(btn.dataset.tool);
      });
    });
  }

  // ===================================================================
  // 画面8: E2Eパイプライン
  // ===================================================================

  function renderE2EPipelinePage() {
    var content = document.getElementById('e2e-pipeline-content');
    var projects = (typeof MockData !== 'undefined' && MockData.projects) ? MockData.projects : [];

    content.innerHTML = '<button class="back-btn" id="e2e-back">\u2190 ツール</button>' +
      '<div class="e2e-form">' +
        '<div class="e2e-section">' +
          '<label class="e2e-label">プロジェクト選択</label>' +
          '<select class="e2e-select" id="e2e-project-select">' +
            '<option value="">-- 選択してください --</option>' +
            projects.map(function(p) {
              return '<option value="' + escapeAttr(p.id) + '">' + escapeHTML(p.guestName) + ' - ' + escapeHTML(p.title) + '</option>';
            }).join('') +
          '</select>' +
        '</div>' +
        '<div class="e2e-section">' +
          '<label class="e2e-label">Vimeo Video ID（任意）</label>' +
          '<input type="text" class="e2e-input" id="e2e-vimeo-id" placeholder="例: 123456789">' +
        '</div>' +
        '<div class="e2e-section">' +
          '<label class="e2e-toggle-wrap">' +
            '<input type="checkbox" id="e2e-dryrun" checked>' +
            '<span class="e2e-toggle-text">Dry Run（テスト実行）</span>' +
          '</label>' +
        '</div>' +
        '<button class="e2e-run-btn" id="e2e-run-btn">E2Eパイプライン実行</button>' +
      '</div>' +
      '<div class="e2e-progress" id="e2e-progress" style="display:none;"></div>' +
      '<div class="e2e-result" id="e2e-result" style="display:none;"></div>';

    document.getElementById('e2e-back').addEventListener('click', function() {
      renderToolsMenu();
    });

    document.getElementById('e2e-run-btn').addEventListener('click', function() {
      runE2EPipeline();
    });
  }

  function runE2EPipeline() {
    var pid = document.getElementById('e2e-project-select').value;
    if (!pid) {
      alert('プロジェクトを選択してください');
      return;
    }

    var vimeoId = document.getElementById('e2e-vimeo-id').value.trim();
    var dryRun = document.getElementById('e2e-dryrun').checked;
    var progressEl = document.getElementById('e2e-progress');
    var resultEl = document.getElementById('e2e-result');
    var runBtn = document.getElementById('e2e-run-btn');

    // 5段階のパイプラインステップ
    var steps = [
      { key: 'fb_fetch', label: 'FB取得', icon: '1' },
      { key: 'learning_rules', label: '学習ルール確認', icon: '2' },
      { key: 'video_insights', label: '映像インサイト', icon: '3' },
      { key: 'direction_gen', label: 'ディレクション生成', icon: '4' },
      { key: 'vimeo_post', label: 'Vimeo投稿', icon: '5' }
    ];

    // 進捗表示を初期化
    progressEl.style.display = 'block';
    resultEl.style.display = 'none';
    runBtn.disabled = true;
    progressEl.innerHTML = '<div class="e2e-steps">' +
      steps.map(function(s) {
        return '<div class="e2e-step" id="e2e-step-' + s.key + '">' +
          '<div class="e2e-step-icon e2e-step-pending">' + s.icon + '</div>' +
          '<div class="e2e-step-label">' + s.label + '</div>' +
          '<div class="e2e-step-status">待機中</div>' +
        '</div>';
      }).join('<div class="e2e-step-connector"></div>') +
    '</div>';

    var body = { dry_run: dryRun };
    if (vimeoId) body.vimeo_video_id = vimeoId;

    fetch('http://localhost:8210/api/v1/projects/' + encodeURIComponent(pid) + '/e2e-pipeline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        runBtn.disabled = false;
        var pipelineSteps = data.steps || data.pipeline_steps || [];

        // 各ステップのステータスを更新
        steps.forEach(function(s) {
          var el = document.getElementById('e2e-step-' + s.key);
          if (!el) return;
          var stepData = pipelineSteps.find(function(ps) { return ps.key === s.key || ps.step === s.key; });
          var status = stepData ? (stepData.status || 'pending') : 'pending';
          var iconEl = el.querySelector('.e2e-step-icon');
          var statusEl = el.querySelector('.e2e-step-status');

          iconEl.className = 'e2e-step-icon e2e-step-' + status;
          if (status === 'success') {
            statusEl.textContent = '成功';
            statusEl.style.color = 'var(--status-complete)';
          } else if (status === 'failed' || status === 'error') {
            statusEl.textContent = '失敗';
            statusEl.style.color = 'var(--accent)';
          } else if (status === 'skipped') {
            statusEl.textContent = 'スキップ';
            statusEl.style.color = 'var(--text-muted)';
          } else {
            statusEl.textContent = '完了';
            statusEl.style.color = 'var(--status-complete)';
          }
        });

        // 結果表示
        resultEl.style.display = 'block';
        var overall = data.status || data.overall_status || 'completed';
        resultEl.innerHTML = '<div class="e2e-result-card ' + (overall === 'failed' ? 'e2e-result-fail' : 'e2e-result-ok') + '">' +
          '<div class="e2e-result-title">' + (overall === 'failed' ? 'パイプライン失敗' : 'パイプライン完了') + '</div>' +
          (data.message ? '<div class="e2e-result-msg">' + escapeHTML(data.message) + '</div>' : '') +
          (dryRun ? '<div class="e2e-result-dryrun">Dry Runモード: 実際の投稿は行われていません</div>' : '') +
        '</div>';
      })
      .catch(function() {
        runBtn.disabled = false;
        // 全ステップを失敗表示
        steps.forEach(function(s) {
          var el = document.getElementById('e2e-step-' + s.key);
          if (!el) return;
          el.querySelector('.e2e-step-icon').className = 'e2e-step-icon e2e-step-failed';
          el.querySelector('.e2e-step-status').textContent = '接続エラー';
          el.querySelector('.e2e-step-status').style.color = 'var(--accent)';
        });
        resultEl.style.display = 'block';
        resultEl.innerHTML = '<div class="e2e-result-card e2e-result-fail">' +
          '<div class="e2e-result-title">接続エラー</div>' +
          '<div class="e2e-result-msg">サーバーに接続できませんでした。APIサーバーが起動しているか確認してください。</div>' +
        '</div>';
      });
  }

  // ===================================================================
  // 画面9: テロップチェック
  // ===================================================================

  function renderTelopCheckPage() {
    var content = document.getElementById('telop-check-content');
    var projects = (typeof MockData !== 'undefined' && MockData.projects) ? MockData.projects : [];

    content.innerHTML = '<button class="back-btn" id="tc-back">\u2190 ツール</button>' +
      '<div class="tc-form">' +
        '<div class="tc-section">' +
          '<label class="tc-label">プロジェクト選択</label>' +
          '<select class="e2e-select" id="tc-project-select">' +
            '<option value="">-- 選択してください --</option>' +
            projects.map(function(p) {
              return '<option value="' + escapeAttr(p.id) + '">' + escapeHTML(p.guestName) + ' - ' + escapeHTML(p.title) + '</option>';
            }).join('') +
          '</select>' +
        '</div>' +
        '<div class="tc-section">' +
          '<label class="tc-label">入力方式</label>' +
          '<div class="tc-input-toggle">' +
            '<button class="tc-toggle-btn active" data-mode="text" id="tc-mode-text">テキスト入力</button>' +
            '<button class="tc-toggle-btn" data-mode="image" id="tc-mode-image">フレーム画像</button>' +
          '</div>' +
        '</div>' +
        '<div class="tc-section" id="tc-text-area">' +
          '<label class="tc-label">テロップテキスト</label>' +
          '<textarea class="tc-textarea" id="tc-text-input" placeholder="チェックしたいテロップテキストを入力..."></textarea>' +
        '</div>' +
        '<div class="tc-section" id="tc-image-area" style="display:none;">' +
          '<label class="tc-label">フレーム画像</label>' +
          '<div class="tc-drop-zone" id="tc-drop-zone">' +
            '<div class="tc-drop-icon">+</div>' +
            '<div class="tc-drop-text">タップして画像を選択</div>' +
            '<input type="file" id="tc-file-input" accept="image/*" style="display:none;">' +
          '</div>' +
          '<div id="tc-preview" style="display:none;"></div>' +
        '</div>' +
        '<button class="e2e-run-btn" id="tc-run-btn">テロップチェック実行</button>' +
      '</div>' +
      '<div id="tc-result" style="display:none;"></div>';

    document.getElementById('tc-back').addEventListener('click', function() {
      renderToolsMenu();
    });

    // 入力モード切替
    document.getElementById('tc-mode-text').addEventListener('click', function() {
      document.getElementById('tc-text-area').style.display = 'block';
      document.getElementById('tc-image-area').style.display = 'none';
      this.classList.add('active');
      document.getElementById('tc-mode-image').classList.remove('active');
    });
    document.getElementById('tc-mode-image').addEventListener('click', function() {
      document.getElementById('tc-text-area').style.display = 'none';
      document.getElementById('tc-image-area').style.display = 'block';
      this.classList.add('active');
      document.getElementById('tc-mode-text').classList.remove('active');
    });

    // 画像アップロード
    var dropZone = document.getElementById('tc-drop-zone');
    var fileInput = document.getElementById('tc-file-input');
    dropZone.addEventListener('click', function() { fileInput.click(); });
    fileInput.addEventListener('change', function() {
      if (fileInput.files.length > 0) {
        var preview = document.getElementById('tc-preview');
        preview.style.display = 'block';
        preview.innerHTML = '<div class="tc-preview-file">\u2713 ' + escapeHTML(fileInput.files[0].name) + '</div>';
      }
    });

    document.getElementById('tc-run-btn').addEventListener('click', function() {
      runTelopCheck();
    });
  }

  function runTelopCheck() {
    var pid = document.getElementById('tc-project-select').value;
    if (!pid) {
      alert('プロジェクトを選択してください');
      return;
    }

    var resultEl = document.getElementById('tc-result');
    var runBtn = document.getElementById('tc-run-btn');
    runBtn.disabled = true;
    resultEl.style.display = 'block';
    resultEl.innerHTML = '<div class="ef-loading"><div class="yt-loading-text">テロップチェック中...</div></div>';

    var isTextMode = document.getElementById('tc-mode-text').classList.contains('active');
    var formData = new FormData();

    if (isTextMode) {
      var text = document.getElementById('tc-text-input').value;
      formData.append('telop_text', text);
    } else {
      var fileInput = document.getElementById('tc-file-input');
      if (fileInput.files.length > 0) {
        formData.append('frame_image', fileInput.files[0]);
      }
    }

    fetch('http://localhost:8210/api/v1/projects/' + encodeURIComponent(pid) + '/telop-check', {
      method: 'POST',
      body: formData
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        runBtn.disabled = false;
        renderTelopCheckResult(resultEl, data);
      })
      .catch(function() {
        runBtn.disabled = false;
        resultEl.innerHTML = '<div class="e2e-result-card e2e-result-fail">' +
          '<div class="e2e-result-title">接続エラー</div>' +
          '<div class="e2e-result-msg">サーバーに接続できませんでした。</div>' +
        '</div>';
      });
  }

  function renderTelopCheckResult(container, data) {
    var issues = data.issues || data.checks || data.results || [];
    var html = '<div class="tc-result-wrap">';

    // 総合判定
    var totalErrors = issues.filter(function(i) { return (i.severity || i.level) === 'error'; }).length;
    var totalWarnings = issues.filter(function(i) { return (i.severity || i.level) === 'warning'; }).length;
    var totalInfo = issues.filter(function(i) { return (i.severity || i.level) === 'info'; }).length;

    html += '<div class="tc-summary-row">' +
      '<span class="tc-summary-badge tc-sev-error">\u2717 エラー ' + totalErrors + '</span>' +
      '<span class="tc-summary-badge tc-sev-warning">\u26a0 警告 ' + totalWarnings + '</span>' +
      '<span class="tc-summary-badge tc-sev-info">\u24d8 情報 ' + totalInfo + '</span>' +
    '</div>';

    // 各問題の一覧
    if (issues.length > 0) {
      issues.forEach(function(issue) {
        var sev = issue.severity || issue.level || 'info';
        var sevClass = sev === 'error' ? 'tc-sev-error' : sev === 'warning' ? 'tc-sev-warning' : 'tc-sev-info';
        var msg = issue.message || issue.text || issue.description || '';
        var category = issue.category || issue.type || '';

        html += '<div class="tc-issue-card ' + sevClass + '-card">' +
          '<div class="tc-issue-sev ' + sevClass + '">' + sev.toUpperCase() + '</div>' +
          '<div class="tc-issue-body">' +
            (category ? '<div class="tc-issue-cat">' + escapeHTML(category) + '</div>' : '') +
            '<div class="tc-issue-msg">' + escapeHTML(msg) + '</div>' +
          '</div>' +
        '</div>';
      });
    } else {
      html += '<div class="tc-no-issues">' +
        '<div class="tc-ok-icon">\u2713</div>' +
        '<div class="tc-ok-text">テロップに問題は検出されませんでした</div>' +
      '</div>';
    }

    html += '</div>';
    container.innerHTML = html;
  }

  // ===================================================================
  // 画面10: 音声品質評価
  // ===================================================================

  function renderAudioEvalPage() {
    var content = document.getElementById('audio-eval-content');
    var projects = (typeof MockData !== 'undefined' && MockData.projects) ? MockData.projects : [];

    content.innerHTML = '<button class="back-btn" id="ae-back">\u2190 ツール</button>' +
      '<div class="ae-form">' +
        '<div class="e2e-section">' +
          '<label class="e2e-label">プロジェクト選択</label>' +
          '<select class="e2e-select" id="ae-project-select">' +
            '<option value="">-- 選択してください --</option>' +
            projects.map(function(p) {
              return '<option value="' + escapeAttr(p.id) + '">' + escapeHTML(p.guestName) + ' - ' + escapeHTML(p.title) + '</option>';
            }).join('') +
          '</select>' +
        '</div>' +
        '<div class="e2e-section">' +
          '<label class="e2e-label">動画パス（任意）</label>' +
          '<input type="text" class="e2e-input" id="ae-video-path" placeholder="/path/to/video.mp4">' +
        '</div>' +
        '<button class="e2e-run-btn" id="ae-run-btn">評価実行</button>' +
      '</div>' +
      '<div id="ae-result" style="display:none;"></div>';

    document.getElementById('ae-back').addEventListener('click', function() {
      renderToolsMenu();
    });

    document.getElementById('ae-run-btn').addEventListener('click', function() {
      runAudioEval();
    });
  }

  function runAudioEval() {
    var pid = document.getElementById('ae-project-select').value;
    if (!pid) {
      alert('プロジェクトを選択してください');
      return;
    }

    var videoPath = document.getElementById('ae-video-path').value.trim();
    var resultEl = document.getElementById('ae-result');
    var runBtn = document.getElementById('ae-run-btn');
    runBtn.disabled = true;
    resultEl.style.display = 'block';
    resultEl.innerHTML = '<div class="ef-loading"><div class="yt-loading-text">音声品質を評価中...</div></div>';

    var body = {};
    if (videoPath) body.video_path = videoPath;

    fetch('http://localhost:8210/api/v1/projects/' + encodeURIComponent(pid) + '/audio-evaluation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        runBtn.disabled = false;
        renderAudioEvalResult(resultEl, data);
      })
      .catch(function() {
        runBtn.disabled = false;
        resultEl.innerHTML = '<div class="e2e-result-card e2e-result-fail">' +
          '<div class="e2e-result-title">接続エラー</div>' +
          '<div class="e2e-result-msg">サーバーに接続できませんでした。</div>' +
        '</div>';
      });
  }

  function renderAudioEvalResult(container, data) {
    var metrics = data.metrics || data.audio_metrics || {};
    var issues = data.issues || data.problems || [];
    var overallScore = data.overall_score || data.score || null;

    var html = '<div class="ae-result-wrap">';

    // 総合スコア表示
    if (overallScore !== null) {
      var sColor = scoreColor(overallScore);
      var sClass = scoreClass(overallScore);
      html += '<div class="ae-overall">' +
        '<div class="ae-overall-label">音声品質スコア</div>' +
        '<div class="ae-overall-score ' + sClass + '" style="color:' + sColor + '">' + overallScore + '</div>' +
      '</div>';
    }

    // メトリクスカード
    var metricItems = [
      { key: 'loudness_lufs', label: '音量 (LUFS)', unit: 'LUFS' },
      { key: 'peak_dbfs', label: 'ピーク', unit: 'dBFS' },
      { key: 'dynamic_range', label: 'ダイナミックレンジ', unit: 'dB' },
      { key: 'silence_segments', label: '無音区間', unit: '箇所' },
      { key: 'sudden_changes', label: '急激な音量変化', unit: '箇所' }
    ];

    html += '<div class="ae-metrics-grid">';
    metricItems.forEach(function(m) {
      var val = metrics[m.key] !== undefined ? metrics[m.key] :
                metrics[m.key.replace(/_/g, '')] !== undefined ? metrics[m.key.replace(/_/g, '')] : '--';
      html += '<div class="ae-metric-card">' +
        '<div class="ae-metric-label">' + m.label + '</div>' +
        '<div class="ae-metric-value">' + val + '</div>' +
        '<div class="ae-metric-unit">' + m.unit + '</div>' +
      '</div>';
    });
    html += '</div>';

    // 問題リスト
    if (issues.length > 0) {
      html += '<div class="ae-issues-section">' +
        '<div class="ae-issues-title">検出された問題</div>';
      issues.forEach(function(issue) {
        var sev = issue.severity || issue.level || 'info';
        var sevColor = sev === 'error' || sev === 'critical' ? 'var(--accent)' :
                       sev === 'warning' ? 'var(--status-editing)' : 'var(--status-directed)';
        var msg = issue.message || issue.text || issue.description || '';
        html += '<div class="ae-issue-item">' +
          '<div class="ae-issue-dot" style="background:' + sevColor + '"></div>' +
          '<div class="ae-issue-body">' +
            '<div class="ae-issue-sev" style="color:' + sevColor + '">' + sev.toUpperCase() + '</div>' +
            '<div class="ae-issue-msg">' + escapeHTML(msg) + '</div>' +
          '</div>' +
        '</div>';
      });
      html += '</div>';
    } else {
      html += '<div class="tc-no-issues">' +
        '<div class="tc-ok-icon">\u2713</div>' +
        '<div class="tc-ok-text">音声品質に問題は検出されませんでした</div>' +
      '</div>';
    }

    html += '</div>';
    container.innerHTML = html;
  }

  // ===================================================================
  // 画面11: ナレッジページ閲覧
  // ===================================================================

  var knowledgeBrowseState = { pages: [], filteredPages: [], searchQuery: '', guestFilter: '' };

  function renderKnowledgeBrowsePage() {
    var content = document.getElementById('knowledge-browse-content');
    content.innerHTML = '<button class="back-btn" id="kb-back">\u2190 ツール</button>' +
      '<div class="kb-search-wrap">' +
        '<div class="search-bar">' +
          '<svg class="icon-search" viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>' +
          '<input type="text" id="kb-search" placeholder="ナレッジを検索...">' +
        '</div>' +
      '</div>' +
      '<div class="kb-filter-bar" id="kb-filters"></div>' +
      '<div class="kb-page-count" id="kb-page-count"></div>' +
      '<div class="kb-grid" id="kb-grid"></div>' +
      '<div class="kb-modal-overlay" id="kb-modal" style="display:none;">' +
        '<div class="kb-modal-content">' +
          '<div class="kb-modal-header">' +
            '<span class="kb-modal-title" id="kb-modal-title"></span>' +
            '<button class="kb-modal-close" id="kb-modal-close">\u2715</button>' +
          '</div>' +
          '<div class="kb-modal-body" id="kb-modal-body"></div>' +
        '</div>' +
      '</div>';

    document.getElementById('kb-back').addEventListener('click', function() {
      renderToolsMenu();
    });

    document.getElementById('kb-modal-close').addEventListener('click', function() {
      document.getElementById('kb-modal').style.display = 'none';
    });
    document.getElementById('kb-modal').addEventListener('click', function(e) {
      if (e.target === this) this.style.display = 'none';
    });

    // ページ一覧を取得
    content.querySelector('.kb-grid').innerHTML = '<div class="ef-loading"><div class="yt-loading-text">ナレッジページを読み込み中...</div></div>';

    fetch('http://localhost:8210/api/v1/knowledge/pages')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var pages = data.pages || data || [];
        knowledgeBrowseState.pages = pages;
        knowledgeBrowseState.filteredPages = pages;
        renderKnowledgeFilters(pages);
        renderKnowledgeGrid(pages);
      })
      .catch(function() {
        // フォールバック: knowledge-pages-mapから取得
        var pages = [];
        if (typeof KNOWLEDGE_PAGES_MAP !== 'undefined') {
          Object.keys(KNOWLEDGE_PAGES_MAP).forEach(function(name) {
            pages.push({ guest_name: name, filename: KNOWLEDGE_PAGES_MAP[name], title: name + ' ナレッジページ' });
          });
        }
        knowledgeBrowseState.pages = pages;
        knowledgeBrowseState.filteredPages = pages;
        renderKnowledgeFilters(pages);
        renderKnowledgeGrid(pages);
      });

    // 検索ハンドラー
    document.getElementById('kb-search').addEventListener('input', function() {
      knowledgeBrowseState.searchQuery = this.value.toLowerCase();
      filterKnowledgePages();
    });
  }

  function renderKnowledgeFilters(pages) {
    var guests = [];
    var seen = {};
    pages.forEach(function(p) {
      var name = p.guest_name || p.guestName || '';
      if (name && !seen[name]) {
        seen[name] = true;
        guests.push(name);
      }
    });
    guests.sort();

    var filterBar = document.getElementById('kb-filters');
    filterBar.innerHTML = '<button class="filter-btn active" data-guest="">すべて</button>' +
      guests.map(function(g) {
        return '<button class="filter-btn" data-guest="' + escapeAttr(g) + '">' + escapeHTML(g) + '</button>';
      }).join('');

    filterBar.querySelectorAll('.filter-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        filterBar.querySelectorAll('.filter-btn').forEach(function(b) { b.classList.remove('active'); });
        btn.classList.add('active');
        knowledgeBrowseState.guestFilter = btn.dataset.guest;
        filterKnowledgePages();
      });
    });
  }

  function filterKnowledgePages() {
    var pages = knowledgeBrowseState.pages;
    var query = knowledgeBrowseState.searchQuery;
    var guest = knowledgeBrowseState.guestFilter;

    var filtered = pages.filter(function(p) {
      var name = (p.guest_name || p.guestName || '').toLowerCase();
      var title = (p.title || '').toLowerCase();
      var matchSearch = !query || name.includes(query) || title.includes(query);
      var matchGuest = !guest || (p.guest_name || p.guestName || '') === guest;
      return matchSearch && matchGuest;
    });

    // 検索APIも使う
    if (query && query.length >= 2) {
      fetch('http://localhost:8210/api/v1/knowledge/search?q=' + encodeURIComponent(query))
        .then(function(r) { return r.json(); })
        .then(function(data) {
          var searchResults = data.results || data.pages || data || [];
          // マージ（重複除去）
          var ids = {};
          filtered.forEach(function(p) { ids[p.filename || p.id] = true; });
          searchResults.forEach(function(p) {
            var key = p.filename || p.id;
            if (!ids[key]) {
              filtered.push(p);
              ids[key] = true;
            }
          });
          renderKnowledgeGrid(filtered);
        })
        .catch(function() {
          renderKnowledgeGrid(filtered);
        });
    } else {
      renderKnowledgeGrid(filtered);
    }
  }

  function renderKnowledgeGrid(pages) {
    var grid = document.getElementById('kb-grid');
    var countEl = document.getElementById('kb-page-count');
    countEl.textContent = pages.length + '件のナレッジページ';

    if (pages.length === 0) {
      grid.innerHTML = '<div class="ef-empty">該当するナレッジページがありません</div>';
      return;
    }

    grid.innerHTML = pages.map(function(p) {
      var guestName = p.guest_name || p.guestName || '';
      var title = p.title || guestName + ' ナレッジ';
      var filename = p.filename || '';

      return '<div class="kb-card" data-filename="' + escapeAttr(filename) + '" data-title="' + escapeAttr(title) + '">' +
        '<div class="kb-card-icon">KN</div>' +
        '<div class="kb-card-body">' +
          '<div class="kb-card-guest">' + escapeHTML(guestName) + '</div>' +
          '<div class="kb-card-title">' + escapeHTML(title) + '</div>' +
        '</div>' +
      '</div>';
    }).join('');

    grid.querySelectorAll('.kb-card').forEach(function(card) {
      card.addEventListener('click', function() {
        var filename = card.dataset.filename;
        var title = card.dataset.title;
        openKnowledgeModal(filename, title);
      });
    });
  }

  function openKnowledgeModal(filename, title) {
    var modal = document.getElementById('kb-modal');
    var modalTitle = document.getElementById('kb-modal-title');
    var modalBody = document.getElementById('kb-modal-body');

    modalTitle.textContent = title;
    modal.style.display = 'flex';

    if (filename) {
      modalBody.innerHTML = '<iframe src="knowledge-pages/' + encodeURIComponent(filename) + '" class="kb-iframe" sandbox="allow-same-origin"></iframe>';
    } else {
      modalBody.innerHTML = '<div class="ef-empty">コンテンツを読み込めません</div>';
    }
  }

  // ===================================================================
  // 画面12: FB学習詳細
  // ===================================================================

  function renderFBLearningPage() {
    var content = document.getElementById('fb-learning-content');
    content.innerHTML = '<button class="back-btn" id="fbl-back">\u2190 ツール</button>' +
      '<div class="ef-loading"><div class="yt-loading-text">FB学習データを読み込み中...</div></div>';

    document.getElementById('fbl-back').addEventListener('click', function() {
      renderToolsMenu();
    });

    // 並列でAPI呼び出し
    var patternsPromise = fetch('http://localhost:8210/api/learning/feedback-patterns')
      .then(function(r) { return r.ok ? r.json() : null; })
      .catch(function() { return null; });

    var summaryPromise = fetch('http://localhost:8210/api/learning/summary')
      .then(function(r) { return r.ok ? r.json() : null; })
      .catch(function() { return null; });

    Promise.all([patternsPromise, summaryPromise]).then(function(results) {
      var patternsData = results[0];
      var summaryData = results[1];
      renderFBLearningContent(content, patternsData, summaryData);
    });
  }

  function renderFBLearningContent(container, patternsData, summaryData) {
    var html = '<button class="back-btn" id="fbl-back2">\u2190 ツール</button>';

    // サマリー統計
    var fbLearning = {};
    if (summaryData) {
      fbLearning = summaryData.feedback_learning || summaryData.feedbackLearning || summaryData || {};
    }

    var totalPatterns = fbLearning.total_patterns || fbLearning.totalPatterns || 0;
    var activeRules = fbLearning.active_rules || fbLearning.activeRules || 0;
    var totalFeedbacks = fbLearning.total_feedbacks || fbLearning.totalFeedbacks || 0;

    html += '<div class="fbl-stats-row">' +
      '<div class="fbl-stat-card">' +
        '<div class="fbl-stat-num">' + totalPatterns + '</div>' +
        '<div class="fbl-stat-label">検出パターン</div>' +
      '</div>' +
      '<div class="fbl-stat-card">' +
        '<div class="fbl-stat-num" style="color:var(--status-complete)">' + activeRules + '</div>' +
        '<div class="fbl-stat-label">有効ルール</div>' +
      '</div>' +
      '<div class="fbl-stat-card">' +
        '<div class="fbl-stat-num" style="color:var(--status-directed)">' + totalFeedbacks + '</div>' +
        '<div class="fbl-stat-label">学習元FB</div>' +
      '</div>' +
    '</div>';

    // パターン一覧テーブル
    var patterns = [];
    if (patternsData) {
      patterns = patternsData.patterns || patternsData.detected_patterns || patternsData || [];
    }
    if (Array.isArray(patterns) && patterns.length > 0) {
      html += '<div class="fbl-section">' +
        '<div class="fbl-section-title">パターン一覧</div>' +
        '<div class="fbl-table-wrap">' +
          '<table class="fbl-table">' +
            '<thead><tr>' +
              '<th>カテゴリ</th><th>パターン</th><th>確信度</th><th>頻度</th>' +
            '</tr></thead>' +
            '<tbody>';

      patterns.forEach(function(pat) {
        var cat = pat.category || pat.type || '全般';
        var text = pat.pattern || pat.text || pat.description || '';
        var conf = pat.confidence || pat.score || 0;
        var confPct = Math.round(conf * 100);
        var freq = pat.frequency || pat.count || 0;
        var confColor = confPct >= 80 ? 'var(--status-complete)' : confPct >= 50 ? 'var(--status-editing)' : 'var(--accent)';

        html += '<tr>' +
          '<td><span class="fbl-cat-badge">' + escapeHTML(cat) + '</span></td>' +
          '<td class="fbl-text-cell">' + escapeHTML(text) + '</td>' +
          '<td><div class="fbl-conf-cell"><div class="fbl-conf-bar"><div class="fbl-conf-fill" style="width:' + confPct + '%;background:' + confColor + '"></div></div><span class="fbl-conf-pct">' + confPct + '%</span></div></td>' +
          '<td class="fbl-freq-cell">' + freq + '回</td>' +
        '</tr>';
      });

      html += '</tbody></table></div></div>';
    }

    // ルール一覧テーブル
    var rules = fbLearning.rules || fbLearning.learned_rules || [];
    if (rules.length > 0) {
      html += '<div class="fbl-section">' +
        '<div class="fbl-section-title">ルール一覧</div>' +
        '<div class="fbl-table-wrap">' +
          '<table class="fbl-table">' +
            '<thead><tr>' +
              '<th>ルール</th><th>カテゴリ</th><th>優先度</th><th>生成日</th>' +
            '</tr></thead>' +
            '<tbody>';

      rules.forEach(function(rule) {
        var rText = rule.text || rule.rule || rule.description || '';
        var rCat = rule.category || '全般';
        var rPriority = rule.priority || rule.weight || '';
        var rDate = rule.created_at || rule.createdAt || rule.date || '';

        html += '<tr>' +
          '<td class="fbl-text-cell">' + escapeHTML(rText) + '</td>' +
          '<td><span class="fbl-cat-badge">' + escapeHTML(rCat) + '</span></td>' +
          '<td>' + escapeHTML(String(rPriority)) + '</td>' +
          '<td class="fbl-date-cell">' + escapeHTML(rDate) + '</td>' +
        '</tr>';
      });

      html += '</tbody></table></div></div>';
    }

    container.innerHTML = html;

    document.getElementById('fbl-back2').addEventListener('click', function() {
      renderToolsMenu();
    });
  }

  // ===================================================================
  // 画面13: フレーム評価詳細
  // ===================================================================

  function renderFrameEvalDetailPage() {
    var content = document.getElementById('frame-eval-detail-content');
    var projects = (typeof MockData !== 'undefined' && MockData.projects) ? MockData.projects : [];

    content.innerHTML = '<button class="back-btn" id="fed-back">\u2190 ツール</button>' +
      '<div class="fed-form">' +
        '<div class="e2e-section">' +
          '<label class="e2e-label">プロジェクト選択</label>' +
          '<select class="e2e-select" id="fed-project-select">' +
            '<option value="">-- 選択してください --</option>' +
            projects.map(function(p) {
              return '<option value="' + escapeAttr(p.id) + '">' + escapeHTML(p.guestName) + ' - ' + escapeHTML(p.title) + '</option>';
            }).join('') +
          '</select>' +
        '</div>' +
        '<button class="e2e-run-btn" id="fed-run-btn">評価データ取得</button>' +
      '</div>' +
      '<div id="fed-result" style="display:none;"></div>';

    document.getElementById('fed-back').addEventListener('click', function() {
      renderToolsMenu();
    });

    document.getElementById('fed-run-btn').addEventListener('click', function() {
      runFrameEvalDetail();
    });
  }

  function runFrameEvalDetail() {
    var pid = document.getElementById('fed-project-select').value;
    if (!pid) {
      alert('プロジェクトを選択してください');
      return;
    }

    var resultEl = document.getElementById('fed-result');
    var runBtn = document.getElementById('fed-run-btn');
    runBtn.disabled = true;
    resultEl.style.display = 'block';
    resultEl.innerHTML = '<div class="ef-loading"><div class="yt-loading-text">フレーム評価データを取得中...</div></div>';

    fetch('http://localhost:8210/api/v1/projects/' + encodeURIComponent(pid) + '/frame-evaluation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        runBtn.disabled = false;
        renderFrameEvalDetailResult(resultEl, data);
      })
      .catch(function() {
        runBtn.disabled = false;
        resultEl.innerHTML = '<div class="e2e-result-card e2e-result-fail">' +
          '<div class="e2e-result-title">接続エラー</div>' +
          '<div class="e2e-result-msg">サーバーに接続できませんでした。</div>' +
        '</div>';
      });
  }

  function renderFrameEvalDetailResult(container, data) {
    var frames = data.frames || data.evaluations || [];
    var overallScore = data.overall_score || data.overallScore || null;
    var summary = data.summary || '';
    var categories = data.categories || data.category_scores || {};
    var history = data.history || data.evaluation_history || [];

    var html = '<div class="fed-result-wrap">';

    // 総合スコア
    if (overallScore !== null) {
      var sColor = scoreColor(overallScore);
      html += '<div class="ae-overall">' +
        '<div class="ae-overall-label">フレーム総合評価</div>' +
        '<div class="ae-overall-score" style="color:' + sColor + '">' + overallScore + '</div>' +
        (summary ? '<div class="frame-eval-summary">' + escapeHTML(summary) + '</div>' : '') +
      '</div>';
    }

    // カテゴリ別評価
    var catEntries = Object.entries(categories);
    if (catEntries.length > 0) {
      html += '<div class="fed-section">' +
        '<div class="fed-section-title">カテゴリ別評価</div>' +
        '<div class="fed-cat-grid">';
      catEntries.forEach(function(entry) {
        var catName = entry[0];
        var catScore = entry[1];
        var cColor = scoreColor(typeof catScore === 'number' ? catScore : (catScore.score || 0));
        var cVal = typeof catScore === 'number' ? catScore : (catScore.score || 0);
        html += '<div class="fed-cat-card">' +
          '<div class="fed-cat-name">' + escapeHTML(catName) + '</div>' +
          '<div class="fed-cat-score" style="color:' + cColor + '">' + cVal + '</div>' +
          '<div class="fed-cat-bar"><div class="fed-cat-bar-fill" style="width:' + cVal + '%;background:' + cColor + '"></div></div>' +
        '</div>';
      });
      html += '</div></div>';
    }

    // 各フレーム詳細（既存のbuildFrameEvaluationHTMLと同じ構造）
    if (frames.length > 0) {
      html += '<div class="fed-section">' +
        '<div class="fed-section-title">各フレーム評価詳細</div>';
      frames.forEach(function(frame, idx) {
        var frameScore = frame.score || frame.overall_score || 0;
        var fColor = scoreColor(frameScore);
        var timestamp = frame.timestamp || frame.time || '';
        var tsStr = typeof timestamp === 'number' ? formatTimestamp(timestamp) : (timestamp || '');
        var issues = frame.issues || frame.findings || [];
        var suggestions = frame.suggestions || frame.improvements || [];

        html += '<div class="frame-eval-card">' +
          '<div class="frame-eval-card-header">' +
            '<div class="frame-eval-frame-num">フレーム #' + (idx + 1) + (tsStr ? ' (' + tsStr + ')' : '') + '</div>' +
            '<div class="frame-eval-frame-score" style="color:' + fColor + '">' + frameScore + '</div>' +
          '</div>';

        if (issues.length > 0) {
          html += '<div class="frame-eval-issues"><div class="frame-eval-sub-label">指摘事項</div>';
          issues.forEach(function(issue) {
            var issueText = typeof issue === 'string' ? issue : (issue.text || issue.message || '');
            var sev = typeof issue === 'object' ? (issue.severity || 'info') : 'info';
            var sevColor = sev === 'error' || sev === 'critical' ? 'var(--accent)' :
                           sev === 'medium' ? 'var(--status-editing)' : 'var(--status-directed)';
            html += '<div class="frame-eval-issue-item"><div class="frame-eval-issue-dot" style="background:' + sevColor + '"></div><div class="frame-eval-issue-text">' + escapeHTML(issueText) + '</div></div>';
          });
          html += '</div>';
        }

        if (suggestions.length > 0) {
          html += '<div class="frame-eval-suggestions"><div class="frame-eval-sub-label">改善提案</div>';
          suggestions.forEach(function(sug) {
            var sugText = typeof sug === 'string' ? sug : (sug.text || sug.suggestion || '');
            html += '<div class="frame-eval-sug-item"><span class="frame-eval-sug-arrow">\u2192</span><span class="frame-eval-sug-text">' + escapeHTML(sugText) + '</span></div>';
          });
          html += '</div>';
        }

        html += '</div>';
      });
      html += '</div>';
    }

    // 過去の評価履歴
    if (history.length > 0) {
      html += '<div class="fed-section">' +
        '<div class="fed-section-title">過去の評価履歴</div>';
      history.forEach(function(h) {
        var hDate = h.date || h.created_at || h.createdAt || '';
        var hScore = h.score || h.overall_score || 0;
        var hColor = scoreColor(hScore);
        var hFrames = h.frame_count || h.frameCount || 0;
        html += '<div class="fed-history-card">' +
          '<div class="fed-history-date">' + escapeHTML(hDate) + '</div>' +
          '<div class="fed-history-score" style="color:' + hColor + '">' + hScore + '</div>' +
          '<div class="fed-history-frames">' + hFrames + 'フレーム</div>' +
        '</div>';
      });
      html += '</div>';
    }

    html += '</div>';
    container.innerHTML = html;
  }

  // ===================================================================
  // 画面14: PDCA品質改善
  // ===================================================================

  function renderPDCAPage() {
    var content = document.getElementById('pdca-content');
    content.innerHTML = '<button class="back-btn" id="pdca-back">\u2190 ツール</button>' +
      '<div class="pdca-loading">読み込み中...</div>';

    document.getElementById('pdca-back').addEventListener('click', function() {
      renderToolsMenu();
    });

    // サマリーとステート情報を並列取得
    var summaryData = null;
    var statesData = null;
    var loaded = 0;

    function renderPDCAContent() {
      loaded++;
      if (loaded < 2) return;

      var html = '';

      // サマリーカード
      if (summaryData) {
        html += '<div class="pdca-summary-grid">' +
          '<div class="pdca-summary-card">' +
            '<div class="pdca-summary-value">' + (summaryData.total_projects || 0) + '</div>' +
            '<div class="pdca-summary-label">総プロジェクト</div>' +
          '</div>' +
          '<div class="pdca-summary-card">' +
            '<div class="pdca-summary-value pdca-val-green">' + (summaryData.completed || 0) + '</div>' +
            '<div class="pdca-summary-label">完了</div>' +
          '</div>' +
          '<div class="pdca-summary-card">' +
            '<div class="pdca-summary-value pdca-val-yellow">' + (summaryData.in_progress || 0) + '</div>' +
            '<div class="pdca-summary-label">進行中</div>' +
          '</div>' +
          '<div class="pdca-summary-card">' +
            '<div class="pdca-summary-value pdca-val-red">' + (summaryData.issues || 0) + '</div>' +
            '<div class="pdca-summary-label">要対応</div>' +
          '</div>' +
        '</div>';
      }

      // PDCAステート一覧
      var phases = ['Plan', 'Do', 'Check', 'Act'];
      if (statesData && statesData.length > 0) {
        html += '<div class="pdca-states-list">';
        statesData.forEach(function(item) {
          var currentPhase = item.current_phase || item.phase || 'Plan';
          var currentIdx = phases.indexOf(currentPhase);
          if (currentIdx < 0) currentIdx = 0;

          html += '<div class="pdca-state-card">' +
            '<div class="pdca-state-header">' +
              '<div class="pdca-state-name">' + escapeHTML(item.project_name || item.name || '不明') + '</div>' +
              '<div class="pdca-state-phase">' + escapeHTML(currentPhase) + '</div>' +
            '</div>' +
            '<div class="pdca-step-indicator">';
          phases.forEach(function(phase, idx) {
            var cls = 'pdca-step';
            if (idx < currentIdx) cls += ' pdca-step-done';
            if (idx === currentIdx) cls += ' pdca-step-active';
            html += '<div class="' + cls + '">' +
              '<div class="pdca-step-dot"></div>' +
              '<div class="pdca-step-label">' + phase + '</div>' +
            '</div>';
            if (idx < phases.length - 1) {
              html += '<div class="pdca-step-line' + (idx < currentIdx ? ' pdca-step-line-done' : '') + '"></div>';
            }
          });
          html += '</div>';

          if (item.note || item.description) {
            html += '<div class="pdca-state-note">' + escapeHTML(item.note || item.description) + '</div>';
          }
          html += '</div>';
        });
        html += '</div>';
      } else {
        html += '<div class="pdca-empty">PDCAデータがありません</div>';
      }

      content.innerHTML = '<button class="back-btn" id="pdca-back2">\u2190 ツール</button>' + html;
      document.getElementById('pdca-back2').addEventListener('click', function() {
        renderToolsMenu();
      });
    }

    // API呼び出し: サマリー
    fetch('/api/pdca/summary')
      .then(function(r) { return r.json(); })
      .then(function(data) { summaryData = data; renderPDCAContent(); })
      .catch(function() { summaryData = { total_projects: 0, completed: 0, in_progress: 0, issues: 0 }; renderPDCAContent(); });

    // API呼び出し: ステート一覧
    fetch('/api/pdca/states')
      .then(function(r) { return r.json(); })
      .then(function(data) { statesData = Array.isArray(data) ? data : (data.states || []); renderPDCAContent(); })
      .catch(function() { statesData = []; renderPDCAContent(); });
  }

  // ===================================================================
  // 画面15: 監査ループ
  // ===================================================================

  function renderAuditPage() {
    var content = document.getElementById('audit-content');
    content.innerHTML = '<button class="back-btn" id="audit-back">\u2190 ツール</button>' +
      '<div class="audit-loading">読み込み中...</div>';

    document.getElementById('audit-back').addEventListener('click', function() {
      renderToolsMenu();
    });

    var latestData = null;
    var historyData = null;
    var loaded = 0;

    function renderAuditContent() {
      loaded++;
      if (loaded < 2) return;

      var html = '';

      // 手動監査実行ボタン
      html += '<div class="audit-action-bar">' +
        '<button class="audit-run-btn" id="audit-run-btn">手動監査実行</button>' +
      '</div>';

      // 最新監査レポート
      html += '<div class="audit-section-title">最新監査レポート</div>';
      if (latestData && latestData.id) {
        var statusCls = latestData.status === 'pass' ? 'audit-status-pass' : 'audit-status-fail';
        html += '<div class="audit-latest-card">' +
          '<div class="audit-latest-header">' +
            '<div class="audit-latest-date">' + escapeHTML(latestData.date || latestData.created_at || '') + '</div>' +
            '<div class="audit-status ' + statusCls + '">' + escapeHTML(latestData.status || '不明') + '</div>' +
          '</div>' +
          '<div class="audit-latest-score">スコア: <strong>' + (latestData.score || 0) + '</strong> / 100</div>';
        if (latestData.issues && latestData.issues.length > 0) {
          html += '<div class="audit-issues-title">検出事項</div><ul class="audit-issues-list">';
          latestData.issues.forEach(function(issue) {
            html += '<li>' + escapeHTML(typeof issue === 'string' ? issue : (issue.message || issue.description || '')) + '</li>';
          });
          html += '</ul>';
        }
        html += '</div>';
      } else {
        html += '<div class="audit-empty">最新の監査データがありません</div>';
      }

      // 監査履歴
      html += '<div class="audit-section-title">監査履歴（直近10件）</div>';
      if (historyData && historyData.length > 0) {
        html += '<div class="audit-history-list">';
        historyData.slice(0, 10).forEach(function(h) {
          var hStatusCls = h.status === 'pass' ? 'audit-status-pass' : 'audit-status-fail';
          html += '<div class="audit-history-card">' +
            '<div class="audit-history-date">' + escapeHTML(h.date || h.created_at || '') + '</div>' +
            '<div class="audit-history-score">' + (h.score || 0) + '</div>' +
            '<div class="audit-status ' + hStatusCls + '">' + escapeHTML(h.status || '') + '</div>' +
          '</div>';
        });
        html += '</div>';
      } else {
        html += '<div class="audit-empty">監査履歴がありません</div>';
      }

      content.innerHTML = '<button class="back-btn" id="audit-back2">\u2190 ツール</button>' + html;
      document.getElementById('audit-back2').addEventListener('click', function() {
        renderToolsMenu();
      });

      // 手動監査実行ボタンのイベント
      var runBtn = document.getElementById('audit-run-btn');
      if (runBtn) {
        runBtn.addEventListener('click', function() {
          runBtn.disabled = true;
          runBtn.textContent = '監査実行中...';
          fetch('/api/audit/run', { method: 'POST' })
            .then(function(r) { return r.json(); })
            .then(function(result) {
              runBtn.disabled = false;
              runBtn.textContent = '手動監査実行';
              // 監査完了後に画面リフレッシュ
              renderAuditPage();
            })
            .catch(function() {
              runBtn.disabled = false;
              runBtn.textContent = '手動監査実行';
              alert('監査実行に失敗しました');
            });
        });
      }
    }

    // API呼び出し: 最新監査
    fetch('/api/audit/latest')
      .then(function(r) { return r.json(); })
      .then(function(data) { latestData = data; renderAuditContent(); })
      .catch(function() { latestData = {}; renderAuditContent(); });

    // API呼び出し: 監査履歴
    fetch('/api/audit/history')
      .then(function(r) { return r.json(); })
      .then(function(data) { historyData = Array.isArray(data) ? data : (data.history || []); renderAuditContent(); })
      .catch(function() { historyData = []; renderAuditContent(); });
  }

  // ===================================================================
  // 画面16: 編集者管理
  // ===================================================================

  function renderEditorsPage() {
    var content = document.getElementById('editors-content');
    content.innerHTML = '<button class="back-btn" id="editors-back">\u2190 ツール</button>' +
      '<div class="editors-loading">読み込み中...</div>';

    document.getElementById('editors-back').addEventListener('click', function() {
      renderToolsMenu();
    });

    fetch('/api/editors')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var editors = Array.isArray(data) ? data : (data.editors || []);
        renderEditorsContent(editors);
      })
      .catch(function() {
        renderEditorsContent([]);
      });

    function renderEditorsContent(editors) {
      var html = '<button class="back-btn" id="editors-back2">\u2190 ツール</button>';

      // 新規編集者登録フォーム
      html += '<div class="editors-form-section">' +
        '<div class="editors-form-title">新規編集者登録</div>' +
        '<div class="editors-form">' +
          '<input type="text" class="editors-input" id="editor-name" placeholder="名前">' +
          '<input type="text" class="editors-input" id="editor-skills" placeholder="スキル（カンマ区切り）">' +
          '<button class="editors-add-btn" id="editor-add-btn">登録</button>' +
        '</div>' +
      '</div>';

      // 編集者一覧
      html += '<div class="editors-section-title">編集者一覧</div>';
      if (editors.length > 0) {
        html += '<div class="editors-grid">';
        editors.forEach(function(ed) {
          var skills = ed.skills || [];
          if (typeof skills === 'string') skills = skills.split(',');
          html += '<div class="editors-card">' +
            '<div class="editors-card-header">' +
              '<div class="editors-card-name">' + escapeHTML(ed.name || '不明') + '</div>' +
              '<div class="editors-card-count">' + (ed.project_count || ed.projects || 0) + '件</div>' +
            '</div>' +
            '<div class="editors-card-skills">';
          skills.forEach(function(s) {
            html += '<span class="editors-skill-tag">' + escapeHTML(s.trim()) + '</span>';
          });
          html += '</div>' +
            '<button class="editors-handover-btn" data-eid="' + escapeAttr(ed.id || ed.editor_id || '') + '">引き継ぎパッケージ生成</button>' +
          '</div>';
        });
        html += '</div>';
      } else {
        html += '<div class="editors-empty">編集者が登録されていません</div>';
      }

      content.innerHTML = html;

      // 戻るボタン
      document.getElementById('editors-back2').addEventListener('click', function() {
        renderToolsMenu();
      });

      // 新規登録ボタン
      document.getElementById('editor-add-btn').addEventListener('click', function() {
        var nameVal = document.getElementById('editor-name').value.trim();
        var skillsVal = document.getElementById('editor-skills').value.trim();
        if (!nameVal) { alert('名前を入力してください'); return; }

        var btn = document.getElementById('editor-add-btn');
        btn.disabled = true;
        btn.textContent = '登録中...';

        fetch('/api/editors', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: nameVal, skills: skillsVal.split(',').map(function(s) { return s.trim(); }) })
        })
          .then(function(r) { return r.json(); })
          .then(function() {
            btn.disabled = false;
            btn.textContent = '登録';
            renderEditorsPage(); // リフレッシュ
          })
          .catch(function() {
            btn.disabled = false;
            btn.textContent = '登録';
            alert('登録に失敗しました');
          });
      });

      // 引き継ぎパッケージ生成ボタン
      content.querySelectorAll('.editors-handover-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var eid = btn.dataset.eid;
          btn.disabled = true;
          btn.textContent = '生成中...';
          fetch('/api/editors/' + eid + '/handover')
            .then(function(r) { return r.json(); })
            .then(function(data) {
              btn.disabled = false;
              btn.textContent = '引き継ぎパッケージ生成';
              alert('引き継ぎパッケージを生成しました: ' + (data.path || data.url || 'OK'));
            })
            .catch(function() {
              btn.disabled = false;
              btn.textContent = '引き継ぎパッケージ生成';
              alert('生成に失敗しました');
            });
        });
      });
    }
  }

  // ===================================================================
  // 画面17: 通知設定
  // ===================================================================

  function renderNotificationsPage() {
    var content = document.getElementById('notifications-content');
    content.innerHTML = '<button class="back-btn" id="notif-back">\u2190 ツール</button>' +
      '<div class="notif-loading">読み込み中...</div>';

    document.getElementById('notif-back').addEventListener('click', function() {
      renderToolsMenu();
    });

    fetch('/api/notifications/config')
      .then(function(r) { return r.json(); })
      .then(function(config) {
        renderNotifContent(config);
      })
      .catch(function() {
        // デフォルト設定でレンダリング
        renderNotifContent({
          slack_enabled: false,
          email_enabled: false,
          line_enabled: false,
          on_complete: true,
          on_error: true,
          on_review: true,
          daily_digest: false
        });
      });

    function renderNotifContent(config) {
      var toggles = [
        { key: 'slack_enabled', label: 'Slack通知', desc: 'Slackチャネルに通知' },
        { key: 'email_enabled', label: 'メール通知', desc: 'メールで通知' },
        { key: 'line_enabled', label: 'LINE通知', desc: 'LINEに通知' },
        { key: 'on_complete', label: '完了時通知', desc: '処理完了時に通知する' },
        { key: 'on_error', label: 'エラー時通知', desc: 'エラー発生時に通知する' },
        { key: 'on_review', label: 'レビュー時通知', desc: 'レビュー待ち時に通知する' },
        { key: 'daily_digest', label: 'デイリーダイジェスト', desc: '1日のサマリーを送信' }
      ];

      var html = '<button class="back-btn" id="notif-back2">\u2190 ツール</button>';

      html += '<div class="notif-toggles">';
      toggles.forEach(function(t) {
        var checked = config[t.key] ? 'checked' : '';
        html += '<div class="notif-toggle-row">' +
          '<div class="notif-toggle-info">' +
            '<div class="notif-toggle-label">' + t.label + '</div>' +
            '<div class="notif-toggle-desc">' + t.desc + '</div>' +
          '</div>' +
          '<label class="notif-switch">' +
            '<input type="checkbox" data-key="' + t.key + '" ' + checked + '>' +
            '<span class="notif-switch-slider"></span>' +
          '</label>' +
        '</div>';
      });
      html += '</div>';

      // アクションボタン
      html += '<div class="notif-actions">' +
        '<button class="notif-save-btn" id="notif-save-btn">設定を保存</button>' +
        '<button class="notif-test-btn" id="notif-test-btn">テスト通知送信</button>' +
      '</div>';

      content.innerHTML = html;

      // 戻るボタン
      document.getElementById('notif-back2').addEventListener('click', function() {
        renderToolsMenu();
      });

      // 保存ボタン
      document.getElementById('notif-save-btn').addEventListener('click', function() {
        var newConfig = {};
        content.querySelectorAll('.notif-switch input[type="checkbox"]').forEach(function(cb) {
          newConfig[cb.dataset.key] = cb.checked;
        });

        var btn = document.getElementById('notif-save-btn');
        btn.disabled = true;
        btn.textContent = '保存中...';

        fetch('/api/notifications/config', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newConfig)
        })
          .then(function(r) { return r.json(); })
          .then(function() {
            btn.disabled = false;
            btn.textContent = '設定を保存';
            // 保存成功フィードバック
            btn.textContent = '保存しました ✓';
            setTimeout(function() { btn.textContent = '設定を保存'; }, 2000);
          })
          .catch(function() {
            btn.disabled = false;
            btn.textContent = '設定を保存';
            alert('設定の保存に失敗しました');
          });
      });

      // テスト通知ボタン
      document.getElementById('notif-test-btn').addEventListener('click', function() {
        var btn = document.getElementById('notif-test-btn');
        btn.disabled = true;
        btn.textContent = '送信中...';

        fetch('/api/notifications/test', { method: 'POST' })
          .then(function(r) { return r.json(); })
          .then(function() {
            btn.disabled = false;
            btn.textContent = 'テスト通知送信';
            btn.textContent = '送信しました ✓';
            setTimeout(function() { btn.textContent = 'テスト通知送信'; }, 2000);
          })
          .catch(function() {
            btn.disabled = false;
            btn.textContent = 'テスト通知送信';
            alert('テスト通知の送信に失敗しました');
          });
      });
    }
  }

  // HTML文字列エスケープ
  function escapeHTML(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // HTML属性値エスケープ
  function escapeAttr(str) {
    if (!str) return '';
    return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

})();
