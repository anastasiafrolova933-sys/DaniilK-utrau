/* ─────────────────────────────────────────────────────────────────────────
   Утрау Report Chat Widget — AI-чат для дашбордов загородного клуба «Утрау».
   Подключение: <script src="chat-widget.js" data-report="budget"></script>
   report_id определяется по data-report или имени файла.
   Сервер берётся из api_url.json (динамический cloudflared-туннель).
   ───────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  var DEFAULT_SERVER = 'https://stack-television-regularly-nest.trycloudflare.com'; // подменяется start_server.ps1 на туннель
  var serverUrl = null;

  function detectReportId() {
    var s = document.currentScript || document.querySelector('script[data-report]');
    if (s && s.dataset.report) return s.dataset.report;
    var p = location.pathname.toLowerCase();
    if (p.indexOf('finance') >= 0) return 'finance';
    if (p.indexOf('budget') >= 0) return 'budget';
    return null;
  }
  var REPORT_ID = detectReportId();
  if (!REPORT_ID) { console.warn('[chat] report_id не определён'); return; }

  var TITLES = { finance: 'Помощник по доходности', budget: 'Помощник по бюджету' };
  var CHIPS = {
    finance: ['Главные изменения', 'Найди аномалии', 'Лучший месяц по выручке'],
    budget:  ['Как выполняется план?', 'Где перерасход?', 'Сравни с прошлым годом'],
  };

  // ── Сервер: api_url.json → window.__chatServerUrl → default ──
  // force=true перечитывает api_url.json (URL туннеля мог смениться при перезапуске сервера)
  function resolveServer(force) {
    if (window.__chatServerUrl) { serverUrl = window.__chatServerUrl; return Promise.resolve(serverUrl); }
    if (serverUrl && !force) return Promise.resolve(serverUrl);
    return fetch('api_url.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { serverUrl = (j && j.url) ? j.url : DEFAULT_SERVER; return serverUrl; })
      .catch(function () { serverUrl = DEFAULT_SERVER; return serverUrl; });
  }

  // ── Данные дашборда → текст для ИИ ──
  function extractData() {
    if (typeof window.__reportData === 'function') {
      try { return window.__reportData(); } catch (e) {}
    }
    var parts = [];
    var t = document.querySelector('.page-title, h1, h2');
    if (t) parts.push('# ' + t.innerText.trim());
    document.querySelectorAll('table').forEach(function (tb, i) {
      if (i < 8) parts.push('Таблица ' + (i + 1) + ':\n' + tb.innerText.replace(/\t/g, ' | '));
    });
    if (parts.length < 2) parts.push((document.body.innerText || '').slice(0, 60000));
    return parts.join('\n\n');
  }

  var STYLE = `
.uc-btn{position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;
  background:#4fb8b0;border:none;cursor:pointer;color:#06120f;display:flex;align-items:center;
  justify-content:center;font-size:24px;box-shadow:0 8px 24px rgba(0,0,0,.45);z-index:9999;
  transition:transform .2s,background .2s;}
.uc-btn:hover{transform:translateY(-3px);background:#63c8c0;}
.uc-btn.open{background:#06120f;color:#4fb8b0;border:1px solid #4fb8b0;}
.uc-panel{position:fixed;bottom:88px;right:24px;width:380px;max-width:calc(100vw - 32px);
  height:560px;max-height:calc(100vh - 120px);background:#0b120c;border:1px solid rgba(255,255,255,.08);
  border-radius:14px;display:none;flex-direction:column;z-index:9998;color:#eeeae4;
  font-family:'DM Sans',-apple-system,system-ui,sans-serif;box-shadow:0 24px 64px rgba(0,0,0,.6);overflow:hidden;}
.uc-panel.open{display:flex;}
.uc-head{padding:16px 18px;border-bottom:1px solid rgba(255,255,255,.08);display:flex;
  justify-content:space-between;align-items:center;flex-shrink:0;}
.uc-head-title{font-family:'Cormorant',Georgia,serif;font-style:italic;font-size:18px;color:#fff;}
.uc-head-sub{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:#4fb8b0;margin-top:2px;font-weight:500;}
.uc-clear{background:transparent;border:none;color:rgba(255,255,255,.4);cursor:pointer;font-size:11px;
  text-transform:uppercase;letter-spacing:.1em;padding:4px 8px;font-family:inherit;}
.uc-clear:hover{color:#4fb8b0;}
.uc-msgs{flex:1;overflow-y:auto;padding:16px 18px;display:flex;flex-direction:column;gap:14px;}
.uc-msgs::-webkit-scrollbar{width:4px;}
.uc-msgs::-webkit-scrollbar-thumb{background:rgba(79,184,176,.4);}
.uc-msg{font-size:14px;line-height:1.55;}
.uc-msg.user{color:rgba(255,255,255,.6);padding-left:14px;border-left:2px solid rgba(79,184,176,.35);}
.uc-msg.ai{color:#eeeae4;white-space:pre-wrap;}
.uc-msg.ai strong{color:#4fb8b0;}
.uc-msg.err{color:#e07070;font-size:12px;font-style:italic;}
.uc-typing{display:flex;gap:4px;padding:6px 0;}
.uc-typing span{width:6px;height:6px;border-radius:50%;background:#4fb8b0;animation:ucDot 1.2s infinite ease-in-out;}
.uc-typing span:nth-child(2){animation-delay:.2s;}
.uc-typing span:nth-child(3){animation-delay:.4s;}
@keyframes ucDot{0%,80%,100%{opacity:.3;transform:scale(.8);}40%{opacity:1;transform:scale(1);}}
.uc-chips{padding:0 18px 12px;display:flex;flex-wrap:wrap;gap:6px;flex-shrink:0;}
.uc-chip{font-size:11px;color:rgba(255,255,255,.55);background:rgba(255,255,255,.04);
  border:1px solid rgba(255,255,255,.08);padding:6px 12px;cursor:pointer;border-radius:14px;
  transition:border-color .2s,color .2s;font-family:inherit;}
.uc-chip:hover{border-color:#4fb8b0;color:#4fb8b0;}
.uc-input-row{padding:12px 14px;border-top:1px solid rgba(255,255,255,.08);display:flex;gap:8px;
  flex-shrink:0;background:rgba(255,255,255,.02);}
.uc-input{flex:1;background:transparent;border:1px solid rgba(255,255,255,.1);border-radius:8px;
  padding:10px 12px;color:#fff;font-size:14px;font-family:inherit;outline:none;
  transition:border-color .2s;resize:none;min-height:38px;max-height:120px;}
.uc-input:focus{border-color:#4fb8b0;}
.uc-send{background:#4fb8b0;color:#06120f;border:none;border-radius:8px;padding:0 16px;
  font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;cursor:pointer;
  font-family:inherit;transition:background .2s;}
.uc-send:hover:not(:disabled){background:#63c8c0;}
.uc-send:disabled{opacity:.4;cursor:wait;}
.uc-footer{padding:8px 18px;font-size:10px;color:rgba(255,255,255,.25);text-align:center;
  letter-spacing:.08em;border-top:1px solid rgba(255,255,255,.05);flex-shrink:0;}
@media(max-width:480px){.uc-panel{right:8px;left:8px;width:auto;bottom:80px;height:calc(100vh - 100px);}
  .uc-btn{right:16px;bottom:16px;}}
`;

  var HIST_KEY = 'utrau_chat_' + REPORT_ID;
  var history = [];
  try { var raw = sessionStorage.getItem(HIST_KEY); if (raw) history = JSON.parse(raw); } catch (e) {}
  function saveHistory() { try { sessionStorage.setItem(HIST_KEY, JSON.stringify(history.slice(-20))); } catch (e) {} }

  var st = document.createElement('style'); st.textContent = STYLE; document.head.appendChild(st);

  var btn = document.createElement('button');
  btn.className = 'uc-btn'; btn.innerHTML = '✦'; btn.title = 'Спросить ИИ-помощника';

  var panel = document.createElement('div');
  panel.className = 'uc-panel';
  panel.innerHTML =
    '<div class="uc-head"><div><div class="uc-head-title">' + (TITLES[REPORT_ID] || 'AI Помощник') +
    '</div><div class="uc-head-sub">AI · Утрау</div></div>' +
    '<button class="uc-clear" title="Очистить">Очистить</button></div>' +
    '<div class="uc-msgs"></div><div class="uc-chips"></div>' +
    '<div class="uc-input-row"><textarea class="uc-input" placeholder="Задайте вопрос по отчёту..." rows="1"></textarea>' +
    '<button class="uc-send">Отправить</button></div>' +
    '<div class="uc-footer">Ответы носят информационный характер</div>';

  document.body.appendChild(btn); document.body.appendChild(panel);
  var msgs = panel.querySelector('.uc-msgs'), input = panel.querySelector('.uc-input'),
      sendBtn = panel.querySelector('.uc-send'), chipsRow = panel.querySelector('.uc-chips'),
      clearBtn = panel.querySelector('.uc-clear');

  (CHIPS[REPORT_ID] || []).forEach(function (t) {
    var c = document.createElement('button'); c.className = 'uc-chip'; c.textContent = t;
    c.onclick = function () { input.value = t; input.focus(); }; chipsRow.appendChild(c);
  });

  function renderHistory() {
    msgs.innerHTML = '';
    if (!history.length) {
      var h = document.createElement('div'); h.className = 'uc-msg ai';
      h.innerHTML = '<strong>Здравствуйте!</strong> Я вижу данные этого отчёта и отвечу на вопросы — про цифры, тренды, отклонения от плана. Спрашивайте.';
      msgs.appendChild(h);
    } else history.forEach(function (m) { addMessage(m.role, m.content, false); });
    msgs.scrollTop = msgs.scrollHeight;
  }
  function addMessage(role, text, save) {
    if (save === undefined) save = true;
    var el = document.createElement('div'); el.className = 'uc-msg ' + (role === 'user' ? 'user' : 'ai');
    if (role === 'assistant') text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/^#+\s*/gm, '');
    el.innerHTML = text; msgs.appendChild(el); msgs.scrollTop = msgs.scrollHeight;
    if (save) { history.push({ role: role, content: text }); saveHistory(); }
  }
  function showTyping() {
    var t = document.createElement('div'); t.className = 'uc-msg ai';
    t.innerHTML = '<div class="uc-typing"><span></span><span></span><span></span></div>';
    msgs.appendChild(t); msgs.scrollTop = msgs.scrollHeight; return t;
  }

  function doFetch(q) {
    return fetch((serverUrl || DEFAULT_SERVER).replace(/\/$/, '') + '/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report_id: REPORT_ID, question: q, data: extractData(),
                             history: history.slice(-6, -1) })
    });
  }

  function send() {
    var q = input.value.trim();
    if (!q || sendBtn.disabled) return;
    input.value = ''; input.style.height = 'auto';
    addMessage('user', q); sendBtn.disabled = true;
    var typing = showTyping();
    resolveServer().then(function () { return doFetch(q); })
      .catch(function () {
        // сетевой сбой — URL туннеля мог смениться: перечитываем api_url.json и пробуем ещё раз
        return resolveServer(true).then(function () { return doFetch(q); });
      })
      .then(function (resp) {
        typing.remove();
        if (!resp.ok) return resp.json().catch(function () { return { error: 'код ' + resp.status }; })
          .then(function (e) { addMessage('assistant', '<span class="uc-msg err">Ошибка: ' + (e.error || '?') + '</span>'); });
        return resp.json().then(function (j) { addMessage('assistant', j.answer); });
      })
      .catch(function () {
        typing.remove();
        addMessage('assistant', '<span class="uc-msg err">Не удалось связаться с сервером. Возможно, он выключен — попробуйте через минуту.</span>');
      })
      .then(function () { sendBtn.disabled = false; input.focus(); });
  }

  input.addEventListener('input', function () {
    input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  sendBtn.onclick = send;
  clearBtn.onclick = function () { if (confirm('Очистить историю?')) { history = []; saveHistory(); renderHistory(); } };
  btn.onclick = function () {
    var open = !panel.classList.contains('open');
    panel.classList.toggle('open', open); btn.classList.toggle('open', open);
    btn.innerHTML = open ? '×' : '✦';
    if (open) { renderHistory(); setTimeout(function () { input.focus(); }, 100); }
  };

  resolveServer();
  renderHistory();
  console.log('[chat] loaded for', REPORT_ID);
})();
