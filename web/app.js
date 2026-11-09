/**
 * Hope AI Agent — ChatGPT-Identical Application Logic
 * Pure Vanilla ES6 — Ultra-lightweight, zero build step, lightning fast.
 */

// ── Application State ──────────────────────────────────────────────────────────
const state = {
  isGenerating: false,
  isRecording: false,
  pendingCount: 0,
  routingMode: 'auto',
  lastStatus: null,
};

// ── DOM Element References ───────────────────────────────────────────────────
const elements = {
  // Sidebar
  sidebar: document.getElementById('sidebar'),
  sidebarBackdrop: document.getElementById('sidebarBackdrop'),
  sidebarToggleBtn: document.getElementById('sidebarToggleBtn'),
  openSidebarBtn: document.getElementById('openSidebarBtn'),
  sidebarNewChatBtn: document.getElementById('sidebarNewChatBtn'),
  headerNewChatBtn: document.getElementById('headerNewChatBtn'),
  sidebarApprovalsBadge: document.getElementById('sidebarApprovalsBadge'),
  userName: document.getElementById('userName'),
  userPlan: document.getElementById('userPlan'),
  userAvatar: document.getElementById('userAvatar'),
  // Navigation
  navChatBtn: document.getElementById('navChatBtn'),
  navApprovalsBtn: document.getElementById('navApprovalsBtn'),
  navMemoryBtn: document.getElementById('navMemoryBtn'),
  navBriefingBtn: document.getElementById('navBriefingBtn'),
  navSettingsBtn: document.getElementById('navSettingsBtn'),
  userProfileBtn: document.getElementById('userProfileBtn'),
  // Header & Model Picker
  modelSelectorBtn: document.getElementById('modelSelectorBtn'),
  modelDropdown: document.getElementById('modelDropdown'),
  currentModelLabel: document.getElementById('currentModelLabel'),
  currentModelBadge: document.getElementById('currentModelBadge'),
  headerApprovalsAlert: document.getElementById('headerApprovalsAlert'),
  headerApprovalsCount: document.getElementById('headerApprovalsCount'),
  // Chat
  chatViewport: document.getElementById('chatViewport'),
  welcomeHero: document.getElementById('welcomeHero'),
  chatThread: document.getElementById('chatThread'),
  chatInput: document.getElementById('chatInput'),
  sendBtn: document.getElementById('sendBtn'),
  voiceBtn: document.getElementById('voiceBtn'),
  // Modals
  approvalsModal: document.getElementById('approvalsModal'),
  modalPendingCount: document.getElementById('modalPendingCount'),
  modalPendingList: document.getElementById('modalPendingList'),
  modalRecentList: document.getElementById('modalRecentList'),
  modalClearApprovalsBtn: document.getElementById('modalClearApprovalsBtn'),
  memoryModal: document.getElementById('memoryModal'),
  modalMemoryTextarea: document.getElementById('modalMemoryTextarea'),
  modalSaveMemoryBtn: document.getElementById('modalSaveMemoryBtn'),
  briefingModal: document.getElementById('briefingModal'),
  modalGenerateBriefingBtn: document.getElementById('modalGenerateBriefingBtn'),
  modalBriefingContent: document.getElementById('modalBriefingContent'),
  settingsModal: document.getElementById('settingsModal'),
  modalIntegrationsGrid: document.getElementById('modalIntegrationsGrid'),
  toastContainer: document.getElementById('toastContainer'),
};

