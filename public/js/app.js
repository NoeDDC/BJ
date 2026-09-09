/* ── iOS installed-PWA viewport bug ──
   When the on-screen keyboard opens in a home-screen web app, WebKit shrinks
   the layout viewport (window.innerHeight drops by ~60px) and does not grow
   it back when the keyboard closes. Every inset:0 / position:fixed layout
   then ends ~60px above the real screen edge for the rest of the session,
   which is the "gap under the bottom nav" seen on iPhone. Forcing a
   remeasure by toggling display on the full-screen root snaps it back; the
   synchronous reflow in between means nothing is painted in the hidden
   state. */
let maxViewportH = window.innerHeight;
let lastViewportW = window.innerWidth;

function isInstalledApp() {
  return window.navigator.standalone === true ||
         (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches);
}

function isTyping() {
  const el = document.activeElement;
  return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA');
}

function healViewport() {
  window.scrollTo(0, 0);
  if (!isInstalledApp()) return;                            // the bug only exists in home-screen mode
  if (Math.abs(window.innerWidth - lastViewportW) > 40) {   // rotated: new baseline
    lastViewportW = window.innerWidth;
    maxViewportH = window.innerHeight;
  }
  if (window.innerHeight > maxViewportH) maxViewportH = window.innerHeight;
  const shrink = maxViewportH - window.innerHeight;
  if (shrink <= 4) return;
  // A real keyboard takes 200px+. A ~60px deficit while an input still has
  // focus means the keyboard was closed with its own hide button, so heal
  // anyway (the input loses focus, which is what the user wanted).
  if (isTyping() && shrink > 120) return;

  const page = document.getElementById('appContent');
  const view = document.querySelector('.view.active');
  const scrollTop = view ? view.scrollTop : 0;
  page.style.display = 'none';
  void page.offsetHeight;
  page.style.display = '';
  if (view) view.scrollTop = scrollTop;
}

document.addEventListener('focusout', e => {
  const t = e.target;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) {
    setTimeout(healViewport, 150);   // right after the keyboard slides away
    setTimeout(healViewport, 600);   // and once more, iOS sometimes settles late
  }
});
window.addEventListener('resize', () => setTimeout(healViewport, 100));
window.addEventListener('orientationchange', () => setTimeout(healViewport, 300));
if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', () => setTimeout(healViewport, 100));
}

/* ── state ── */
const state = {
  z: { g: 0, b: 0 }, n: { g: 0, b: 0 },
  theme: 'theme-1', jours_sans_course: 0,
  streaks: { z: { count: 0, type: null }, n: { count: 0, type: null } }
};
const MAX_H = 42;

