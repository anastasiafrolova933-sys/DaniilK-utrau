/**
 * notify.js — кнопка «Уведомления» + модалка: инструкция «На экран Домой» (iPhone)
 * и включение push. Зависит от js/pwa.js (UtrauPWA).
 */
(function () {
  'use strict';
  if (!window.UtrauPWA) { console.warn('[notify] UtrauPWA не загружен'); }

  var isStandalone = window.matchMedia('(display-mode: standalone)').matches ||
                     window.navigator.standalone === true;

  var STYLE = `
.un-btn{position:fixed;top:18px;right:18px;z-index:9997;display:inline-flex;align-items:center;gap:7px;
  background:rgba(79,184,176,.12);border:1px solid rgba(79,184,176,.4);color:#4fb8b0;border-radius:22px;
  padding:8px 15px;font-size:12px;font-weight:500;letter-spacing:.04em;cursor:pointer;
  font-family:'DM Sans',system-ui,sans-serif;transition:.18s;backdrop-filter:blur(8px);}
.un-btn:hover{background:rgba(79,184,176,.22);}
.un-ov{position:fixed;inset:0;z-index:10000;background:rgba(4,8,6,.72);backdrop-filter:blur(4px);
  display:none;align-items:center;justify-content:center;padding:20px;}
.un-ov.open{display:flex;}
.un-modal{background:#0d150e;border:1px solid rgba(255,255,255,.1);border-radius:16px;max-width:440px;
  width:100%;max-height:90vh;overflow-y:auto;color:#eeeae4;font-family:'DM Sans',system-ui,sans-serif;
  box-shadow:0 32px 80px rgba(0,0,0,.6);}
.un-head{padding:22px 24px 16px;border-bottom:1px solid rgba(255,255,255,.08);display:flex;
  justify-content:space-between;align-items:flex-start;}
.un-title{font-family:'Cormorant',Georgia,serif;font-style:italic;font-size:22px;color:#fff;}
.un-sub{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:#4fb8b0;margin-top:3px;}
.un-x{background:transparent;border:none;color:rgba(255,255,255,.4);font-size:22px;cursor:pointer;line-height:1;}
.un-x:hover{color:#fff;}
.un-body{padding:20px 24px 24px;}
.un-status{font-size:12px;padding:8px 12px;border-radius:8px;margin-bottom:18px;text-align:center;}
.un-status.on{background:rgba(126,200,138,.12);color:#7ec88a;}
.un-status.off{background:rgba(255,255,255,.05);color:rgba(238,234,228,.5);}
.un-status.warn{background:rgba(224,176,112,.12);color:#e0b070;}
.un-step{display:flex;gap:12px;margin-bottom:14px;font-size:13px;line-height:1.5;color:rgba(238,234,228,.85);}
.un-num{flex-shrink:0;width:22px;height:22px;border-radius:50%;background:rgba(79,184,176,.15);
  color:#4fb8b0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;}
.un-sec-label{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:rgba(238,234,228,.3);
  font-weight:600;margin:20px 0 12px;}
.un-act{width:100%;padding:13px;border-radius:10px;border:1px solid #4fb8b0;background:rgba(79,184,176,.15);
  color:#4fb8b0;font-size:13px;font-weight:600;letter-spacing:.04em;cursor:pointer;font-family:inherit;
  transition:.18s;margin-bottom:10px;}
.un-act:hover{background:rgba(79,184,176,.28);color:#fff;}
.un-act.ghost{border-color:rgba(255,255,255,.12);background:transparent;color:rgba(238,234,228,.6);}
.un-act.ghost:hover{border-color:rgba(255,255,255,.3);color:#fff;background:transparent;}
.un-note{font-size:11px;color:rgba(238,234,228,.4);line-height:1.5;margin-top:14px;}
`;
  var st = document.createElement('style'); st.textContent = STYLE; document.head.appendChild(st);

  var btn = document.createElement('button');
  btn.className = 'un-btn'; btn.innerHTML = '🔔 Уведомления';

  var ov = document.createElement('div');
  ov.className = 'un-ov';
  ov.innerHTML =
    '<div class="un-modal"><div class="un-head"><div>' +
    '<div class="un-title">Уведомления</div><div class="un-sub">Утрау · PWA</div></div>' +
    '<button class="un-x">×</button></div><div class="un-body" id="un-body"></div></div>';
  document.body.appendChild(btn); document.body.appendChild(ov);
  var body = ov.querySelector('#un-body');

  function close() { ov.classList.remove('open'); }
  ov.querySelector('.un-x').onclick = close;
  ov.onclick = function (e) { if (e.target === ov) close(); };

  function statusHtml() {
    var s = window.UtrauPWA ? UtrauPWA.pushPermissionState() : 'unsupported';
    if (s === 'granted') return '<div class="un-status on">✓ Уведомления включены на этом устройстве</div>';
    if (s === 'denied')  return '<div class="un-status warn">Уведомления заблокированы в настройках браузера</div>';
    if (s === 'unsupported') return '<div class="un-status warn">Этот браузер пока не поддерживает push — нужна установка на экран «Домой»</div>';
    return '<div class="un-status off">Уведомления не включены</div>';
  }

  var iosSteps =
    '<div class="un-sec-label">iPhone / iPad — установка</div>' +
    '<div class="un-step"><span class="un-num">1</span><span>Откройте этот сайт в <b>Safari</b> (не в другом браузере)</span></div>' +
    '<div class="un-step"><span class="un-num">2</span><span>Нажмите <b>«Поделиться»</b> — квадрат со стрелкой вверх внизу экрана</span></div>' +
    '<div class="un-step"><span class="un-num">3</span><span>Прокрутите вниз → <b>«На экран Домой»</b> → «Добавить»</span></div>' +
    '<div class="un-step"><span class="un-num">4</span><span>Откройте приложение <b>с экрана Домой</b> и снова нажмите «Уведомления» → «Включить»</span></div>';

  var androidSteps =
    '<div class="un-sec-label">Установка приложения</div>' +
    '<div class="un-step"><span class="un-num">1</span><span>Нажмите «Установить приложение» ниже (или меню браузера → «Установить»)</span></div>' +
    '<div class="un-step"><span class="un-num">2</span><span>Подтвердите установку — иконка появится на экране</span></div>';

  function render() {
    var ios = window.UtrauPWA && UtrauPWA.isIOS();
    var html = statusHtml();
    html += '<p style="font-size:13px;line-height:1.6;color:rgba(238,234,228,.7);margin-bottom:4px;">' +
            'Добавьте отчёты на экран «Домой» как приложение и получайте push-уведомления об <b>аномалиях</b>, ' +
            '<b>ежедневный дайджест</b> и сигнал об <b>обновлении данных</b>.</p>';

    if (ios && !isStandalone) {
      html += iosSteps;
      html += '<div class="un-note">На iPhone push работает только после добавления на экран «Домой» (требование Apple, iOS 16.4+).</div>';
    } else {
      // push controls
      var s = window.UtrauPWA ? UtrauPWA.pushPermissionState() : 'unsupported';
      html += '<div class="un-sec-label">Push-уведомления</div>';
      if (s === 'granted') {
        html += '<button class="un-act" id="un-test">Отправить тестовое</button>';
        html += '<button class="un-act ghost" id="un-off">Отключить уведомления</button>';
      } else {
        html += '<button class="un-act" id="un-on">Включить уведомления</button>';
      }
      if (!isStandalone && !ios && window.UtrauPWA && UtrauPWA.canInstall) {
        html += androidSteps;
        html += '<button class="un-act ghost" id="un-install">Установить приложение</button>';
      }
    }
    body.innerHTML = html;
    wire();
  }

  function wire() {
    var on = body.querySelector('#un-on'), off = body.querySelector('#un-off'),
        test = body.querySelector('#un-test'), inst = body.querySelector('#un-install');
    if (on) on.onclick = function () {
      on.disabled = true; on.textContent = 'Подключение…';
      UtrauPWA.enablePush().then(function () { render(); alert('Готово! Уведомления включены.'); })
        .catch(function (e) { on.disabled = false; on.textContent = 'Включить уведомления'; alert(e.message || 'Ошибка'); });
    };
    if (off) off.onclick = function () {
      UtrauPWA.disablePush().then(function () { render(); });
    };
    if (test) test.onclick = function () {
      test.disabled = true; test.textContent = 'Отправка…';
      UtrauPWA.testPush().then(function (r) {
        test.disabled = false; test.textContent = 'Отправить тестовое';
        if (r && r.error) alert(r.error); else alert('Тест отправлен (' + (r.sent || 0) + '). Уведомление появится через пару секунд.');
      }).catch(function () { test.disabled = false; test.textContent = 'Отправить тестовое'; alert('Сервер недоступен.'); });
    };
    if (inst) inst.onclick = function () { UtrauPWA.install(); };
  }

  btn.onclick = function () { render(); ov.classList.add('open'); };
})();
