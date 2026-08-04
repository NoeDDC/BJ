/* ── real viewport height (works around iOS PWA vh/dvh bugs) ── */
function setAppHeight() {
  const h = (window.visualViewport && window.visualViewport.height) || window.innerHeight;
  document.documentElement.style.setProperty('--app-height', h + 'px');
}
setAppHeight();
window.addEventListener('resize', setAppHeight);
window.addEventListener('orientationchange', () => setTimeout(setAppHeight, 100));
if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', setAppHeight);
}

/* ── state ── */
const state = { z: { g: 0, b: 0 }, n: { g: 0, b: 0 }, ui: 'a', themeA: 'theme-1', themeB: 'scrap-1', jours_sans_course: 0 };
const MAX_H = 42;

/* ── Interface B: which person's card is the front card ── */
let bPerson = 'z';
function showCard(p) {
  bPerson = p;
  document.getElementById('bTabZ').classList.toggle('active', p === 'z');
  document.getElementById('bTabN').classList.toggle('active', p === 'n');
  document.getElementById('bCardZ').classList.toggle('active', p === 'z');
  document.getElementById('bCardN').classList.toggle('active', p === 'n');
}

/* ── streak history (localStorage, per device) ── */
function loadHist(p)   { try { return JSON.parse(localStorage.getItem('hist-'+p) || '[]'); } catch(e) { return []; } }
function saveHist(p,h) { try { localStorage.setItem('hist-'+p, JSON.stringify(h)); } catch(e) {} }

const hist = { z: loadHist('z'), n: loadHist('n') };

function computeStreak(h) {
  if (!h.length) return { count: 0, type: null };
  const last = h[h.length - 1];
  let count = 0;
  for (let i = h.length - 1; i >= 0 && h[i] === last; i--) count++;
  return { count, type: last };
}

function renderStreak(p) {
  const s = computeStreak(hist[p]);

  ['snum-' + p, 'b-snum-' + p].forEach(id => renderStreakNum(id, s));
  ['slbl-' + p, 'b-slbl-' + p].forEach(id => renderStreakLbl(id, s));
  ['dots-' + p, 'b-dots-' + p].forEach(id => renderStreakDots(id, p, s));
}

function renderStreakNum(id, s) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = s.count === 0 ? '—' : s.count;
  el.className   = 'streak-num ' + (s.count === 0 ? 'empty' : (s.type === 'g' ? 'good' : 'bad'));
  el.classList.remove('pop');
  void el.offsetWidth;
  el.classList.add('pop');
  el.addEventListener('animationend', () => el.classList.remove('pop'), { once: true });
}

function renderStreakLbl(id, s) {
  const el = document.getElementById(id);
  if (!el) return;
  if (s.count === 0) { el.textContent = 'série de suite'; return; }
  const plural = s.count > 1 ? 's' : '';
  el.textContent = (s.type === 'g' ? 'bonne' : 'mauvaise') + plural + ' de suite';
}

function renderStreakDots(id, p, s) {
  const dotsEl = document.getElementById(id);
  if (!dotsEl) return;
  if (s.count === 0) { dotsEl.innerHTML = ''; return; }

  const col    = s.type === 'g'
    ? (p === 'z' ? 'var(--z)' : 'var(--n)')
    : (p === 'z' ? 'var(--z-light)' : 'var(--n-light)');
  const border = s.type === 'b'
    ? (p === 'z' ? '1px solid var(--z2)' : '1px solid var(--n2)')
    : 'none';
  const shown  = Math.min(s.count, 6);
  dotsEl.innerHTML = Array.from({ length: shown }, (_, i) => {
    const op = (i === shown - 1 && s.count > shown) ? 'opacity:.35;' : '';
    return `<div class="streak-dot" style="background:${col};border:${border};${op}"></div>`;
  }).join('');
}