// ── Toast Notifications ──────────────────────────────────────────────────────
function showToast(message, type = 'success', duration = 3000) {
  const toast = document.createElement('div');
  toast.className = 'toast';
  const icon = type === 'success' ? '✓' : '⚠️';
  toast.innerHTML = `<span style="color:${type === 'success' ? '#10a37f' : '#f87171'};font-weight:700;">${icon}</span> <span>${escapeHtml(message)}</span>`;
  elements.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'all 0.25s ease';
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

// ── Markdown Formatter with ChatGPT Code Blocks ───────────────────────────────
function formatMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Multi-line code blocks with language bar & Copy button
  html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const language = lang || 'code';
    const codeId = 'code-' + Math.random().toString(36).substr(2, 9);
    return `
      <div class="code-block-container">
        <div class="code-block-header">
          <span>${language}</span>
          <button class="copy-code-btn" onclick="copyCode('${codeId}', this)">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            <span>Copy code</span>
          </button>
        </div>
        <pre class="code-block-content"><code id="${codeId}">${code}</code></pre>
      </div>
    `;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Bold & Italics
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Lists
  html = html.replace(/^\s*•\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:#38bdf8;text-decoration:underline;">$1</a>');

  // Paragraphs & Line breaks
  html = html.replace(/\n\n/g, '<p></p>');
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

window.copyCode = function (id, btn) {
  const el = document.getElementById(id);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent).then(() => {
    btn.innerHTML = `<span>✓ Copied!</span>`;
    setTimeout(() => {
      btn.innerHTML = `
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
        <span>Copy code</span>
      `;
    }, 2000);
  });
};

// ── Sidebar Toggle & Responsiveness ──────────────────────────────────────────
function toggleSidebar() {
  const isMobile = window.innerWidth <= 768;
  if (isMobile) {
    const isOpen = elements.sidebar.classList.contains('mobile-open');
    elements.sidebar.classList.toggle('mobile-open', !isOpen);
    elements.sidebarBackdrop.classList.toggle('visible', !isOpen);
  } else {
    const isCollapsed = elements.sidebar.classList.contains('collapsed');
    elements.sidebar.classList.toggle('collapsed', !isCollapsed);
    localStorage.setItem('hope_sidebar_collapsed', !isCollapsed);
  }
}

elements.sidebarToggleBtn.addEventListener('click', toggleSidebar);
elements.openSidebarBtn.addEventListener('click', toggleSidebar);
elements.sidebarBackdrop.addEventListener('click', () => {
  elements.sidebar.classList.remove('mobile-open');
  elements.sidebarBackdrop.classList.remove('visible');
});

// Load saved desktop sidebar state
if (window.innerWidth > 768 && localStorage.getItem('hope_sidebar_collapsed') === 'true') {
  elements.sidebar.classList.add('collapsed');
}

// ── Model Selector Dropdown ──────────────────────────────────────────────────
elements.modelSelectorBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  elements.modelDropdown.classList.toggle('open');
});

document.addEventListener('click', (e) => {
  if (!elements.modelDropdown.contains(e.target) && e.target !== elements.modelSelectorBtn) {
    elements.modelDropdown.classList.remove('open');
  }
});

document.querySelectorAll('.model-option').forEach((opt) => {
  opt.addEventListener('click', async () => {
    const mode = opt.getAttribute('data-mode');
    try {
      const res = await fetch('/api/config/routing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);

      document.querySelectorAll('.model-option').forEach((o) => o.classList.remove('selected'));
      opt.classList.add('selected');
      elements.modelDropdown.classList.remove('open');
      showToast(data.message);
      fetchStatus();
    } catch (err) {
      showToast(err.message, 'error');
    }
  });
});

// ── Chat Messaging Dynamics ──────────────────────────────────────────────────
function updateSendButton() {
  const hasText = elements.chatInput.value.trim().length > 0;
  elements.sendBtn.classList.toggle('active', hasText && !state.isGenerating);
}

elements.chatInput.addEventListener('input', () => {
  // Auto-expand textarea
  elements.chatInput.style.height = 'auto';
  elements.chatInput.style.height = Math.min(elements.chatInput.scrollHeight, 200) + 'px';
  updateSendButton();
});

elements.chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (elements.chatInput.value.trim().length > 0 && !state.isGenerating) {
      sendMessage();
    }
  }
});

elements.sendBtn.addEventListener('click', () => {
  if (elements.chatInput.value.trim().length > 0 && !state.isGenerating) {
    sendMessage();
  }
});

window.loadPrompt = function (text) {
  elements.chatInput.value = text;
  elements.chatInput.style.height = 'auto';
  elements.chatInput.style.height = Math.min(elements.chatInput.scrollHeight, 200) + 'px';
  updateSendButton();
  sendMessage();
};

function startNewChat() {
  elements.chatThread.innerHTML = '';
  elements.chatThread.style.display = 'none';
  elements.welcomeHero.style.display = 'flex';
  elements.chatInput.value = '';
  elements.chatInput.style.height = 'auto';
  updateSendButton();
  elements.chatInput.focus();
}

elements.sidebarNewChatBtn.addEventListener('click', startNewChat);
elements.headerNewChatBtn.addEventListener('click', startNewChat);
elements.navChatBtn.addEventListener('click', startNewChat);

