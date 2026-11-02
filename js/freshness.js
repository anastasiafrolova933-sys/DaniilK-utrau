/* freshness.js — «Данные по …» и плашка «данные устарели» на портале Утрау.
   Читает health.json (пишет scripts/check_health.py после ежедневной сборки); с 2026-11-02 на сайте
   он зашифрован (data/enc/health.enc) и читается через js/secure.js после входа.
   Раньше в шапке отчётов стояло «Обновлено <время сборки>» — оно менялось каждый день,
   даже когда новых цифр не было больше двух месяцев, и устаревание никто не замечал.
   Подключение: <script src="js/freshness.js?v=1" data-report="finance|budget|fnb|spa|portal"></script> */
(function () {
  var me = document.currentScript;
  var report = (me && me.getAttribute('data-report')) || 'portal';
  var PAGES = { 'finance.html': 'finance', 'budget.html': 'budget', 'fnb.html': 'fnb', 'spa.html': 'spa' };
  var COLORS = { ok: '#4fb8b0', warn: '#e0b25c', error: '#e57373' };

  function el(tag, css, text) {
    var e = document.createElement(tag);
    if (css) e.style.cssText = css;
    if (text != null) e.textContent = text;
    return e;
  }
  function fmtChecked(s) {                       // "2026-11-02 17:33" -> "02.11 17:33"
    var m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})/.exec(s || '');
    return m ? m[3] + '.' + m[2] + ' ' + m[4] : (s || '');
  }

  function applyReport(r, checked) {
    var hdr = document.getElementById('hdr-updated');
    if (hdr) {
      if (hdr.previousElementSibling) hdr.previousElementSibling.textContent = 'Данные по';
      hdr.textContent = r.dataToLabel || '—';
      if (r.state !== 'ok') hdr.style.color = COLORS[r.state];
      hdr.title = 'Сборка ' + (r.built || '—') + ' · проверено ' + fmtChecked(checked);
    }
    var sb = document.getElementById('sb-updated');
    if (sb) sb.textContent = 'Данные по ' + (r.dataToLabel || '—') + ' · проверено ' + fmtChecked(checked);
    if (r.state === 'ok') return;

    var c = COLORS[r.state];
    var box = el('div', 'margin:0 0 20px;padding:12px 16px;border-radius:12px;border:1px solid ' + c + '55;' +
      'background:' + c + '14;font-size:13px;line-height:1.5;color:var(--text,#eeeae4);');
    box.setAttribute('role', 'status');
    box.appendChild(el('div', 'font-weight:600;color:' + c + ';',
      (r.state === 'error' ? '⚠ Данные устарели: ' : '⚠ Внимание: ') + (r.summary || '')));
    var list = (r.problems || []).slice(0, 4);
    if (list.length) {
      var ul = el('ul', 'margin:6px 0 0;padding-left:18px;font-size:12px;color:var(--text2,rgba(238,234,228,.6));');
      list.forEach(function (p) { ul.appendChild(el('li', '', p)); });
      box.appendChild(ul);
    }
    box.appendChild(el('div', 'margin-top:6px;font-size:11px;color:var(--text3,rgba(238,234,228,.35));',
      'Цифры ниже — по последнюю загруженную дату. Проверено ' + fmtChecked(checked) + '.'));

    var main = document.querySelector('.main') || document.body;
    var header = main.querySelector('.page-header');
    if (header && header.parentNode) header.parentNode.insertBefore(box, header.nextSibling);
    else main.insertBefore(box, main.firstChild);
  }

  function applyPortal(h) {
    Object.keys(PAGES).forEach(function (page) {
      var r = h.reports && h.reports[PAGES[page]];
      var card = document.querySelector('a.card[href="' + page + '"] .card-content');
      if (!r || !card) return;
      var c = COLORS[r.state] || COLORS.ok;
      var chip = el('div', 'margin-top:12px;align-self:flex-start;font-size:11px;padding:3px 10px;border-radius:20px;' +
        'border:1px solid ' + c + '66;color:' + c + ';background:' + c + '12;',
        (r.state === 'ok' ? '● ' : '⚠ ') + 'данные по ' + (r.dataToLabel || '—'));
      chip.title = (r.problems || []).join('\n');
      card.insertBefore(chip, card.querySelector('.card-arrow'));
    });
  }

  // ждём вход и отрисовку отчёта: страница сама пишет «Обновлено …» и перетёрла бы «Данные по …»
  if (!window.UtrauSecure) return;
  UtrauSecure.ready
    .then(function () { return UtrauSecure.load('health'); })
    .then(function (text) {
      var h = JSON.parse(text);
      if (!h || !h.reports) return;
      if (report === 'portal') applyPortal(h);
      else if (h.reports[report]) applyReport(h.reports[report], h.checked);
    })
    .catch(function () { /* нет health.json — страница работает как раньше */ });
})();
