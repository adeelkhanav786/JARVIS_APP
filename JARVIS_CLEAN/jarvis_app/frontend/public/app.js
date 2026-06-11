/**
 * app.js — Shared config for Jarvis.app
 * Detects whether running locally or on a deployed server automatically.
 */

// ── API base URL ──────────────────────────────────────────────────────────────
// Locally:   http://localhost:8000
// Deployed:  auto-detected from current page origin
const API_BASE = (() => {
  const { protocol, hostname, port } = location;
  // If opened as a file:// (unlikely for PWA but just in case)
  if (protocol === 'file:') return 'http://localhost:8000';
  // If running on localhost, backend is on port 8000
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return `${protocol}//${hostname}:8000`;
  }
  // Deployed — backend is same origin
  return `${protocol}//${location.host}`;
})();

// ── WebSocket base ────────────────────────────────────────────────────────────
const WS_BASE = (() => {
  const { protocol, hostname, port } = location;
  const wsProto = protocol === 'https:' ? 'wss' : 'ws';
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return `${wsProto}://${hostname}:8000`;
  }
  return `${wsProto}://${location.host}`;
})();

// ── Register Service Worker (PWA) ─────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(reg => console.log('SW registered:', reg.scope))
      .catch(err => console.warn('SW failed:', err));
  });
}

// ── Install prompt (Add to Home Screen) ──────────────────────────────────────
let _deferredInstall = null;
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  _deferredInstall = e;
  // Show install button if it exists on the page
  const btn = document.getElementById('installBtn');
  if (btn) btn.style.display = 'flex';
});

function showInstallPrompt() {
  if (_deferredInstall) {
    _deferredInstall.prompt();
    _deferredInstall.userChoice.then(() => { _deferredInstall = null; });
  }
}