async function sendMessage(promptText) {
  const text = (promptText || elements.chatInput.value).trim();
  if (!text || state.isGenerating) return;

  // Hide welcome hero, show thread
  elements.welcomeHero.style.display = 'none';
  elements.chatThread.style.display = 'flex';

  // Clear input
  elements.chatInput.value = '';
  elements.chatInput.style.height = 'auto';
  updateSendButton();

  // 1. Append User Message
  appendUserMessage(text);

  // 2. Append Assistant Thinking Placeholder
  state.isGenerating = true;
  updateSendButton();
  const agentRow = appendAgentMessageSkeleton();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Populate Agent Body
    const bodyEl = agentRow.querySelector('.agent-body');
    bodyEl.innerHTML = formatMarkdown(data.reply);

    // Update pending approvals if changed
    if (typeof data.pending_count === 'number') {
      updateApprovalsBadge(data.pending_count);
    }
  } catch (err) {
    const bodyEl = agentRow.querySelector('.agent-body');
    bodyEl.innerHTML = `<span style="color:#f87171;">⚠️ Error communicating with Hope: ${escapeHtml(err.message)}</span>`;
    showToast(err.message, 'error');
  } finally {
    state.isGenerating = false;
    updateSendButton();
    elements.chatViewport.scrollTop = elements.chatViewport.scrollHeight;
    elements.chatInput.focus();
  }
}

function appendUserMessage(text) {
  const row = document.createElement('div');
  row.className = 'message-row user';
  row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
  elements.chatThread.appendChild(row);
  elements.chatViewport.scrollTop = elements.chatViewport.scrollHeight;
}

function appendAgentMessageSkeleton() {
  const row = document.createElement('div');
  row.className = 'message-row agent';
  row.innerHTML = `
    <div class="agent-wrapper">
      <div class="agent-avatar">
        <svg viewBox="0 0 24 24"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/></svg>
      </div>
      <div class="agent-body">
        <div class="tool-disclosure">
          <div class="tool-spinner"></div>
          <span>Thinking...</span>
        </div>
      </div>
    </div>
  `;
  elements.chatThread.appendChild(row);
  elements.chatViewport.scrollTop = elements.chatViewport.scrollHeight;
  return row;
}

// ── Voice Input (Web Speech API) ─────────────────────────────────────────────
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    state.isRecording = true;
    elements.voiceBtn.classList.add('recording');
    showToast('Listening... Speak now', 'success', 2000);
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    elements.chatInput.value = transcript;
    elements.chatInput.style.height = 'auto';
    elements.chatInput.style.height = Math.min(elements.chatInput.scrollHeight, 200) + 'px';
    updateSendButton();
    elements.chatInput.focus();
    showToast(`Heard: "${transcript}"`);
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

// ── Modals Management (Approvals, Memory, Briefing, Settings) ────────────────
function openModal(modalEl) {
  modalEl.classList.add('open');
}

function closeModal(modalEl) {
  modalEl.classList.remove('open');
}

document.querySelectorAll('[data-close]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const modalId = btn.getAttribute('data-close');
    const modal = document.getElementById(modalId);
    if (modal) closeModal(modal);
  });
});

document.querySelectorAll('.modal-backdrop').forEach((backdrop) => {
  backdrop.addEventListener('click', (e) => {
    if (e.target === backdrop) closeModal(backdrop);
  });
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-backdrop.open').forEach(closeModal);
    elements.modelDropdown.classList.remove('open');
  }
});

// Approvals Modal triggers
elements.navApprovalsBtn.addEventListener('click', () => {
  openModal(elements.approvalsModal);
  fetchApprovals();
});

elements.headerApprovalsAlert.addEventListener('click', () => {
  openModal(elements.approvalsModal);
  fetchApprovals();
});

// Memory Modal trigger
elements.navMemoryBtn.addEventListener('click', () => {
  openModal(elements.memoryModal);
  fetchMemory();
});

// Briefing Modal trigger
elements.navBriefingBtn.addEventListener('click', () => {
  openModal(elements.briefingModal);
});

// Settings Modal trigger
elements.navSettingsBtn.addEventListener('click', () => {
  openModal(elements.settingsModal);
  fetchStatus();
});

elements.userProfileBtn.addEventListener('click', () => {
  openModal(elements.settingsModal);
  fetchStatus();
});