/* ── popup messages ── */
const MSGS = {
  good: [
    "🫶",
  ],
  bad: [
    "Les mauvaises journées finissent elles aussi.",
    "Ça arrive. Et ça passe.",
    "Même les jours difficiles font partie du compte.",
    "Demain est une autre page.",
    "Il n'y a pas de mauvaise journée sans lendemain.",
    "C'est noté. Et c'est déjà derrière toi.",
    "Certains jours sont là pour rappeler que les autres sont doux.",
    "Une journée difficile n'efface pas les bonnes.",
    "Parfois, juste traverser la journée, c'est suffisant.",
    "La nuit remet les compteurs à zéro.",
    "Ce n'était pas le meilleur des jours. Ce n'est pas grave.",
    "Les jours gris font ressortir les jours de soleil.",
    "Même fatigué, tu as continué. C'est quelque chose.",
    "Tout ne peut pas être lumineux. Et c'est humain.",
    "Une mauvaise journée, ce n'est pas une mauvaise vie.",
    "Le reste viendra. Pour l'instant, c'est terminé.",
    "Les jours difficiles ont leur utilité, même cachée.",
    "Même les orages ont une fin.",
    "Tu l'as traversée. C'est l'essentiel.",
    "Certains jours résistent. Toi aussi.",
    "Ce jour-là est compté — et il appartient déjà au passé.",
    "Il faut bien des nuages pour apprécier le ciel bleu.",
    "Mauvaise journée, mais bonne résilience.",
    "Ça ne durera pas — les mauvaises journées n'ont jamais le dernier mot.",
    "Même dans les jours difficiles, quelque chose tient.",
    "Ce soir, pose tout ça et dors.",
  ],
  minus: [
    "On efface, on recommence.",
    "Une correction dans le grand cahier.",
    "Retour en arrière autorisé.",
    "Les erreurs aussi font partie du compte.",
    "Ce n'était peut-être pas si sûr, après tout.",
    "On peut toujours revenir sur ses pas.",
    "Le crayon a une gomme pour une bonne raison.",
    "Tout peut se réviser.",
  ],
};

function pickMsg(pool) { return pool[Math.floor(Math.random() * pool.length)]; }

/* ── popup ── */
let popupTimer = null;

function showPopup(person, type, delta) {
  const dot    = document.getElementById('popup-dot');
  const accent = document.getElementById('popup-accent');
  const msg    = document.getElementById('popup-msg');

  let pool, dotClass, accentText;
  if (delta < 0) {
    pool       = MSGS.minus;
    dotClass   = type === 'g' ? 'dot-good-' + person : 'dot-bad-' + person;
    accentText = '— correction —';
  } else if (type === 'g') {
    pool       = MSGS.good;
    dotClass   = 'dot-good-' + person;
    accentText = person === 'z' ? '— Z · bonne journée —' : '— N · bonne journée —';
  } else {
    pool       = MSGS.bad;
    dotClass   = 'dot-bad-' + person;
    accentText = person === 'z' ? '— Z · mauvaise journée —' : '— N · mauvaise journée —';
  }

  dot.className      = 'popup-dot ' + dotClass;
  accent.textContent = accentText;
  msg.textContent    = pickMsg(pool);

  document.getElementById('overlay').classList.add('show');
  if (popupTimer) clearTimeout(popupTimer);
  popupTimer = setTimeout(hidePopup, 4800);
}

function hidePopup() {
  document.getElementById('overlay').classList.remove('show');
  if (popupTimer) { clearTimeout(popupTimer); popupTimer = null; }
}

