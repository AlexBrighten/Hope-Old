/**
 * Hope AI Agent — Executive Dashboard Application Logic
 * Pure Vanilla ES6 — Ultra-lightweight, zero build step, lightning fast.
 */

// ── Application State ──────────────────────────────────────────────────────────
const state = {
  activeTab: 'tab-chat',
  pendingCount: 0,
  isGenerating: false,
  isRecording: false,
  routingMode: 'auto',
  lastStatus: null,
};

// ── DOM Element References ───────────────────────────────────────────────────
const elements = {
  tabBtns: document.querySelectorAll('.tab-btn'),
  tabPanes: document.querySelectorAll('.tab-pane'),
  headerApprovalsBtn: document.getElementById('headerApprovalsBtn'),
  headerApprovalsText: document.getElementById('headerApprovalsText'),
  navApprovalsBadge: document.getElementById('navApprovalsBadge'),
  brainModelText: document.getElementById('brainModelText'),
  onlineBadge: document.getElementById('onlineBadge'),
  // Chat
  chatHistory: document.getElementById('chatHistory'),
  chatInput: document.getElementById('chatInput'),
  sendBtn: document.getElementById('sendBtn'),
  voiceBtn: document.getElementById('voiceBtn'),
  suggestionsBar: document.getElementById('suggestionsBar'),
  // Approvals
  pendingList: document.getElementById('pendingList'),
  recentList: document.getElementById('recentList'),
  pendingApprovalsCount: document.getElementById('pendingApprovalsCount'),
  refreshApprovalsBtn: document.getElementById('refreshApprovalsBtn'),
  clearApprovalsBtn: document.getElementById('clearApprovalsBtn'),
  // Memory
  memoryTextarea: document.getElementById('memoryTextarea'),
  saveMemoryBtn: document.getElementById('saveMemoryBtn'),
  // Briefing
  generateBriefingBtn: document.getElementById('generateBriefingBtn'),
  briefingContainer: document.getElementById('briefingContainer'),
  briefingContent: document.getElementById('briefingContent'),
  briefingEmpty: document.getElementById('briefingEmpty'),
  // Settings
  routingPills: document.querySelectorAll('.routing-pill'),
  integrationsGrid: document.getElementById('integrationsGrid'),
  toastContainer: document.getElementById('toastContainer'),
};