// ── Approvals Center Logic ───────────────────────────────────────────────────
function updateApprovalsBadge(count) {
  state.pendingCount = count;
  elements.modalPendingCount.textContent = count;
  elements.headerApprovalsCount.textContent = `${count} Pending`;

  if (count > 0) {
    elements.headerApprovalsAlert.classList.add('visible');
    elements.sidebarApprovalsBadge.style.display = 'inline-block';
    elements.sidebarApprovalsBadge.textContent = count;
  } else {
    elements.headerApprovalsAlert.classList.remove('visible');
    elements.sidebarApprovalsBadge.style.display = 'none';
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
  elements.modalPendingList.innerHTML = '';

  if (!pendingItems || pendingItems.length === 0) {
    elements.modalPendingList.innerHTML = `
      <div style="text-align:center;padding:24px;color:var(--text-muted);background:var(--bg-surface);border-radius:12px;">
        <div style="font-size: 24px; margin-bottom: 6px;">🛡️</div>
        <p style="font-weight:600;color:var(--text-primary);">All clear! No actions pending approval.</p>
        <p style="font-size: 12px; margin-top: 4px;">Mutating actions (email send, PR create, commit, calendar delete) will appear here for 1-click confirmation.</p>
      </div>
    `;
    return;
  }

  pendingItems.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'modal-approval-card';
    card.id = `card-${item.action_id}`;

    card.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <span class="approval-badge">${escapeHtml(item.action_name)}</span>
        <span style="font-size:12px;color:var(--text-muted);">${item.time_str || ''}</span>
      </div>
      <div style="font-size:14px;color:var(--text-primary);line-height:1.45;">${escapeHtml(item.summary)}</div>
      <div style="font-size:11.5px;font-family:var(--font-mono);color:var(--text-muted);">ID: ${item.action_id}</div>
      <div class="modal-btn-row">
        <button class="btn-primary" onclick="handleActionApproval('${item.action_id}', true)">✓ Approve & Execute</button>
        <button class="btn-danger" onclick="handleActionApproval('${item.action_id}', false)">✕ Reject</button>
      </div>
    `;

    elements.modalPendingList.appendChild(card);
  });
}

function renderRecentList(recentItems) {
  elements.modalRecentList.innerHTML = '';
  const filtered = (recentItems || []).filter((r) => r.status !== 'pending');

  if (filtered.length === 0) {
    elements.modalRecentList.innerHTML = `<p style="font-size:12.5px;color:var(--text-muted);">No past action records.</p>`;
    return;
  }

  filtered.forEach((item) => {
    const div = document.createElement('div');
    div.style.cssText = 'background:var(--bg-surface);padding:10px 14px;border-radius:10px;font-size:13px;display:flex;justify-content:space-between;align-items:center;';

    let color = '#34d399';
    if (item.status === 'rejected') color = '#f87171';
    if (item.status === 'expired') color = '#fbbf24';

    div.innerHTML = `
      <div>
        <span style="font-weight:600;">${escapeHtml(item.action_name)}</span> — <span style="color:var(--text-muted);">${escapeHtml(item.summary)}</span>
      </div>
      <span style="font-size:11px;font-weight:700;color:${color};text-transform:uppercase;">● ${item.status}</span>
    `;

    elements.modalRecentList.appendChild(div);
  });
}

window.handleActionApproval = async function (actionId, isApproved) {
  const endpoint = isApproved ? `/api/approvals/${actionId}/approve` : `/api/approvals/${actionId}/reject`;
  try {
    const res = await fetch(endpoint, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed');
    showToast(data.message, isApproved ? 'success' : 'error');
    fetchApprovals();
  } catch (err) {
    showToast(err.message, 'error');
  }
};

elements.modalClearApprovalsBtn.addEventListener('click', async () => {
  try {
    const res = await fetch('/api/approvals/clear', { method: 'POST' });
    const data = await res.json();
    showToast(`Cleared ${data.cleared_count} action logs.`);
    fetchApprovals();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// ── Memory Studio Logic ──────────────────────────────────────────────────────
async function fetchMemory() {
  try {
    const res = await fetch('/api/memory');
    const data = await res.json();
    elements.modalMemoryTextarea.value = data.content || '';
  } catch (err) {
    showToast('Failed to load memory', 'error');
  }
}

elements.modalSaveMemoryBtn.addEventListener('click', async () => {
  const content = elements.modalMemoryTextarea.value;
  elements.modalSaveMemoryBtn.disabled = true;
  elements.modalSaveMemoryBtn.textContent = 'Saving...';
  try {
    const res = await fetch('/api/memory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) throw new Error('Save failed');
    showToast('Custom memory notes saved!');
    closeModal(elements.memoryModal);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    elements.modalSaveMemoryBtn.disabled = false;
    elements.modalSaveMemoryBtn.textContent = '💾 Save Instructions';
  }
});

// ── Morning Briefing Logic ───────────────────────────────────────────────────
elements.modalGenerateBriefingBtn.addEventListener('click', async () => {
  elements.modalGenerateBriefingBtn.disabled = true;
  elements.modalGenerateBriefingBtn.textContent = 'Generating...';
  elements.modalBriefingContent.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px;color:var(--text-muted);">
      <div class="tool-spinner"></div>
      <span>Scanning calendar, emails, and pull requests with Dual-Brain...</span>
    </div>
  `;

  try {
    const res = await fetch('/api/briefing', { method: 'POST' });
    if (!res.ok) throw new Error('Briefing generation failed');
    const data = await res.json();
    elements.modalBriefingContent.innerHTML = formatMarkdown(data.briefing);
    showToast("Today's briefing compiled!");
  } catch (err) {
    elements.modalBriefingContent.innerHTML = `<span style="color:#f87171;">⚠️ ${escapeHtml(err.message)}</span>`;
    showToast(err.message, 'error');
  } finally {
    elements.modalGenerateBriefingBtn.disabled = false;
    elements.modalGenerateBriefingBtn.textContent = '⚡ Re-generate Briefing';
  }
});

