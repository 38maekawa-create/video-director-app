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
  }

  // ===== 録音モーダル =====
  function createRecordingModal() {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'recording-modal';
    modal.innerHTML = `
      <div class="modal-content">
        <div class="modal-text">音声フィードバック</div>
        <div class="modal-subtext">タップして録音を開始</div>
        <button class="modal-record-btn" id="modal-record-btn">
          <svg viewBox="0 0 24 24"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg>
        </button>
        <button class="modal-close" id="modal-close">閉じる</button>
      </div>
    `;
    document.body.appendChild(modal);

    document.getElementById('modal-close').addEventListener('click', () => {
      showRecordingModal(false);
    });

    document.getElementById('modal-record-btn').addEventListener('click', () => {
      isRecording = !isRecording;
      const btn = document.getElementById('modal-record-btn');
      btn.classList.toggle('recording', isRecording);
      document.querySelector('.modal-subtext').textContent = isRecording ? '録音中... タップして停止' : 'タップして録音を開始';
    });

    // 背景クリックで閉じる
    modal.addEventListener('click', (e) => {
      if (e.target === modal) showRecordingModal(false);
    });
  }

  function showRecordingModal(show) {
    const modal = document.getElementById('recording-modal');
    if (modal) {
      modal.classList.toggle('visible', show);
      if (!show) {
        isRecording = false;
        const btn = document.getElementById('modal-record-btn');
        if (btn) btn.classList.remove('recording');
      }
    }
  }

  // ===== リサイズ対応（Canvas再描画） =====
  window.addEventListener('resize', () => {
    if (currentTab === 'quality') {
      drawTrendChart();
    }
  });

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