// ── Toast Notification Helper ────────────────────────────────────────────────
function showToast(message, type = 'success', duration = 3500) {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icon = type === 'success' ? '✅' : '⚠️';
  toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
  elements.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ── Simple Safe Markdown Formatter ───────────────────────────────────────────
function formatMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Multi-line code blocks
  html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre><code class="language-${lang}">${code}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3 style="font-size:1.05rem;font-weight:700;margin:12px 0 6px 0;color:#e2e8f0;">$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2 style="font-size:1.15rem;font-weight:700;margin:14px 0 8px 0;color:#f8fafc;">$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1 style="font-size:1.25rem;font-weight:800;margin:16px 0 10px 0;color:#ffffff;">$1</h1>');

  // Bold & Italics
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Lists
  html = html.replace(/^\s*•\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul style="margin:8px 0 8px 20px;">$1</ul>');

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:#38bdf8;text-decoration:underline;">$1</a>');

  // Line breaks
  html = html.replace(/\n\n/g, '<p style="margin-top:8px;"></p>');
  html = html.replace(/\n/g, '<br>');

  return html;
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ── Tab Navigation ───────────────────────────────────────────────────────────
function switchTab(targetTabId) {
  state.activeTab = targetTabId;

  elements.tabBtns.forEach((btn) => {
    const isTarget = btn.getAttribute('data-tab') === targetTabId;
    btn.classList.toggle('active', isTarget);
  });

  elements.tabPanes.forEach((pane) => {
    const isTarget = pane.id === targetTabId;
    pane.classList.toggle('active', isTarget);
  });

  if (targetTabId === 'tab-approvals') {
    fetchApprovals();
  } else if (targetTabId === 'tab-memory') {
    fetchMemory();
  } else if (targetTabId === 'tab-integrations') {
    fetchStatus();
  }
}

elements.tabBtns.forEach((btn) => {
  btn.addEventListener('click', () => switchTab(btn.getAttribute('data-tab')));
});

elements.headerApprovalsBtn.addEventListener('click', () => {
  switchTab('tab-approvals');
});

// ── Chat Functions ───────────────────────────────────────────────────────────
function appendMessage(role, text) {
  const bubble = document.createElement('div');
  bubble.className = `message-bubble ${role === 'user' ? 'message-user' : 'message-agent'}`;

  if (role === 'agent') {
    bubble.innerHTML = `<div class="message-header">✨ Hope</div>${formatMarkdown(text)}`;
  } else {
    bubble.textContent = text;
  }

  elements.chatHistory.appendChild(bubble);
  elements.chatHistory.scrollTop = elements.chatHistory.scrollHeight;
  return bubble;
}

function appendThinkingBubble() {
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble message-agent thinking-bubble';
  bubble.innerHTML = `
    <div class="tool-banner">
      <div class="tool-spinner"></div>
      <span>Dual-Brain processing with tools & memory...</span>
    </div>
  `;
  elements.chatHistory.appendChild(bubble);
  elements.chatHistory.scrollTop = elements.chatHistory.scrollHeight;
  return bubble;
}

async function sendMessage(text) {
  const message = (text || elements.chatInput.value).trim();
  if (!message || state.isGenerating) return;

  // Clear input
  elements.chatInput.value = '';
  elements.chatInput.style.height = 'auto';

  // Append user message
  appendMessage('user', message);

  // Show thinking indicator
  state.isGenerating = true;
  elements.sendBtn.disabled = true;
  elements.sendBtn.style.opacity = '0.5';
  const thinkingBubble = appendThinkingBubble();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message }),
    });

    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    const data = await res.json();
    thinkingBubble.remove();
    appendMessage('agent', data.reply);

    // Update pending approvals counter if changed
    if (typeof data.pending_count === 'number') {
      updateApprovalsBadge(data.pending_count);
    }
  } catch (err) {
    thinkingBubble.remove();
    appendMessage('agent', `⚠️ Error communicating with Hope: ${err.message}`);
    showToast(err.message, 'error');
  } finally {
    state.isGenerating = false;
    elements.sendBtn.disabled = false;
    elements.sendBtn.style.opacity = '1';
    elements.chatInput.focus();
  }
}

// Chat input listeners
elements.sendBtn.addEventListener('click', () => sendMessage());

elements.chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Auto-expand textarea
elements.chatInput.addEventListener('input', () => {
  elements.chatInput.style.height = 'auto';
  elements.chatInput.style.height = Math.min(elements.chatInput.scrollHeight, 120) + 'px';
});

// Suggested prompt buttons
elements.suggestionsBar.addEventListener('click', (e) => {
  const chip = e.target.closest('.suggestion-chip');
  if (chip) {
    const prompt = chip.getAttribute('data-prompt');
    sendMessage(prompt);
  }
});

// Voice Input (Web Speech API)
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    state.isRecording = true;
    elements.voiceBtn.classList.add('recording');
    showToast('Listening... Speak now', 'success', 2000);
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    elements.chatInput.value = transcript;
    elements.chatInput.focus();
    showToast(`Heard: "${transcript}"`, 'success', 2500);
  };

  recognition.onerror = (event) => {
    showToast(`Microphone error: ${event.error}`, 'error');
  };

  recognition.onend = () => {
    state.isRecording = false;
    elements.voiceBtn.classList.remove('recording');
  };

  elements.voiceBtn.addEventListener('click', () => {
    if (state.isRecording) {
      recognition.stop();
    } else {
      recognition.start();
    }
  });
} else {
  elements.voiceBtn.style.display = 'none';
}

