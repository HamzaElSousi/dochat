/* DocChat Widget — v1
 * Self-contained Shadow DOM chat widget.
 * Zero dependencies. No external modules. Vanilla ES2020+.
 * All HTML, CSS, and JS inlined in a single IIFE.
 *
 * Embed:
 *   <script>
 *     window.DocChatConfig = {
 *       apiUrl: 'https://social-automate.com/chat',
 *       primaryColor: '#3b82f6',
 *       title: 'Ask us anything'
 *     };
 *   </script>
 *   <script src="https://social-automate.com/dochat/widget.js"></script>
 */
(function () {
  'use strict';

  /* ── Section 1: Config reading ── */
  var cfg = Object.assign({
    primaryColor:    '#3b82f6',
    headerBg:        null,          // null → falls back to --dc-primary in CSS
    botBubbleColor:  '#f1f5f9',
    userBubbleColor: null,          // null → falls back to --dc-primary in CSS
    textColor:       '#1e293b',
    logo:            null,
    title:           'Ask us anything',
    apiUrl:          '',
    borderRadius:    '12px',
    fontFamily:      'inherit',
  }, window.DocChatConfig || {});

  /* ── Section 2: Shadow DOM host injection ── */
  var host = document.createElement('div');
  host.id = 'dochat-host';
  document.body.appendChild(host);
  var shadow = host.attachShadow({ mode: 'open' });

  /* ── Section 3: CSS string ── */
  function sanitizeCssValue(val, fallback) {
    if (typeof val !== 'string') return fallback;
    // Reject values containing characters that could break out of CSS context
    if (/[<>"'`{}\\;]/.test(val)) return fallback;
    return val;
  }

  var style = document.createElement('style');
  style.textContent = [
    /* Custom properties (theming) */
    ':host {',
    '  --dc-primary:     ' + sanitizeCssValue(cfg.primaryColor, '#3b82f6') + ';',
    '  --dc-header-bg:   ' + sanitizeCssValue(cfg.headerBg, 'var(--dc-primary)') + ';',
    '  --dc-bot-bubble:  ' + sanitizeCssValue(cfg.botBubbleColor, '#f1f5f9') + ';',
    '  --dc-user-bubble: ' + sanitizeCssValue(cfg.userBubbleColor, 'var(--dc-primary)') + ';',
    '  --dc-text:        ' + sanitizeCssValue(cfg.textColor, '#1e293b') + ';',
    '  --dc-radius:      ' + sanitizeCssValue(cfg.borderRadius, '12px') + ';',
    '  --dc-font-family: ' + sanitizeCssValue(cfg.fontFamily, 'inherit') + ';',
    '  font-family: var(--dc-font-family, inherit);',
    '}',

    /* FAB button */
    '#dc-fab {',
    '  position: fixed;',
    '  bottom: 24px;',
    '  right: 24px;',
    '  width: 48px;',
    '  height: 48px;',
    '  border-radius: 50%;',
    '  background: var(--dc-primary);',
    '  border: none;',
    '  cursor: pointer;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: center;',
    '  box-shadow: 0 4px 12px rgba(0,0,0,0.15);',
    '  z-index: 2147483647;',
    '  transition: filter 150ms ease;',
    '}',
    '#dc-fab:hover { filter: brightness(0.9); }',
    '#dc-fab:focus { outline: 2px solid #fff; outline-offset: 2px; }',

    /* Panel */
    '#dc-panel {',
    '  position: fixed;',
    '  bottom: 80px;',
    '  right: 24px;',
    '  width: 380px;',
    '  height: 560px;',
    '  background: #fff;',
    '  border-radius: var(--dc-radius);',
    '  box-shadow: 0 8px 32px rgba(0,0,0,0.18);',
    '  z-index: 2147483647;',
    '  display: flex;',
    '  flex-direction: column;',
    '  overflow: hidden;',
    '  opacity: 0;',
    '  transform: translateY(8px);',
    '  transition: opacity 200ms ease-out, transform 200ms ease-out;',
    '  pointer-events: none;',
    '}',
    '#dc-panel.dc-open {',
    '  opacity: 1;',
    '  transform: translateY(0);',
    '  pointer-events: auto;',
    '}',

    /* Header */
    '#dc-header {',
    '  background: var(--dc-header-bg, var(--dc-primary));',
    '  height: 56px;',
    '  min-height: 56px;',
    '  padding: 0 16px;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: space-between;',
    '  gap: 8px;',
    '}',
    '#dc-logo {',
    '  max-height: 32px;',
    '  max-width: 80px;',
    '  object-fit: contain;',
    '  display: none;',
    '}',
    '#dc-logo.dc-visible { display: block; }',
    '#dc-title {',
    '  font-size: 15px;',
    '  font-weight: 600;',
    '  color: #fff;',
    '  flex: 1;',
    '  overflow: hidden;',
    '  text-overflow: ellipsis;',
    '  white-space: nowrap;',
    '}',
    '#dc-close {',
    '  width: 44px;',
    '  height: 44px;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: center;',
    '  background: none;',
    '  border: none;',
    '  color: #fff;',
    '  cursor: pointer;',
    '  border-radius: 4px;',
    '  flex-shrink: 0;',
    '}',
    '#dc-close:focus { outline: 2px solid #fff; outline-offset: 2px; }',

    /* Message area */
    '#dc-messages {',
    '  flex: 1;',
    '  overflow-y: auto;',
    '  padding: 16px;',
    '  display: flex;',
    '  flex-direction: column;',
    '  gap: 8px;',
    '  background: #fff;',
    '  scroll-behavior: smooth;',
    '}',

    /* Empty state */
    '#dc-empty {',
    '  display: flex;',
    '  flex-direction: column;',
    '  align-items: center;',
    '  justify-content: center;',
    '  text-align: center;',
    '  gap: 8px;',
    '  padding: 24px;',
    '  height: 100%;',
    '  color: var(--dc-text, #1e293b);',
    '}',
    '#dc-empty h2 { font-size: 15px; font-weight: 600; margin: 0; }',
    '#dc-empty p  { font-size: 13px; color: #64748b; margin: 0; }',

    /* Bubbles */
    '.dc-bubble {',
    '  max-width: 85%;',
    '  padding: 8px 16px;',
    '  font-size: 15px;',
    '  line-height: 1.5;',
    '  word-break: break-word;',
    '}',
    '.dc-bubble-user {',
    '  background: var(--dc-user-bubble, var(--dc-primary));',
    '  color: #fff;',
    '  border-radius: var(--dc-radius) var(--dc-radius) 4px var(--dc-radius);',
    '  max-width: 75%;',
    '  align-self: flex-end;',
    '  margin-left: auto;',
    '}',
    '.dc-bubble-bot {',
    '  background: var(--dc-bot-bubble, #f1f5f9);',
    '  color: var(--dc-text, #1e293b);',
    '  border-radius: var(--dc-radius) var(--dc-radius) var(--dc-radius) 4px;',
    '  align-self: flex-start;',
    '  margin-right: auto;',
    '}',
    '.dc-bubble-error {',
    '  background: #fef2f2;',
    '  border: 1px solid #fecaca;',
    '  color: #b91c1c;',
    '  border-radius: var(--dc-radius) var(--dc-radius) var(--dc-radius) 4px;',
    '  align-self: flex-start;',
    '  margin-right: auto;',
    '  font-size: 13px;',
    '  display: flex;',
    '  align-items: center;',
    '  gap: 6px;',
    '}',

    /* Typing indicator */
    '.dc-typing {',
    '  display: flex;',
    '  align-items: center;',
    '  gap: 4px;',
    '  padding: 12px 16px;',
    '}',
    '.dc-dot {',
    '  width: 6px;',
    '  height: 6px;',
    '  border-radius: 50%;',
    '  background: #94a3b8;',
    '  animation: dc-bounce 1.2s ease-in-out infinite;',
    '}',
    '.dc-dot:nth-child(2) { animation-delay: 0.2s; }',
    '.dc-dot:nth-child(3) { animation-delay: 0.4s; }',
    '@keyframes dc-bounce {',
    '  0%, 80%, 100% { transform: translateY(0); }',
    '  40%           { transform: translateY(-6px); }',
    '}',

    /* Chips */
    '.dc-chips {',
    '  display: flex;',
    '  flex-wrap: wrap;',
    '  gap: 8px;',
    '  margin-top: 8px;',
    '}',
    '.dc-chip {',
    '  background: var(--dc-bot-bubble, #f1f5f9);',
    '  border: 1px solid #cbd5e1;',
    '  border-radius: var(--dc-radius);',
    '  padding: 8px 12px;',
    '  min-height: 44px;',
    '  cursor: pointer;',
    '  font-size: 13px;',
    '  color: var(--dc-text, #1e293b);',
    '  font-family: var(--dc-font-family, inherit);',
    '  transition: background 150ms ease, color 150ms ease, border-color 150ms ease;',
    '  display: inline-flex;',
    '  align-items: center;',
    '  line-height: 1.4;',
    '}',
    '.dc-chip:hover {',
    '  background: var(--dc-primary);',
    '  color: #fff;',
    '  border-color: var(--dc-primary);',
    '}',
    '.dc-chip:focus { outline: 2px solid var(--dc-primary); outline-offset: 2px; }',

    /* Input area */
    '#dc-input-area {',
    '  border-top: 1px solid #e2e8f0;',
    '  padding: 12px 16px;',
    '  display: flex;',
    '  gap: 8px;',
    '  align-items: flex-end;',
    '  background: #fff;',
    '}',
    '#dc-input {',
    '  flex: 1;',
    '  resize: none;',
    '  border: 1px solid #e2e8f0;',
    '  border-radius: 8px;',
    '  padding: 8px 12px;',
    '  font-size: 15px;',
    '  font-family: var(--dc-font-family, inherit);',
    '  line-height: 1.5;',
    '  outline: none;',
    '  overflow-y: hidden;',
    '  max-height: calc(15px * 1.5 * 4 + 16px);',
    '}',
    '#dc-input:focus { border-color: var(--dc-primary); }',
    '#dc-send {',
    '  width: 44px;',
    '  height: 44px;',
    '  min-width: 44px;',
    '  background: var(--dc-primary);',
    '  border: none;',
    '  border-radius: 8px;',
    '  cursor: pointer;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: center;',
    '  flex-shrink: 0;',
    '}',
    '#dc-send:disabled { opacity: 0.4; cursor: not-allowed; }',
    '#dc-send:focus { outline: 2px solid var(--dc-primary); outline-offset: 2px; }',

    /* Lead capture form */
    '.dc-lead-form {',
    '  background: var(--dc-bot-bubble, #f1f5f9);',
    '  border-radius: var(--dc-radius) var(--dc-radius) var(--dc-radius) 4px;',
    '  padding: 12px 16px;',
    '  align-self: flex-start;',
    '  margin-right: auto;',
    '  max-width: 90%;',
    '  width: 90%;',
    '  font-size: 14px;',
    '}',
    '.dc-lead-form p { margin: 0 0 8px; font-size: 14px; color: var(--dc-text, #1e293b); line-height: 1.4; }',
    '.dc-lead-form input {',
    '  width: 100%;',
    '  padding: 6px 10px;',
    '  margin-bottom: 6px;',
    '  border: 1px solid #cbd5e1;',
    '  border-radius: 6px;',
    '  font-size: 14px;',
    '  font-family: var(--dc-font-family, inherit);',
    '  box-sizing: border-box;',
    '}',
    '.dc-lead-form input:focus { outline: 2px solid var(--dc-primary); outline-offset: 1px; }',
    '.dc-lead-submit {',
    '  width: 100%;',
    '  padding: 8px;',
    '  background: var(--dc-primary);',
    '  color: #fff;',
    '  border: none;',
    '  border-radius: 6px;',
    '  font-size: 14px;',
    '  cursor: pointer;',
    '  margin-top: 4px;',
    '  min-height: 44px;',
    '}',
    '.dc-lead-submit:disabled { opacity: 0.5; cursor: not-allowed; }',
    '.dc-cta-btn {',
    '  display: inline-block;',
    '  margin-top: 8px;',
    '  padding: 10px 16px;',
    '  background: var(--dc-primary);',
    '  color: #fff;',
    '  border-radius: 6px;',
    '  text-decoration: none;',
    '  font-size: 14px;',
    '  font-weight: 600;',
    '  min-height: 44px;',
    '  line-height: 24px;',
    '}',
    '.dc-cta-btn:hover { filter: brightness(0.9); }',
    '.dc-thankyou {',
    '  background: var(--dc-bot-bubble, #f1f5f9);',
    '  border-radius: var(--dc-radius) var(--dc-radius) var(--dc-radius) 4px;',
    '  padding: 12px 16px;',
    '  align-self: flex-start;',
    '  margin-right: auto;',
    '  max-width: 90%;',
    '  font-size: 14px;',
    '  color: var(--dc-text, #1e293b);',
    '}',

    /* Reduced motion */
    '@media (prefers-reduced-motion: reduce) {',
    '  #dc-panel { transition: none; }',
    '  .dc-dot   { animation: none; }',
    '}',

    /* Mobile breakpoint */
    '@media (max-width: 480px) {',
    '  #dc-panel {',
    '    width: calc(100vw - 16px);',
    '    height: calc(100vh - 80px);',
    '    bottom: 72px;',
    '    right: 8px;',
    '    left: 8px;',
    '  }',
    '  #dc-fab {',
    '    bottom: 16px;',
    '    right: 16px;',
    '  }',
    '}',
  ].join('\n');

  shadow.appendChild(style);

  /* ── Section 4: HTML template ── */
  var tpl = document.createElement('template');
  tpl.innerHTML = [
    /* FAB */
    '<button id="dc-fab" aria-label="Open chat">',
    '  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff"',
    '       stroke-width="2" stroke-linecap="round" stroke-linejoin="round">',
    '    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    '  </svg>',
    '</button>',

    /* Panel */
    '<div id="dc-panel" role="dialog" aria-label="Chat widget" aria-hidden="true">',

    '  <!-- Header -->',
    '  <div id="dc-header">',
    '    <img id="dc-logo" alt="Logo" />',
    '    <span id="dc-title">Ask us anything</span>',
    '    <button id="dc-close" aria-label="Close chat">',
    '      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"',
    '           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">',
    '        <line x1="18" y1="6" x2="6" y2="18"/>',
    '        <line x1="6" y1="6" x2="18" y2="18"/>',
    '      </svg>',
    '    </button>',
    '  </div>',

    '  <!-- Message area -->',
    '  <div id="dc-messages" role="log" aria-live="polite" aria-label="Chat messages">',
    '    <div id="dc-empty">',
    '      <h2>How can I help you?</h2>',
    '      <p>Ask me anything about our services.</p>',
    '    </div>',
    '  </div>',

    '  <!-- Input area -->',
    '  <div id="dc-input-area">',
    '    <textarea id="dc-input" rows="1"',
    '              placeholder="Type your message…"',
    '              aria-label="Chat input"></textarea>',
    '    <button id="dc-send" aria-label="Send message" disabled>',
    '      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff"',
    '           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">',
    '        <line x1="22" y1="2" x2="11" y2="13"/>',
    '        <polygon points="22 2 15 22 11 13 2 9 22 2"/>',
    '      </svg>',
    '    </button>',
    '  </div>',

    '</div>',
  ].join('\n');

  shadow.appendChild(tpl.content.cloneNode(true));

  /* ── Section 5: State and DOM refs ── */
  var state = {
    open:           false,
    loading:        false,
    sessionId:      sessionStorage.getItem('dochat_session_id') || null,
    messages:       [],   // {role:'user'|'bot'|'error', text:str} — JS memory only
    _leadSubmitted: false,   // D-02: prevents repeat form on subsequent fallback: true
    _settingsUrl:   '',      // D-12: fetched once on init from GET /dochat/api/settings
  };

  var fab      = shadow.getElementById('dc-fab');
  var panel    = shadow.getElementById('dc-panel');
  var closeBtn = shadow.getElementById('dc-close');
  var messages = shadow.getElementById('dc-messages');
  var empty    = shadow.getElementById('dc-empty');
  var input    = shadow.getElementById('dc-input');
  var sendBtn  = shadow.getElementById('dc-send');
  var logo     = shadow.getElementById('dc-logo');
  var title    = shadow.getElementById('dc-title');

  /* ── Section 6: apiUrl guard ── */
  if (!cfg.apiUrl) {
    console.warn('[DocChat] apiUrl is required — widget is non-functional without it');
    input.disabled = true;
    sendBtn.disabled = true;
    input.placeholder = 'Chat unavailable — apiUrl not configured';
  }

  /* ── Section 6b: Fetch settings from backend (D-12) ── */
  function fetchSettings() {
    // Derive settings URL: replace trailing /chat with /api/settings,
    // or use explicit cfg.settingsUrl if provided
    var settingsUrl = cfg.settingsUrl || cfg.apiUrl.replace(/\/chat$/, '/api/settings');
    if (!settingsUrl || settingsUrl === cfg.apiUrl) return;  // guard: apiUrl has no /chat suffix
    fetch(settingsUrl)
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (data && data.book_call_url) {
          state._settingsUrl = data.book_call_url;
        }
      })
      .catch(function () { /* silent — non-critical */ });
  }

  if (cfg.apiUrl) {
    fetchSettings();
  }

  /* ── Section 7: Apply DocChatConfig title and logo ── */
  title.textContent = cfg.title || 'Ask us anything';
  if (cfg.logo) {
    logo.src = cfg.logo;
    logo.classList.add('dc-visible');
  }

  /* ── Section 8: Toggle open/close ── */
  function openPanel() {
    state.open = true;
    panel.classList.add('dc-open');
    panel.setAttribute('aria-hidden', 'false');
    fab.setAttribute('aria-label', 'Close chat');
    fab.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    input.focus();
  }

  function closePanel() {
    state.open = false;
    panel.classList.remove('dc-open');
    panel.setAttribute('aria-hidden', 'true');
    fab.setAttribute('aria-label', 'Open chat');
    fab.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  }

  fab.addEventListener('click', function () {
    state.open ? closePanel() : openPanel();
  });
  closeBtn.addEventListener('click', closePanel);

  /* ── Section 9: Textarea auto-resize ── */
  input.addEventListener('input', function () {
    input.style.height = 'auto';
    var lineHeight = 15 * 1.5;   // 22.5px
    var maxHeight  = lineHeight * 4 + 16;
    input.style.height = Math.min(input.scrollHeight, maxHeight) + 'px';
    sendBtn.disabled = input.value.trim() === '' || state.loading;
  });

  /* ── Section 10: Enter key submit ── */
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) sendMessage(input.value.trim());
    }
  });
  sendBtn.addEventListener('click', function () {
    if (!sendBtn.disabled) sendMessage(input.value.trim());
  });

  /* ── Section 11: Rendering helpers ── */
  function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  function showEmpty(show) {
    empty.style.display = show ? '' : 'none';
  }

  function addUserBubble(text) {
    showEmpty(false);
    var div = document.createElement('div');
    div.className = 'dc-bubble dc-bubble-user';
    div.textContent = text;
    messages.appendChild(div);
    scrollToBottom();
    return div;
  }

  function addTypingIndicator() {
    var div = document.createElement('div');
    div.className = 'dc-bubble dc-bubble-bot dc-typing';
    div.setAttribute('role', 'status');
    div.setAttribute('aria-label', 'DocChat is typing');
    div.innerHTML = '<span class="dc-dot"></span><span class="dc-dot"></span><span class="dc-dot"></span>';
    messages.appendChild(div);
    scrollToBottom();
    return div;
  }

  function addBotBubble(text, chips) {
    var wrapper = document.createElement('div');

    var div = document.createElement('div');
    div.className = 'dc-bubble dc-bubble-bot';
    div.textContent = text;
    wrapper.appendChild(div);

    // Render chips (max 3; only when chips is a non-empty array)
    if (Array.isArray(chips) && chips.length > 0) {
      var chipsEl = document.createElement('div');
      chipsEl.className = 'dc-chips';
      chips.slice(0, 3).forEach(function (q) {
        var btn = document.createElement('button');
        btn.className = 'dc-chip';
        btn.textContent = q;
        btn.addEventListener('click', function () {
          if (state.loading) return;   // guard against double-click race (WR-06)
          chipsEl.remove();   // Remove chips from DOM on click (D-07)
          sendMessage(q);
        });
        chipsEl.appendChild(btn);
      });
      wrapper.appendChild(chipsEl);
    }

    messages.appendChild(wrapper);
    scrollToBottom();
    return wrapper;
  }

  function addErrorBubble() {
    var div = document.createElement('div');
    div.className = 'dc-bubble dc-bubble-error';
    // Build SVG via createElementNS to avoid innerHTML entirely
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('width', '16'); svg.setAttribute('height', '16');
    svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', '#ef4444'); svg.setAttribute('stroke-width', '2');
    svg.setAttribute('stroke-linecap', 'round'); svg.setAttribute('stroke-linejoin', 'round');
    var circle = document.createElementNS(ns, 'circle');
    circle.setAttribute('cx', '12'); circle.setAttribute('cy', '12'); circle.setAttribute('r', '10');
    var l1 = document.createElementNS(ns, 'line');
    l1.setAttribute('x1', '12'); l1.setAttribute('y1', '8'); l1.setAttribute('x2', '12'); l1.setAttribute('y2', '12');
    var l2 = document.createElementNS(ns, 'line');
    l2.setAttribute('x1', '12'); l2.setAttribute('y1', '16'); l2.setAttribute('x2', '12.01'); l2.setAttribute('y2', '16');
    svg.appendChild(circle); svg.appendChild(l1); svg.appendChild(l2);
    var span = document.createElement('span');
    span.textContent = 'Something went wrong. Check your connection and try again.';
    div.appendChild(svg); div.appendChild(span);
    messages.appendChild(div);
    scrollToBottom();
    return div;
  }

  function addLeadForm(question) {
    var wrapper = document.createElement('div');
    wrapper.className = 'dc-lead-form';

    var heading = document.createElement('p');
    heading.textContent = "I couldn't find an answer to that. Leave your details and we'll get back to you.";
    wrapper.appendChild(heading);

    var nameInput = document.createElement('input');
    nameInput.type = 'text'; nameInput.placeholder = 'Your name'; nameInput.maxLength = 200;
    nameInput.setAttribute('aria-label', 'Your name');
    wrapper.appendChild(nameInput);

    var emailInput = document.createElement('input');
    emailInput.type = 'email'; emailInput.placeholder = 'Your email'; emailInput.maxLength = 254;
    emailInput.setAttribute('aria-label', 'Your email');
    wrapper.appendChild(emailInput);

    var phoneInput = document.createElement('input');
    phoneInput.type = 'tel'; phoneInput.placeholder = 'Your phone (optional)'; phoneInput.maxLength = 30;
    phoneInput.setAttribute('aria-label', 'Your phone');
    wrapper.appendChild(phoneInput);

    var submitBtn = document.createElement('button');
    submitBtn.className = 'dc-lead-submit';
    submitBtn.textContent = 'Send';
    wrapper.appendChild(submitBtn);

    submitBtn.addEventListener('click', function () {
      var name  = nameInput.value.trim();
      var email = emailInput.value.trim();
      var phone = phoneInput.value.trim();
      if (!name || !email) {
        nameInput.style.borderColor  = name  ? '#cbd5e1' : '#ef4444';
        emailInput.style.borderColor = email ? '#cbd5e1' : '#ef4444';
        return;
      }
      submitBtn.disabled = true;
      submitBtn.textContent = 'Sending…';

      // Derive leads URL: replace /chat suffix with /api/leads (same pattern as settings)
      var leadsUrl = cfg.leadsUrl || cfg.apiUrl.replace(/\/chat$/, '/api/leads');
      fetch(leadsUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, email: email, phone: phone, question: question }),
      })
        .then(function (res) { return res.ok ? res.json() : Promise.reject(res.status); })
        .then(function () {
          state._leadSubmitted = true;  // D-02
          // Replace form with thank-you + CTA (D-05)
          var ty = document.createElement('div');
          ty.className = 'dc-thankyou';
          var tyMsg = document.createElement('p');
          tyMsg.textContent = "Thank you! We'll be in touch soon.";
          ty.appendChild(tyMsg);
          if (state._settingsUrl) {
            var cta = document.createElement('a');
            cta.className = 'dc-cta-btn';
            cta.href = state._settingsUrl;
            cta.target = '_blank';
            cta.rel = 'noopener noreferrer';
            cta.textContent = 'Book a Call';
            ty.appendChild(cta);
          }
          wrapper.replaceWith(ty);
          scrollToBottom();
        })
        .catch(function () {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Send';
          var errMsg = document.createElement('p');
          errMsg.style.color = '#ef4444';
          errMsg.textContent = 'Could not submit. Please try again.';
          if (!wrapper.querySelector('.dc-lead-err')) {
            errMsg.className = 'dc-lead-err';
            wrapper.appendChild(errMsg);
          }
        });
    });

    messages.appendChild(wrapper);
    scrollToBottom();
    return wrapper;
  }

  /* ── Section 12: sendMessage() and API call ── */
  function setLoading(on) {
    state.loading = on;
    input.disabled = on;
    sendBtn.disabled = on;
  }

  function sendMessage(text) {
    if (!text || state.loading) return;
    if (!cfg.apiUrl) return;

    // Clear input
    input.value = '';
    input.style.height = 'auto';
    sendBtn.disabled = true;

    // Append user bubble
    addUserBubble(text);
    state.messages.push({ role: 'user', text: text });

    setLoading(true);
    var typingEl = addTypingIndicator();

    fetch(cfg.apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message:    text,
        session_id: state.sessionId || null,
      }),
    })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        typingEl.remove();
        if (data.session_id) {
          state.sessionId = data.session_id;
          sessionStorage.setItem('dochat_session_id', data.session_id);
        }
        // D-01: any fallback:true response triggers lead form (if not already submitted)
        if (data.fallback && !state._leadSubmitted) {
          addLeadForm(text);   // D-03: form replaces fallback bubble; question captured from 'text' closure
        } else {
          var chips = Array.isArray(data.chips) ? data.chips : [];
          addBotBubble(data.answer || '', chips);
          state.messages.push({ role: 'bot', text: data.answer || '' });
        }
      })
      .catch(function () {
        typingEl.remove();
        addErrorBubble();
      })
      .finally(function () {
        setLoading(false);
        sendBtn.disabled = input.value.trim() === '';
      });
  }

  /* ── Section 13: Close IIFE ── */
})();