function closePopup(e) {
  if (e.target === document.getElementById('overlay')) hidePopup();
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') hidePopup(); });

/* ── render ── */
function barH(v, mx) { return mx ? Math.max(3, Math.round(v / mx * MAX_H)) : 3; }

function setText(id, text) { const el = document.getElementById(id); if (el) el.textContent = text; }
function setHeight(id, px) { const el = document.getElementById(id); if (el) el.style.height = px + 'px'; }

function render() {
  const vals = [state.z.g, state.z.b, state.n.g, state.n.b];
  const mx   = Math.max(...vals, 1);

  [['zg', state.z.g], ['zb', state.z.b], ['ng', state.n.g], ['nb', state.n.b]].forEach(([k, v]) => {
    setText('count-' + k, v);
    setText('bv-' + k, v);
    setHeight('bar-' + k, barH(v, mx));
    setText('b-count-' + k, v);
    setHeight('b-bar-' + k, barH(v, mx));
  });

  const tz = state.z.g + state.z.b;
  const tn = state.n.g + state.n.b;
  const total = vals.reduce((a, b) => a + b, 0);
  setText('total-z', tz + ' journée' + (tz > 1 ? 's' : ''));
  setText('total-n', tn + ' journée' + (tn > 1 ? 's' : ''));
  setText('total', total);
  setText('b-total-z', tz + ' journée' + (tz > 1 ? 's' : ''));
  setText('b-total-n', tn + ' journée' + (tn > 1 ? 's' : ''));
  setText('b-total', total);
  setText('running-count', state.jours_sans_course);
  setText('b-running-count', state.jours_sans_course);

  const uiClass    = state.ui === 'b' ? 'ui-b' : 'ui-a';
  const variantCls = state.ui === 'b' ? state.themeB : state.themeA;
  document.body.className = uiClass + ' ' + variantCls;

  document.getElementById('uiBtnA').setAttribute('aria-pressed', String(state.ui !== 'b'));
  document.getElementById('uiBtnB').setAttribute('aria-pressed', String(state.ui === 'b'));
  document.getElementById('paletteA').hidden = state.ui === 'b';
  document.getElementById('paletteB').hidden = state.ui !== 'b';
  document.querySelectorAll('#paletteA .swatch').forEach(b => b.classList.toggle('active', b.dataset.variant === state.themeA));
  document.querySelectorAll('#paletteB .swatch').forEach(b => b.classList.toggle('active', b.dataset.variant === state.themeB));

  const metaTheme = document.querySelector('meta[name="theme-color"]');
  if (metaTheme) {
    const ink = getComputedStyle(document.body).getPropertyValue('--ink').trim();
    if (ink) metaTheme.setAttribute('content', ink);
  }
}

/* ── change ── */
function change(person, type, delta) {
  const prev = state[person][type];
  const next = Math.max(0, prev + delta);
  if (next === prev) return;
  state[person][type] = next;

  render();
  saveAdjust(person + type, next - prev);
  showPopup(person, type, delta);

  if (delta > 0) {
    hist[person].push(type);
    if (hist[person].length > 60) hist[person].shift();
  } else {
    hist[person].pop();
  }
  saveHist(person, hist[person]);
  renderStreak(person);

  ['bar-' + person + type, 'b-bar-' + person + type].forEach(id => {
    const barEl = document.getElementById(id);
    if (!barEl) return;
    barEl.classList.remove('bump', 'dip');
    void barEl.offsetWidth;
    barEl.classList.add(delta > 0 ? 'bump' : 'dip');
    barEl.addEventListener('animationend', () => barEl.classList.remove('bump', 'dip'), { once: true });
  });
}

function changeRunning(delta) {
  const prev = state.jours_sans_course;
  const next = Math.max(0, prev + delta);
  if (next === prev) return;
  state.jours_sans_course = next;
  render();
  saveAdjust('jours_sans_course', next - prev);
}

/* ── server: journal ── */
async function load() {
  try {
    const res  = await fetch('/api/counters');
    const data = await res.json();
    state.z.g = data.zg ?? 0;
    state.z.b = data.zb ?? 0;
    state.n.g = data.ng ?? 0;
    state.n.b = data.nb ?? 0;
    state.ui     = data.ui === 'b' ? 'b' : 'a';
    state.themeA = data.theme_a || 'theme-1';
    state.themeB = data.theme_b || 'scrap-1';
    state.jours_sans_course = parseInt(data.jours_sans_course || "0") || 0;
    render();
    renderStreak('z');
    renderStreak('n');
    setStatus('');
  } catch(e) {
    setStatus('Erreur de connexion');
  }
}

// Sends only the delta for one counter — never the whole local snapshot —
// so a stale tab can't clobber increments made from another device since
// this one last loaded. The server applies it atomically and returns the
// authoritative totals, which we adopt here to self-heal any staleness.
async function saveAdjust(key, delta) {
  try {
    const res = await fetch('/api/counters/adjust', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, delta })
    });
    if (!res.ok) throw new Error();
    const data = await res.json();
    state.z.g = data.zg ?? state.z.g;
    state.z.b = data.zb ?? state.z.b;
    state.n.g = data.ng ?? state.n.g;
    state.n.b = data.nb ?? state.n.b;
    state.jours_sans_course = parseInt(data.jours_sans_course || "0") || 0;
    render();
    setStatus('');
  } catch(e) {
    setStatus('Erreur de sauvegarde');
  }
}