// ── Approvals Center ─────────────────────────────────────────────────────────
function updateApprovalsBadge(count) {
  state.pendingCount = count;
  elements.headerApprovalsText.textContent = `${count} ${count === 1 ? 'Approval' : 'Approvals'}`;
  elements.pendingApprovalsCount.textContent = count;

  if (count > 0) {
    elements.headerApprovalsBtn.classList.add('has-pending');
    elements.navApprovalsBadge.style.display = 'inline-block';
    elements.navApprovalsBadge.textContent = count;
  } else {
    elements.headerApprovalsBtn.classList.remove('has-pending');
    elements.navApprovalsBadge.style.display = 'none';
  }
}

async function fetchApprovals() {
  try {
    const res = await fetch('/api/approvals');
    if (!res.ok) throw new Error('Failed to load approvals');
    const data = await res.json();

    updateApprovalsBadge(data.pending.length);
    renderPendingList(data.pending);
    renderRecentList(data.recent);
  } catch (err) {
    console.error('Error fetching approvals:', err);
  }
}

function renderPendingList(pendingItems) {
  elements.pendingList.innerHTML = '';

  if (!pendingItems || pendingItems.length === 0) {
    elements.pendingList.innerHTML = `
      <div class="empty-state">
        <div style="font-size: 2rem; margin-bottom: 8px;">🛡️</div>
        <p style="font-weight: 600; color: #f8fafc;">All clear! No actions pending approval.</p>
        <p style="font-size: 0.8rem; margin-top: 4px;">Mutating commands (emails, commits, PRs, calendar deletes) will appear here for 1-click confirmation.</p>
      </div>
    `;
    return;
  }

  pendingItems.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'approval-card pending';
    card.id = `card-${item.action_id}`;

    card.innerHTML = `
      <div class="approval-card-top">
        <div style="display:flex;align-items:center;gap:8px;">
          <span class="action-badge">${escapeHtml(item.action_name)}</span>
          <span style="font-size:0.75rem;font-family:var(--font-mono);color:var(--text-dim);">${item.action_id}</span>
        </div>
        <span class="approval-time">${item.time_str || ''}</span>
      </div>

      <div class="approval-summary">
        ${escapeHtml(item.summary)}
      </div>

      <div class="approval-actions-bar">
        <button class="btn-approve" onclick="handleActionApproval('${item.action_id}', true)">
          <span>✓ Approve & Execute</span>
        </button>
        <button class="btn-reject" onclick="handleActionApproval('${item.action_id}', false)">
          <span>✕ Reject</span>
        </button>
      </div>
    `;

    elements.pendingList.appendChild(card);
  });
}

function renderRecentList(recentItems) {
  elements.recentList.innerHTML = '';
  const filtered = (recentItems || []).filter((r) => r.status !== 'pending');

  if (filtered.length === 0) {
    elements.recentList.innerHTML = `<p style="font-size:0.84rem;color:var(--text-dim);">No past actions recorded.</p>`;
    return;
  }

  filtered.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'approval-card';
    card.style.opacity = '0.85';

    let statusBadgeColor = '#94a3b8';
    if (item.status === 'approved' || item.status === 'executed') statusBadgeColor = '#34d399';
    if (item.status === 'rejected') statusBadgeColor = '#f87171';
    if (item.status === 'expired') statusBadgeColor = '#fbbf24';

    card.innerHTML = `
      <div class="approval-card-top">
        <div style="display:flex;align-items:center;gap:8px;">
          <span class="action-badge" style="background:rgba(255,255,255,0.05);color:#cbd5e1;">${escapeHtml(item.action_name)}</span>
          <span style="font-size:0.75rem;color:${statusBadgeColor};font-weight:700;text-transform:uppercase;">● ${item.status}</span>
        </div>
        <span class="approval-time">${item.time_str || ''}</span>
      </div>
      <div style="font-size:0.86rem;color:var(--text-muted);">${escapeHtml(item.summary)}</div>
    `;

    elements.recentList.appendChild(card);
  });
}

