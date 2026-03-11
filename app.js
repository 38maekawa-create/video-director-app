// VideoDirectorAgent WebApp MVP
// HTML + CSS + JS のみ。フレームワーク不使用。

(function() {
  'use strict';

  // ===== 状態管理 =====
  let currentTab = 'home';
  let currentProject = null;
  let historyFilter = 'all';
  let isRecording = false;
  let currentReportTab = '概要';

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
  function hasNavigableUrl(url) {
    return !!url && !String(url).startsWith('#');
  }

  function renderTranscriptBlock(fullTranscript) {
    if (!fullTranscript) return '<div class="transcript-empty">全文スクリプトはまだ未設定です。</div>';
    return `<div class="transcript-block">${String(fullTranscript).replace(/\n/g, '<br>')}</div>`;
  }

  function renderExternalLink(url, label, className = 'detail-link') {
    if (!hasNavigableUrl(url)) {
      return `<span class="${className} is-disabled" aria-disabled="true">${label}</span>`;
    }
    return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="${className}">${label}</a>`;
  }

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
    const integrationStates = [
      { label: '素材', ok: !!p.sourceVideo },
      { label: '編集後', ok: !!p.editedVideo },
      { label: 'KB', ok: !!p.knowledge },
      { label: 'Vimeo', ok: !!p.vimeoReview }
    ];

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
        <div class="card-status-line">
          <span class="card-status-pill" data-status="${p.status}">${p.statusLabel}</span>
          ${p.feedbackSummary?.historyCount ? `<span class="card-status-meta">FB ${p.feedbackSummary.historyCount}</span>` : ''}
        </div>
        <div class="card-flags">
          <span class="card-flag">素材</span>
          <span class="card-flag">編集後</span>
          ${p.knowledge ? '<span class="card-flag">KB</span>' : ''}
          ${p.feedbackSummary?.historyCount ? `<span class="card-flag">FB ${p.feedbackSummary.historyCount}</span>` : ''}
        </div>
        <div class="card-integration-bar">
          ${integrationStates.map(state => `
            <div class="integration-chip ${state.ok ? 'ready' : 'missing'}">${state.label}</div>
          `).join('')}
        </div>
        ${p.feedbackSummary?.latestFeedback ? `
          <div class="card-feedback-preview">${p.feedbackSummary.latestFeedback}</div>
        ` : ''}
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
    currentReportTab = '概要';

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
          <button class="btn-vimeo ${hasNavigableUrl(p.vimeoReview?.url) ? '' : 'is-disabled'}" id="open-vimeo-review" ${hasNavigableUrl(p.vimeoReview?.url) ? '' : 'disabled'}>▶ Vimeoレビューを開く</button>
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
    document.getElementById('open-vimeo-review').addEventListener('click', () => {
      if (!hasNavigableUrl(p.vimeoReview?.url)) return;
      window.open(p.vimeoReview.url, '_blank', 'noopener,noreferrer');
    });

    // タブ
    renderReportTabs();
    renderReportTab(currentReportTab);

    // 下部アクションバー表示
    showBottomActionBar(true);
  }

  function renderReportTabs() {
    const tabs = ['概要', 'ディレクション', '素材', '編集後', 'FB / 評価', 'ナレッジ'];

    const container = document.getElementById('report-tabs');
    container.innerHTML = tabs.map((t, i) => `
      <button class="tab-selector-btn ${i === 0 ? 'active' : ''}" data-tab-name="${t}">
        <span class="tab-label">${t}</span>
        <div class="tab-indicator"></div>
      </button>
    `).join('');

    container.querySelectorAll('.tab-selector-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        container.querySelectorAll('.tab-selector-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentReportTab = btn.dataset.tabName;
        renderReportTab(currentReportTab);
      });
    });
  }

  function renderReportTab(tabName) {
    switch (tabName) {
      case '概要':
        renderOverviewSection();
        break;
      case 'ディレクション':
        renderDirectionSection();
        break;
      case '素材':
        renderSourceSection();
        break;
      case '編集後':
        renderEditedSection();
        break;
      case 'FB / 評価':
        renderFeedbackSection();
        break;
      case 'ナレッジ':
        renderKnowledgeSection();
        break;
      default:
        renderOverviewSection();
    }
  }

  function getProjectFeedbackItems(project) {
    return MockData.historyItems.filter(item => item.videoId === project.videoId);
  }

  function timestampToSeconds(timestamp) {
    if (!timestamp) return 0;
    const parts = timestamp.split(':').map(n => parseInt(n, 10));
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    return 0;
  }

  function durationToSeconds(duration) {
    return timestampToSeconds(duration);
  }

function getProjectKnowledgeFile(project) {
  if (typeof findKnowledgePage !== 'function') return null;
  return findKnowledgePage(project.guestName);
}

function wireReportTabJumps(container) {
  container.querySelectorAll('[data-report-tab]').forEach(button => {
    button.addEventListener('click', () => {
      currentReportTab = button.dataset.reportTab;
      renderReport();
    });
  });
}


function refreshProjectSyncSummary(project) {
  const items = getProjectFeedbackItems(project);
  const pendingItems = items.filter(item => !item.isSent || item.syncState === 'pending_sync' || item.syncState === 'draftOnly');
  project.hasUnsentFeedback = pendingItems.length > 0;
  project.feedbackSummary = project.feedbackSummary || {};
  project.feedbackSummary.historyCount = items.length;
  project.feedbackSummary.latestFeedback = items[0]?.convertedText || project.feedbackSummary.latestFeedback || '';
  project.vimeoReview = project.vimeoReview || {};
  project.vimeoReview.pendingCount = pendingItems.length;
  project.vimeoReview.lastSyncedAt = new Date().toLocaleString('ja-JP');

  if (pendingItems.length === 0) {
    project.vimeoReview.syncStatus = 'awaiting_editor';
    project.vimeoReview.statusLabel = '編集者確認待ち';
  } else if (pendingItems.length < items.length) {
    project.vimeoReview.syncStatus = 'partial';
    project.vimeoReview.statusLabel = '一部未送信あり';
  } else {
    project.vimeoReview.syncStatus = 'draftOnly';
    project.vimeoReview.statusLabel = '変換レビュー待ち';
  }
}

function simulateRelaySend(project) {
  const items = getProjectFeedbackItems(project);
  let sentCount = 0;
  items.forEach(item => {
    if (!item.isSent || item.syncState === 'pending_sync' || item.syncState === 'draftOnly') {
      item.isSent = true;
      item.syncState = 'awaiting_editor';
      item.editorStatus = '編集者確認待ち';
      sentCount += 1;
    }
  });
  project.relay = project.relay || {};
  project.relay.routeStatus = sentCount > 0 ? 'sent' : (project.relay.routeStatus || 'ready');
  refreshProjectSyncSummary(project);
  renderHome();
  renderReport();
}

function renderOverviewSection() {
  const p = currentProject;
  const feedbackItems = getProjectFeedbackItems(p);
  const pendingItems = feedbackItems.filter(item => !item.isSent || item.syncState !== 'synced');
  const knowledgeFile = getProjectKnowledgeFile(p);
  const knowledgeHighlights = p.knowledge?.highlights || [];
  const container = document.getElementById('report-sections');

  container.innerHTML = `
    <div class="report-stack">
      <div class="info-card">
        <div class="info-card-title">案件サマリー</div>
        <div class="info-grid two-col">
          <div class="info-pill">
            <span class="info-pill-label">videoId</span>
            <span class="info-pill-value">${p.videoId}</span>
          </div>
          <div class="info-pill">
            <span class="info-pill-label">Vimeo</span>
            <span class="info-pill-value">${p.vimeoReview?.statusLabel || '未設定'}</span>
          </div>
          <div class="info-pill">
            <span class="info-pill-label">素材</span>
            <span class="info-pill-value">${p.sourceVideo?.duration || '-'}</span>
          </div>
          <div class="info-pill">
            <span class="info-pill-label">FB件数</span>
            <span class="info-pill-value">${feedbackItems.length}</span>
          </div>
        </div>
        <div class="summary-callout">
          ${p.feedbackSummary?.evaluation || 'この案件の評価サマリーは未設定です。'}
        </div>
      </div>

      <div class="before-after-board">
        <div class="ba-card">
          <div class="ba-label">BEFORE</div>
          <div class="ba-title">${p.sourceVideo?.title || '素材未設定'}</div>
          <div class="ba-meta">${p.sourceVideo?.duration || '-'} / ${p.sourceVideo?.summary || ''}</div>
        </div>
        <div class="ba-arrow">→</div>
        <div class="ba-card after">
          <div class="ba-label">AFTER</div>
          <div class="ba-title">${p.editedVideo?.title || '編集後未設定'}</div>
          <div class="ba-meta">${p.editedVideo?.statusLabel || '-'} / 品質 ${p.editedVideo?.qualityScore ?? '-'}</div>
        </div>
      </div>

      <div class="info-card">
        <div class="info-card-title">連携状況</div>
        <div class="link-list">
          <div class="link-row"><span>素材URL</span>${renderExternalLink(p.sourceVideo?.sourceUrl, '開く ↗', 'inline-link')}</div>
          <div class="link-row"><span>編集後URL</span>${renderExternalLink(p.editedVideo?.editedUrl, '開く ↗', 'inline-link')}</div>
          <div class="link-row"><span>Vimeoレビュー</span>${renderExternalLink(p.vimeoReview?.url, '開く ↗', 'inline-link')}</div>
          <div class="link-row"><span>ナレッジ</span><span>${knowledgeFile ? 'あり' : '未生成'}</span></div>
        </div>
      </div>

      <div class="info-card">
        <div class="info-card-title">素材ナレッジ要点</div>
        <div class="summary-callout">${p.knowledge?.summary || '素材ナレッジ要約は未設定です。'}</div>
        ${knowledgeHighlights.length ? `
          <div class="highlight-chip-row">
            ${knowledgeHighlights.map(item => `<span class="highlight-chip">${item}</span>`).join('')}
          </div>
        ` : ''}
        ${p.knowledge?.transcriptPreview ? `<div class="transcript-preview">${p.knowledge.transcriptPreview}</div>` : ''}
        <div class="detail-actions inline-actions">
          <button class="detail-link detail-link-button" data-report-tab="knowledge">ナレッジを開く</button>
        </div>
      </div>

      <div class="info-card">
        <div class="info-card-title">レビュー同期キュー</div>
        <div class="sync-summary-row">
          <div class="sync-status-pill ${p.vimeoReview?.syncStatus || 'draftOnly'}">
            ${p.vimeoReview?.statusLabel || '未設定'}
          </div>
          <div class="sync-meta">
            <span>未送信 ${pendingItems.length}</span>
            <span>最終同期 ${p.vimeoReview?.lastSyncedAt || '-'}</span>
          </div>
        </div>
        ${pendingItems.length ? `
          <div class="pending-review-list compact">
            ${pendingItems.slice(0, 3).map(item => `
              <div class="pending-review-item compact">
                <div class="pending-review-time">${item.timestamp}</div>
                <div class="pending-review-body">
                  <div class="pending-review-title">${item.convertedText}</div>
                  <div class="pending-review-sub">${renderSyncBadgeLabel(item.syncState)}</div>
                </div>
              </div>
            `).join('')}
          </div>
        ` : `<div class="summary-callout">未送信レビューはありません。Vimeoとアプリのコメントは揃っています。</div>`}
        <div class="detail-actions inline-actions">
          <button class="detail-link detail-link-button" data-report-tab="feedback">FB / 評価へ</button>
        </div>
      </div>
    </div>
  `;

  wireReportTabJumps(container);
}

  function renderDirectionSection() {
    const container = document.getElementById('report-sections');
    container.innerHTML = MockData.reportSections.map(section => `
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
    `).join('');

    container.querySelectorAll('.expandable-header').forEach(header => {
      header.addEventListener('click', () => {
        const section = header.closest('.expandable-section');
        section.classList.toggle('collapsed');
      });
    });
  }

function renderSourceSection() {
  const p = currentProject;
  const knowledgeHighlights = p.knowledge?.highlights || [];
  const knowledgeFile = getProjectKnowledgeFile(p);
  const encodedFilename = knowledgeFile ? encodeURIComponent(knowledgeFile) : null;
  const container = document.getElementById('report-sections');
  container.innerHTML = `
    <div class="report-stack">
      <div class="detail-card">
        <div class="detail-card-header">
          <span class="detail-chip">素材</span>
          <span class="detail-score">${p.sourceVideo?.duration || '-'}</span>
        </div>
        <div class="detail-card-title">${p.sourceVideo?.title || '素材未設定'}</div>
        <div class="detail-card-body">${p.sourceVideo?.summary || '素材要約はまだありません。'}</div>
        ${knowledgeHighlights.length ? `
          <div class="highlight-chip-row">
            ${knowledgeHighlights.map(item => `<span class="highlight-chip">${item}</span>`).join('')}
          </div>
        ` : ''}
        ${p.knowledge?.transcriptPreview ? `<div class="transcript-preview">${p.knowledge.transcriptPreview}</div>` : ''}
        <div class="transcript-section">
          <div class="transcript-section-title">全文スクリプト</div>
          ${renderTranscriptBlock(p.knowledge?.fullTranscript)}
        </div>
        <div class="detail-actions">
          ${renderExternalLink(p.sourceVideo?.sourceUrl, '素材を開く ↗', 'detail-link')}
          <button class="detail-link detail-link-button" data-report-tab="knowledge">ナレッジタブを開く</button>
        </div>
      </div>
      ${knowledgeFile ? `
        <div class="knowledge-viewer embedded-source-knowledge">
          <div class="knowledge-header">
            <span class="knowledge-header-icon">KN</span>
            <span class="knowledge-header-title">素材ナレッジ閲覧ページ</span>
          </div>
          <div class="knowledge-iframe-wrap">
            <iframe
              src="knowledge-pages/${encodedFilename}"
              class="knowledge-iframe"
              sandbox="allow-same-origin"
              title="素材ナレッジ閲覧ページ"
            ></iframe>
          </div>
          <a href="knowledge-pages/${encodedFilename}" target="_blank" class="knowledge-open-btn">
            閲覧ページを別タブで開く ↗
          </a>
        </div>
      ` : `
        <div class="knowledge-empty">
          <div class="knowledge-empty-icon">KN</div>
          <div class="knowledge-empty-text">素材ナレッジ閲覧ページ未生成</div>
          <div class="knowledge-empty-sub">スプシの閲覧ページ相当データはまだ利用できません</div>
        </div>
      `}
    </div>
  `;

  wireReportTabJumps(container);
}

function renderEditedSection() {
  const p = currentProject;
  const container = document.getElementById('report-sections');
  const feedbackItems = getProjectFeedbackItems(p);
  const pendingItems = feedbackItems.filter(item => !item.isSent || item.syncState !== 'synced');
  const syncLabelMap = {
    synced: 'Vimeo同期済み',
    partial: '一部未送信あり',
    draftOnly: '変換レビュー待ち',
    awaiting_editor: '編集者確認待ち'
  };

  container.innerHTML = `
    <div class="report-stack">
      <div class="detail-card">
        <div class="detail-card-header">
          <span class="detail-chip success">${p.editedVideo?.statusLabel || '編集後未設定'}</span>
          <span class="detail-score">品質 ${p.editedVideo?.qualityScore ?? '-'}</span>
        </div>
        <div class="detail-card-title">${p.editedVideo?.title || '編集後未設定'}</div>
        <div class="detail-card-body">${p.feedbackSummary?.latestFeedback || '最新フィードバックはまだありません。'}</div>
        <div class="detail-actions">
          ${renderExternalLink(p.editedVideo?.editedUrl, '編集後を開く ↗', 'detail-link')}
          ${renderExternalLink(p.vimeoReview?.url, 'Vimeoレビュー ↗', 'detail-link')}
        </div>
      </div>
      <div class="info-card">
        <div class="info-card-title">レビュー同期状況</div>
        <div class="sync-summary-row">
          <div class="sync-status-pill ${p.vimeoReview?.syncStatus || 'draftOnly'}">
            ${syncLabelMap[p.vimeoReview?.syncStatus] || '未設定'}
          </div>
          <div class="sync-meta">
            <span>未送信 ${pendingItems.length}</span>
            <span>最終同期 ${p.vimeoReview?.lastSyncedAt || '-'}</span>
          </div>
        </div>
        <div class="summary-callout">
          スマホ音声FB → 変換レビュー → Vimeoコメント投稿 → アプリ内タイムライン同期、の流れをここで追えるようにする。
        </div>
        ${pendingItems.length ? `
          <div class="pending-review-list">
            ${pendingItems.map(item => `
              <div class="pending-review-item">
                <div class="pending-review-time">${item.timestamp}</div>
                <div class="pending-review-body">
                  <div class="pending-review-title">${item.convertedText}</div>
                  <div class="pending-review-sub">${item.referenceExample?.title || '参考事例なし'} / ${renderSyncBadgeLabel(item.syncState)}</div>
                </div>
              </div>
            `).join('')}
          </div>
        ` : ''}
        <div class="package-preview-box">
          <div class="package-preview-title">Vimeo送信パッケージ</div>
          <pre class="package-preview-code">${serializeVimeoReviewPayload(p)}</pre>
        </div>
        <div class="package-preview-box relay">
          <div class="package-preview-title">Mac側中継APIリクエスト</div>
          <div class="relay-meta-row">
            <span>endpoint: ${p.relay?.endpoint || '-'}</span>
            <span>route: ${p.relay?.routeStatus || '-'}</span>
            <span>auth: ${p.relay?.authMode || '-'}</span>
          </div>
          <pre class="package-preview-code">${serializeRelayRequest(p)}</pre>
        </div>
        <div class="package-preview-box relay">
          <div class="package-preview-title">relay送信用 curl</div>
          <pre class="package-preview-code">${buildRelayCurlCommand(p)}</pre>
        </div>
        <div class="detail-actions inline-actions">
          <button class="detail-link detail-link-button" data-report-tab="feedback">FB / 評価へ</button>
          <button class="detail-link detail-link-button" id="export-vimeo-package-btn">JSONを書き出す</button>
          <button class="detail-link detail-link-button" id="copy-vimeo-package-btn">JSONをコピー</button>
          <button class="detail-link detail-link-button" id="copy-relay-request-btn">中継API用JSONをコピー</button>
          <button class="detail-link detail-link-button" id="copy-relay-curl-btn">curlをコピー</button>
          <button class="detail-link detail-link-button primary" id="simulate-relay-send-btn">relay送信をシミュレート</button>
        </div>
      </div>
    </div>
  `;

  wireReportTabJumps(container);
  const exportBtn = document.getElementById('export-vimeo-package-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => exportVimeoReviewPackage(p));
  }
  const copyBtn = document.getElementById('copy-vimeo-package-btn');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      const copied = await copyVimeoReviewPackage(p);
      copyBtn.textContent = copied ? 'コピー済み' : 'コピー不可';
      setTimeout(() => { copyBtn.textContent = 'JSONをコピー'; }, 1400);
    });
  }
  const relayBtn = document.getElementById('copy-relay-request-btn');
  if (relayBtn) {
    relayBtn.addEventListener('click', async () => {
      const copied = await copyRelayRequest(p);
      relayBtn.textContent = copied ? 'コピー済み' : 'コピー不可';
      setTimeout(() => { relayBtn.textContent = '中継API用JSONをコピー'; }, 1400);
    });
  }
  const relayCurlBtn = document.getElementById('copy-relay-curl-btn');
  if (relayCurlBtn) {
    relayCurlBtn.addEventListener('click', async () => {
      const copied = await copyRelayCurlCommand(p);
      relayCurlBtn.textContent = copied ? 'コピー済み' : 'コピー不可';
      setTimeout(() => { relayCurlBtn.textContent = 'curlをコピー'; }, 1400);
    });
  }
  const simulateBtn = document.getElementById('simulate-relay-send-btn');
  if (simulateBtn) {
    simulateBtn.addEventListener('click', () => simulateRelaySend(p));
  }
}

  function renderFeedbackSection() {
    const p = currentProject;
    const feedbackItems = getProjectFeedbackItems(p);
    const container = document.getElementById('report-sections');

    if (!feedbackItems.length) {
      container.innerHTML = `
        <div class="knowledge-empty">
          <div class="knowledge-empty-icon">FB</div>
          <div class="knowledge-empty-text">フィードバック履歴なし</div>
          <div class="knowledge-empty-sub">この案件に紐づいた音声FBはまだありません</div>
        </div>
      `;
      return;
    }

    const durationSeconds = durationToSeconds(p.sourceVideo?.duration || p.editedVideo?.duration || '00:01');
    const markers = feedbackItems.map(item => {
      const seconds = timestampToSeconds(item.timestamp);
      const ratio = durationSeconds > 0 ? Math.min((seconds / durationSeconds) * 100, 100) : 0;
      return { ...item, ratio };
    });

    container.innerHTML = `
      <div class="report-stack">
        <div class="info-card">
          <div class="info-card-title">評価サマリー</div>
          <div class="summary-callout">${p.feedbackSummary?.evaluation || '-'}</div>
          <div class="detail-actions inline-actions">
            <button class="detail-link detail-link-button" id="feedback-export-package-btn">Vimeo送信パッケージを書き出す</button>
          </div>
        </div>
        <div class="review-timeline-shell">
          <div class="review-timeline-header">
            <div>
              <div class="review-timeline-title">レビュータイムライン</div>
              <div class="review-timeline-sub">動画時間とFBを紐づけて確認</div>
            </div>
            <div class="review-duration">${p.sourceVideo?.duration || '-'}</div>
          </div>
          <div class="review-track">
            <div class="review-track-line"></div>
            ${markers.map(item => `
              <button class="review-marker ${item.isSent ? 'sent' : 'unsent'}" style="left: ${item.ratio}%;" data-feedback-id="${item.id}">
                <span>${item.timestamp}</span>
              </button>
            `).join('')}
          </div>
        </div>
        <div class="timeline-list">
          ${feedbackItems.map(item => `
            <div class="timeline-card" id="feedback-${item.id}">
              <div class="timeline-head">
                <span class="timeline-time">${item.timestamp}</span>
                <div class="timeline-badges">
                  <span class="sent-badge ${item.isSent ? 'sent' : 'unsent'}">${item.isSent ? '送信済み' : '未送信'}</span>
                  <span class="review-sync-badge ${item.syncState || 'draftOnly'}">
                    ${renderSyncBadgeLabel(item.syncState)}
                  </span>
                </div>
              </div>
              <div class="timeline-raw">${item.rawVoiceText}</div>
              <div class="timeline-converted">${item.convertedText}</div>
              ${item.referenceExample ? `
                <div class="reference-box">
                  <div class="reference-title">参考事例</div>
                  <a href="${item.referenceExample.url}" target="_blank" class="reference-link">${item.referenceExample.title} ↗</a>
                  <div class="reference-note">${item.referenceExample.note}</div>
                </div>
              ` : ''}
              <div class="timeline-foot">
                <span>${item.editorStatus}</span>
                ${item.learningEffect ? `<span>${item.learningEffect}</span>` : ''}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    container.querySelectorAll('.review-marker').forEach(marker => {
      marker.addEventListener('click', () => {
        const target = document.getElementById(`feedback-${marker.dataset.feedbackId}`);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'center' });
          target.classList.add('focus-pulse');
          setTimeout(() => target.classList.remove('focus-pulse'), 1400);
        }
      });
    });

    const exportBtn = document.getElementById('feedback-export-package-btn');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => exportVimeoReviewPackage(p));
    }
  }

  function renderSyncBadgeLabel(syncState) {
    const labels = {
      synced: 'Vimeo同期済み',
      pending_sync: '送信待ち',
      awaiting_editor: '編集者確認待ち',
      draftOnly: '変換レビューのみ'
    };
    return labels[syncState] || '状態未設定';
  }


  function buildVimeoReviewPayload(project) {
    const feedbackItems = getProjectFeedbackItems(project);
    const pendingItems = feedbackItems.filter(item => !item.isSent || item.syncState !== 'synced');
    return {
      videoId: project.videoId,
      projectTitle: project.title,
      guestName: project.guestName,
      vimeoReviewUrl: project.vimeoReview?.url || null,
      exportedAt: new Date().toISOString(),
      pendingCount: pendingItems.length,
      comments: pendingItems.map(item => ({
        feedbackId: item.id,
        timestamp: item.timestamp,
        rawVoiceText: item.rawVoiceText,
        convertedText: item.convertedText,
        syncState: item.syncState,
        editorStatus: item.editorStatus,
        referenceExample: item.referenceExample || null
      }))
    };
  }

  function serializeVimeoReviewPayload(project) {
    return JSON.stringify(buildVimeoReviewPayload(project), null, 2);
  }

  function downloadJsonFile(filename, payload) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  async function copyVimeoReviewPackage(project) {
    const text = serializeVimeoReviewPayload(project);
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    return false;
  }

  function exportVimeoReviewPackage(project) {
    const payload = buildVimeoReviewPayload(project);
    downloadJsonFile(`${project.videoId}-vimeo-review-package.json`, payload);
  }


  function buildRelayRequest(project) {
    return {
      endpoint: project.relay?.endpoint || null,
      method: 'POST',
      authMode: project.relay?.authMode || 'relay_token',
      targetVideoId: project.relay?.targetVideoId || null,
      body: buildVimeoReviewPayload(project)
    };
  }

  function serializeRelayRequest(project) {
    return JSON.stringify(buildRelayRequest(project), null, 2);
  }

  function buildRelayCurlCommand(project) {
    const request = buildRelayRequest(project);
    const body = JSON.stringify(request.body).replace(/'/g, "'\''");
    return `curl -X ${request.method} "${request.endpoint}" -H "Content-Type: application/json" -H "X-Relay-Auth: ${request.authMode}" -d '${body}'`;
  }

  async function copyRelayRequest(project) {
    const text = serializeRelayRequest(project);
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    return false;
  }

  async function copyRelayCurlCommand(project) {
    const text = buildRelayCurlCommand(project);
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    return false;
  }

  function renderKnowledgeSection() {
    const p = currentProject;
    const knowledgePage = getProjectKnowledgeFile(p);
    const container = document.getElementById('report-sections');

    if (!knowledgePage) {
      renderKnowledgePage(null);
      return;
    }

    const encodedFilename = encodeURIComponent(knowledgePage);
    container.innerHTML = `
      <div class="report-stack">
        <div class="info-card">
          <div class="info-card-title">素材ナレッジ要約</div>
          <div class="summary-callout">${p.knowledge?.summary || '要約未設定'}</div>
          <div class="link-list compact">
            <div class="link-row"><span>全文文字起こし</span><span>${p.knowledge?.transcriptAvailable ? 'あり' : 'なし'}</span></div>
          </div>
        </div>
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
            全文を別タブで開く ↗
          </a>
        </div>
      </div>
    `;
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
        <div class="modal-project-name">案件未選択</div>
        <div class="modal-subtext">タップして録音を開始</div>
        <button class="modal-record-btn" id="modal-record-btn">
          <svg viewBox="0 0 24 24"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg>
        </button>
        <div class="modal-preview-stack"></div>
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

    modal.addEventListener('click', (e) => {
      if (e.target === modal) showRecordingModal(false);
    });
  }

  function getRecordingPreviewItem(project) {
    const items = getProjectFeedbackItems(project);
    return items.find(item => item.syncState !== 'synced') || items[0] || null;
  }

  function renderRecordingPreview() {
    const modal = document.getElementById('recording-modal');
    if (!modal || !currentProject) return;
    const preview = getRecordingPreviewItem(currentProject);
    const projectNode = modal.querySelector('.modal-project-name');
    const previewNode = modal.querySelector('.modal-preview-stack');
    if (!projectNode || !previewNode) return;

    projectNode.textContent = `${currentProject.title} / ${currentProject.guestName}`;

    if (!preview) {
      previewNode.innerHTML = `
        <div class="modal-preview-card raw">
          <div class="modal-preview-label">音声FBイメージ</div>
          <div class="modal-preview-text">ここで話した内容が、編集者向けの具体指示に変換されます。</div>
        </div>
      `;
      return;
    }

    previewNode.innerHTML = `
      <div class="modal-preview-card raw">
        <div class="modal-preview-label">生の音声FB</div>
        <div class="modal-preview-time">${preview.timestamp}</div>
        <div class="modal-preview-text">${preview.rawVoiceText}</div>
      </div>
      <div class="modal-preview-arrow">→</div>
      <div class="modal-preview-card converted">
        <div class="modal-preview-label">Vimeo送信用レビュー</div>
        <div class="modal-preview-time">${preview.timestamp}</div>
        <div class="modal-preview-text strong">${preview.convertedText}</div>
        ${preview.referenceExample ? `
          <div class="modal-reference-box">
            <div class="modal-reference-title">参考事例</div>
            <a href="${preview.referenceExample.url}" target="_blank" class="modal-reference-link">${preview.referenceExample.title} ↗</a>
            <div class="modal-reference-note">${preview.referenceExample.note}</div>
          </div>
        ` : ''}
      </div>
      <div class="modal-preview-card sync">
        <div class="modal-preview-label">投稿先</div>
        <div class="modal-preview-text strong">Vimeoレビューモード ${preview.timestamp}</div>
        <div class="modal-preview-sub">アプリ内タイムラインにも同時反映</div>
      </div>
    `;
  }

  function showRecordingModal(show) {
    const modal = document.getElementById('recording-modal');
    if (modal) {
      modal.classList.toggle('visible', show);
      if (show) renderRecordingPreview();
      if (!show) {
        isRecording = false;
        const btn = document.getElementById('modal-record-btn');
        if (btn) btn.classList.remove('recording');
        const sub = document.querySelector('.modal-subtext');
        if (sub) sub.textContent = 'タップして録音を開始';
      }
    }
  }

  // ===== リサイズ対応（Canvas再描画） =====
  window.addEventListener('resize', () => {
    if (currentTab === 'quality') {
      drawTrendChart();
    }
  });

})();