// Like saveAdjust: send only the one field that actually changed (never a
// full snapshot), and adopt the server's response as truth, so a stale tab
// switching the interface or theme can't stomp a pick made on another device.
async function saveMeta(body, okMsg) {
  try {
    const res = await fetch('/api/counters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error();
    const data = await res.json();
    state.ui     = data.ui === 'b' ? 'b' : 'a';
    state.themeA = data.theme_a || state.themeA;
    state.themeB = data.theme_b || state.themeB;
    render();
    setStatus(okMsg);
  } catch(e) {
    setStatus('Erreur de sauvegarde');
  }
}

function setInterface(ui) {
  state.ui = ui === 'b' ? 'b' : 'a';
  render();
  saveMeta({ ui: state.ui }, 'Interface changée');
}

function setThemeVariant(scope, variant) {
  if (scope === 'b') { state.themeB = variant; render(); saveMeta({ theme_b: variant }, 'Style mis à jour'); }
  else               { state.themeA = variant; render(); saveMeta({ theme_a: variant }, 'Style mis à jour'); }
}

function setStatus(msg) {
  setText('status', msg);
  setText('b-status', msg);
}

/* ══════════════════ CALENDRIER ══════════════════ */

const FR_MONTHS = ['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre'];

let currentPerson = localStorage.getItem('bj_person') || null;
let calYear, calMonth;
let availability = { z: {}, n: {} };
let calPollTimer = null;
let pendingPushToggle = false;

function pad2(n) { return String(n).padStart(2, '0'); }
function dateKey(y, m, d) { return `${y}-${pad2(m + 1)}-${pad2(d)}`; }

function switchView(view) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById('view-' + view).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === view));

  if (view === 'calendar') {
    if (!currentPerson) { showGate(); }
    renderCalYou();
    updateSubscribeButton();
    loadCalendarLinks();
    loadAvailability().then(renderCalendar);
    if (calPollTimer) clearInterval(calPollTimer);
    calPollTimer = setInterval(() => { loadAvailability().then(() => renderCalendarGrid()); }, 20000);
  } else if (calPollTimer) {
    clearInterval(calPollTimer);
    calPollTimer = null;
  }
}

function showGate() { document.getElementById('personGate').classList.add('show'); }
function hideGate() { document.getElementById('personGate').classList.remove('show'); }

function choosePerson(p) {
  currentPerson = p;
  try { localStorage.setItem('bj_person', p); } catch(e) {}
  hideGate();
  renderCalYou();
  renderCalendarGrid();
  updateSubscribeButton();
  loadCalendarLinks();
  if (pendingPushToggle) { pendingPushToggle = false; togglePush(); }
}

function switchPerson() { showGate(); }

async function loadAvailability() {
  try {
    const res = await fetch('/api/availability');
    const data = await res.json();
    availability = { z: data.z || {}, n: data.n || {} };
  } catch(e) {}
}

async function saveAvailability(person, date, status) {
  try {
    const res = await fetch('/api/availability', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ person, date, status })
    });
    const data = await res.json();
    availability = { z: data.z || {}, n: data.n || {} };
  } catch(e) {}
}

function calShiftMonth(delta) {
  calMonth += delta;
  if (calMonth < 0) { calMonth = 11; calYear--; }
  if (calMonth > 11) { calMonth = 0; calYear++; }
  renderCalendarGrid();
}

function renderCalendar() {
  const now = new Date();
  if (calYear === undefined) { calYear = now.getFullYear(); calMonth = now.getMonth(); }
  renderCalendarGrid();
}

function renderCalYou() {
  const el = document.getElementById('calYou');
  if (!currentPerson) { el.innerHTML = ''; return; }
  const name = currentPerson === 'z' ? 'Zoé' : 'Noé';
  el.innerHTML = `Connecté·e comme <b class="you-${currentPerson}">${name}</b> · <a onclick="switchPerson()">changer</a>`;
}

function renderCalendarGrid(pulseKey) {
  if (calYear === undefined) { const now = new Date(); calYear = now.getFullYear(); calMonth = now.getMonth(); }

  document.getElementById('calMonthLabel').textContent = FR_MONTHS[calMonth] + ' ' + calYear;
  const grid = document.getElementById('calGrid');
  grid.innerHTML = '';

  const first = new Date(calYear, calMonth, 1);
  const startDow = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();

  const today = new Date();
  const todayStr = dateKey(today.getFullYear(), today.getMonth(), today.getDate());

  for (let i = 0; i < startDow; i++) {
    grid.insertAdjacentHTML('beforeend', '<span class="day-cell empty"></span>');
  }

  for (let d = 1; d <= daysInMonth; d++) {
    const key = dateKey(calYear, calMonth, d);
    const zs = availability.z[key];
    const ns = availability.n[key];
    const both = zs === 'free' && ns === 'free';
    const cls = ['day-cell'];
    if (key === todayStr) cls.push('today');
    if (both) cls.push('both-free');
    if (key === pulseKey) cls.push('pulse');

    grid.insertAdjacentHTML('beforeend', `
      <button class="${cls.join(' ')}" data-date="${key}" onclick="cycleAvailability('${key}')">
        <span class="day-num">${d}</span>
        <span class="day-dots">
          <span class="day-dot z ${zs || 'none'}"></span>
          <span class="day-dot n ${ns || 'none'}"></span>
        </span>
        ${both ? '<span class="day-star">★</span>' : ''}
      </button>`);
  }
}