// Global action handler exposed for onclick
window.handleActionApproval = async function (actionId, isApproved) {
  const card = document.getElementById(`card-${actionId}`);
  if (card) {
    card.style.opacity = '0.5';
    card.style.pointerEvents = 'none';
  }

  const endpoint = isApproved ? `/api/approvals/${actionId}/approve` : `/api/approvals/${actionId}/reject`;

  try {
    const res = await fetch(endpoint, { method: 'POST' });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Action failed');
    }

    showToast(data.message, isApproved ? 'success' : 'error');
    fetchApprovals();
  } catch (err) {
    showToast(err.message, 'error');
    if (card) {
      card.style.opacity = '1';
      card.style.pointerEvents = 'auto';
    }
  }
};

elements.refreshApprovalsBtn.addEventListener('click', fetchApprovals);

elements.clearApprovalsBtn.addEventListener('click', async () => {
  try {
    const res = await fetch('/api/approvals/clear', { method: 'POST' });
    const data = await res.json();
    showToast(`Cleared ${data.cleared_count} resolved action records.`);
    fetchApprovals();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// ── Long-Term Memory ─────────────────────────────────────────────────────────
async function fetchMemory() {
  try {
    const res = await fetch('/api/memory');
    const data = await res.json();
    elements.memoryTextarea.value = data.content || '';
  } catch (err) {
    showToast('Failed to load memory file', 'error');
  }
}

elements.saveMemoryBtn.addEventListener('click', async () => {
  const content = elements.memoryTextarea.value;
  elements.saveMemoryBtn.disabled = true;
  elements.saveMemoryBtn.innerHTML = '<span>⏳ Saving...</span>';

  try {
    const res = await fetch('/api/memory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });

    if (!res.ok) throw new Error('Save failed');
    showToast('Long-term memory notes saved successfully!');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    elements.saveMemoryBtn.disabled = false;
    elements.saveMemoryBtn.innerHTML = '<span>💾 Save Notes</span>';
  }
});

// ── Executive Briefing ───────────────────────────────────────────────────────
elements.generateBriefingBtn.addEventListener('click', async () => {
  elements.generateBriefingBtn.disabled = true;
  elements.generateBriefingBtn.innerHTML = `
    <div class="tool-spinner" style="margin-right:8px;"></div>
    <span>Compiling schedule, emails & updates...</span>
  `;

  try {
    const res = await fetch('/api/briefing', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to generate briefing');
    const data = await res.json();

    elements.briefingEmpty.style.display = 'none';
    elements.briefingContent.style.display = 'block';
    elements.briefingContent.innerHTML = formatMarkdown(data.briefing);
    showToast("Today's Executive Briefing compiled!", 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    elements.generateBriefingBtn.disabled = false;
    elements.generateBriefingBtn.innerHTML = '<span>⚡ Re-generate Briefing</span>';
  }
});

// ── Routing Settings ─────────────────────────────────────────────────────────
elements.routingPills.forEach((pill) => {
  pill.addEventListener('click', async () => {
    const mode = pill.getAttribute('data-mode');
    try {
      const res = await fetch('/api/config/routing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);

      elements.routingPills.forEach((p) => p.classList.remove('selected'));
      pill.classList.add('selected');
      showToast(data.message, 'success');
      fetchStatus();
    } catch (err) {
      showToast(err.message, 'error');
    }
  });
});

// ── Status & Integrations Grid ───────────────────────────────────────────────
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const st = await res.json();
    state.lastStatus = st;

    // Brain pill
    let brainLabel = 'Cloud (Gemini)';
    if (st.local_brain_available) {
      brainLabel = `Dual: ${st.local_brain_model} + Gemini`;
    }
    elements.brainModelText.textContent = brainLabel;

    // Routing pill selection
    elements.routingPills.forEach((p) => {
      p.classList.toggle('selected', p.getAttribute('data-mode') === st.routing_mode);
    });

    // Update approvals badge
    updateApprovalsBadge(st.pending_approvals_count);

    // Render integrations grid
    renderIntegrations(st);
  } catch (err) {
    elements.onlineBadge.innerHTML = `<span class="status-dot" style="background:#ef4444;"></span> Offline`;
  }
}

function renderIntegrations(st) {
  const ints = st.integrations || {};

  const items = [
    {
      name: 'GitHub',
      icon: '🐙',
      active: ints.github,
      desc: ints.github ? 'Active with fine-grained repo token & approval gate' : 'Unconfigured (Add GITHUB_TOKEN to .env)',
    },
    {
      name: 'Gmail',
      icon: '📬',
      active: ints.gmail,
      desc: ints.gmail ? 'Connected with draft-only safety & sending gates' : 'Unconfigured (Add Google OAuth token.json)',
    },
    {
      name: 'Google Calendar',
      icon: '📅',
      active: ints.calendar,
      desc: ints.calendar ? 'Live meeting schedules & deletion gates' : 'Unconfigured (OAuth or CALENDAR_ICAL_URL)',
    },
    {
      name: 'Google Docs',
      icon: '📝',
      active: ints.gdocs,
      desc: ints.gdocs ? 'Drive document search, reading & append' : 'Unconfigured (Google OAuth token.json)',
    },
    {
      name: 'Google Sheets',
      icon: '📊',
      active: ints.gsheets,
      desc: ints.gsheets ? 'Spreadsheet CRUD, cell range read/write & append' : 'Unconfigured (Google OAuth token.json)',
    },
    {
      name: 'Browser Automation',
      icon: '🌐',
      active: ints.puppeteer,
      desc: ints.puppeteer ? 'Puppeteer headless/headful runner ready' : 'Runner missing',
    },
    {
      name: 'Local Ollama Brain',
      icon: '💻',
      active: st.local_brain_available,
      desc: st.local_brain_available
        ? `Model: ${st.local_brain_model} (sized for Intel Core i7 8GB RAM)`
        : 'Offline (Start Ollama locally on Debian)',
    },
    {
      name: 'Mobile Push (ntfy.sh)',
      icon: '🔔',
      active: st.ntfy_configured,
      desc: st.ntfy_configured
        ? 'Real-time 1-tap lock screen notifications active'
        : 'Set NTFY_TOPIC in .env for free mobile alerts',
    },
  ];

  elements.integrationsGrid.innerHTML = items
    .map(
      (item) => `
    <div class="integration-card">
      <div class="integration-top">
        <div class="integration-title">
          <span>${item.icon}</span>
          <span>${escapeHtml(item.name)}</span>
        </div>
        <span class="status-badge" style="${item.active ? '' : 'background:rgba(255,255,255,0.05);color:#94a3b8;border-color:rgba(255,255,255,0.1);'}">
          <span class="status-dot" style="${item.active ? '' : 'background:#94a3b8;'}"></span>
          ${item.active ? 'Active' : 'Unconfigured'}
        </span>
      </div>
      <div class="integration-desc">${escapeHtml(item.desc)}</div>
    </div>
  `
    )
    .join('');
}

// ── PWA & Service Worker Registration ─────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then(() => console.log('[PWA] Service Worker registered.'))
      .catch((err) => console.log('[PWA] Service Worker registration failed:', err));
  });
}

// ── Initialization & Polling ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  fetchStatus();
  fetchApprovals();

  // Background polling every 4 seconds for instant approval badge updates
  setInterval(() => {
    fetchStatus();
    if (state.activeTab === 'tab-approvals') {
      fetchApprovals();
    }
  }, 4000);
});

