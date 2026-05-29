const API_BASE = '/api';

class ApiClient {
  getToken() {
    return localStorage.getItem('access_token');
  }

  getRefreshToken() {
    return localStorage.getItem('refresh_token');
  }

  setTokens(access, refresh, userId, email) {
    localStorage.setItem('access_token', access);
    if (refresh) localStorage.setItem('refresh_token', refresh);
    if (userId) localStorage.setItem('user_id', userId);
    if (email) localStorage.setItem('user_email', email);
  }

  clearTokens() {
    ['access_token', 'refresh_token', 'user_id', 'user_email'].forEach(k => localStorage.removeItem(k));
  }

  async request(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    const token = this.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    let res = await fetch(`${API_BASE}${path}`, { ...options, headers });

    if (res.status === 401 && this.getRefreshToken()) {
      const refreshed = await this.refresh();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.getToken()}`;
        res = await fetch(`${API_BASE}${path}`, { ...options, headers });
      }
    }

    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.message || `Error ${res.status}`);
    return data;
  }

  async refresh() {
    try {
      const data = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: this.getRefreshToken() }),
      }).then(r => r.json());
      if (data.access_token) {
        this.setTokens(data.access_token, data.refresh_token, data.user_id, data.email);
        return true;
      }
    } catch (_) {}
    this.clearTokens();
    return false;
  }

  get(path) { return this.request(path); }
  post(path, body) { return this.request(path, { method: 'POST', body: JSON.stringify(body) }); }
  patch(path, body) { return this.request(path, { method: 'PATCH', body: JSON.stringify(body) }); }
  delete(path) { return this.request(path, { method: 'DELETE' }); }

  async upload(path, formData) {
    const headers = {};
    const token = this.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}${path}`, { method: 'POST', headers, body: formData });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Upload failed`);
    return data;
  }
}

const api = new ApiClient();

function requireAuth() {
  if (!api.getToken()) {
    window.location.href = '/login.html';
    return false;
  }
  return true;
}

function showToast(message, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function wrapListItems(html) {
  return html.replace(/((?:<li>[\s\S]*?<\/li>\s*)+)/g, (block) => `<ul>${block}</ul>`);
}

function renderMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text)
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^\d+\. (.+)$/gm, '<li data-ol>$1</li>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
  html = wrapListItems(html);
  html = html.replace(/<li data-ol>/g, '<li>').replace(/<ul>((?:<li>[\s\S]*?<\/li>\s*)+)<\/ul>/g, (m, inner) => {
    if (m.includes('data-ol')) return m;
    return m;
  });
  if (!html.startsWith('<')) html = `<p>${html}</p>`;
  return `<div class="markdown-body">${html}</div>`;
}

function simpleMarkdown(text) {
  return renderMarkdown(text);
}

function titleCaseKey(key) {
  return String(key).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatStructuredData(data, depth = 0) {
  if (data == null) return '';
  let obj = data;
  if (typeof data === 'string') {
    const t = data.trim();
    if ((t.startsWith('{') && t.endsWith('}')) || (t.startsWith('[') && t.endsWith(']'))) {
      try {
        obj = JSON.parse(t);
      } catch {
        return renderMarkdown(data);
      }
    } else {
      return renderMarkdown(data);
    }
  }
  if (typeof obj !== 'object') return renderMarkdown(String(obj));

  if (Array.isArray(obj)) {
    if (!obj.length) return '<p class="text-muted">—</p>';
    return `<ul>${obj.map((item) => {
      if (typeof item === 'object' && item !== null) {
        return `<li>${formatStructuredData(item, depth + 1)}</li>`;
      }
      return `<li>${escapeHtml(String(item))}</li>`;
    }).join('')}</ul>`;
  }

  const scoreKeys = ['score', 'accuracy', 'understanding_score'];
  let html = '<div class="structured-result">';
  for (const [key, val] of Object.entries(obj)) {
    if (val == null || val === '') continue;
    if (scoreKeys.includes(key) && typeof val === 'number') {
      html += `<div class="result-score">${titleCaseKey(key)}: ${val}%</div>`;
      continue;
    }
    html += `<div class="result-section"><h3>${escapeHtml(titleCaseKey(key))}</h3>`;
    if (Array.isArray(val)) {
      html += formatStructuredData(val, depth + 1);
    } else if (typeof val === 'object') {
      html += formatStructuredData(val, depth + 1);
    } else {
      html += renderMarkdown(String(val));
    }
    html += '</div>';
  }
  html += '</div>';
  return html;
}

function renderAssistantContent(content) {
  if (!content) return '';
  const trimmed = String(content).trim();
  if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    try {
      return formatStructuredData(JSON.parse(trimmed));
    } catch (_) { /* use markdown */ }
  }
  return renderMarkdown(content);
}

function formatRagSources(sources) {
  if (!sources?.length) return '';
  const chips = sources.map((s) => {
    const name = escapeHtml(s.filename || s.name || 'Document');
    const score = s.score != null ? `<strong>${(s.score * 100).toFixed(0)}%</strong>` : '';
    return `<span class="source-chip">📄 ${name} ${score}</span>`;
  }).join('');
  return `<div class="sources-panel"><span class="sources-label">Sources</span>${chips}</div>`;
}

function renderMessage(role, content, options = {}) {
  const body = role === 'assistant' || role === 'ai'
    ? renderAssistantContent(content)
    : `<p>${escapeHtml(content).replace(/\n/g, '<br>')}</p>`;
  let html = `<div class="message ${role}">${body}`;
  if (options.sources?.length) html += formatRagSources(options.sources);
  html += '</div>';
  return html;
}

function scrollChat(container) {
  if (container) {
    requestAnimationFrame(() => { container.scrollTop = container.scrollHeight; });
  }
}

function initChatPage() {
  const page = document.getElementById('page-content');
  if (page) page.classList.add('page-chat');
}

function bindChatSidebar(listEl, onSelect) {
  if (!listEl) return;
  listEl.querySelectorAll('.chat-item').forEach((el) => {
    el.onclick = (e) => {
      e.preventDefault();
      const id = el.dataset.id;
      if (id) onSelect(id);
    };
  });
}

function setActiveChatItem(listEl, id) {
  if (!listEl) return;
  listEl.querySelectorAll('.chat-item').forEach((el) => {
    el.classList.toggle('active', el.dataset.id === id);
  });
}

function renderChatHistory(messages, emptyText = 'No messages yet. Send a message to start.') {
  if (!messages?.length) {
    return `<p class="chat-empty-hint">${escapeHtml(emptyText)}</p>`;
  }
  return messages.map((m) => renderMessage(m.role, m.content, {
    sources: m.role === 'assistant' ? m.sources : null,
  })).join('');
}

function appendChatMessage(container, role, content, options = {}) {
  container.querySelectorAll('.chat-empty-hint').forEach((el) => el.remove());
  container.insertAdjacentHTML('beforeend', renderMessage(role, content, options));
  scrollChat(container);
}