async function cycleAvailability(key) {
  if (!currentPerson) { showGate(); return; }
  const cur = availability[currentPerson][key];
  const next = cur === 'free' ? null : 'free';

  if (next) availability[currentPerson][key] = next;
  else delete availability[currentPerson][key];
  renderCalendarGrid(key);

  await saveAvailability(currentPerson, key, next);
}

/* ── lien d'abonnement (.ics) vers les dispos de l'autre ── */
let calendarLinks = null;

function otherPerson() {
  return currentPerson === 'z' ? 'n' : (currentPerson === 'n' ? 'z' : null);
}

function updateSubscribeButton() {
  const btn = document.getElementById('subscribeBtn');
  if (!btn) return;
  const other = otherPerson();
  if (!other) {
    btn.textContent = '📋 Copier le lien (choisis dabord qui tu es)';
    return;
  }
  const name = other === 'z' ? 'Zoé' : 'Noé';
  btn.textContent = `📋 Copier le lien des dispos de ${name}`;
}

async function loadCalendarLinks() {
  try {
    const res = await fetch('/api/calendar-links');
    calendarLinks = await res.json();
  } catch(e) { calendarLinks = null; }
  return calendarLinks;
}

function legacyCopy(text) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  let ok = false;
  try { ok = document.execCommand('copy'); } catch(e) {}
  document.body.removeChild(ta);
  return ok;
}

function copySubscribeLink() {
  const other = otherPerson();
  if (!other) { showGate(); return; }

  const url = calendarLinks && calendarLinks[other];
  if (!url) {
    // Links not preloaded yet (rare) — fetch then just show it as text,
    // since by then we're past the user gesture and clipboard access
    // may be refused by the browser.
    loadCalendarLinks().then(links => {
      const u = links && links[other];
      setSubscribeHint(u || 'Erreur — réessaie dans un instant.');
    });
    return;
  }

  const onCopied = () => setSubscribeHint('Lien copié ! Colle-le dans Google Agenda (ou Apple Calendrier) → Ajouter un agenda → À partir de l\'URL.');
  const onFailed = () => setSubscribeHint(url); // show it as selectable text so it can be copied by hand

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(onCopied).catch(() => {
      if (legacyCopy(url)) onCopied(); else onFailed();
    });
  } else if (legacyCopy(url)) {
    onCopied();
  } else {
    onFailed();
  }
}

function setSubscribeHint(msg) {
  const el = document.getElementById('subscribeHint');
  if (el) el.textContent = msg;
}

/* ══════════════════ NOTIFICATIONS PUSH ══════════════════ */

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
}

function updatePushButton(active) {
  const btn = document.getElementById('pushToggle');
  if (!btn) return;
  btn.classList.remove('blocked');
  btn.disabled = false;
  btn.classList.toggle('active', active);
  btn.textContent = active ? '🔔 Notifications activées' : '🔕 Activer les notifications';
}

async function initPush() {
  const btn = document.getElementById('pushToggle');
  if (!btn) return;
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    btn.style.display = 'none';
    return;
  }
  if (Notification.permission === 'denied') {
    btn.textContent = '🔕 Notifications bloquées par le navigateur';
    btn.classList.add('blocked');
    btn.disabled = true;
    return;
  }
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    updatePushButton(!!sub);
  } catch(e) {}
}

async function togglePush() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
  if (!currentPerson) { pendingPushToggle = true; showGate(); return; }

  const reg = await navigator.serviceWorker.ready;
  const existing = await reg.pushManager.getSubscription();

  if (existing) {
    try {
      await fetch('/api/push/unsubscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint: existing.endpoint })
      });
      await existing.unsubscribe();
    } catch(e) {}
    updatePushButton(false);
    return;
  }

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') { updatePushButton(false); return; }

  try {
    const keyRes = await fetch('/api/push/public-key');
    const { publicKey } = await keyRes.json();
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey)
    });
    await fetch('/api/push/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ person: currentPerson, subscription: sub.toJSON() })
    });
    updatePushButton(true);
  } catch(e) {
    updatePushButton(false);
  }
}

/* ── init ── */
load();
loadAvailability();
initPush();

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