// ── Status & Integrations ────────────────────────────────────────────────────
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const st = await res.json();
    state.lastStatus = st;

    // Header badge
    if (st.routing_mode === 'cloud') {
      elements.currentModelLabel.textContent = 'Hope (Gemini 2.5)';
      elements.currentModelBadge.textContent = 'Cloud';
    } else if (st.routing_mode === 'local') {
      elements.currentModelLabel.textContent = `Hope (${st.local_brain_model || 'Ollama'})`;
      elements.currentModelBadge.textContent = 'Local';
    } else {
      elements.currentModelLabel.textContent = 'Hope 2.0';
      elements.currentModelBadge.textContent = 'Auto';
    }

    // Owner info in footer
    if (st.owner) elements.userName.textContent = st.owner;
    elements.userPlan.textContent = st.local_brain_available ? `Dual-Brain (${st.local_brain_model})` : 'Gemini Cloud Brain';

    // Model options selection check
    document.querySelectorAll('.model-option').forEach((opt) => {
      opt.classList.toggle('selected', opt.getAttribute('data-mode') === st.routing_mode);
    });

    // Approvals badge
    updateApprovalsBadge(st.pending_approvals_count);

    // Integrations grid
    renderIntegrationsGrid(st);
  } catch (err) {
    console.error('fetchStatus error:', err);
  }
}

function renderIntegrationsGrid(st) {
  const ints = st.integrations || {};
  const list = [
    { name: 'GitHub', icon: '🐙', active: ints.github, desc: 'Repo search, read, issues, PRs' },
    { name: 'Gmail', icon: '📬', active: ints.gmail, desc: 'Draft-only safety & search' },
    { name: 'Google Calendar', icon: '📅', active: ints.calendar, desc: 'Schedule inspection & events' },
    { name: 'Google Docs', icon: '📝', active: ints.gdocs, desc: 'Drive doc read, create & append' },
    { name: 'Google Sheets', icon: '📊', active: ints.gsheets, desc: 'Spreadsheet read/write ranges' },
    { name: 'Browser Automation', icon: '🌐', active: ints.puppeteer, desc: 'Headless Puppeteer runner' },
    { name: 'Local Ollama Brain', icon: '💻', active: st.local_brain_available, desc: st.local_brain_model || 'Offline' },
    { name: 'Mobile Push (ntfy.sh)', icon: '🔔', active: st.ntfy_configured, desc: 'Free lock-screen alerts' },
  ];

  elements.modalIntegrationsGrid.innerHTML = list
    .map(
      (item) => `
    <div style="background:var(--bg-surface);padding:12px;border-radius:10px;border:1px solid var(--border-light);display:flex;flex-direction:column;gap:4px;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <span style="font-weight:600;font-size:13.5px;">${item.icon} ${escapeHtml(item.name)}</span>
        <span style="font-size:10.5px;font-weight:700;color:${item.active ? '#34d399' : '#8e8e8e'};">${item.active ? '● ACTIVE' : '○ OFF'}</span>
      </div>
      <span style="font-size:12px;color:var(--text-muted);">${escapeHtml(item.desc)}</span>
    </div>
  `
    )
    .join('');
}

// ── Service Worker Registration ──────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => console.log('SW registration error:', err));
  });
}

// ── Startup Polling ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  fetchStatus();
  fetchApprovals();

  // Poll approvals & status every 4 seconds
  setInterval(() => {
    fetchStatus();
    if (elements.approvalsModal.classList.contains('open')) {
      fetchApprovals();
    }
  }, 4000);
});
