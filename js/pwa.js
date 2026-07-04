/**
 * pwa.js — Service Worker + установка + web-push для портала «Утрау».
 * Упрощённая версия (без per-user auth): подписки по устройствам.
 * API: window.UtrauPWA.{registerSW, install, canInstall, pushPermissionState, enablePush, disablePush, testPush}
 */
(function (global) {
  'use strict';
  var SW_PATH = 'sw.js';
  var DEFAULT_SERVER = 'https://interview-feb-acoustic-chains.trycloudflare.com';
  var serverUrl = null;
  var vapidKey = null;
  var installPrompt = null;

  function resolveServer() {
    if (window.__chatServerUrl) { serverUrl = window.__chatServerUrl; return Promise.resolve(serverUrl); }
    if (serverUrl) return Promise.resolve(serverUrl);
    return fetch('api_url.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { serverUrl = (j && j.url) ? j.url : DEFAULT_SERVER; return serverUrl; })
      .catch(function () { serverUrl = DEFAULT_SERVER; return serverUrl; });
  }
  function api(path) { return (serverUrl || DEFAULT_SERVER).replace(/\/$/, '') + path; }

  function registerSW() {
    if (!('serviceWorker' in navigator)) return Promise.resolve(null);
    return navigator.serviceWorker.register(SW_PATH, { scope: './' })
      .then(function (reg) { console.log('[pwa] SW scope:', reg.scope); return reg; })
      .catch(function (e) { console.warn('[pwa] SW failed', e); return null; });
  }

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault(); installPrompt = e;
    document.dispatchEvent(new CustomEvent('utrau-pwa-installable'));
  });
  window.addEventListener('appinstalled', function () { installPrompt = null; });

  function isIOS() { return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream; }

  function install() {
    if (!installPrompt) return Promise.resolve(false);
    installPrompt.prompt();
    return installPrompt.userChoice.then(function (r) { installPrompt = null; return r.outcome === 'accepted'; });
  }

  function pushPermissionState() {
    if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) return 'unsupported';
    return Notification.permission;
  }

  function getVapid() {
    if (vapidKey) return Promise.resolve(vapidKey);
    // force=true: URL туннеля мог смениться при перезапуске сервера — берём свежий
    return resolveServer(true).then(function () { return fetch(api('/api/push/vapid'), { cache: 'no-store' }); })
      .then(function (r) { return r.json(); })
      .then(function (j) { vapidKey = j.public_key; return vapidKey; });
  }
  function b64ToU8(s) {
    var pad = '='.repeat((4 - (s.length % 4)) % 4);
    var b = (s + pad).replace(/-/g, '+').replace(/_/g, '/');
    var raw = atob(b); var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  function enablePush() {
    var state = pushPermissionState();
    if (state === 'unsupported')
      return Promise.reject(new Error('Браузер не поддерживает уведомления. На iPhone сначала добавьте сайт «На экран Домой» через Safari.'));
    if (state === 'denied')
      return Promise.reject(new Error('Уведомления заблокированы. Включите их в настройках для этого сайта.'));
    var permP = state === 'default' ? Notification.requestPermission() : Promise.resolve('granted');
    return permP.then(function (perm) {
      if (perm !== 'granted') throw new Error('Без разрешения уведомления не работают.');
      return getVapid();
    }).then(function (pub) {
      return navigator.serviceWorker.ready.then(function (reg) {
        return reg.pushManager.getSubscription().then(function (sub) {
          return sub || reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToU8(pub) });
        });
      });
    }).then(function (sub) {
      return fetch(api('/api/push/subscribe'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subscription: sub.toJSON(), ua: navigator.userAgent })
      }).then(function () { return true; });
    });
  }

  function disablePush() {
    return navigator.serviceWorker.ready.then(function (reg) {
      return reg.pushManager.getSubscription().then(function (sub) {
        if (!sub) return true;
        return fetch(api('/api/push/unsubscribe'), {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: sub.endpoint })
        }).catch(function () {}).then(function () { return sub.unsubscribe(); });
      });
    });
  }

  function testPush() {
    return resolveServer(true).then(function () {
      return navigator.serviceWorker.ready;
    }).then(function (reg) {
      return reg.pushManager.getSubscription();
    }).then(function (sub) {
      return fetch(api('/api/push/test'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint: sub ? sub.endpoint : null })
      }).then(function (r) { return r.json(); });
    });
  }

  global.UtrauPWA = {
    registerSW: registerSW, install: install,
    get canInstall() { return installPrompt !== null; },
    isIOS: isIOS, pushPermissionState: pushPermissionState,
    enablePush: enablePush, disablePush: disablePush, testPush: testPush,
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', registerSW);
  else registerSW();
})(window);
