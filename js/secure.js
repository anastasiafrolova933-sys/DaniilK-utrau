/* secure.js — вход и расшифровка данных портала Утрау (с 2026-11-02).
   Репозиторий и GitHub Pages публичные, поэтому данные лежат на сайте только зашифрованными:
   data/enc/<имя>.enc (пишет scripts/encrypt_data.py), AES-256-GCM, ключ = PBKDF2-SHA256 из пароля.
   Пароль проверяется расшифровкой контрольной строки из data/enc/meta.json; на устройстве
   хранится ключ (не пароль) — localStorage 'utrau_key', «Выйти» его стирает.

   Отчёт:  <script src="js/secure.js?v=1" data-data="finance"></script> в <head>, а основной скрипт
           страницы — <script type="text/x-utrau">: он выполнится, когда данные расшифрованы.
           Нет ключа или он устарел (сменили пароль) — переход на вход reports.html?next=<страница>.
   Портал: UtrauSecure.login(пароль) / verify() / logout(); freshness.js ждёт UtrauSecure.ready. */
(function () {
  var STORE = 'utrau_key';                         // {k: ключ base64, s: соль base64}
  var ENC = 'data/enc/';
  var PAGES = ['finance.html', 'budget.html', 'fnb.html', 'spa.html'];
  var me = document.currentScript;
  var dataName = me && me.getAttribute('data-data');   // finance | budget | fnb | spa; на портале нет
  var markReady;
  var ready = new Promise(function (resolve) { markReady = resolve; });

  function b64(buf) {
    var s = '', a = new Uint8Array(buf);
    for (var i = 0; i < a.length; i++) s += String.fromCharCode(a[i]);
    return btoa(s);
  }
  function unb64(s) {
    var bin = atob(s), a = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
    return a;
  }
  // как normalize() в encrypt_data.py: регистр, пробелы и дефисы не важны
  function normalize(p) { return String(p).normalize('NFC').trim().toLowerCase().replace(/[\s\-]+/g, ''); }

  function stored() {
    try { var s = JSON.parse(localStorage.getItem(STORE) || 'null'); return s && s.k ? s : null; }
    catch (e) { return null; }
  }
  function forget() {
    try { localStorage.removeItem(STORE); localStorage.removeItem('utrau_ok'); } catch (e) {}
  }
  function loginNeeded() { var e = new Error('нужен вход'); e.login = true; return e; }

  function aesKey(raw) { return crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['decrypt']); }
  function open(key, blob, name) {                 // blob = IV (12 байт) + шифротекст с тегом
    return crypto.subtle.decrypt({ name: 'AES-GCM', iv: blob.slice(0, 12),
      additionalData: new TextEncoder().encode(name) }, key, blob.slice(12));
  }
  function get(url, asJson) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status + ' — ' + url);
      return asJson ? r.json() : r.arrayBuffer();
    });
  }
  function meta() { return get(ENC + 'meta.json', true); }

  // пароль -> ключ; верный, если расшифровалась контрольная строка. true / false; нет сети — ошибка
  function login(password) {
    return meta().then(function (m) {
      return crypto.subtle.importKey('raw', new TextEncoder().encode(normalize(password)), 'PBKDF2', false, ['deriveBits'])
        .then(function (base) {
          return crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: unb64(m.salt), iterations: m.iter }, base, 256);
        })
        .then(function (raw) {
          return aesKey(raw)
            .then(function (key) { return open(key, unb64(m.check), 'check'); })
            .then(function () {
              forget();
              localStorage.setItem(STORE, JSON.stringify({ k: b64(raw), s: m.salt }));
              return true;
            }, function () { return false; });
        });
    });
  }

  // сохранённый ключ ещё подходит? true / false (сменили пароль — ключ стёрт) / null (нет сети)
  function verify() {
    var s = stored();
    if (!s) return Promise.resolve(false);
    return meta().then(function (m) {
      if (m.salt !== s.s) { forget(); return false; }
      return aesKey(unb64(s.k))
        .then(function (key) { return open(key, unb64(m.check), 'check'); })
        .then(function () { return true; }, function () { forget(); return false; });
    }, function () { return null; });
  }

  // расшифрованный текст data/enc/<name>.enc; ключ не подошёл — стираем его, ошибка с .login
  function load(name) {
    var s = stored();
    if (!s) return Promise.reject(loginNeeded());
    return Promise.all([aesKey(unb64(s.k)), get(ENC + name + '.enc')]).then(function (r) {
      return open(r[0], new Uint8Array(r[1]), name).then(
        function (buf) { return new TextDecoder().decode(buf); },
        function () { forget(); throw loginNeeded(); });
    });
  }

  function run(code, place) {                      // выполнить в глобальной области, как обычный <script>
    var s = document.createElement('script');
    s.text = code;
    if (place) place.parentNode.replaceChild(s, place);
    else { document.head.appendChild(s); document.head.removeChild(s); }
  }

  function toLogin() {
    var page = location.pathname.split('/').pop();
    location.replace('reports.html' + (PAGES.indexOf(page) >= 0 ? '?next=' + page : ''));
  }

  function fail(msg) {
    var box = document.createElement('div');
    box.setAttribute('role', 'alert');
    box.style.cssText = 'position:fixed;left:16px;right:16px;top:16px;z-index:9999;padding:14px 18px;' +
      'border-radius:12px;border:1px solid #e5737366;background:#2a1414;color:#eeeae4;' +
      'font:14px/1.5 system-ui,sans-serif;';
    box.textContent = msg;
    document.body.appendChild(box);
  }

  // страница отчёта: расшифровать данные, затем выполнить отложенные скрипты страницы
  if (dataName) {
    if (!stored()) toLogin();
    else {
      var dom = new Promise(function (resolve) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', resolve);
        else resolve();
      });
      Promise.all([load(dataName), dom]).then(function (r) {
        run(r[0]);
        var list = document.querySelectorAll('script[type="text/x-utrau"]');
        for (var i = 0; i < list.length; i++) run(list[i].text, list[i]);
        markReady();
      }).catch(function (e) {
        if (e && e.login) { toLogin(); return; }
        dom.then(function () {
          fail('Не удалось загрузить данные отчёта (' + ((e && e.message) || e) + '). Проверьте интернет и обновите страницу.');
        });
      });
    }
  }

  window.UtrauSecure = {
    login: login,
    verify: verify,
    load: load,
    logout: forget,
    hasKey: function () { return !!stored(); },
    ready: ready,                                  // отчёт: страница отрисована; портал: вход выполнен
    markReady: function () { markReady(); },
    next: function () {                            // куда вернуть после входа (только свои страницы)
      var m = /[?&]next=([a-z]+\.html)/.exec(location.search);
      return m && PAGES.indexOf(m[1]) >= 0 ? m[1] : null;
    }
  };
})();