/* ── streak (stored server-side, so both people see the same running streak) ── */
function renderStreak(p) {
  const s      = state.streaks[p] || { count: 0, type: null };
  const numEl  = document.getElementById('snum-' + p);
  const lblEl  = document.getElementById('slbl-' + p);
  const dotsEl = document.getElementById('dots-' + p);

  if (s.count === 0) {
    numEl.textContent = '·';
    numEl.className   = 'streak-num empty';
    lblEl.textContent = 'série de suite';
    dotsEl.innerHTML  = '';
    return;
  }

  numEl.textContent = s.count;
  numEl.className   = 'streak-num ' + (s.type === 'g' ? 'good' : 'bad');

  const plural = s.count > 1 ? 's' : '';
  lblEl.textContent = (s.type === 'g' ? 'bonne' : 'mauvaise') + plural + ' de suite';

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

  numEl.classList.remove('pop');
  void numEl.offsetWidth;
  numEl.classList.add('pop');
  numEl.addEventListener('animationend', () => numEl.classList.remove('pop'), { once: true });
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
    "Ce jour-là est compté, et il appartient déjà au passé.",
    "Il faut bien des nuages pour apprécier le ciel bleu.",
    "Mauvaise journée, mais bonne résilience.",
    "Ça ne durera pas : les mauvaises journées n'ont jamais le dernier mot.",
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

/* ══════════════════ ÉNIGMES (bonnes journées seulement) ══════════════════
   Ajouter une bonne journée ouvre une petite énigme à trois choix. Bonne
   réponse : des confettis. Mauvaise réponse : la solution, en douceur. Dans
   les deux cas la journée est déjà comptée — l'énigme est un bonus, jamais
   une condition. Pour en ajouter une, une ligne suffit : la bonne réponse
   dans `a`, deux leurres dans `w`. */
const RIDDLES = [
  { q: "Je suis toujours devant toi, pourtant tu ne me verras jamais. Qui suis-je ?",
    a: "demain",        alt: ["l'avenir", "le futur", "le lendemain"] },
  { q: "Qu'est-ce qui se brise dès qu'on le prononce ?",
    a: "le silence",    alt: [] },
  { q: "Je monte et je descends sans jamais bouger. Qui suis-je ?",
    a: "un escalier",   alt: ["les escaliers", "les marches"] },
  { q: "J'ai des dents mais je ne mords jamais. Qui suis-je ?",
    a: "un peigne",     alt: ["les peignes", "un râteau"] },
  { q: "Je n'ai pas de bouche et pourtant je te réponds toujours. Qui suis-je ?",
    a: "l'écho",        alt: ["les échos"] },
  { q: "Plus j'en fais, plus j'en laisse derrière moi. Qu'est-ce que c'est ?",
    a: "des pas",       alt: ["un pas", "des empreintes", "des traces", "des traces de pas"] },
  { q: "C'est à toi, mais les autres s'en servent bien plus que toi. Qu'est-ce que c'est ?",
    a: "ton prénom",    alt: ["ton nom"] },
  { q: "J'ai un cou mais pas de tête. Qui suis-je ?",
    a: "une bouteille", alt: ["les bouteilles", "un flacon"] },
  { q: "J'ai des aiguilles mais je ne pique jamais. Qui suis-je ?",
    a: "une horloge",   alt: ["les horloges", "une montre", "une pendule", "un réveil"] },
  { q: "Deux personnes peuvent le partager, mais il ne se divise jamais. Qu'est-ce que c'est ?",
    a: "un secret",     alt: ["les secrets"] },
  { q: "Plus on le partage, plus il grandit. Qu'est-ce que c'est ?",
    a: "le bonheur",    alt: ["l'amour", "la joie", "le savoir", "la connaissance"] },
];

const RIDDLE_OK    = ["Bravo 🎉", "Exactement.", "C'était bien ça.", "Joli.", "Sans hésiter."];
const RIDDLE_RETRY = ["Pas tout à fait. Réessaie.", "Non, retente ta chance.", "Raté. Une autre idée ?", "Pas encore. Encore un essai ?"];
const RIDDLE_STATE_KEY = 'bj_riddle_day';

/* On tape sa réponse, donc la comparaison doit être indulgente : majuscules,
   accents, ponctuation, espaces en trop et article de tête sont ignorés.
   « L'Écho ! », « echo » et « un écho » valent donc tous « l'écho ». Le pluriel
   et les synonymes, eux, sont listés dans `alt` énigme par énigme. */
function normalizeAnswer(s) {
  return (s || '')
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')      // accents
    .replace(/[\u2018\u2019\u02bc`]/g, "'")               // apostrophes typographiques
    .replace(/[^a-z0-9']+/g, ' ')                          // ponctuation
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^(?:[ldcjmnst]'|(?:le|la|les|un|une|des|du|de|mon|ma|mes|ton|ta|tes|son|sa|ses|au|aux) )+/, '')
    .trim();
}

function todayStr() {
  const d = new Date();
  return dateKey(d.getFullYear(), d.getMonth(), d.getDate());
}

/* L'énigme du jour se déduit de la date : Zoé et Noé tombent sur la même, elle
   ne change pas si on referme et qu'on rouvre, et la liste défile en entier
   avant qu'une énigme ne revienne. */
function riddleOfTheDay() {
  const day = Math.floor(Date.parse(todayStr() + 'T00:00:00Z') / 86400000);
  return RIDDLES[((day % RIDDLES.length) + RIDDLES.length) % RIDDLES.length];
}

/* Deux drapeaux, remis à zéro à chaque nouveau jour : la journée a-t-elle été
   validée (le bouton énigme n'apparaît qu'ensuite) et l'énigme trouvée. */
function riddleState() {
  const today = todayStr();
  try {
    const s = JSON.parse(localStorage.getItem(RIDDLE_STATE_KEY) || 'null');
    if (s && s.date === today) return { date: today, unlocked: !!s.unlocked, solved: !!s.solved };
  } catch(e) {}
  return { date: today, unlocked: false, solved: false };
}

function saveRiddleState(changes) {
  const s = Object.assign(riddleState(), changes);
  try { localStorage.setItem(RIDDLE_STATE_KEY, JSON.stringify(s)); } catch(e) {}
  updateRiddleButton();
  return s;
}

function updateRiddleButton() {
  const btn = document.getElementById('riddleBtn');
  if (!btn) return;
  const s = riddleState();
  btn.classList.toggle('show', s.unlocked);     // rien tant que la journée n'est pas validée
  btn.classList.toggle('solved', s.solved);
  const label = s.solved ? 'Énigme du jour (trouvée)' : 'Énigme du jour';
  btn.title = label;
  btn.setAttribute('aria-label', label);
}

/* ── confettis ── */
function launchConfetti() {
  // respecte le réglage système "réduire les animations"
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const old = document.querySelector('.confetti-canvas');
  if (old) old.remove();

  const w = window.innerWidth, h = window.innerHeight;
  const canvas = document.createElement('canvas');
  canvas.className = 'confetti-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = w * dpr; canvas.height = h * dpr;
  canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
  document.body.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const styles = getComputedStyle(document.body);
  const colors = ['--z', '--z2', '--n', '--n2', '--gold']
    .map(v => styles.getPropertyValue(v).trim())
    .filter(Boolean);

  const pieces = Array.from({ length: 90 }, () => ({
    x: Math.random() * w,
    y: -20 - Math.random() * h * 0.6,          // échelonnés au-dessus de l'écran
    vx: (Math.random() - 0.5) * 1.4,
    vy: 1.8 + Math.random() * 2.4,
    size: 5 + Math.random() * 6,
    rot: Math.random() * Math.PI,
    vr: (Math.random() - 0.5) * 0.26,
    color: colors[Math.floor(Math.random() * colors.length)] || '#C9962E',
  }));

  const FADE_AT = 2600, END = 3800;
  let start = null;
  function frame(ts) {
    if (start === null) start = ts;
    const elapsed = ts - start;
    ctx.clearRect(0, 0, w, h);
    let onScreen = 0;
    for (const p of pieces) {
      p.vy += 0.02;                                     // gravité
      p.vx += Math.sin((p.y + p.x) / 60) * 0.02;        // dérive latérale
      p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      if (p.y < h + 30) onScreen++;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.globalAlpha = elapsed > FADE_AT ? Math.max(0, 1 - (elapsed - FADE_AT) / (END - FADE_AT)) : 1;
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
      ctx.restore();
    }
    if (onScreen && elapsed < END) requestAnimationFrame(frame);
    else canvas.remove();
  }
  requestAnimationFrame(frame);
}

/* ── popup ── */
let popupTimer = null;

/* person vaut 'z' ou 'n' quand l'énigme suit une bonne journée, null quand on
   la rouvre depuis le bouton du haut. */
function renderRiddle(person) {
  const dot    = document.getElementById('popup-dot');
  const accent = document.getElementById('popup-accent');
  const msg    = document.getElementById('popup-msg');
  const box    = document.getElementById('riddleForm');
  const input  = document.getElementById('riddleInput');
  const send   = document.getElementById('riddleSend');
  const note   = document.getElementById('riddleNote');
  const riddle = riddleOfTheDay();
  const solved = riddleState().solved;

  dot.className      = 'popup-dot ' + (person ? 'dot-good-' + person : 'dot-riddle');
  accent.textContent = person
    ? (person === 'z' ? 'Z · bonne journée' : 'N · bonne journée')
    : (solved ? 'énigme du jour · trouvée' : 'énigme du jour');
  msg.textContent    = riddle.q;   // la question reste affichée pendant les essais

  // Pas de focus automatique : le clavier surgirait juste après la tape sur
  // « + ». On touche le champ quand on est prêt à répondre.
  box.classList.add('show');
  input.value    = solved ? riddle.a : '';
  input.disabled = solved;
  send.disabled  = solved;

  note.className   = 'riddle-note' + (solved ? ' ok' : '');
  note.textContent = solved ? 'Déjà trouvée aujourd\'hui.' : '';

  document.getElementById('overlay').classList.add('show');
  if (popupTimer) clearTimeout(popupTimer);   // aucune fermeture auto : on prend son temps
  popupTimer = null;
}

/* Mauvaise réponse : on le dit et on laisse réessayer, autant de fois qu'on
   veut, dans la foulée ou en rouvrant l'énigme plus tard. La réponse n'est
   jamais dévoilée tant qu'elle n'a pas été trouvée. */
function submitRiddle() {
  const input = document.getElementById('riddleInput');
  const note  = document.getElementById('riddleNote');
  if (input.disabled) return;

  const given = normalizeAnswer(input.value);
  if (!given) { input.focus(); return; }

  const riddle   = riddleOfTheDay();
  const accepted = [riddle.a].concat(riddle.alt || []).map(normalizeAnswer);

  if (accepted.indexOf(given) === -1) {
    note.className   = 'riddle-note';
    note.textContent = pickMsg(RIDDLE_RETRY);
    input.select();                    // prêt à retenter sans tout réeffacer
    return;
  }

  input.value    = riddle.a;           // on réaffiche la forme « propre »
  input.disabled = true;
  document.getElementById('riddleSend').disabled = true;
  input.blur();                        // referme le clavier pour laisser voir les confettis
  note.className   = 'riddle-note ok';
  note.textContent = pickMsg(RIDDLE_OK);

  saveRiddleState({ solved: true });
  launchConfetti();
  if (popupTimer) clearTimeout(popupTimer);
  popupTimer = setTimeout(hidePopup, 3600);
}

/* Clavier ouvert : le popup remonte, sinon il reste centré derrière le clavier.
   On ne réagit pas au focus mais au rétrécissement réel de la fenêtre : bouger
   le popup entre l'appui et le relâchement ferait atterrir la tape à côté. */
function updatePopupForKeyboard() {
  const overlay = document.getElementById('overlay');
  const vv = window.visualViewport;
  const keyboardOpen = !!vv && isTyping() && (window.innerHeight - vv.height) > 120;
  overlay.classList.toggle('typing', overlay.classList.contains('show') && keyboardOpen);
}

/* Fermeture en touchant à côté : seulement si l'appui ET le relâchement ont eu
   lieu sur le fond. Sinon un décalage de mise en page, ou un glissement en
   sélectionnant du texte, refermait le popup par accident. */
let overlayPressStartedOutside = false;

function initRiddleInput() {
  const overlay = document.getElementById('overlay');
  const input   = document.getElementById('riddleInput');
  overlay.addEventListener('pointerdown', e => { overlayPressStartedOutside = (e.target === overlay); });
  if (input) input.addEventListener('blur', () => overlay.classList.remove('typing'));
  if (window.visualViewport) window.visualViewport.addEventListener('resize', updatePopupForKeyboard);
}

/* bouton « énigme du jour », en haut à gauche */
function openRiddle() {
  if (!riddleState().unlocked) return;
  renderRiddle(null);
}

function showPopup(person, type, delta) {
  const dot    = document.getElementById('popup-dot');
  const accent = document.getElementById('popup-accent');
  const msg    = document.getElementById('popup-msg');
  const box    = document.getElementById('riddleForm');
  const note   = document.getElementById('riddleNote');
  const input  = document.getElementById('riddleInput');
  box.classList.remove('show');       // remet à zéro : champ masqué et vide
  input.value = '';
  input.disabled = false;
  document.getElementById('riddleSend').disabled = false;
  note.className = 'riddle-note';
  note.textContent = '';

  // Ajouter une bonne journée débloque l'énigme du jour et l'ouvre. Si elle a
  // déjà été trouvée, on repasse simplement au message habituel.
  if (delta > 0 && type === 'g' && RIDDLES.length) {
    const s = saveRiddleState({ unlocked: true });
    if (!s.solved) { renderRiddle(person); return; }
  }

  let pool, dotClass, accentText;
  if (delta < 0) {
    pool       = MSGS.minus;
    dotClass   = type === 'g' ? 'dot-good-' + person : 'dot-bad-' + person;
    accentText = 'correction';
  } else if (type === 'g') {
    pool       = MSGS.good;
    dotClass   = 'dot-good-' + person;
    accentText = person === 'z' ? 'Z · bonne journée' : 'N · bonne journée';
  } else {
    pool       = MSGS.bad;
    dotClass   = 'dot-bad-' + person;
    accentText = person === 'z' ? 'Z · mauvaise journée' : 'N · mauvaise journée';
  }

  dot.className      = 'popup-dot ' + dotClass;
  accent.textContent = accentText;
  msg.textContent    = pickMsg(pool);

  document.getElementById('overlay').classList.add('show');
  if (popupTimer) clearTimeout(popupTimer);
  popupTimer = setTimeout(hidePopup, 4800);
}

function hidePopup() {
  const input = document.getElementById('riddleInput');
  if (input) input.blur();            // le clavier se referme avec le popup
  document.getElementById('overlay').classList.remove('show', 'typing');
  if (popupTimer) { clearTimeout(popupTimer); popupTimer = null; }
}

function closePopup(e) {
  const outside = e.target === document.getElementById('overlay') && overlayPressStartedOutside;
  overlayPressStartedOutside = false;
  if (outside) hidePopup();
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') hidePopup(); });

/* ── render ── */
function barH(v, mx) { return mx ? Math.max(3, Math.round(v / mx * MAX_H)) : 3; }

function render() {
  const vals = [state.z.g, state.z.b, state.n.g, state.n.b];
  const mx   = Math.max(...vals, 1);

  [['zg', state.z.g], ['zb', state.z.b], ['ng', state.n.g], ['nb', state.n.b]].forEach(([k, v]) => {
    document.getElementById('count-' + k).textContent = v;
    document.getElementById('bv-'    + k).textContent = v;
    document.getElementById('bar-'   + k).style.height = barH(v, mx) + 'px';
  });

  const tz = state.z.g + state.z.b;
  const tn = state.n.g + state.n.b;
  document.getElementById('total-z').textContent = tz + ' journée' + (tz > 1 ? 's' : '');
  document.getElementById('total-n').textContent = tn + ' journée' + (tn > 1 ? 's' : '');
  document.getElementById('total').textContent   = vals.reduce((a, b) => a + b, 0);
  document.getElementById('running-count').textContent = state.jours_sans_course;
  document.body.className = state.theme || 'theme-1';
  document.querySelectorAll('#paletteRow .swatch').forEach(b => b.classList.toggle('active', b.dataset.variant === state.theme));
  const metaTheme = document.querySelector('meta[name="theme-color"]');
  if (metaTheme) {
    const ink = getComputedStyle(document.body).getPropertyValue('--ink').trim();
    if (ink) metaTheme.setAttribute('content', ink);
  }
}

/* Optimistic mirror of the server's streak rule, so the streak box reacts
   on tap instead of after the network round trip. The server's answer
   (adopted in saveAdjust) stays authoritative. */
function applyStreakLocally(person, type, delta) {
  const s = state.streaks[person] || { count: 0, type: null };
  if (delta > 0) {
    s.count = s.type === type ? s.count + delta : delta;
    s.type = type;
  } else if (s.type === type) {
    s.count = Math.max(0, s.count + delta);
    if (s.count === 0) s.type = null;
  }
  state.streaks[person] = s;
  renderStreak(person);
}

/* ── change ── */
function change(person, type, delta) {
  const prev = state[person][type];
  const next = Math.max(0, prev + delta);
  if (next === prev) return;
  state[person][type] = next;
  applyStreakLocally(person, type, next - prev);

  render();
  saveAdjust(person + type, next - prev);
  showPopup(person, type, delta);

  const barEl = document.getElementById('bar-' + person + type);
  barEl.classList.remove('bump', 'dip');
  void barEl.offsetWidth;
  barEl.classList.add(delta > 0 ? 'bump' : 'dip');
  barEl.addEventListener('animationend', () => barEl.classList.remove('bump', 'dip'), { once: true });
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
    state.theme = data.theme || 'theme-1';
    state.jours_sans_course = parseInt(data.jours_sans_course || "0") || 0;
    state.streaks = data.streaks || state.streaks;
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
// authoritative totals (including streaks, which live server-side so both
// people always see the same running streak), which we adopt here.
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
    state.streaks = data.streaks || state.streaks;
    render();
    renderStreak('z');
    renderStreak('n');
    setStatus('');
  } catch(e) {
    setStatus('Erreur de sauvegarde');
  }
}

function toggleStylePicker() {
  document.getElementById('paletteRow').classList.toggle('show');
}

async function changeTheme(theme) {
  state.theme = theme;
  render();
  document.getElementById('paletteRow').classList.remove('show');
  try {
    const res = await fetch('/api/counters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme })
    });
    if (!res.ok) throw new Error();
    setStatus('Style mis à jour');
  } catch(e) {
    setStatus('Erreur de sauvegarde');
  }
}

function setStatus(msg) { document.getElementById('status').textContent = msg; }

/* ══════════════════ CALENDRIER ══════════════════ */

const FR_MONTHS = ['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre'];

let currentPerson = localStorage.getItem('bj_person') || null;
let calYear, calMonth;
let availability = { z: {}, n: {} };
let calPollTimer = null;
let notesPollTimer = null;
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

  if (view === 'notes') {
    if (!currentPerson) { showGate(); }
    loadNotes();
    if (notesPollTimer) clearInterval(notesPollTimer);
    notesPollTimer = setInterval(loadNotes, 30000);
  } else if (notesPollTimer) {
    clearInterval(notesPollTimer);
    notesPollTimer = null;
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
  loadNotes();
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
    const both  = zs === 'free' && ns === 'free';              // ★ whole day together
    const night = !both && nightOk(zs) && nightOk(ns);        // ☾ one of us is out in the evening, the night still works
    const cls = ['day-cell'];
    if (key === todayStr) cls.push('today');
    if (both) cls.push('both-free');
    if (night) cls.push('night-free');
    if (key === pulseKey) cls.push('pulse');

    grid.insertAdjacentHTML('beforeend', `
      <button class="${cls.join(' ')}" data-date="${key}">
        <span class="day-num">${d}</span>
        <span class="day-dots">
          <span class="day-dot z ${zs || 'none'}"></span>
          <span class="day-dot n ${ns || 'none'}"></span>
        </span>
        ${both ? '<span class="day-star">★</span>' : (night ? '<span class="day-moon">☾</span>' : '')}
      </button>`);
  }
}

function nightOk(status) { return status === 'free' || status === 'evening'; }

/* ── gestures on a day: tap = dispo toute la journée (on/off),
   long press = acti le soir mais dodo possible (on/off) ── */
const LONG_PRESS_MS = 450;
let press = null;   // { key, x, y, timer, fired } for the pointer currently down

function applyAvailability(key, status) {
  if (!currentPerson) { showGate(); return; }
  if (status) availability[currentPerson][key] = status;
  else delete availability[currentPerson][key];
  renderCalendarGrid(key);
  saveAvailability(currentPerson, key, status);
}

function tapAvailability(key) {
  const cur = availability[currentPerson] && availability[currentPerson][key];
  applyAvailability(key, cur === 'free' ? null : 'free');
}

function longPressAvailability(key) {
  const cur = availability[currentPerson] && availability[currentPerson][key];
  applyAvailability(key, cur === 'evening' ? null : 'evening');
}

function initCalendarGestures() {
  const grid = document.getElementById('calGrid');
  const cancelPress = () => { if (press && press.timer) { clearTimeout(press.timer); press.timer = null; } };

  grid.addEventListener('pointerdown', e => {
    const cell = e.target.closest('.day-cell[data-date]');
    if (!cell) return;
    cancelPress();
    press = { key: cell.dataset.date, x: e.clientX, y: e.clientY, timer: null, fired: false };
    press.timer = setTimeout(() => {
      press.timer = null;
      press.fired = true;
      if (!currentPerson) { showGate(); return; }
      longPressAvailability(press.key);
    }, LONG_PRESS_MS);
  });
  // a finger that moves is scrolling the month, not pressing
  grid.addEventListener('pointermove', e => {
    if (press && press.timer && Math.hypot(e.clientX - press.x, e.clientY - press.y) > 10) cancelPress();
  });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(t => grid.addEventListener(t, cancelPress));

  grid.addEventListener('click', e => {
    const cell = e.target.closest('.day-cell[data-date]');
    if (!cell) return;
    if (press && press.fired) { press.fired = false; return; }   // the click that trails a long press
    if (!currentPerson) { showGate(); return; }
    tapAvailability(cell.dataset.date);
  });
  grid.addEventListener('contextmenu', e => e.preventDefault());   // Android's long-press menu
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
      setSubscribeHint(u || 'Erreur : réessaie dans un instant.');
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

/* ══════════════════ RAPPEL DISCUSSION ══════════════════ */

let notesState = { mine: [], otherCount: 0 };

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

async function loadNotes() {
  if (!currentPerson) { renderNotes(); return; }
  try {
    const res = await fetch('/api/notes?person=' + currentPerson);
    notesState = await res.json();
  } catch(e) {}
  renderNotes();
}

function renderNotes() {
  const mineEl = document.getElementById('notesMine');
  const otherEl = document.getElementById('notesOther');
  if (!mineEl || !otherEl) return;

  if (!currentPerson) {
    mineEl.innerHTML = '';
    otherEl.innerHTML = '';
    return;
  }

  const other = otherPerson();
  const otherName = other === 'z' ? 'Zoé' : 'Noé';
  const n = notesState.otherCount || 0;
  const otherMsg = n === 0
    ? `${otherName} n'a rien noté pour l'instant`
    : `${otherName} a <b>${n}</b> sujet${n > 1 ? 's' : ''} en réserve`;
  otherEl.innerHTML = `<div class="notes-other-card"><span class="notes-other-icon">🤫</span><span class="notes-other-text">${otherMsg}</span></div>`;

  const mine = notesState.mine || [];
  if (!mine.length) {
    mineEl.innerHTML = '<div class="notes-empty">Rien pour l\'instant</div>';
    return;
  }
  mineEl.innerHTML = mine.map(note => `
    <div class="note-item${note.pending ? ' pending' : ''}">
      <span class="note-text">${escapeHtml(note.text)}</span>
      <button class="note-del" onclick="deleteNote('${note.id}')" aria-label="Supprimer"${note.pending ? ' disabled' : ''}>✕</button>
    </div>
  `).join('');
}

// Both edits below show up instantly (a greyed "pending" note, or the note
// gone) and are then replaced by the server's answer; on failure the
// previous list comes back so nothing silently disappears.
async function addNote() {
  if (!currentPerson) { showGate(); return; }
  const input = document.getElementById('noteInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';

  const tempId = 'tmp-' + Date.now();
  notesState.mine = [...(notesState.mine || []), { id: tempId, text, pending: true }];
  renderNotes();

  try {
    const res = await fetch('/api/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ person: currentPerson, text })
    });
    if (!res.ok) throw new Error();
    notesState = await res.json();
  } catch(e) {
    notesState.mine = (notesState.mine || []).filter(n => n.id !== tempId);
    if (!input.value) input.value = text;   // give the text back rather than losing it
  }
  renderNotes();
}

async function deleteNote(id) {
  if (!currentPerson || String(id).startsWith('tmp-')) return;
  const before = notesState.mine || [];
  notesState.mine = before.filter(n => String(n.id) !== String(id));
  renderNotes();

  try {
    const res = await fetch('/api/notes/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ person: currentPerson, id: Number(id) })
    });
    if (!res.ok) throw new Error();
    notesState = await res.json();
  } catch(e) {
    notesState.mine = before;
  }
  renderNotes();
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
  btn.textContent = active ? '🔔' : '🔕';
  btn.title = active ? 'Notifications activées' : 'Activer les notifications';
}

async function initPush() {
  const btn = document.getElementById('pushToggle');
  if (!btn) return;
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    btn.style.display = 'none';
    return;
  }
  if (Notification.permission === 'denied') {
    btn.textContent = '🔕';
    btn.title = 'Notifications bloquées par le navigateur';
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

/* ── refresh when the app comes back to the foreground ──
   There is no polling on the journal, so this is how the other person's
   taps show up when the installed app is reopened. */
function refreshActiveView() {
  load();
  const activeBtn = document.querySelector('.nav-btn.active');
  const view = activeBtn ? activeBtn.dataset.view : 'journal';
  if (view === 'calendar') loadAvailability().then(() => renderCalendarGrid());
  if (view === 'notes') loadNotes();
}
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState !== 'visible') return;
  refreshActiveView();
  updateRiddleButton();          // minuit a pu passer pendant que l'app dormait
  setTimeout(healViewport, 200);
});
window.addEventListener('pageshow', e => { if (e.persisted) refreshActiveView(); });

/* ── init ── */
initRiddleInput();
updateRiddleButton();
initCalendarGestures();
load();
loadAvailability();
initPush();

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
