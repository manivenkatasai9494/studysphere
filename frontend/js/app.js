const NAV_ITEMS = [
  { href: '/dashboard.html', icon: '🏠', label: 'Dashboard' },
  { href: '/tutor.html', icon: '🎓', label: 'AI Tutor' },
  { href: '/rag.html', icon: '📄', label: 'RAG Notes' },
  { href: '/quiz.html', icon: '✅', label: 'Quiz Generator' },
  { href: '/feynman.html', icon: '💡', label: 'Feynman Checker' },
  { href: '/debate.html', icon: '⚔️', label: 'Debate Partner' },
  { href: '/career.html', icon: '🚀', label: 'Career Guidance' },
  { href: '/planner.html', icon: '📅', label: 'Study Planner' },
  { href: '/roadmap.html', icon: '🗺️', label: 'Roadmap' },
  { href: '/voice.html', icon: '🎤', label: 'Voice Assistant' },
  { href: '/rooms.html', icon: '👥', label: 'Study Rooms' },
  { href: '/profile.html', icon: '👤', label: 'Profile' },
  { href: '/settings.html', icon: '⚙️', label: 'Settings' },
];

function initTheme() {
  const theme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
}

function renderSidebar(activePath) {
  const nav = document.getElementById('sidebar-nav');
  if (!nav) return;
  nav.innerHTML = NAV_ITEMS.map(item => `
    <a href="${item.href}" class="nav-item ${activePath === item.href ? 'active' : ''}">
      <span class="icon">${item.icon}</span>
      <span>${item.label}</span>
    </a>
  `).join('');
}

function initAppLayout(activePath, pageTitle) {
  if (!requireAuth()) return false;
  initTheme();
  renderSidebar(activePath);
  const titleEl = document.getElementById('page-title');
  if (titleEl) titleEl.textContent = pageTitle;

  document.getElementById('logout-btn')?.addEventListener('click', () => {
    api.clearTokens();
    window.location.href = '/login.html';
  });

  document.getElementById('theme-toggle')?.addEventListener('click', toggleTheme);

  document.getElementById('mobile-menu')?.addEventListener('click', () => {
    document.querySelector('.sidebar')?.classList.toggle('open');
  });

  const email = localStorage.getItem('user_email');
  const userEl = document.getElementById('user-email');
  if (userEl && email) userEl.textContent = email;
  return true;
}

function appLayoutHTML(activePath, pageTitle) {
  return `
  <div class="app-layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo">StudySphere AI</div>
      </div>
      <nav class="sidebar-nav" id="sidebar-nav"></nav>
      <div class="sidebar-footer">
        <small id="user-email" style="color:var(--text-muted);display:block;margin-bottom:.5rem;"></small>
        <button class="btn btn-secondary btn-sm" id="logout-btn" style="width:100%">Logout</button>
      </div>
    </aside>
    <main class="main-content">
      <header class="topbar">
        <button class="mobile-toggle" id="mobile-menu">☰</button>
        <h1 id="page-title">${pageTitle}</h1>
        <div class="topbar-actions">
          <button class="btn btn-secondary btn-sm" id="theme-toggle">🌓 Theme</button>
        </div>
      </header>
      <div class="page-content" id="page-content"></div>
    </main>
  </div>`;
}
