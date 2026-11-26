/* 종합관리 — 화면 */
'use strict';
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const MODE = new URLSearchParams(location.search).get('mode') === 'browser' ? 'browser' : 'app';
const COLOR = {red: 'bad', orange: 'warn', green: 'ok', blue: 'now', gray: 'wait', purple: 'now', teal: 'ok'};
// 할 일 줄 공통: 기한(위 = 남은 날 · 아래 = 날짜) · 종류 꼬리표 · 둘째 줄 조각
const dueTxt = left => left < 0 ? `${-left}일 지남` : left === 0 ? '오늘' : `D-${left}`;
const dueCls = left => left <= 0 ? 'over' : left <= ((S && S.todo && S.todo.hot_days) || 3) ? 'hot' : left <= 7 ? 'soon' : '';
function todoDue(i, editable) {
  if (i.done || !i.due) return '<div class="due none"></div>';
  const tip = (i.estimated ? '진행 날짜에 정해진 날수를 더한 예상 기한이에요. 실제 기한은 명령서로 확인해 주세요. ' : '') + (editable ? '· 눌러서 기한 바꾸기' : '');
  return `<div class="due ${dueCls(i.left)}" ${editable ? 'data-act="due"' : ''} ${tip ? `title="${tip}"` : ''}><b>${dueTxt(i.left)}</b><span>${md(i.due)}${i.estimated ? ' 예상' : ''}</span></div>`;
}
const todoKind = (k, c) => `<span class="kd" style="--k:${HEX[c] || HEX.blue}">${esc(k)}</span>`;
const todoTitle = i => `${i.case_no ? `<span class="no">${esc(i.case_no)}</span>` : ''}${i.party ? `<span class="pt">${esc(i.party)}</span>` : ''}${todoKind(i.kind, i.color)}${i.new ? '<span class="td-new">새로</span>' : ''}`;
const HEX = {red: '#cf3f3f', orange: '#b06f08', green: '#1b8a4e', blue: '#525252', gray: '#a3a3a3', purple: '#525252', teal: '#1b8a4e'};
let INFO = null, S = null, CUR = 'home', ARGS = {};

// ------------------------------------------------------------------ 기능 호출
function rawCall(name, args) {
  if (MODE === 'browser') {
    return fetch('/api', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, args})}).then(r => r.json());
  }
  return window.pywebview.api.call(name, args || {});
}
async function api(name, args) {
  const r = await rawCall(name, args);
  if (!r || !r.ok) throw new Error((r && r.error) || '알 수 없는 오류');
  return r.data;
}
window.api = api;
function toast(text, bad) {
  const el = document.createElement('div');
  el.className = 'note' + (bad ? ' bad' : '');
  el.textContent = text;
  $('#toasts').appendChild(el);
  setTimeout(() => el.remove(), bad ? 6000 : 3200);
}
async function safe(fn) {
  try { return await fn(); } catch (e) { toast(e.message, true); }
}

// ------------------------------------------------------------------ 공통 조각
const chip = (text, color) => `<span class="chip ${COLOR[color] || color || 'now'}">${esc(text)}</span>`;
const stChip = c => c.status ? chip(c.status, c.color) : c.last_result === 'notfound' ? chip('찾을 수 없음', 'bad') : chip('조회 전', 'wait');
const tg = (on, attrs = '') => `<div class="tg ${on ? 'on' : ''}" ${attrs}></div>`;
// 뒤로가기: 화면을 옮길 때마다 앞 화면을 기억 (같은 화면을 다시 그리는 것은 기록하지 않음)
const HIST = [];
const backBtn = () => HIST.length ? `<a class="back-btn" title="앞 화면으로 (Alt + ←, 마우스 뒤로 단추)">‹ 뒤로</a>` : '';
const head = (crumb, title, right = '') => `<div class="head"><div><div class="crumb">${backBtn()}${crumb}</div><h1>${title}</h1></div><div class="row-gap">${right}</div></div>`;
function goBack() { const h = HIST.pop(); if (h) go(h.id, h.args, {back: true}); }
const md = d => d ? d.slice(5).replace('-', '.') : '';
const fullDate = d => d ? d.replace(/-/g, '.') : '';
function dday(left) {
  if (left === null || left === undefined) return '';
  if (left < 0) return `<span class="dday hot">${-left}일 지남</span>`;
  if (left === 0) return '<span class="dday hot">오늘</span>';
  const hot = left <= (S.todo.hot_days || 3);
  return `<span class="dday ${hot ? 'hot' : left <= 7 ? 'soon' : ''}">D-${left}</span>`;
}
function empty(title, text, btn = '') {
  return `<div class="empty"><b>${title}</b>${text}${btn ? `<div>${btn}</div>` : ''}</div>`;
}
const WEEK = ['일', '월', '화', '수', '목', '금', '토'];
const wd = d => WEEK[new Date(d + 'T00:00').getDay()];

function modal(title, body, buttons, wide) {
  return new Promise(resolve => {
    const bg = document.createElement('div');
    bg.className = 'modal-bg';
    bg.innerHTML = `<div class="modal ${wide ? 'wide' : ''}"><div class="modal-h"><h3>${title}</h3><button class="mx">×</button></div>
      <div class="modal-b">${body}</div><div class="modal-f">${buttons.map((b, i) => `<button class="btn ${b.cls || ''}" data-i="${i}">${b.text}</button>`).join('')}</div></div>`;
    document.body.appendChild(bg);
    const close = v => { bg.remove(); resolve(v); };
    bg.addEventListener('click', e => { if (e.target === bg || e.target.classList.contains('mx')) close(null); });
    $$('.modal-f .btn', bg).forEach(b => b.onclick = async () => {
      const btn = buttons[+b.dataset.i];
      if (!btn.value) return close(null);
      const v = await btn.value(bg);
      if (v !== false) close(v);
    });
    const first = $('input,textarea,select', bg);
    if (first) setTimeout(() => first.focus(), 50);
    bg.addEventListener('keydown', e => {
      if (e.key === 'Escape') close(null);
      if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') { const p = $('.modal-f .btn.primary,.modal-f .btn.blue', bg); if (p) p.click(); }
    });
  });
}
const confirmBox = (title, text, ok = '확인') => modal(title, `<div class="muted" style="line-height:1.7">${text}</div>`, [{text: '취소'}, {text: ok, cls: 'primary', value: () => true}]);

// ------------------------------------------------------------------ 화면 이동
const NAV_OF = {run: 'pick', import: 'ledger', case: 'ledger', auction_case: 'auction', result: 'hist'};
const NAV_PILLS = [];  // 다른 화면 파일이 메뉴 숫자를 더한다 (legal.js)
async function go(id, args = {}, opt = {}) {
  if (!opt.back && CUR && id !== CUR && SCREENS[CUR]) { HIST.push({id: CUR, args: ARGS}); if (HIST.length > 40) HIST.shift(); }
  if (CUR === 'run' && id !== 'run') document.removeEventListener('keydown', runKeys);
  if (id !== 'auction' && typeof auStop === 'function') auStop();
  CUR = id; ARGS = args;
  $$('#nav button').forEach(b => b.classList.toggle('on', b.dataset.s === (NAV_OF[id] || id)));
  markNav();
  $('main').scrollTop = 0;
  const view = $('#view');
  view.classList.add('loading');
  try {
    await SCREENS[id](view, args);
    const cr = $('.head .crumb', view);  // 제목을 따로 그리는 화면에도 「‹ 뒤로」
    if (cr && HIST.length && !$('.back-btn', cr)) cr.insertAdjacentHTML('afterbegin', backBtn());
  } catch (e) {
    view.innerHTML = empty('화면을 열지 못했어요', esc(e.message));
  }
  view.classList.remove('loading');
  refreshPills().then(() => markNav()).catch(() => {});
}
document.addEventListener('click', e => {
  if (e.target.closest('.back-btn')) { e.preventDefault(); return goBack(); }
  const g = e.target.closest('[data-go]');
  if (g) { e.preventDefault(); go(g.dataset.go, g.dataset.arg ? JSON.parse(g.dataset.arg) : {}); }
});
$$('#nav button').forEach(b => b.onclick = () => go(b.dataset.s));
document.addEventListener('keydown', e => { if (e.altKey && e.key === 'ArrowLeft' && !$('.modal-bg')) { e.preventDefault(); goBack(); } });
document.addEventListener('mouseup', e => { if (e.button === 3 && !$('.modal-bg')) { e.preventDefault(); goBack(); } });

async function refreshPills() {
  try {
    const i = await api('info', {mode: MODE});
    INFO = i; S = i.settings;
    const t = $('#pillTodo');
    t.hidden = !i.counts.todo; t.textContent = i.counts.todo;
    const au = $('#pillAuc');
    if (au) { au.hidden = !i.auction_count; au.textContent = i.auction_count; }
    const r = $('#pillRun');
    r.hidden = !i.running; if (i.running) r.textContent = `${i.running.done} / ${i.running.total}`;
    NAV_PILLS.forEach(f => f(i));
    if (document.body.classList.contains('side-mini')) sideMini(true);
  } catch (e) { /* 무시 */ }
}

// ------------------------------------------------------------------ 밝게/어둡게 · 화면 설정
function applyLook() {
  const L = S.look || {};
  const t = L.theme === 'auto' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : (L.theme || 'light');
  document.documentElement.dataset.theme = t;
  $$('#themeSw button').forEach(b => b.classList.toggle('on', b.dataset.t === t));
  document.body.classList.toggle('big', L.font === 'big');
  document.body.classList.toggle('dense', !!L.dense);
  sideMini(!!L.side_mini);
  if (L.accent && L.accent !== '#3355ff' && t === 'light') { document.documentElement.style.setProperty('--accent', L.accent); document.documentElement.style.setProperty('--accent-text', '#fff'); }
  else { document.documentElement.style.removeProperty('--accent'); document.documentElement.style.removeProperty('--accent-text'); }
  const hidden = new Set(S.menu_hidden || []);
  $$('#nav button').forEach(b => b.classList.toggle('hide', hidden.has(b.dataset.s)));
  buildNav();
}
// 메뉴 묶음: 자주 쓰는 것이 위, 나머지는 접어 둘 수 있음. 설정 → 메뉴 구성에서 순서·묶음을 바꿈
const MENU_DEFAULT = [
  {name: '자주 쓰는 것', items: ['console', 'home', 'pick', 'lg_dlv', 'fm']},
  {name: '사건 · 경매', items: ['cal', 'ledger', 'auction']},
  {name: '법조치', items: ['lg_home', 'lg_debtors', 'lg_rehab']},
  {name: '자료', items: ['xl', 'hist', 'report']},
  {name: '설정', items: ['lg_std', 'settings']},
];
const MENU_FOLD_DEFAULT = {'사건 · 경매': false, '법조치': false, '자료': true, '설정': true};
function menuLayout() {
  const all = $$('#nav button').map(b => b.dataset.s);
  let lay = (S.menu_layout && S.menu_layout.length ? S.menu_layout : MENU_DEFAULT).map(g => ({name: g.name, items: g.items.filter(s => all.includes(s))}));
  if (!lay.some(g => g.items.includes('console')) && all.includes('console') && lay[0]) lay[0].items.unshift('console');
  const seen = new Set(lay.flatMap(g => g.items));
  const rest = all.filter(s => !seen.has(s));  // 새로 생긴 메뉴는 마지막 묶음 앞에
  if (rest.length) { const i = Math.max(0, lay.length - 1); lay[i] = {name: lay[i].name, items: rest.concat(lay[i].items)}; }
  if (!lay.some(g => g.items.includes('settings'))) lay[lay.length - 1].items.push('settings');
  return lay;
}
function menuFold() { return Object.assign({}, MENU_FOLD_DEFAULT, (S.look && S.look.menu_fold) || {}); }
function buildNav() {
  const nav = $('#nav');
  if (!nav) return;
  const btn = {};
  $$('#nav button').forEach(b => { btn[b.dataset.s] = b; });
  const fold = menuFold(), lay = menuLayout();
  nav.innerHTML = '';
  lay.forEach((g, gi) => {
    const lab = document.createElement('div');
    lab.className = 'menu-label fold' + (fold[g.name] && gi ? ' folded' : '');
    lab.dataset.g = g.name;
    lab.innerHTML = `<span>${esc(g.name)}</span>${gi ? '<i class="arr"></i>' : ''}<b class="fdot" hidden></b>`;
    nav.appendChild(lab);
    g.items.forEach(s => { if (btn[s]) { btn[s].dataset.g = g.name; btn[s].classList.toggle('in-fold', !!(fold[g.name] && gi)); nav.appendChild(btn[s]); } });
  });
  markNav();
}
function markNav() {
  $$('#nav .menu-label').forEach(l => {
    const items = $$(`#nav button[data-g="${CSS.escape(l.dataset.g)}"]`).filter(b => !b.classList.contains('hide'));
    l.hidden = !items.length;
    const pills = items.map(b => b.querySelector('.pill:not([hidden])')).filter(Boolean);
    const dot = l.querySelector('.fdot');
    dot.hidden = !(l.classList.contains('folded') && pills.length);
    if (!dot.hidden) dot.className = 'fdot' + (pills.some(p => p.classList.contains('red')) ? ' red' : '');
    l.classList.toggle('has-on', l.classList.contains('folded') && items.some(b => b.classList.contains('on')));
  });
}
document.addEventListener('click', e => {
  const l = e.target.closest('#nav .menu-label.fold');
  if (!l || !l.querySelector('.arr')) return;
  const f = menuFold();
  f[l.dataset.g] = !l.classList.contains('folded');
  setSetting('look.menu_fold', f).then(() => buildNav());
});
async function setSetting(path, value, note) {
  S = await api('setting_set', {path, value, note: note || ''});
  INFO.settings = S;
  if (path.startsWith('look') || path === 'menu_hidden') applyLook();
}
$$('#themeSw button').forEach(b => b.onclick = () => safe(() => setSetting('look.theme', b.dataset.t)));
// ------------------------------------------------------------------ 왼쪽 메뉴 접기 (아이콘만) · Ctrl+B
function sideMini(on) {
  document.body.classList.toggle('side-mini', on);
  const t = $('#sideTg');
  if (t) { t.title = on ? '메뉴 펼치기 (Ctrl+B)' : '메뉴 접기 (Ctrl+B)'; t.setAttribute('aria-label', on ? '메뉴 펼치기' : '메뉴 접기'); }
  // 접으면 글자가 안 보이니 마우스를 올리면 이름이 뜨게
  $$('#nav button').forEach(b => { const n = [...b.childNodes].filter(x => x.nodeType === 3).map(x => x.textContent).join('').trim(); const p = b.querySelector('.pill:not([hidden])');
    b.title = on ? n + (p ? ` (${p.textContent})` : '') : ''; });
  const bk = $('#bookSel'); if (bk) { bk.dataset.ini = ((typeof INFO !== 'undefined' && INFO.book) || '').trim().slice(0, 1); bk.title = on ? `채권: ${(typeof INFO !== 'undefined' && INFO.book) || ''} · 바꾸기` : '채권 바꾸기'; }
}
function sideToggle() { safe(() => setSetting('look.side_mini', !document.body.classList.contains('side-mini'))); }
$('#sideTg').onclick = sideToggle;
document.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && (e.key || '').toLowerCase() === 'b' && !$('.modal-bg') && !/INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || '')) { e.preventDefault(); sideToggle(); } });

// ------------------------------------------------------------------ 끌어다 놓기 (엑셀)
window.onAppEvent = ev => {
  if (ev.type === 'drop' && ev.paths && ev.paths.length) {
    if (CUR === 'import' || CUR === 'ledger') go('import', {path: ev.paths[0]});
    else go('pick', {xl: ev.paths[0]});
  }
};
document.addEventListener('dragover', e => { e.preventDefault(); document.body.classList.add('drop-on'); });
document.addEventListener('dragleave', e => { if (!e.relatedTarget) document.body.classList.remove('drop-on'); });
document.addEventListener('drop', e => { e.preventDefault(); document.body.classList.remove('drop-on'); });

// ------------------------------------------------------------------ 채권 고르기
function drawBook() {
  $('#bookName').textContent = INFO.book;
  document.title = `${INFO.demo ? '[시연 판] ' : ''}종합관리 · ${INFO.book}`;
  if (document.body.classList.contains('side-mini')) sideMini(true);
  // 시연 판(--demo): 법원 사이트 대신 꾸며 낸 결과 → 실제 판과 헷갈리지 않게 늘 표시
  if (INFO.demo && !$('#demoBar')) document.body.insertAdjacentHTML('beforeend', '<div id="demoBar" class="demo-bar"><b>시연 판</b> 법원 사이트에 접속하지 않아요 · 조회 결과는 꾸며 낸 것이에요 · 실제 업무는 「종합관리」로</div>');
}
$('#bookSel').onclick = e => {
  e.stopPropagation();
  const old = $('.book-menu');
  if (old) { old.remove(); return; }
  const m = document.createElement('div');
  m.className = 'book-menu';
  m.innerHTML = INFO.books.map(b => `<div class="bi ${b.current ? 'on' : ''}" data-b="${esc(b.name)}">${b.current ? '✓ ' : ''}${esc(b.name)}<span>${b.cases}건</span></div>`).join('') +
    '<div class="sep"></div><div class="bi" data-act="add">+ 새 채권 만들기</div><div class="bi" data-act="manage">채권 이름 바꾸기 · 지우기</div>';
  document.body.appendChild(m);
  const r = $('#bookSel').getBoundingClientRect();
  m.style.top = (r.bottom + 6) + 'px'; m.style.left = r.left + 'px'; m.style.width = Math.max(250, r.width) + 'px';
  const close = () => { m.remove(); document.removeEventListener('click', close); };
  setTimeout(() => document.addEventListener('click', close), 0);
  $$('.bi', m).forEach(x => x.onclick = () => safe(async () => {
    close();
    if (x.dataset.b) return switchBook(x.dataset.b);
    if (x.dataset.act === 'add') {
      const name = await modal('새 채권 만들기', '<label class="lb">채권 이름</label><input class="field" id="bn" placeholder="예: ○○캐피탈 2025-1차">' +
        '<div class="small muted mt8">채권마다 사건 대장 · 조회 결과 · 확인할 것 · 조회 기록이 따로 쌓여요. 설정은 함께 써요.</div>',
        [{text: '취소'}, {text: '만들기', cls: 'primary', value: bg => $('#bn', bg).value.trim() || false}]);
      if (!name) return;
      await api('book_add', {name});
      await afterBook(`「${name}」을 만들었어요`, 'ledger');
    } else manageBooks();
  }));
};
async function switchBook(name) {
  if (INFO.running && !await confirmBox('채권 바꾸기', '하던 조회를 멈추고 바꿔요. 「조회 기록」에서 이어서 할 수 있어요.', '바꾸기')) return;
  await api('book_switch', {name});
  await afterBook(`「${name}」으로 바꿨어요`);
}
async function afterBook(msg, screen) {
  INFO = await api('info', {mode: MODE}); S = INFO.settings;
  drawBook(); applyLook(); toast(msg);
  go(screen || (INFO.counts.cases ? (S.todo.start || 'home') : 'pick'));
}
async function manageBooks() {
  const books = await api('books');
  await modal('채권 관리', `<table class="tbl">${books.map(b => `<tr><td><b>${esc(b.name)}</b>${b.current ? ' ' + chip('지금', 'blue') : ''}</td><td class="muted">${b.cases}건</td>
      <td class="right nowrap"><button class="btn sm ghost" data-rn="${esc(b.name)}">이름 바꾸기</button>${b.current ? '<button class="btn sm ghost" data-clr="1">비우기</button>' : ''}<button class="btn sm ghost" data-del="${esc(b.name)}" ${books.length < 2 ? 'disabled' : ''}>지우기</button></td></tr>`).join('')}</table>
    <div class="small muted mt8">지우거나 비우기 전에 자료를 압축해서 남겨 둬요 (자료 폴더의 「지운 채권」·백업).</div>`, [{text: '닫기'}], true);
}
document.addEventListener('click', e => {
  const rn = e.target.closest('[data-rn]'), del = e.target.closest('[data-del]'), clr = e.target.closest('[data-clr]');
  if (!rn && !del && !clr) return;
  const bg = e.target.closest('.modal-bg');
  safe(async () => {
    if (rn) {
      const name = await modal('채권 이름 바꾸기', `<label class="lb">새 이름</label><input class="field" id="bn" value="${esc(rn.dataset.rn)}">`, [{text: '취소'}, {text: '바꾸기', cls: 'primary', value: b => $('#bn', b).value.trim() || false}]);
      if (!name || name === rn.dataset.rn) return;
      await api('book_rename', {old: rn.dataset.rn, new: name});
      if (bg) bg.remove();
      await afterBook('이름을 바꿨어요', CUR);
    } else if (del) {
      if (!await confirmBox('채권 지우기', `「${esc(del.dataset.del)}」의 사건 대장·결과·기록을 지워요.<br>지우기 전에 압축 파일로 남겨 둬요.`, '지우기')) return;
      await api('book_delete', {name: del.dataset.del});
      if (bg) bg.remove();
      await afterBook('지웠어요');
    } else if (clr) {
      if (!await confirmBox('이 채권 비우기', `「${esc(INFO.book)}」의 사건·결과·기록을 모두 비우고 처음 상태로 만들어요.<br>먼저 백업해 둬요 (설정 → 저장·백업에서 되살릴 수 있어요).`, '비우기')) return;
      const n = await api('book_clear');
      if (bg) bg.remove();
      await afterBook('비웠어요 · 백업 ' + n, 'pick');
    }
  });
});

const SCREENS = {};

// ================================================================== 확인할 것
// 묶음: 사건 조회 · 보정·송달 · 경매 · 회생·파산 · 시효 / 「오늘 할 것만」= 기한이 오늘이거나 지난 것, 새로 들어온 것, 기한을 넣어야 하는 것
const TODO_CATS = ['사건 조회', '보정·송달', '경매', '회생·파산', '시효', '배당'];
function todoCat(i) {
  if (i.dv || String(i.key).startsWith('D|')) return '배당';
  if (i.aid || String(i.key).startsWith('A|')) return '경매';
  if (/회생|파산/.test(i.kind)) return '회생·파산';
  if (/시효/.test(i.kind)) return '시효';
  if (/보정|송달|공시/.test(i.kind)) return '보정·송달';
  return '사건 조회';
}
const isToday = i => !i.done && ((i.left !== null && i.left !== undefined && i.left <= 0) || i.ask || i.new || i.date === INFO.today);
const HOMEF = (() => { try { return JSON.parse(localStorage.getItem('home-f') || '{}'); } catch (e) { return {}; } })();
SCREENS.home = async (v, a) => {
  if ('cat' in a) HOMEF.cat = a.cat;
  if ('today' in a) HOMEF.today = a.today;
  try { localStorage.setItem('home-f', JSON.stringify({cat: HOMEF.cat || '', today: !!HOMEF.today})); } catch (e) { /* 저장 못 해도 화면은 그대로 */ }
  const cat = HOMEF.cat || '', todayOnly = !!HOMEF.today;
  const d0 = await api('home', {show_done: !!a.done});
  const all = d0.items;
  const catN = c => all.filter(i => !i.done && todoCat(i) === c && (!todayOnly || isToday(i))).length;
  const d = Object.assign({}, d0, {items: all.filter(i => (!cat || todoCat(i) === cat) && (!todayOnly || isToday(i) || i.done && a.done))});
  const open = d.items.filter(i => !i.done);
  const kinds = {};
  open.forEach(i => { kinds[i.kind] = kinds[i.kind] || {n: 0, color: i.color, hot: null}; kinds[i.kind].n++; if (i.left !== null && (kinds[i.kind].hot === null || i.left < kinds[i.kind].hot)) kinds[i.kind].hot = i.left; });
  const order = Object.entries(kinds).sort((x, y) => y[1].n - x[1].n).slice(0, 4);
  const filter = a.kind || '';
  const shown = d.items.filter(i => !filter || i.kind === filter);
  const groups = {};
  shown.forEach(i => (groups[i.group] = groups[i.group] || []).push(i));
  const icon = {red: '!', orange: '✉', green: '✓', blue: '◷', gray: '·'};
  const row = i => `<div class="todo ${i.done ? 'done' : ''}" data-key="${esc(i.key)}">
      <div class="bar" style="background:${HEX[i.color] || HEX.blue}"></div><div class="chk" data-act="done">✓</div>
      <div class="m"><div class="t">${todoTitle(i)}</div>
      <div class="s">${i.date && i.date !== i.due ? `<span>${md(i.date)}</span>` : ''}<span class="tx">${esc(i.text)}</span>${i.court ? `<span>${esc(i.court)}</span>` : ''}${i.memo1 ? `<span>메모 ${esc(i.memo1)}</span>` : ''}${i.done ? `<span>처리함${i.done_note ? ' 「' + esc(i.done_note) + '」' : ''} ${esc(i.done_by)}</span>` : ''}${i.ask ? '<span class="ask">기한을 확인해 넣어 주세요</span>' : ''}</div></div>
      ${todoDue(i, true)}
      ${i.done ? '<button class="btn sm ghost" data-act="undo">되돌리기</button>' : (i.ask ? '<button class="btn sm ask-btn" data-act="due">기한 넣기</button>' : '')}
      <button class="btn sm" ${i.legal ? `data-go="${i.go}" data-arg='${JSON.stringify(i.arg || {})}'` : i.aid ? `data-go="auction_case" data-arg='${JSON.stringify({aid: i.aid, tab: 't3'})}'` : `data-go="case" data-arg='${JSON.stringify({cid: i.cid})}'`}>자세히</button></div>`;
  v.innerHTML = head(`${esc(INFO.book)} · ${fullDate(INFO.today)} (${wd(INFO.today)})${d.last_run ? ' · 마지막 조회 ' + esc(d.last_run.slice(0, 16)) : ''}`,
      `확인할 것 <span class="faint" style="font-weight:500">${open.length}</span>`,
      `<button class="btn ${a.done ? 'primary' : ''}" id="showDone">${a.done ? '✓ 처리한 것도 보는 중' : '처리한 것 보기'}</button><button class="btn primary" data-go="pick">조회하기 →</button>`) + notices(d) +
    (order.length ? `<div class="todo-cats">${order.map(([k, x]) => `<div class="card tc ${filter === k ? 'on' : ''}" data-kind="${esc(k)}" style="--k:${HEX[x.color] || HEX.blue}"><div class="top">${x.hot !== null ? `<span class="due-t ${dueCls(x.hot)}" title="이 묶음에서 가장 급한 것">${dueTxt(x.hot)}</span>` : ''}</div><div class="v num">${x.n}</div><div class="l">${esc(k)}</div></div>`).join('')}</div>` : '') +
    `<div class="todo-bar"><div class="seg">${[''].concat(TODO_CATS).map(c => `<button class="${cat === c ? 'on' : ''}" data-cat="${c}">${c || '모두'}${c ? ` <b>${catN(c)}</b>` : ''}</button>`).join('')}</div>
      <label class="todo-today ${todayOnly ? 'on' : ''}">${tg(todayOnly, 'id="tdOnly"')}오늘 할 것만 <span class="small faint">기한 오늘·지남 · 새로 · 기한 넣기</span></label>
      <span class="small faint" style="margin-left:auto">${all.filter(i => !i.done).length}건 중 ${open.length}건 보는 중</span></div>
    <div class="g2"><div class="card" style="overflow:hidden">
      ${(() => { const ks = Object.entries(kinds).sort((p, q) => q[1].n - p[1].n), lim = HOMEF.kall || ks.length <= 7 ? ks.length : 6, vis = ks.slice(0, lim);
        if (filter && !vis.some(([k]) => k === filter)) vis.push(ks.find(([k]) => k === filter));
        return `<div class="filters"><span class="small faint" style="margin-right:2px">종류</span><button class="f ${!filter ? 'on' : ''}" data-kind="">전체<em>${open.length}</em></button>${vis.filter(Boolean).map(([k, x]) => `<button class="f ${filter === k ? 'on' : ''}" data-kind="${esc(k)}" style="--k:${HEX[x.color] || HEX.blue}">${esc(k)}<em>${x.n}</em></button>`).join('')}${ks.length > lim ? `<button class="f more" id="kMore">+ ${ks.length - lim}개 더</button>` : HOMEF.kall && ks.length > 7 ? '<button class="f more" id="kMore">접기</button>' : ''}</div>`; })()}
      ${shown.length ? Object.entries(groups).map(([g, items]) => `<div class="group-h">${g}</div>${items.map(row).join('')}`).join('') :
        (cat || todayOnly) && all.some(i => !i.done) ? empty(todayOnly ? '오늘 할 것이 없어요' : `「${esc(cat)}」에 확인할 것이 없어요`, '위에서 「모두」를 누르거나 「오늘 할 것만」을 끄면 다른 것도 보여요.') :
        empty(INFO.counts.cases ? '확인할 것이 없어요' : '아직 사건이 없어요', INFO.counts.cases ? '조회하면 보정명령·송달불능·선고·확정·기일이 여기에 모여요.' : '사건 대장에 엑셀로 사건을 넣고 조회해 보세요.',
          INFO.counts.cases ? '<button class="btn primary" data-go="pick">조회하기</button>' : '<button class="btn primary" data-go="import">엑셀로 사건 넣기</button>')}
    </div><div class="side-col">
      <div class="card next-run"><div class="ic">↻</div><div style="flex:1"><b>${d.next_run ? `다음 조회 권장 ${md(d.next_run)} (${wd(d.next_run)})` : '아직 조회한 적이 없어요'}</b><div class="small muted">${d.cycle}일마다 · 설정에서 바꿀 수 있어요</div></div></div>
      <div class="card"><div class="card-h"><h2>다가오는 기일</h2><button class="btn sm ghost" data-go="cal">달력 →</button></div>
        <div class="mini-list" style="margin-top:12px">${d.hearings.length ? d.hearings.map(h => `<div class="it pointer" ${h.aid ? `data-go="auction_case" data-arg='${JSON.stringify({aid: h.aid, tab: 't2'})}'` : `data-go="case" data-arg='${JSON.stringify({cid: h.cid})}'`}><div class="date"><b>${+h.date.slice(8)}</b><small>${+h.date.slice(5, 7)}월 ${wd(h.date)}</small></div><div style="flex:1"><b class="small">${esc(h.case_no)} · ${esc(h.party)}</b><div class="small muted">${esc(h.kind)} ${esc(h.time)} · ${esc(h.place)}</div></div>${h.aid ? chip('매각', 'orange') : chip(h.kind.includes('선고') ? '선고' : '기일', h.kind.includes('선고') ? 'green' : 'blue')}</div>`).join('') : '<div class="it small faint">예정된 기일이 없어요</div>'}</div></div>
    </div></div>`;
  $$('[data-kind]', v).forEach(el => el.onclick = () => go('home', {kind: el.dataset.kind === filter ? '' : el.dataset.kind}));
  if ($('#kMore')) $('#kMore').onclick = () => { HOMEF.kall = !HOMEF.kall; go('home', a, {back: true}); };
  $$('[data-cat]', v).forEach(el => el.onclick = () => go('home', {cat: el.dataset.cat, done: a.done}));
  $('#tdOnly').onclick = () => go('home', {today: !todayOnly, cat, done: a.done});
  $('#showDone').onclick = () => go('home', Object.assign({}, a, {done: !a.done}));
  $$('.todo', v).forEach(el => {
    const key = el.dataset.key;
    const item = d.items.find(i => i.key === key);
    $$('[data-act]', el).forEach(b => b.onclick = () => safe(async () => {
      const act = b.dataset.act;
      if (act === 'done') {
        if (item.done) { await api('todo_undo', {key}); return go('home', a); }
        let note = '';
        if (S.todo.memo_on_done) {
          note = await modal('처리함으로 표시', `<label class="lb">한 줄 메모 (사건 메모에도 남아요)</label><input class="field" id="m" placeholder="예: 주소보정서 제출함">`,
            [{text: '취소'}, {text: '처리함', cls: 'primary', value: bg => $('#m', bg).value.trim()}]);
          if (note === null) return;
        }
        await api('todo_done', {key, note});
        toast('처리함으로 표시했어요');
      } else if (act === 'undo') {
        await api('todo_undo', {key});
      } else if (act === 'due') {
        const date = await modal('기한 넣기', `<div class="small muted mb16">${esc(item.case_no)} · ${esc(item.kind)} · ${md(item.date)} ${esc(item.text)}</div><label class="lb">기한 날짜</label><input class="field" type="date" id="dt" value="${item.due || ''}">`,
          [{text: '취소'}, {text: '저장', cls: 'primary', value: bg => $('#dt', bg).value || false}]);
        if (!date) return;
        await api('deadline_set', {key, date});
        toast('기한을 넣었어요');
      }
      go('home', a);
    }));
  });
};

// 알림 띠: 다른 PC 사용 중 · 공용 폴더 · 새 판 · 오래된 내보내기 · 처음 쓰는 안내
function notices(d) {
  const out = [];
  if (INFO.other_user) out.push(`<div class="notice bad"><b>다른 PC(${esc(INFO.other_user.host)})가 이 자료 폴더를 쓰는 중이에요.</b> 두 곳에서 동시에 쓰면 자료가 깨질 수 있어요. 한 곳에서만 써 주세요.</div>`);
  else if (INFO.network_dir) out.push(`<div class="notice">자료 폴더가 <b>공용(네트워크) 폴더</b>예요. 여러 PC가 함께 쓰면 자료가 깨질 수 있어요 · 설정 → 저장·백업에서 이 PC 폴더로 옮길 수 있어요.</div>`);
  if (INFO.update) out.push(`<div class="notice info"><b>새 판 v${esc(INFO.update.version)}이 나왔어요.</b> <a data-open="${esc(INFO.update.path)}">파일 열기</a> → 실행하면 자료는 그대로 두고 바뀌어요.</div>`);
  if (d && d.old_exports) out.push(`<div class="notice">내보낸 엑셀 중 <b>90일이 넘은 파일이 ${d.old_exports}개</b> 있어요. 개인정보가 담긴 파일은 필요 없으면 지워 주세요. <a data-open="${esc(d.export_dir)}">폴더 열기</a></div>`);
  return out.join('');
}
document.addEventListener('click', e => { const o = e.target.closest('[data-open]'); if (o) api('open_path', {path: o.dataset.open}); });
function firstGuide() {
  if (S.guide_closed) return '';
  return `<div class="card guide mb16"><div class="card-h"><h2>처음 쓰시나요? 세 단계면 돼요</h2><button class="btn sm ghost" id="guideX">닫기</button></div><div class="card-b guide-steps">
    <div><b>1</b><span>왼쪽 위 <b>「채권 ▾」</b>에서 채권을 만들거나 골라요</span></div>
    <div><b>2</b><span>아래 <b>직접 입력</b>이나 <b>엑셀</b>로 사건을 넣고 「바로 조회」</span></div>
    <div><b>3</b><span>그림 속 숫자를 치면 결과가 쌓이고, 할 일은 <b>「확인할 것」</b>에 모여요</span></div></div></div>`;
}

// ================================================================== 조회할 사건 고르기
const CONDS = [
  {k: 'closed', t: () => '확정·종결된 사건 빼기', s: () => `상태가 ${esc(S.rules.filter(r => r.skip).map(r => r.status).join(' · ') || '없음')}인 사건 (설정 → 상태 분류 규칙에서 고쳐요)`},
  {k: 'recent', t: c => `최근 <input class="inp" data-n="recent_days" value="${c.recent_days}">일 안에 조회한 사건 빼기`, s: () => '같은 사건을 너무 자주 조회하지 않게'},
  {k: 'stale', t: c => `진행이 <input class="inp" data-n="stale_months" value="${c.stale_months}">개월 넘게 없는 사건은 <input class="inp" data-n="stale_every" value="${c.stale_every}">일에 한 번만`, s: () => '오래 멈춘 사건은 덜 자주 조회'},
  {k: 'hearing_first', t: c => `기일이 <input class="inp" data-n="hearing_days" value="${c.hearing_days}">일 안에 있는 사건 먼저`, s: () => '순서만 바꿔요'},
  {k: 'owner', t: c => `담당자가 <select class="inp" data-n="owner_value"><option value="">고르기</option>${INFO.owners.map(o => `<option ${o === c.owner_value ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>인 사건만`, s: () => '사건 대장의 담당 칸 기준'},
  {k: 'court', t: c => `법원 <select class="inp" data-n="court_value" style="max-width:220px"><option value="">고르기</option>${[...new Set(INFO.courts)].map(o => `<option ${o === c.court_value ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>만`, s: () => '특정 법원만 조회할 때'},
  {k: 'only_notfound', t: () => '지난번 「찾을 수 없음」 사건만', s: () => '이름 표기를 바꿔 다시 시도할 때'},
  {k: 'only_hearing', t: c => `기일이 ${c.hearing_days}일 안에 있는 사건만`, s: () => '기일 직전 확인용'},
];
SCREENS.pick = async (v, a) => {
  const running = INFO.running;
  const cond = Object.assign({}, S.conditions, a.cond || {});
  const preset = a.preset || S.presets[0]?.name || '정기 조회';
  v.innerHTML = head(`${esc(INFO.book)} · 조회하기`, '조회하기',
      `${running ? `<button class="btn primary" data-go="run">하던 조회 이어서 (${running.done}/${running.total})</button>` : ''}<button class="btn" id="resetAll">↺ 초기화</button>`) +
    notices(null) + (INFO.counts.cases ? '' : firstGuide()) + `<div class="pick-grid"><div class="side-col">${quickCard(a)}<div class="card main-card" id="bulk"></div></div>
     <div class="side-col"><div class="card"><div class="card-h"><h2>사건 대장에서 조건으로 조회</h2></div>
        <div class="small muted" style="padding:6px 22px 4px">「${esc(INFO.book)}」 사건 대장 ${INFO.counts.cases}건 중 켠 조건을 모두 적용</div>
        <div class="cond-mini">${CONDS.map(c => `<div class="cond">${tg(cond[c.k], `data-c="${c.k}"`)}<div class="m"><div class="t">${c.t(cond)}</div></div><div class="cnt" data-cnt="${c.k}"></div></div>`).join('')}</div>
        <div class="card-b" style="border-top:1px solid var(--line)"><div id="sum"></div>
          <div class="row-gap mt8"><input class="inp wide" id="runName" value="${esc(preset)}" title="이번 조회 이름" style="flex:1;width:auto"><button class="btn blue" id="startBtn">조회 시작 →</button></div>
          <div class="row-gap mt8"><select class="inp" id="presetSel" style="flex:1;width:auto">${S.presets.map((p, i) => `<option value="${i}" ${p.name === preset ? 'selected' : ''}>저장한 조건: ${esc(p.name)}</option>`).join('')}</select><button class="btn sm ghost" id="addPreset">+ 저장</button><button class="btn sm ghost" id="saveCond">기본으로</button></div>
        </div></div></div></div>`;
  const draw = async () => {
    const p = await api('pick_preview', {cond});
    $('#sum').innerHTML = `<div class="flow" style="display:flex;align-items:baseline;gap:8px"><span class="faint num" style="text-decoration:line-through">${p.total}</span><span class="faint">→</span><b class="num" style="font-size:30px;letter-spacing:-.03em">${p.count}</b><span class="muted">건 · 약 ${p.eta_min}분</span></div>`;
    CONDS.forEach(c => { const el = $(`[data-cnt="${c.k}"]`); if (el) { const n = p.removed[c.k]; el.textContent = !cond[c.k] ? '' : c.k === 'hearing_first' ? '순서' : n ? `−${n}` : '−0'; el.className = 'cnt ' + (cond[c.k] && n ? 'minus' : 'faint'); } });
    $('#startBtn').textContent = `${p.count}건 조회 →`;
    $('#startBtn').disabled = !p.count;
  };
  $$('.cond .tg', v).forEach(t => t.onclick = () => { t.classList.toggle('on'); cond[t.dataset.c] = t.classList.contains('on'); draw(); });
  $$('[data-n]', v).forEach(i => i.onchange = () => { cond[i.dataset.n] = i.tagName === 'SELECT' ? i.value : (+i.value || 0); draw(); });
  $('#presetSel').onchange = e => { const pr = S.presets[+e.target.value]; go('pick', Object.assign({}, a, {cond: Object.assign({}, S.conditions, pr.cond), preset: pr.name})); };
  $('#saveCond').onclick = () => safe(async () => { await setSetting('conditions', cond, '기본 조회 조건 바꿈'); toast('기본 조건으로 저장했어요'); });
  $('#addPreset').onclick = () => safe(async () => {
    const name = await modal('조건 저장', '<label class="lb">이름</label><input class="field" id="pn" placeholder="예: 내 담당 정기 조회">', [{text: '취소'}, {text: '저장', cls: 'primary', value: bg => $('#pn', bg).value.trim() || false}]);
    if (!name) return;
    const diff = {};
    Object.keys(cond).forEach(k => { if (cond[k] !== S.conditions[k]) diff[k] = cond[k]; });
    await setSetting('presets', S.presets.filter(p => p.name !== name).concat([{name, cond: diff}]), `조건 「${name}」 저장`);
    go('pick', Object.assign({}, a, {cond, preset: name}));
  });
  $('#startBtn').onclick = () => safe(async () => go('run', {state: await api('run_start', {name: $('#runName').value.trim() || preset, cond})}));
  $('#resetAll').onclick = () => safe(async () => {
    if (INFO.running && !await confirmBox('초기화', '하던 조회를 멈추고 입력한 내용을 모두 비워요.<br>멈춘 조회는 「조회 기록」에서 이어서 할 수 있어요.', '초기화')) return;
    if (INFO.running) await api('run_stop');
    await refreshPills();
    go('pick', {});
    toast('초기화했어요');
  });
  if ($('#guideX')) $('#guideX').onclick = () => safe(async () => { await setSetting('guide_closed', true); $('.guide').remove(); });
  bindQuick(v, a);
  drawBulk(a);
  await draw();
};

// ------------------------------------------------------------------ 직접 입력해서 조회 (수기 검색)
function quickCard(a) {
  const multi = !!a.multi;
  return `<div class="card main-card" id="quick"><div class="card-h"><div class="mc-h"><span class="mc-ic">✎</span><div><h2>직접 입력해서 조회</h2><div class="small muted">사건 대장에 없어도 바로 조회해요</div></div></div><a class="small" id="qMode">${multi ? '한 건씩 넣기' : '여러 건 붙여넣기'}</a></div><div class="card-b">
    ${multi ? `<textarea class="field" id="qText" rows="5" placeholder="한 줄에 한 건 — 엑셀에서 그대로 복사해 붙여넣어도 돼요&#10;서울중앙지방법원	2025가소123456	홍길동&#10;수원지법 성남지원, 2024차전8812, 주식회사 대한상사">${esc(a.qtext || '')}</textarea><div class="small muted mt8" id="qInfo">법원 · 사건번호 · 당사자 이름 (· 메모) 순서</div>`
      : `<div class="q-row"><input class="field" id="qCourt" list="qCourts" placeholder="법원 (예: 서울중앙)"><datalist id="qCourts">${[...new Set(INFO.courts)].map(n => `<option value="${esc(n)}">`).join('')}</datalist>
        <input class="field" id="qNo" placeholder="사건번호 (2025가소123456)"><input class="field" id="qParty" placeholder="당사자 이름"></div><div class="small err mt8" id="qInfo"></div>`}
    <div class="row-gap" style="margin-top:12px"><label class="small muted" style="display:flex;align-items:center;gap:6px;flex:1"><input type="checkbox" class="cbx" id="qKeep" checked> 사건 대장에 남기기 <span class="faint">(끄면 조회 후 보관함으로)</span></label>
    <button class="btn ghost sm" id="qClear">비우기</button><button class="btn blue big-btn" id="qGo">바로 조회 →</button></div></div></div>`;
}
function bindQuick(v, a) {
  const multi = !!$('#qText', v);
  $('#qMode', v).onclick = () => go('pick', Object.assign({}, a, {multi: !multi, qtext: ''}));
  const text = () => multi ? $('#qText', v).value : [$('#qCourt', v).value, $('#qNo', v).value, $('#qParty', v).value].map(x => x.trim()).join('\t');
  $('#qClear', v).onclick = () => { $$('#quick input.field, #quick textarea', v).forEach(i => i.value = ''); $('#qInfo', v).textContent = ''; };
  if (multi) {
    const t = $('#qText', v);
    t.oninput = () => { clearTimeout(t._t); t._t = setTimeout(async () => {
      if (!t.value.trim()) { $('#qInfo', v).textContent = '법원 · 사건번호 · 당사자 이름 (· 메모) 순서'; return; }
      const r = await safe(() => api('quick_check', {text: t.value}));
      if (r) $('#qInfo', v).innerHTML = `<span class="ok-t">조회할 사건 ${r.good.length}건</span>${r.bad.length ? ` · <span class="err">못 읽은 줄 ${r.bad.length}: ${r.bad.slice(0, 2).map(b => `${b.line}줄 ${esc(b.problem)}`).join(', ')}</span>` : ''}`;
    }, 300); };
  } else {
    $$('#qCourt,#qNo,#qParty', v).forEach(i => i.onkeydown = e => { if (e.key === 'Enter') $('#qGo', v).click(); });
    setTimeout(() => { const c = $('#qCourt', v); if (c && !a.xl) c.focus(); }, 30);
  }
  $('#qGo', v).onclick = () => safe(async () => {
    try {
      const st = await api('quick_search', {text: text(), keep: $('#qKeep', v).checked});
      if (st.skipped && st.skipped.length) toast(`못 읽은 줄 ${st.skipped.length}개는 빼고 조회해요`);
      go('run', {state: st});
    } catch (e) {
      if (!multi) $('#qInfo', v).textContent = e.message; else throw e;
    }
  });
}

// ------------------------------------------------------------------ 엑셀 넣어서 대량 조회
async function chooseExcel() {
  if (MODE === 'browser') {
    return modal('파일 위치', '<label class="lb">엑셀 파일의 전체 경로</label><input class="field" id="fp" placeholder="C:\\Users\\...\\사건목록.xlsx">', [{text: '취소'}, {text: '열기', cls: 'primary', value: bg => $('#fp', bg).value.trim() || false}]);
  }
  return api('choose_file');
}
async function drawBulk(a) {
  const el = $('#bulk');
  const title = `<div class="card-h"><div class="mc-h"><span class="mc-ic">▦</span><div><h2>엑셀 넣어서 대량 조회</h2><div class="small muted">법원 · 사건번호 · 당사자 칸을 자동으로 찾아요</div></div></div>${a.xl ? '<a class="small" id="xOther">다른 파일</a>' : '<a class="small" id="xTpl">양식 받기</a>'}</div>`;
  if (!a.xl) {
    el.innerHTML = title + `<div class="card-b"><div class="xdrop" id="xDrop"><b>엑셀 파일을 이 창에 끌어다 놓으세요</b><div class="muted mt8">또는 여기를 눌러서 고르기 · .xlsx .xls .csv</div><div class="small faint mt8">칸 이름이 달라도, 머리글이 없어도 값을 보고 찾아요. 틀리면 직접 고를 수 있어요.</div></div></div>`;
    $('#xDrop').onclick = () => safe(async () => { const p = await chooseExcel(); if (p) go('pick', Object.assign({}, a, {xl: p, xmap: null})); });
    $('#xTpl').onclick = () => safe(async () => { const p = await api('template_save'); toast('양식을 저장했어요: ' + p.split(/[\\/]/).pop()); });
    return;
  }
  el.innerHTML = title + '<div class="card-b small faint">파일을 읽는 중…</div>';
  let p;
  try { p = await api('import_preview', {path: a.xl, mapping: a.xmap}); } catch (e) { el.innerHTML = title + `<div class="card-b err">${esc(e.message)}</div>`; $('#xOther').onclick = () => go('pick', Object.assign({}, a, {xl: null})); return; }
  const opt = (k) => `<option value="-1">(안 씀)</option>` + p.header.map((h, j) => `<option value="${j}" ${p.mapping[k] === j ? 'selected' : ''}>${p.letters[j]} · ${esc(h || '(제목 없음)')}${p.peek[j]?.length ? ' — ' + esc(p.peek[j].join(', ')).slice(0, 60) : ''}</option>`).join('');
  const field = (k, name, req) => `<div class="xmap ${req && !(k in p.mapping) ? 'miss' : ''}"><div class="k">${name}${req ? ' <b class="err">*</b>' : ''}${p.auto.includes(k) ? ' <span class="chip info" style="font-size:12px">값을 보고 찾음</span>' : k in p.mapping ? ' <span class="chip ok" style="font-size:12px">칸 이름으로 찾음</span>' : req ? ' <span class="chip bad" style="font-size:12px">골라 주세요</span>' : ''}</div><select class="field" data-xm="${k}">${opt(k)}</select></div>`;
  el.innerHTML = title + `<div class="card-b">
    <div class="file"><div class="ic">XLS</div><div style="flex:1"><b>${esc(p.name)}</b><div class="small muted">${esc(p.sheet)} · ${p.rows}줄</div></div>${chip('조회할 사건 ' + p.good_count, p.good_count ? 'green' : 'red')}${p.skips.length ? ' ' + chip('못 읽은 줄 ' + p.skips.length, 'red') : ''}</div>
    <div class="xmaps">${field('court', '법원', 1)}${field('case', '사건번호', 1)}${field('party', '당사자 이름', 1)}${field('owner', '담당')}${field('memo1', '메모 1 (계좌번호 등)')}</div>
    ${p.rowsview.length ? `<div class="sub-h">이렇게 읽었어요 (처음 ${p.rowsview.length}줄)</div><table class="list-tbl"><tr><th>법원</th><th>사건번호</th><th>당사자</th><th>메모</th></tr>${p.rowsview.map(r => `<tr><td>${esc(r.court)}</td><td><b>${esc(r.case_no)}</b></td><td>${esc(r.party)}</td><td class="muted">${esc(r.memo1)}</td></tr>`).join('')}</table>` : ''}
    ${p.skips.length ? `<details class="mt8"><summary class="small err pointer">못 읽은 줄 ${p.skips.length}개 보기 (조회에서 빠져요)</summary><table class="list-tbl mt8">${p.skips.slice(0, 50).map(r => `<tr><td class="muted">${r.line}줄</td><td>${esc(r.court_raw)} ${esc(r.case_raw)} ${esc(r.party)}</td><td class="err">${esc(r.problem)}</td></tr>`).join('')}</table></details>` : ''}
    <div class="row-gap" style="margin-top:14px"><label class="small muted" style="display:flex;align-items:center;gap:6px;flex:1"><input type="checkbox" class="cbx" id="xKeep" checked> 사건 대장에 남기기 <span class="faint">(끄면 조회 후 보관함으로)</span></label>
      <button class="btn blue big-btn" id="xGo" ${p.good_count ? '' : 'disabled'}>${p.good_count}건 바로 조회 →</button></div></div>`;
  const curMap = () => { const m = {}; $$('[data-xm]', el).forEach(x => { if (+x.value >= 0) m[x.dataset.xm] = +x.value; }); return m; };
  $$('[data-xm]', el).forEach(s => s.onchange = () => go('pick', Object.assign({}, a, {xmap: curMap()})));
  $('#xOther').onclick = () => safe(async () => { const np = await chooseExcel(); if (np) go('pick', Object.assign({}, a, {xl: np, xmap: null})); });
  $('#xGo').onclick = () => safe(async () => {
    const st = await api('bulk_search', {path: a.xl, mapping: curMap(), keep: $('#xKeep').checked});
    toast(`대장에 새로 ${st.imported.added}건 · 이미 있던 ${st.imported.updated}건 — 조회를 시작해요`);
    go('run', {state: st});
  });
}

function presetText(p) {
  const c = Object.assign({}, S.conditions, p.cond);
  const on = [];
  if (c.only_notfound) on.push('찾을 수 없음만');
  if (c.only_hearing) on.push('기일 임박만');
  if (c.owner && c.owner_value) on.push(`담당 ${c.owner_value}`);
  if (c.court && c.court_value) on.push(c.court_value);
  if (c.closed) on.push('확정·종결 빼기');
  if (c.recent) on.push(`최근 ${c.recent_days}일 빼기`);
  return on.join(' · ') || '조건 없이 전부';
}

// ================================================================== 조회 중 (결과까지 한 화면)
let RUN = null, RUN_BUSY = false, CARD_CID = null;
const RUN_SEL = new Set();  // 「이번 조회 결과」에서 고른 사건
const FOLD = (() => { try { return JSON.parse(localStorage.getItem('run-fold') || '{}'); } catch (e) { return {}; } })();
function applyFold() {
  try { localStorage.setItem('run-fold', JSON.stringify(FOLD)); } catch (e) { /* 저장 못 해도 화면은 그대로 */ }
  const side = $('#runSide');
  if (!side) return;
  side.classList.toggle('folded', !!FOLD.side);
  side.closest('.run2').classList.toggle('side-folded', !!FOLD.side);
  $('#foldSide').innerHTML = FOLD.side ? `‹ 목록 펼치기 <b>${RUN ? (RUN.done_list || []).length : ''}</b>` : '오른쪽 목록 접기 ›';
  $('#foldSide').title = FOLD.side ? '오른쪽 목록 펼치기' : '오른쪽 목록 접기 (결과를 넓게)';
  $$('.fold-card', side).forEach(c => c.classList.toggle('closed', !!FOLD[c.dataset.fold]));
}
async function runRemove(args, msg) {
  const r = await api('run_remove', args);
  RUN_SEL.clear();
  if (args.scope || (args.cids || []).includes(CARD_CID)) CARD_CID = null;
  if (!r.active) { await refreshPills(); toast(msg + ' · 목록이 비었어요'); go('pick', {}); return; }
  toast(msg);
  drawRun(r);
}
function runKeys(e) {
  if (CUR !== 'run' || document.querySelector('.modal-bg')) return;
  if (e.key === 'F5') { e.preventDefault(); runAct('run_new_captcha'); }
  else if (e.key === 'F6') { e.preventDefault(); playAudio(); }
  else if (e.key === 'Escape') { e.preventDefault(); runAct('run_skip'); }
  else if (/^[0-9A-Za-z]$/.test(e.key) && $('#capin') && document.activeElement !== $('#capin') && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
    $('#capin').focus();  // 다른 곳을 눌렀다가 숫자를 쳐도 입력칸으로
  }
}
async function playAudio() {
  const a = await safe(() => api('run_audio'));
  if (a) new Audio('data:audio/wav;base64,' + a).play().catch(() => toast('소리를 재생하지 못했어요', true));
  else toast('이 그림은 소리 듣기를 쓸 수 없어요');
}
async function runAct(name, args) {
  if (RUN_BUSY) return;
  RUN_BUSY = true;
  const f = $('#focus');
  if (f) f.classList.add('loading');
  try { drawRun(await api(name, args)); } catch (e) { toast(e.message, true); if (f) f.classList.remove('loading'); }
  RUN_BUSY = false;
}
SCREENS.run = async (v, a) => {
  document.addEventListener('keydown', runKeys);
  const st = a.state || (INFO.running ? await api('run_state', {fetch: false}) : null);
  if (!st || !st.active) { v.innerHTML = head('조회하기', '조회 중') + `<div class="card">${empty('지금 하는 조회가 없어요', '조회할 사건을 먼저 넣어 주세요.', '<button class="btn primary" data-go="pick">조회하기</button>')}</div>`; return; }
  CARD_CID = null;
  v.innerHTML = head(`${esc(INFO.book)} · <a data-go="pick">조회하기</a> · ${esc(st.name)}`, '조회 중',
      `<button class="btn" id="saveRun">엑셀로 저장</button><button class="btn" data-go="home">확인할 것 <span class="pill red" id="todoN" style="margin-left:4px"></span></button><button class="btn" id="stopRun">⏸ 멈추기</button><button class="btn" id="resetRun">↺ 초기화</button>`) +
    `<div class="run2"><div class="side-col"><div class="card focus2" id="focus"></div><div class="card" id="rcard"></div></div>
     <div class="side-col run-side" id="runSide"><button class="fold-btn" id="foldSide"></button><div class="card" id="runStat"></div>
       <div class="card fold-card" data-fold="done"><div class="card-h"><h2 class="fold-h">이번 조회 결과 <span class="small muted" id="doneN"></span></h2><div class="row-gap" id="dlAct"></div></div><div class="done-list" id="doneList"></div></div>
       <div class="card fold-card" data-fold="queue"><div class="card-h"><h2 class="fold-h">다음 차례 <span class="small muted" id="leftN"></span></h2></div><div class="queue" id="queue"></div></div></div></div>`;
  $('#foldSide').onclick = () => { FOLD.side = !FOLD.side; applyFold(); };
  $$('.fold-card .fold-h', v).forEach(h => h.onclick = () => { const k = h.closest('.fold-card').dataset.fold; FOLD[k] = !FOLD[k]; applyFold(); });
  RUN_SEL.clear();
  $('#saveRun').onclick = () => safe(async () => { const p = await api('export_run', {rid: RUN.rid}); toast('저장했어요: ' + p.split(/[\\/]/).pop()); });
  $('#stopRun').onclick = () => safe(async () => { await api('run_stop'); toast('멈췄어요. 조회 기록에서 이어서 할 수 있어요'); go('hist'); });
  $('#resetRun').onclick = () => safe(async () => {  // 묻지 않고 바로 (결과는 남고, 남은 사건은 조회 기록에서 이어서)
    await api('run_stop'); await refreshPills();
    toast('초기화했어요 · 조회한 결과는 「조회 기록 · 결과」에 남아 있어요');
    go('pick', {});
  });
  drawRun(st);
};
const lastProg = (lp, hot) => lp && lp.date ? `<span class="lp ${hot ? 'hot' : ''}">${md(lp.date)} ${esc(lp.text)}</span>` : '<span class="faint">—</span>';
function drawCard(card) {
  const el = $('#rcard');
  if (!el) return;
  if (!card) { el.innerHTML = `<div class="empty" style="padding:40px"><b>여기에 조회 결과가 바로 나와요</b>숫자를 치면 일반내용·진행내용을 가져와 보여줘요.</div>`; return; }
  CARD_CID = card.cid;
  el.innerHTML = `<div class="card-h"><div><div class="small muted">${esc(card.court)} · ${esc(card.party)}${card.memo1 ? ' · ' + esc(card.memo1) : ''}</div>
      <div class="row-gap" style="margin-top:4px"><b style="font-size:22px" class="num">${esc(card.case_no)}</b>${card.status ? chip(card.status, card.color) : ''}${card.new ? `<span class="newdot">새 진행 ${card.new}</span>` : ''}</div></div>
      <div class="row-gap"><button class="btn sm" data-go="case" data-arg='${JSON.stringify({cid: card.cid})}'>사건 상세</button>${card.cfm ? '<button class="btn sm" id="cSihyo">시효 앱으로</button>' : ''}</div></div>
    <div class="card-b">${card.rehab && typeof mgBanner === 'function' ? `<div style="margin-bottom:12px">${mgBanner(card.rehab, true)}</div>` : ''}<div class="lastbig ${card.new ? 'new' : ''}"><span class="small muted">마지막 진행${card.new ? ' · 이번에 새로 생김' : ''}</span><div>${card.last_prog.date ? `<b>${fullDate(card.last_prog.date)}</b> ${esc(card.last_prog.text)}` : '진행내용 없음'}</div></div>
      <div class="g2e" style="grid-template-columns:1.2fr 1fr;gap:20px">
        <div><div class="sec-h"><b>진행내용</b><span>최근 ${card.prog.length} / 전체 ${card.prog_total}건</span></div><div class="timeline">${card.prog.map(x => `<div class="ev ${x.new ? 'new' : ''}"><div class="d">${fullDate(x.date)}${x.new ? ' · <b style="color:var(--warn)">새로</b>' : ''}</div><div class="x">${esc(x.text)}</div></div>`).join('') || '<div class="small faint">없음</div>'}</div></div>
        <div><div class="sec-h"><b>일반내용</b></div><div class="gen-grid one">${card.basic.map(b => `<div><span>${esc(b.label)}</span>${esc(b.value)}</div>`).join('')}${card.next_hearing ? `<div><span>다음 기일</span><b>${esc(card.next_hearing)}</b></div>` : ''}</div></div>
      </div></div>`;
  if ($('#cSihyo')) $('#cSihyo').onclick = () => safe(async () => { const r = await api('sihyo_send', {ids: [card.cid]}); toast(`시효 앱 폴더에 보냈어요 (${r.count}건)`); });
}
function drawRun(st) {
  RUN = st;
  const f = $('#focus');
  if (!f) return;
  f.classList.remove('loading');
  const s = st.stat;
  const pct = s.total ? (s.total - s.left) / s.total : 0;
  $('#runStat').innerHTML = `<div class="ring" style="padding:16px 20px"><svg viewBox="0 0 36 36" style="width:64px;height:64px"><circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--gray-soft)" stroke-width="3.2"/><circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--accent)" stroke-width="3.2" stroke-linecap="round" stroke-dasharray="97.4" stroke-dashoffset="${(97.4 * (1 - pct)).toFixed(1)}"/></svg>
    <div><div class="t num">${s.total - s.left} <span class="small muted" style="font-weight:500">/ ${s.total}</span></div><div class="small muted">${s.left ? `남은 시간 약 ${Math.max(1, Math.round(s.eta_min))}분` : '끝났어요'}</div></div></div>
    <div class="mini"><div><span class="small muted">완료</span><b class="num">${s.done}</b></div><div><span class="small muted">찾을 수 없음</span><b class="num" style="color:var(--bad)">${s.notfound}</b></div>
    <div><span class="small muted">새 진행 생김</span><b class="num" style="color:var(--warn)">${(st.done_list || []).filter(d => d.new).length}건</b></div><div><span class="small muted">한 건 평균</span><b class="num">${s.avg ? s.avg + '초' : '—'}</b></div></div>`;
  $('#leftN').textContent = `${s.left}건 남음`;
  $('#queue').innerHTML = st.queue.filter(q => q.state === 'wait').slice(0, 4).map(q => `<div class="q ${q.cur ? 'cur' : ''}"><div class="n">${q.no}</div><div class="m"><div>${esc(q.case_no)}</div><small>${esc(q.court.replace('지방법원', ''))} · ${esc(q.party)}</small></div>${q.cur ? chip('지금', 'blue') : chip('대기', 'gray')}<button class="rm" data-rm="${q.cid}" title="이번 조회에서 빼기">✕</button></div>`).join('') || '<div class="small faint" style="padding:8px 12px">남은 사건이 없어요</div>';
  const dl = st.done_list || [];
  [...RUN_SEL].forEach(c => { if (!dl.some(d => d.cid === c)) RUN_SEL.delete(c); });
  $('#doneN').textContent = `${dl.length}건`;
  $('#dlAct').innerHTML = !dl.length ? '' : RUN_SEL.size
    ? `<button class="btn sm primary" id="dlDel">선택 삭제 ${RUN_SEL.size}</button><button class="btn sm ghost" id="dlNone">해제</button>`
    : `<button class="btn sm ghost" id="dlAll">전체 선택</button><button class="btn sm" id="dlClear">비우기</button>`;
  $('#doneList').innerHTML = dl.length ? dl.map(d => `<div class="dl ${d.cid === CARD_CID ? 'on' : ''} ${RUN_SEL.has(d.cid) ? 'picked' : ''}" data-cid="${d.cid}" data-state="${d.state}"><input type="checkbox" class="cbx ck" data-ck="${d.cid}" ${RUN_SEL.has(d.cid) ? 'checked' : ''} title="골라서 삭제"><div class="m"><div><b class="num">${esc(d.case_no)}</b> <span class="small muted">${esc(d.party)}</span></div>
      <div class="small">${d.state === 'done' ? lastProg(d.last_prog, d.new) : `<span class="err">${d.state === 'notfound' ? '찾을 수 없음' : '건너뜀'}</span>`}</div></div>
      <div style="text-align:right">${d.state === 'done' ? (d.status ? chip(d.status, d.color) : '') : chip(d.state === 'notfound' ? '없음' : '건너뜀', d.state === 'notfound' ? 'red' : 'gray')}${d.new ? `<div><span class="newdot">새 ${d.new}</span></div>` : ''}</div></div>`).join('')
    : '<div class="small faint" style="padding:14px 22px">아직 없어요</div>';
  $$('#doneList [data-ck]').forEach(c => c.onclick = e => { e.stopPropagation(); c.checked ? RUN_SEL.add(c.dataset.ck) : RUN_SEL.delete(c.dataset.ck); drawRun(RUN); });
  const act = (id, fn) => { const b = $('#' + id); if (b) b.onclick = fn; };
  act('dlAll', () => { dl.forEach(d => RUN_SEL.add(d.cid)); drawRun(RUN); });
  act('dlNone', () => { RUN_SEL.clear(); drawRun(RUN); });
  act('dlDel', () => safe(() => runRemove({cids: [...RUN_SEL]}, `${RUN_SEL.size}건을 이번 조회 목록에서 뺐어요`)));
  act('dlClear', () => safe(() => runRemove({scope: 'done'}, `조회한 ${dl.length}건을 목록에서 비웠어요`)));
  $$('#queue [data-rm]').forEach(b => b.onclick = () => safe(() => runRemove({cids: [b.dataset.rm]}, '이번 조회에서 뺐어요')));
  applyFold();
  $$('#doneList .dl[data-state="done"]').forEach(x => x.onclick = () => safe(async () => {
    drawCard(await api('result_card', {cid: x.dataset.cid}));
    $$('#doneList .dl').forEach(y => y.classList.toggle('on', y === x));
    if ($('#capin')) $('#capin').focus();
  }));
  if (st.last && st.last.card) drawCard(st.last.card);
  else if (!CARD_CID) {
    const first = dl.find(d => d.state === 'done');
    if (first) api('result_card', {cid: first.cid}).then(c => { drawCard(c); const x = $(`#doneList .dl[data-cid="${first.cid}"]`); if (x) x.classList.add('on'); }).catch(() => drawCard(null));
    else drawCard(null);
  }
  api('info', {}).then(i => { const n = $('#todoN'); if (n) { n.textContent = i.counts.todo || ''; n.hidden = !i.counts.todo; } }).catch(() => {});
  const last = st.last;
  const lastHtml = last && last.kind !== 'ok' ? `<div class="toast"><span style="color:var(--bad)">✕</span><div><b>${esc(last.case_no || '')}</b> ${esc(last.text)}</div></div>` : '';
  if (st.finished) {
    f.innerHTML = `<div class="finish" style="padding:26px 30px"><div class="case-top">${esc(st.name)}</div><div class="big num" style="font-size:34px">${s.total}건 조회 끝</div>
      <div class="muted">완료 ${s.done} · 찾을 수 없음 ${s.notfound} · 건너뜀 ${s.error} · 새 진행이 생긴 사건 ${dl.filter(d => d.new).length}건</div>
      <div class="row-gap" style="justify-content:center;margin-top:16px"><button class="btn primary" id="xl2">엑셀로 저장</button><button class="btn" data-go="home">확인할 것</button><button class="btn" data-go="result" data-arg='${JSON.stringify({rid: st.rid, f: 'all'})}'>결과 표로 보기</button><button class="btn blue" id="again">↺ 새로 조회</button></div>${lastHtml}</div>`;
    $('#xl2').onclick = () => safe(async () => { const p = await api('export_run', {rid: st.rid}); toast('저장했어요: ' + p.split(/[\\/]/).pop()); });
    $('#again').onclick = () => safe(async () => { await api('run_stop'); await refreshPills(); go('pick', {}); });
    refreshPills();
    return;
  }
  const c = st.case;
  const zoom = S.run.zoom || 1.5;
  const digits = S.run.digits || S.run.learned_digits || 6;
  const msg = st.message ? (st.message.kind === 'captcha' || st.message.kind === 'retry'
    ? `<div class="cap-msg warn">${esc(st.message.text)}</div>`
    : `<div class="paused">${esc(st.message.text)} <button class="btn sm" id="retry">다시 시도</button></div>`) : '';
  const errHtml = st.error ? `<div class="paused">${esc(st.error.text)} <button class="btn sm" id="retry">다시 시도</button></div>` : '';
  f.innerHTML = `<div class="cap-row">
      <div class="cap-info"><div class="case-top">${chip('지금', 'blue')}${c.no} / ${s.total}</div><div class="case-no num">${esc(c.case_no)}</div>
        <div class="muted small">${esc(c.court)} · ${esc(c.party)}${c.party !== c.orig_party ? ` <span class="faint">(원래 ${esc(c.orig_party)})</span>` : ''}</div></div>
      <div class="cap-box" style="width:${120 * zoom + 24}px;height:${40 * zoom + 24}px;margin:0">${st.captcha ? `<img src="data:${st.captcha.mime || 'image/png'};base64,${st.captcha.image}" style="width:${120 * zoom}px;height:${40 * zoom}px" alt="자동입력방지 그림">` : '<span class="faint small">그림 없음</span>'}</div>
      <div class="cap-in"><div class="otp sm" id="otp"></div><input class="capin" id="capin" autocomplete="off" inputmode="numeric" maxlength="12"></div>
    </div>
    <div class="cap-foot"><div class="hint">숫자 ${digits}개를 치면 <b>Enter 없이 바로</b> 조회돼요 · 개수가 다르면 Enter (그 개수를 기억해요)</div>
      <div class="cap-tools" style="margin:0"><button class="btn sm" id="newCap">↻ 새 그림 <span class="kbd">F5</span></button><button class="btn sm" id="audio">🔊 소리 <span class="kbd">F6</span></button><button class="btn sm ghost" id="skip">건너뛰기 <span class="kbd">Esc</span></button></div></div>${errHtml || msg}${lastHtml}`;
  const inp = $('#capin');
  const drawOtp = state => {
    const val = inp.value;
    const n = Math.max(digits, val.length);
    $('#otp').className = 'otp sm' + (state ? ' ' + state : '');
    $('#otp').innerHTML = Array.from({length: n}, (_, i) => `<div class="${i < val.length ? 'fill' : ''} ${i === val.length && !state ? 'cur' : ''}">${esc(val[i] || '')}</div>`).join('');
  };
  const submit = async () => {
    const val = inp.value.trim();
    if (!val) return;
    if (!S.run.digits && val.length !== digits) {
      S.run.learned_digits = val.length;
      api('setting_set', {path: 'run.learned_digits', value: val.length, note: ''});
    }
    drawOtp('ok');
    await runAct('run_submit', {answer: val, cid: RUN && RUN.case ? RUN.case.cid : null});
  };
  inp.oninput = () => {
    inp.value = inp.value.replace(/[^0-9A-Za-z]/g, '');
    drawOtp();
    if (S.run.auto_submit !== false && inp.value.length >= digits) submit();
  };
  inp.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); submit(); } };
  $('#otp').onclick = () => inp.focus();
  const bad = st.message && st.message.kind === 'captcha';
  drawOtp(bad ? 'bad' : '');
  if (bad) setTimeout(() => drawOtp(), 400);
  inp.focus();
  $('#newCap').onclick = () => runAct('run_new_captcha');
  $('#audio').onclick = playAudio;
  $('#skip').onclick = () => runAct('run_skip');
  if ($('#retry')) $('#retry').onclick = () => runAct('run_new_captcha');
}

// ================================================================== 기일·기한
SCREENS.cal = async (v, a) => {
  const now = new Date(INFO.today + 'T00:00');
  const y = a.y || now.getFullYear(), m = a.m || now.getMonth() + 1;
  const [ev, dl] = await Promise.all([api('calendar', {year: y, month: m}), api('lg_dlv', {tab: 'todo'})]);
  const dues = dl.items.filter(x => x.due).slice(0, 10);
  const sel = a.sel || (y === now.getFullYear() && m === now.getMonth() + 1 ? INFO.today : `${y}-${String(m).padStart(2, '0')}-01`);
  const byDay = {};
  ev.forEach(e => (byDay[e.date] = byDay[e.date] || []).push(e));
  const first = new Date(y, m - 1, 1), days = new Date(y, m, 0).getDate();
  const cls = t => t === '기일' ? 'k' : t === '기한' ? 'b' : t === '매각' ? 'w' : 's';
  let grid = WEEK.map(d => `<div class="wd">${d}</div>`).join('');
  const lead = first.getDay();
  const cells = Math.ceil((lead + days) / 7) * 7;
  for (let i = 0; i < cells; i++) {
    const dn = i - lead + 1;
    if (dn < 1 || dn > days) { grid += '<div class="d out"></div>'; continue; }
    const ds = `${y}-${String(m).padStart(2, '0')}-${String(dn).padStart(2, '0')}`;
    const list = byDay[ds] || [];
    grid += `<div class="d ${i % 7 === 0 ? 'sun' : ''} ${ds === INFO.today ? 'today' : ''} ${ds === sel ? 'sel' : ''}" data-d="${ds}"><span class="n">${dn}</span>${list.slice(0, 3).map(e => `<span class="ev-p ${cls(e.type)}">${esc(e.party || e.case_no)} ${esc(e.text)}</span>`).join('')}${list.length > 3 ? `<span class="more">+${list.length - 3}</span>` : ''}</div>`;
  }
  const pm = m === 1 ? {y: y - 1, m: 12} : {y, m: m - 1}, nm = m === 12 ? {y: y + 1, m: 1} : {y, m: m + 1};
  const dayList = byDay[sel] || [];
  v.innerHTML = head('진행내용·일반내용에서 자동으로 + 직접 넣은 기한', '기일·기한',
      `<button class="btn sm" data-go="cal" data-arg='${JSON.stringify(pm)}'>‹</button><b style="font-size:16px">${y}년 ${m}월</b><button class="btn sm" data-go="cal" data-arg='${JSON.stringify(nm)}'>›</button><button class="btn sm" data-go="cal">오늘</button><button class="btn primary" id="addDue">+ 기한 직접 넣기</button>`) +
    `<div class="g2"><div class="card" style="padding:16px 0 0;overflow:hidden"><div class="cal">${grid}</div></div>
    <div class="side-col"><div class="card"><div class="card-b legend" style="flex-wrap:wrap;padding:16px 22px"><span><i style="background:var(--accent)"></i>변론·심문 기일</span><span><i style="background:var(--ok)"></i>선고·확정 예상</span><span><i style="background:var(--bad)"></i>기한 · 보정</span><span><i style="background:var(--warn)"></i>경매 매각</span></div></div>
      <div class="card"><div class="card-h"><h2>${+sel.slice(5, 7)}월 ${+sel.slice(8)}일 (${wd(sel)})</h2><span class="small muted">${dayList.length}건</span></div>
        <div class="mini-list" style="margin-top:12px">${dayList.length ? dayList.map(e => e.dlv ? `<div class="it"><div style="flex:1" class="pointer" data-go="lg_dlv" data-arg='${JSON.stringify({key: e.key})}'><b class="small">${esc(e.case_no)} · ${esc(e.party)}</b><div class="small muted">${esc(e.text)}</div></div>${dday(e.left)}
            <button class="btn sm" data-dfin="${esc(e.key)}">완료</button><button class="btn sm ghost" data-ddel="${esc(e.key)}" title="보정 관리에서 지우기">지우기</button></div>`
          : `<div class="it ${e.cid || e.aid ? 'pointer' : ''}" ${e.aid ? `data-go="auction_case" data-arg='${JSON.stringify({aid: e.aid})}'` : e.cid ? `data-go="case" data-arg='${JSON.stringify({cid: e.cid})}'` : ''}><div style="flex:1"><b class="small">${esc(e.case_no)} · ${esc(e.party)}</b><div class="small muted">${esc(e.text)}</div></div>${chip(e.type, e.type === '기일' ? 'blue' : e.type === '기한' ? 'red' : e.type === '매각' ? 'orange' : 'green')}</div>`).join('') : '<div class="it small faint">이 날은 일정이 없어요</div>'}</div></div>
      <div class="card"><div class="card-h"><h2>보정 기한 ${dl.items.filter(x => x.due).length}건</h2><button class="btn sm" data-go="lg_dlv">보정 관리 ›</button></div>
        <div class="cal-dl" style="margin-top:10px">${dues.length ? dues.map(x => `<div class="it"><div style="flex:1;min-width:0" class="pointer" data-go="cal" data-arg='${JSON.stringify({y: +x.due.due.slice(0, 4), m: +x.due.due.slice(5, 7), sel: x.due.due})}'><b>${esc(x.debtor ? x.debtor.name : x.party || '—')}</b> <span class="small faint">${esc(x.case_no)}</span><div class="small muted">${md(x.due.due)}(${wd(x.due.due)}) · ${esc(x.act || '조치 정하기')}</div></div>${dday(x.left)}<button class="btn sm" data-dfin="${esc(x.key)}">완료</button></div>`).join('')
          : '<div class="it small faint">기한이 있는 보정이 없어요</div>'}${dl.counts.nodue ? `<div class="it small"><span class="chip warn">기한 없음 ${dl.counts.nodue}건</span><span class="faint">보정명령 받은 날을 넣으면 여기에 떠요</span></div>` : ''}</div></div>
      <div class="card"><div class="card-b small muted" style="line-height:1.7"><b style="color:var(--text)">보정 기한은 진행내용에 날짜가 없을 수 있어요.</b><br>보정명령이 새로 보이면 「확인할 것」에 기한 칸이 함께 떠요. 기본 기한(받은 날 + ${S.rules.find(r => r.id === 'r_fix')?.days || 7}일)은 설정에서 바꿀 수 있어요.</div></div></div></div>`;
  $$('.cal .d[data-d]', v).forEach(d => d.onclick = () => go('cal', {y, m, sel: d.dataset.d}));
  $$('[data-dfin]', v).forEach(b => b.onclick = e => { e.stopPropagation(); safe(async () => { await api('lg_dlv_done', {keys: [b.dataset.dfin]}); toast('보정을 완료로 바꿨어요'); go('cal', {y, m, sel}); }); });
  $$('[data-ddel]', v).forEach(b => b.onclick = e => { e.stopPropagation(); safe(async () => {
    if (!await confirmBox('보정 관리에서 지우기', '이 보정 건을 대장에서 지워요. 끝난 일이면 「완료」가 기록이 남아 좋아요.', '지우기')) return;
    await api('lg_dlv_delete', {keys: [b.dataset.ddel]}); toast('지웠어요'); go('cal', {y, m, sel}); }); });
  $('#addDue').onclick = () => safe(async () => {
    const cases = await api('ledger');
    const r = await modal('기한 직접 넣기', `<div class="form"><div class="full"><label class="lb">사건</label><select class="field" id="c"><option value="">(사건 없이)</option>${cases.map(c => `<option value="${c.id}">${esc(c.case_no)} · ${esc(c.party)}</option>`).join('')}</select></div>
      <div><label class="lb">날짜</label><input class="field" type="date" id="d" value="${sel}"></div><div><label class="lb">내용</label><input class="field" id="t" placeholder="예: 주소보정 기한"></div></div>`,
      [{text: '취소'}, {text: '저장', cls: 'primary', value: bg => ($('#d', bg).value ? {cid: $('#c', bg).value, date: $('#d', bg).value, note: $('#t', bg).value || '직접 넣은 기한'} : false)}]);
    if (!r) return;
    await api('manual_deadline', r);
    go('cal', {y, m, sel: r.date});
  });
};

// ================================================================== 사건 대장
SCREENS.ledger = async (v, a) => {
  const arch = !!a.archived;
  const all = await api('ledger', {archived: arch});
  const f = a.f || '';
  const q = (a.q || '').trim();
  const statuses = {};
  all.forEach(c => { const s = c.status || (c.last_result === 'notfound' ? '찾을 수 없음' : '조회 전'); statuses[s] = (statuses[s] || 0) + 1; });
  const me = S.me;
  const rows = all.filter(c => {
    const s = c.status || (c.last_result === 'notfound' ? '찾을 수 없음' : '조회 전');
    if (f === '__me' ? c.owner !== me : f && s !== f) return false;
    if (q && ![c.case_no, c.party, c.memo1, c.memo2, c.court, c.owner, c.csNm].join(' ').includes(q)) return false;
    return true;
  });
  const colorOf = {};
  all.forEach(c => { if (c.status) colorOf[c.status] = c.color; });
  const top = Object.entries(statuses).sort((x, y) => y[1] - x[1]);
  v.innerHTML = head(`${esc(INFO.book)} · ` + (arch ? '목록에서 빠진 사건 (조회 기록은 남아 있어요)' : '프로그램 안에 보관하는 사건 목록'), `${arch ? '보관함' : '사건 대장'} <span class="faint" style="font-weight:500">${all.length}</span>`,
      `<button class="btn ghost" data-go="ledger" data-arg='${JSON.stringify({archived: !arch})}'>${arch ? '← 사건 대장' : '보관함'}</button><button class="btn" id="addOne">+ 한 건 넣기</button><button class="btn primary" data-go="import">엑셀로 추가·갱신</button>`) +
    (arch ? '' : `<div class="stats">${top.slice(0, 4).map(([k, n]) => `<div class="card stat pointer" data-f="${esc(k)}"><div class="l"><i style="background:${HEX[colorOf[k]] || (k === '찾을 수 없음' ? HEX.red : HEX.gray)}"></i>${esc(k)}</div><div class="v num">${n}<small>건</small></div></div>`).join('')}</div>`) +
    `<div class="card" style="overflow:hidden">
      <div class="filters"><button class="f ${!f ? 'on' : ''}" data-f="">전체<em>${all.length}</em></button>${top.map(([k, n]) => `<button class="f ${f === k ? 'on' : ''}" data-f="${esc(k)}">${esc(k)}<em>${n}</em></button>`).join('')}${me ? `<button class="f ${f === '__me' ? 'on' : ''}" data-f="__me">내 담당<em>${all.filter(c => c.owner === me).length}</em></button>` : ''}
        <input class="search" id="q" placeholder="사건번호·이름·메모 찾기" value="${esc(q)}"></div>
      <div class="sel-bar" id="selBar" hidden><b id="selN"></b><button class="btn sm" id="selRun">지금 조회</button><button class="btn sm" id="selXl">엑셀로 저장</button><button class="btn sm" id="selArch">${arch ? '사건 대장으로 되돌리기' : '보관함으로'}</button></div>
      ${rows.length ? `<div class="card-b" style="padding:10px 8px 8px"><table class="tbl"><tr><th><input type="checkbox" class="cbx" id="all"></th><th>사건</th><th>사건명</th><th>상태</th><th>마지막 진행</th><th>다음 기일</th><th>마지막 조회</th><th>담당</th><th>메모</th></tr>
        ${rows.map(c => `<tr class="click" data-cid="${c.id}"><td><input type="checkbox" class="cbx" data-sel="${c.id}"></td><td class="case"><b class="num">${esc(c.case_no)}</b><small>${esc(c.court.replace('지방법원', ''))} · ${esc(c.party)}</small></td><td>${esc(c.csNm || '')}</td><td>${stChip(c)}${c.new_count ? ` <span class="newdot">새 ${c.new_count}</span>` : ''}</td>
          <td class="w" style="max-width:320px">${lastProg(c.last_prog, c.new_count)}</td><td>${c.next_hearing?.date ? `<b>${md(c.next_hearing.date)}</b> ${esc(c.next_hearing.time || '')}` : '<span class="faint">—</span>'}</td>
          <td class="muted">${c.last_checked ? md(c.last_checked.slice(0, 10)) : '—'}</td><td>${esc(c.owner)}</td><td class="num muted">${esc(c.memo1)}</td></tr>`).join('')}</table></div>`
        : empty(all.length ? '맞는 사건이 없어요' : '사건이 없어요', all.length ? '찾는 말이나 고른 상태를 바꿔 보세요.' : '엑셀 파일을 이 창에 끌어다 놓거나 「엑셀로 추가·갱신」을 눌러 주세요.', all.length ? '' : '<button class="btn primary" data-go="import">엑셀로 사건 넣기</button> <button class="btn" data-go="pick" data-arg=\'{"fresh":true}\'>직접 입력해서 조회</button>')}</div>`;
  $$('[data-f]', v).forEach(el => el.onclick = () => go('ledger', {archived: arch, f: el.dataset.f === f ? '' : el.dataset.f, q}));
  const qi = $('#q');
  qi.oninput = () => { clearTimeout(qi._t); qi._t = setTimeout(() => go('ledger', {archived: arch, f, q: qi.value}).then(() => { const n = $('#q'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }), 300); };
  $$('tr[data-cid]', v).forEach(tr => tr.onclick = e => { if (!e.target.closest('input')) go('case', {cid: tr.dataset.cid}); });
  const selected = () => $$('[data-sel]:checked', v).map(x => x.dataset.sel);
  const upd = () => { const n = selected().length; $('#selBar').hidden = !n; $('#selN').textContent = `${n}건 골랐어요`; };
  $$('[data-sel]', v).forEach(x => x.onchange = upd);
  if ($('#all')) $('#all').onchange = e => { $$('[data-sel]', v).forEach(x => x.checked = e.target.checked); upd(); };
  $('#selRun').onclick = () => safe(async () => { const st = await api('run_start', {name: '고른 사건 조회', case_ids: selected()}); go('run', {state: st}); });
  $('#selXl').onclick = () => safe(async () => { const p = await api('export_cases', {ids: selected()}); toast('저장했어요: ' + p.split(/[\\/]/).pop()); });
  $('#selArch').onclick = () => safe(async () => { const n = await api('case_archive', {ids: selected(), archived: !arch}); toast(`${n}건 옮겼어요`); go('ledger', {archived: arch}); });
  $('#addOne').onclick = () => caseForm();
};
async function caseForm(c) {
  c = c || {};
  const r = await modal(c.id ? '사건 고치기' : '한 건 넣기', `<div class="form">
    <div class="full"><label class="lb">법원</label><input class="field" id="court" list="courtList" value="${esc(c.court || '')}" placeholder="예: 서울중앙지방법원, 수원지법 성남지원"><datalist id="courtList">${INFO.courts.map(n => `<option value="${esc(n)}">`).join('')}</datalist></div>
    <div><label class="lb">사건번호</label><input class="field" id="no" value="${esc(c.case_no || '')}" placeholder="2025가소123456"></div>
    <div><label class="lb">당사자 이름 (2글자 이상)</label><input class="field" id="party" value="${esc(c.party || '')}"></div>
    <div><label class="lb">담당</label><input class="field" id="owner" value="${esc(c.owner || S.me || '')}"></div>
    <div><label class="lb">메모 1 (계좌번호 등)</label><input class="field" id="memo1" value="${esc(c.memo1 || '')}"></div>
    <div class="full"><label class="lb">메모 2</label><input class="field" id="memo2" value="${esc(c.memo2 || '')}"></div></div><div class="err small mt8" id="er"></div>`,
    [{text: '취소'}, {text: '저장', cls: 'primary', value: async bg => {
      try {
        return await api('case_save', {data: {id: c.id, court: $('#court', bg).value, case_no: $('#no', bg).value, party: $('#party', bg).value, owner: $('#owner', bg).value, memo1: $('#memo1', bg).value, memo2: $('#memo2', bg).value}});
      } catch (e) { $('#er', bg).textContent = e.message; return false; }
    }}]);
  if (r) { toast('저장했어요'); go('case', {cid: r}); }
}

// ================================================================== 엑셀로 추가·갱신
SCREENS.import = async (v, a) => {
  let p = null, mapping = a.mapping || null;
  const choose = async () => {
    if (MODE === 'browser') {
      const path = await modal('파일 위치', '<label class="lb">엑셀 파일의 전체 경로</label><input class="field" id="fp" placeholder="C:\\Users\\...\\사건목록.xlsx">', [{text: '취소'}, {text: '열기', cls: 'primary', value: bg => $('#fp', bg).value.trim() || false}]);
      if (path) go('import', {path});
      return;
    }
    const path = await api('choose_file');
    if (path) go('import', {path});
  };
  if (!a.path) {
    v.innerHTML = head('<a data-go="ledger">사건 대장</a> · 엑셀로 추가·갱신', '엑셀로 추가·갱신', '<button class="btn" id="tpl">양식 받기</button>') +
      `<div class="card"><div class="card-b"><div class="drop pointer" id="pickFile" style="padding:60px;text-align:center;border:1.5px dashed var(--line);border-radius:14px">
        <b style="font-size:16px;color:var(--text)">엑셀 파일을 이 창에 끌어다 놓으세요</b><div class="muted mt8">또는 여기를 눌러서 고르기 · .xlsx .xls .csv</div>
        <div class="small faint mt16">법원 · 사건번호 · 당사자 이름 칸이 있으면 돼요. 담당·계좌번호 같은 칸도 함께 옮길 수 있어요.<br>이미 대장에 있는 사건은 담당·메모만 새로 고치고, 조회 결과는 그대로 둬요.</div></div></div></div>`;
    $('#pickFile').onclick = () => safe(choose);
    $('#tpl').onclick = () => safe(async () => { const p2 = await api('template_save'); toast('양식을 저장했어요: ' + p2.split(/[\\/]/).pop()); });
    return;
  }
  p = await api('import_preview', {path: a.path, mapping});
  const opts = j => `<option value="-1">(안 씀)</option>` + p.header.map((h, k) => `<option value="${k}" ${j === k ? 'selected' : ''}>${p.letters[k]} · ${esc(h || '(제목 없음)')}</option>`).join('');
  v.innerHTML = head('<a data-go="ledger">사건 대장</a> · 엑셀로 추가·갱신', '엑셀로 추가·갱신', `<button class="btn ghost" id="other">다른 파일</button><button class="btn primary" id="apply" ${p.good_count ? '' : 'disabled'}>사건 대장에 반영</button>`) +
    `<div class="g2e mb16"><div class="card"><div class="card-h"><h2>엑셀 파일</h2></div><div class="card-b">
      <div class="file"><div class="ic">XLS</div><div style="flex:1"><b>${esc(p.name)}</b><div class="small muted">${esc(p.sheet)} · ${p.rows}줄</div></div></div>
      <div class="diff"><div><span class="small muted">새로 생긴 사건</span><b style="color:var(--accent)">${p.new}</b></div><div><span class="small muted">목록에서 빠짐</span><b style="color:var(--warn)">${p.gone.length}</b></div><div><span class="small muted">이미 있음</span><b>${p.same}</b></div></div>
      <div class="small muted mt16">대장에 있는데 이 파일에 없는 ${p.gone.length}건은 <select class="inp" id="gone" style="width:auto"><option value="keep">그대로 두기</option><option value="archive">보관함으로 옮기기</option></select> · 조회 기록은 지우지 않아요</div>
    </div></div>
    <div class="card"><div class="card-h"><h2>어느 칸이 무엇인가요?</h2><span class="small muted">자동으로 찾았어요 · 바꿀 수 있어요</span></div><div class="card-b maps">
      ${p.fields.filter(x => !(x.key in p.mapping) && ['year', 'dvs', 'serial'].includes(x.key) && 'case' in p.mapping ? false : true).map(x => `<div class="map"><div class="k">${esc(x.name)}${['court', 'case', 'party'].includes(x.key) ? ' <b class="err">*</b>' : ''}</div><select class="field" data-map="${x.key}" style="padding:6px 8px">${opts(p.mapping[x.key])}</select>${p.sample[x.key] ? `<div class="small faint mt8">예: ${esc(p.sample[x.key])}</div>` : ''}</div>`).join('')}
    </div></div></div>
    <div class="card"><div class="card-h"><h2>확인할 줄 ${chip('반영할 사건 ' + p.good_count, 'green')} ${p.fixes.length ? chip('자동 고침 ' + p.fixes.length, 'orange') : ''} ${p.skips.length ? chip('건너뜀 ' + p.skips.length, 'red') : ''}</h2></div><div class="card-b">
      ${p.fixes.length + p.skips.length ? `<table class="tbl"><tr><th>줄</th><th>법원</th><th>사건번호</th><th>당사자</th><th>확인 내용</th><th></th></tr>
        ${p.skips.concat(p.fixes).sort((x, y) => x.line - y.line).slice(0, 300).map(r => `<tr><td class="muted">${r.line}</td><td>${esc(r.court_raw)}</td><td>${esc(r.case_raw)}</td><td>${esc(r.party)}</td><td class="w">${esc(r.problem || r.fix)}</td><td>${r.problem ? chip('건너뜀', 'red') : chip('자동 고침', 'orange')}</td></tr>`).join('')}</table>` : '<div class="small ok-t">모든 줄을 그대로 읽었어요</div>'}
    </div></div>`;
  $$('[data-map]', v).forEach(s => s.onchange = () => {
    const m = {};
    $$('[data-map]', v).forEach(x => { if (+x.value >= 0) m[x.dataset.map] = +x.value; });
    go('import', {path: a.path, mapping: m});
  });
  $('#other').onclick = () => safe(choose);
  $('#apply').onclick = () => safe(async () => {
    const m = {};
    $$('[data-map]', v).forEach(x => { if (+x.value >= 0) m[x.dataset.map] = +x.value; });
    const r = await api('import_apply', {path: a.path, mapping: m, gone_action: $('#gone').value});
    toast(`새로 ${r.added}건 · 고침 ${r.updated}건${r.archived ? ` · 보관함 ${r.archived}건` : ''}${r.skipped ? ` · 건너뜀 ${r.skipped}건` : ''}`);
    go('ledger');
  });
};

// ================================================================== 사건 상세
SCREENS.case = async (v, a) => {
  const d = await api('case_detail', {cid: a.cid});
  const c = d.case;
  const memos = c.memos || [];
  v.innerHTML = `<div class="head"><div><div class="crumb"><a data-go="ledger">사건 대장</a> · 사건 상세</div>
      <div class="detail-head"><h1 class="num">${esc(c.case_no)}</h1>${stChip(c)}${c.archived ? chip('보관함', 'gray') : ''}</div>
      <div class="muted" style="margin-top:6px">${esc(c.court)} · ${esc(c.csNm || '사건명 모름')} · ${esc(c.party)}${c.used_party ? ` (조회한 이름: ${esc(c.used_party)})` : ''}${c.owner ? ' · 담당 ' + esc(c.owner) : ''}${c.memo1 ? ' · ' + esc(c.memo1) : ''}</div></div>
    <div class="row-gap"><button class="btn" id="edit">고치기</button><button class="btn" id="now">이 사건만 지금 조회</button>${c.cfm_date ? '<button class="btn" id="sihyo">시효 앱으로 보내기</button>' : ''}<button class="btn primary" id="xl">엑셀</button></div></div>
    ${d.checked ? `<div class="g2e" style="grid-template-columns:1.1fr 1fr"><div class="side-col">
      <div class="card"><div class="card-h"><h2>일반내용</h2><span class="small muted">${esc(c.last_checked.slice(0, 16))} 조회</span></div><div class="card-b">
        <div class="gen-grid">${d.basic.map(b => `<div><span>${esc(b.label)}</span>${esc(b.value)}</div>`).join('')}${d.basic.length % 2 ? '<div></div>' : ''}</div>
        ${d.lists.map(l => `<div class="sub-h">${esc(l.name)}</div><table class="list-tbl"><tr>${l.cols.map(x => `<th>${esc(x)}</th>`).join('')}</tr>${l.rows.map(r => `<tr>${r.map(x => `<td>${esc(x)}</td>`).join('')}</tr>`).join('')}</table>`).join('')}
      </div></div>
      <div class="card"><div class="card-h"><h2>메모 · 처리 기록</h2><button class="btn sm" id="memo">+ 메모</button></div><div class="card-b" style="display:grid;gap:8px">${memos.length ? memos.map(m => `<div class="memo"><small>${esc(m.at.slice(0, 16))} ${esc(m.by || '')}${m.from ? ' · ' + esc(m.from) + '에서 처리함' : ''}</small>${esc(m.text)}</div>`).join('') : '<div class="small faint">메모가 없어요</div>'}</div></div>
    </div>
    <div class="card"><div class="card-h"><h2>지금까지의 진행</h2><span class="small muted">조회 ${d.rounds.length}회</span></div><div class="card-b">
      ${d.rounds.map(r => `<div class="round-h">${esc(r.at.slice(0, 16))} ${r.first ? '처음 조회' : '조회'} ${r.count && !r.first ? `<span class="newdot">새 ${r.count}</span>` : `<span class="faint" style="font-weight:400">${r.first ? r.count + '건' : '새 진행 없음'}</span>`}${r.error ? ` <span class="err small">진행내용: ${esc(r.error)}</span>` : ''}</div>
        ${r.rows.length ? `<div class="timeline">${r.rows.map(x => `<div class="ev ${x.new ? 'new' : ''}"><div class="d">${fullDate(x.date)}</div><div class="x">${esc(x.text)}</div></div>`).join('')}</div>` : ''}`).join('')}
    </div></div></div>`
    : `<div class="card">${empty('아직 조회하지 않았어요', '「이 사건만 지금 조회」를 누르면 바로 조회해요.')}</div>`}`;
  $('#edit').onclick = () => caseForm(c);
  $('#now').onclick = () => safe(async () => { const st = await api('run_start', {name: '한 건 조회', case_ids: [c.id]}); go('run', {state: st}); });
  $('#xl').onclick = () => safe(async () => { const p = await api('export_cases', {ids: [c.id]}); toast('저장했어요: ' + p.split(/[\\/]/).pop()); });
  if ($('#sihyo')) $('#sihyo').onclick = () => safe(async () => { const r = await api('sihyo_send', {ids: [c.id]}); toast(`시효 앱 폴더에 보냈어요 (${r.count}건)`); });
  if ($('#memo')) $('#memo').onclick = () => safe(async () => {
    const t = await modal('메모', '<textarea class="field" id="t" rows="4"></textarea>', [{text: '취소'}, {text: '저장', cls: 'primary', value: bg => $('#t', bg).value.trim() || false}]);
    if (!t) return;
    await api('memo_add', {cid: c.id, text: t});
    go('case', a);
  });
};

// ================================================================== 결과 보기
SCREENS.result = async (v, a) => {
  const runs = await api('runs');
  if (!runs.length) { v.innerHTML = head('조회한 결과', '결과 보기') + `<div class="card">${empty('아직 조회한 적이 없어요', '조회를 하면 회차별 결과가 여기에 쌓여요.', '<button class="btn primary" data-go="pick">조회하기</button>')}</div>`; return; }
  const rid = a.rid || runs[0].id;
  const d = await api('run_result', {rid});
  const f = a.f || 'changed';
  const rows = d.rows.filter(r => f === 'all' || (f === 'changed' && r.new) || (f === 'cfm' && r.cfm_date) || (f === 'nf' && r.state === 'notfound'));
  const cnt = {all: d.rows.length, changed: d.rows.filter(r => r.new).length, cfm: d.rows.filter(r => r.cfm_date).length, nf: d.rows.filter(r => r.state === 'notfound').length};
  v.innerHTML = head(`<a data-go="hist">조회 기록</a> · ${esc(d.run.name)} · ${esc(d.run.created.slice(0, 16))} · ${d.rows.length}건`, '결과 보기',
      `<select class="inp" id="runSel" style="width:auto">${runs.slice(0, 30).map(r => `<option value="${r.id}" ${r.id === rid ? 'selected' : ''}>${esc(r.created.slice(0, 10))} ${esc(r.name)} (${r.total}건)</option>`).join('')}</select><button class="btn primary" id="xl">엑셀로 저장</button>`) +
    `<div class="stats"><div class="card stat"><div class="l"><i style="background:var(--accent)"></i>조회 완료</div><div class="v num">${d.rows.filter(r => r.state === 'done').length}<small>건</small></div></div>
      <div class="card stat"><div class="l"><i style="background:var(--warn)"></i>새 진행이 생긴 사건</div><div class="v num">${cnt.changed}<small>건</small></div></div>
      <div class="card stat"><div class="l"><i style="background:var(--ok)"></i>확정된 사건</div><div class="v num">${cnt.cfm}<small>건</small></div></div>
      <div class="card stat"><div class="l"><i style="background:var(--bad)"></i>찾을 수 없음</div><div class="v num">${cnt.nf}<small>건</small></div></div></div>
    <div class="card" style="overflow:hidden"><div class="filters">${[['all', '전체'], ['changed', '달라짐'], ['cfm', '확정'], ['nf', '찾을 수 없음']].map(([k, n]) => `<button class="f ${f === k ? 'on' : ''}" data-ff="${k}">${n}<em>${cnt[k]}</em></button>`).join('')}</div>
      ${rows.length ? `<div class="card-b" style="padding:10px 8px 8px"><table class="tbl res"><tr><th>사건</th><th>사건명</th><th>상태</th><th>마지막 진행</th><th>메모</th><th></th></tr>
        ${rows.map(r => `<tr class="click" data-cid="${r.id}"><td class="case"><b class="num">${esc(r.case_no)}</b><small>${esc(r.court.replace('지방법원', ''))} · ${esc(r.party)}</small></td><td>${esc(r.csNm || '')}</td>
          <td>${r.state === 'notfound' ? chip('찾을 수 없음', 'red') : r.state === 'wait' ? chip('조회 안 함', 'gray') : r.state === 'skip' ? chip('건너뜀', 'gray') : stChip(r)}</td>
          <td class="w">${r.last_prog?.date ? lastProg(r.last_prog, r.new) : esc(r.msg || '')}${r.new ? ` <span class="newdot">새 ${r.new}</span>` : ''}</td><td class="num muted">${esc(r.memo1)}</td><td class="muted">⌄</td></tr>`).join('')}</table></div>`
        : empty('해당하는 사건이 없어요', '다른 보기를 골라 보세요.')}</div>`;
  $('#runSel').onchange = e => go('result', {rid: e.target.value, f});
  $$('[data-ff]', v).forEach(b => b.onclick = () => go('result', {rid, f: b.dataset.ff}));
  $('#xl').onclick = () => safe(async () => { const p = await api('export_run', {rid}); toast('저장했어요: ' + p.split(/[\\/]/).pop()); });
  $$('tr[data-cid]', v).forEach(tr => tr.onclick = () => safe(async () => {
    const nx = tr.nextElementSibling;
    if (nx && nx.classList.contains('tl-wrap')) { nx.remove(); tr.classList.remove('open'); return; }
    const dd = await api('case_detail', {cid: tr.dataset.cid});
    const prog = dd.rounds.flatMap(r => r.rows).sort((x, y) => y.date.localeCompare(x.date));
    tr.classList.add('open');
    tr.insertAdjacentHTML('afterend', `<tr class="tl-wrap"><td colspan="6"><div class="tl">
      <div><div class="sec-h"><b>일반내용</b><span>첫 번째 탭</span></div><div class="gen-grid">${dd.basic.slice(0, 14).map(b => `<div><span>${esc(b.label)}</span>${esc(b.value)}</div>`).join('')}${Math.min(14, dd.basic.length) % 2 ? '<div></div>' : ''}</div>
        <div class="mt8"><a data-go="case" data-arg='${JSON.stringify({cid: tr.dataset.cid})}'>사건 상세 열기 →</a></div></div>
      <div><div class="sec-h"><b>진행내용</b><span>두 번째 탭 · ${prog.length}건</span></div><div class="timeline">${prog.slice(0, 12).map(x => `<div class="ev ${x.new ? 'new' : ''}"><div class="d">${fullDate(x.date)}</div><div class="x">${esc(x.text)}</div></div>`).join('')}</div></div>
    </div></td></tr>`);
  }));
};

// ================================================================== 조회 기록
SCREENS.hist = async (v, a) => {
  const [runs, aruns] = await Promise.all([api('runs'), api('auction_runs')]);
  const running = INFO.running;
  const kind = a.k || '';
  const all = runs.map(r => Object.assign({kind: '소송'}, r)).concat(aruns).filter(r => !kind || r.kind === kind)
    .sort((x, y) => y.created.localeCompare(x.created));
  v.innerHTML = head(`${esc(INFO.book)} · 조회한 회차마다 결과를 볼 수 있어요`, '조회 기록 · 결과', '<button class="btn primary" data-go="pick">+ 새 조회</button>') +
    `<div class="filters" style="padding:0 0 16px;border:0">${[['', '전체'], ['소송', '나의사건검색'], ['경매', '경매']].map(([k, n]) => `<button class="f ${kind === k ? 'on' : ''}" data-k="${k}">${n}<em>${(k ? (k === '경매' ? aruns : runs) : runs.concat(aruns)).length}</em></button>`).join('')}</div>` +
    (all.length ? `<div class="hist">${all.slice(0, 80).map(r => {
      const au = r.kind === '경매';
      const live = au ? r.running : running && running.rid === r.id;
      const fin = !!r.finished;
      return `<div class="card h-card"><div class="date">${esc(r.created.slice(0, 16))} · ${fin ? '완료' : live ? '진행 중' : '멈춤'} · ${au ? chip('경매', 'orange') : chip('나의사건검색', 'blue')}</div><div class="name">${esc(r.name)} · ${r.total}건</div>
        <div class="h-bar"><i style="width:${r.total ? r.done / r.total * 100 : 0}%;background:${fin ? 'var(--ok)' : 'var(--accent)'}"></i></div>
        <div class="small muted" style="margin-bottom:16px">${fin ? '' : `${r.done} / ${r.total} · `}${au ? '새 문건·송달' : '새 진행'} ${r.changed}건 · 찾을 수 없음 ${r.notfound}건${r.elapsed ? ` · ${Math.floor(r.elapsed / 60)}분 ${r.elapsed % 60}초` : ''}</div>
        <div class="row-gap">${fin ? '' : `<button class="btn primary sm" data-resume="${r.id}" data-au="${au ? 1 : ''}">이어서 조회</button>`}${au ? '<button class="btn sm" data-go="auction">경매 사건 보기</button>' : `<button class="btn sm" data-go="result" data-arg='${JSON.stringify({rid: r.id, f: 'all'})}'>결과</button><button class="btn ghost sm" data-xl="${r.id}">엑셀</button>`}</div></div>`;
    }).join('')}</div>` : `<div class="card">${empty('조회 기록이 없어요', '조회를 하면 여기에 남아요.')}</div>`);
  $$('[data-k]', v).forEach(b => b.onclick = () => go('hist', {k: b.dataset.k}));
  $$('[data-resume]', v).forEach(b => b.onclick = () => safe(async () => {
    if (b.dataset.au) {
      const st = await api('auction_start', {rid: b.dataset.resume});
      await go('auction', {});
      if (typeof auDrawRun === 'function') auDrawRun(st);
      return;
    }
    const st = running && running.rid === b.dataset.resume ? await api('run_state', {fetch: true}) : await api('run_resume', {rid: b.dataset.resume});
    go('run', {state: st});
  }));
  $$('[data-xl]', v).forEach(b => b.onclick = () => safe(async () => { const p = await api('export_run', {rid: b.dataset.xl}); toast('저장했어요: ' + p.split(/[\\/]/).pop()); }));
};

// ================================================================== 월간 보고서
const PARTS = ['요약 숫자', '상태별 건수', '이번 달 확정 목록', '송달불능·보정명령 목록', '담당자별 건수', '법원별 건수'];
SCREENS.report = async (v, a) => {
  const now = new Date(INFO.today + 'T00:00');
  const y = a.y || now.getFullYear(), m = a.m || now.getMonth() + 1;
  const parts = a.parts || PARTS.slice(0, 4);
  const d = await api('report_preview', {year: y, month: m});
  const months = [];
  for (let i = 0; i < 12; i++) { const dt = new Date(now.getFullYear(), now.getMonth() - i, 1); months.push([dt.getFullYear(), dt.getMonth() + 1]); }
  const total = d.total || 1;
  v.innerHTML = head('보관', '월간 보고서', '<button class="btn" id="pdf">인쇄 · PDF</button><button class="btn primary" id="xl">엑셀로 저장</button>') +
    `<div class="rep"><div class="card"><div class="card-b">
      <label class="lb">기간</label><select class="field mb16" id="mon">${months.map(([yy, mm]) => `<option value="${yy}-${mm}" ${yy === y && mm === m ? 'selected' : ''}>${yy}년 ${mm}월</option>`).join('')}</select>
      <label class="lb">넣을 내용</label>${PARTS.map(p => `<div class="opt"><span class="cb ${parts.includes(p) ? 'on' : ''}" data-part="${p}">✓</span>${p}</div>`).join('')}
      <div class="small muted mt16">파일 이름</div><div class="code mt8">사건현황_<b>${y}년${String(m).padStart(2, '0')}월</b>.xlsx</div></div></div>
    <div class="paper"><h3>${y}년 ${m}월 소송 사건 현황</h3><div class="p-sub">기준 ${fullDate(INFO.today)} · 사건 대장 ${d.total}건${d.me ? ' · 작성 ' + esc(d.me) : ''}</div>
      ${parts.includes('요약 숫자') ? `<div class="kpis"><div>전체<b>${d.total}</b></div><div>진행 중<b>${d.running}</b></div><div>이번 달 확정<b>${d.confirmed.length}</b></div><div>조치 필요<b style="color:#e5484d">${d.action.length}</b></div></div>` : ''}
      ${parts.includes('상태별 건수') ? `<h4>상태별 건수</h4>${Object.entries(d.counts).sort((x, y2) => y2[1] - x[1]).map(([k, n]) => `<div class="hbar"><span>${esc(k)}</span><i style="width:${Math.max(1, n / total * 70)}%;background:${HEX[d.colors[k]] || '#9aa1ad'}"></i>${n}</div>`).join('')}` : ''}
      ${parts.includes('이번 달 확정 목록') ? `<h4 style="margin-top:20px">이번 달 확정 (${d.confirmed.length})</h4>${d.confirmed.length ? `<table><tr><th>사건번호</th><th>법원</th><th>당사자</th><th>확정일</th><th>메모</th></tr>${d.confirmed.map(r => `<tr><td>${esc(r.case_no)}</td><td>${esc(r.court)}</td><td>${esc(r.party)}</td><td>${esc(r.date)}</td><td>${esc(r.memo1)}</td></tr>`).join('')}</table>` : '<div style="font-size:12px;color:#9aa1ad">없음</div>'}` : ''}
      ${parts.includes('송달불능·보정명령 목록') ? `<h4 style="margin-top:20px">조치 필요 (${d.action.length})</h4>${d.action.length ? `<table><tr><th>사건번호</th><th>법원</th><th>당사자</th><th>상태</th><th>메모</th></tr>${d.action.map(r => `<tr><td>${esc(r.case_no)}</td><td>${esc(r.court)}</td><td>${esc(r.party)}</td><td>${esc(r.status)}</td><td>${esc(r.memo1)}</td></tr>`).join('')}</table>` : '<div style="font-size:12px;color:#9aa1ad">없음</div>'}` : ''}
      ${parts.some(p => p.endsWith('별 건수')) ? '<div style="font-size:12px;color:#9aa1ad;margin-top:18px">담당자별·법원별 건수는 엑셀 파일에 들어가요.</div>' : ''}
    </div></div>`;
  $('#mon').onchange = e => { const [yy, mm] = e.target.value.split('-').map(Number); go('report', {y: yy, m: mm, parts}); };
  $$('[data-part]', v).forEach(c => c.onclick = () => { const p = c.dataset.part; go('report', {y, m, parts: parts.includes(p) ? parts.filter(x => x !== p) : parts.concat([p])}); });
  $('#pdf').onclick = () => window.print();
  $('#xl').onclick = () => safe(async () => { const p = await api('report_save', {year: y, month: m, parts}); toast('저장했어요: ' + p.split(/[\\/]/).pop()); });
};

// ================================================================== 설정
const PANES = [['#', '자주 바꾸는 것'], ['look', '🎨 화면'], ['menu', '☰ 메뉴 구성'], ['todo', '✅ 확인할 것 · 기한'], ['run', '🔍 조회 방식'], ['save', '💾 시작 · 저장 · 백업'], ['-'], ['#', '처음 한 번 정하는 것'], ['rule', '🏷 상태 분류 규칙'], ['link', '🔑 연결 기준 (키)'], ['excel', '📄 엑셀 저장 칸'], ['sihyo', '🔗 시효관리 앱 연결'], ['-'], ['log', '🕘 설정 기록']];
const num = (path, val, w = 64) => `<input class="inp" type="number" min="0" data-set="${path}" data-type="num" value="${esc(val)}" style="width:${w}px">`;
const sw = (path, on) => tg(on, `data-set="${path}" data-type="bool"`);
const seg = (path, cur, opts) => `<div class="seg">${opts.map(([v, t]) => `<button class="${String(cur) === String(v) ? 'on' : ''}" data-set="${path}" data-val='${JSON.stringify(v)}'>${t}</button>`).join('')}</div>`;
const srow = (t, s, right) => `<div class="srow"><div class="m"><div class="t">${t}</div>${s ? `<div class="s">${s}</div>` : ''}</div>${right}</div>`;
SCREENS.settings = async (v, a) => {
  const pane = a.p || 'look';
  v.innerHTML = head('바꾼 내용은 바로 저장돼요 · 「설정 기록」에서 되돌리기', '설정', '<button class="btn" id="sx">설정 파일로 내보내기</button><button class="btn" id="si">불러오기</button>') +
    `<div class="set"><div class="card set-nav">${PANES.map(([k, n]) => k === '-' ? '<div class="sep"></div>' : k === '#' ? `<div class="set-sg">${n}</div>` : `<button class="${k === pane ? 'on' : ''}" data-p="${k}">${n}</button>`).join('')}</div><div id="pane"></div></div>`;
  $$('.set-nav button', v).forEach(b => b.onclick = () => go('settings', {p: b.dataset.p}));
  $('#sx').onclick = () => safe(async () => { const p = await api('settings_export'); toast('저장했어요: ' + p.split(/[\\/]/).pop()); });
  $('#si').onclick = () => safe(async () => { const s = await api('settings_import'); if (s) { S = s; applyLook(); toast('설정을 불러왔어요'); go('settings', a); } });
  await PANE[pane]($('#pane'), a);
  bindSettings($('#pane'), a);
};
function bindSettings(el, a) {
  $$('[data-set]', el).forEach(x => {
    const path = x.dataset.set;
    if (x.dataset.val !== undefined) {
      x.onclick = () => safe(async () => { await setSetting(path, JSON.parse(x.dataset.val)); go('settings', a); });
    } else if (x.classList.contains('tg')) {
      x.onclick = () => safe(async () => { x.classList.toggle('on'); await setSetting(path, x.classList.contains('on')); });
    } else {
      x.onchange = () => safe(async () => { await setSetting(path, x.dataset.type === 'num' ? (+x.value || 0) : x.value); toast('저장했어요'); });
    }
  });
}
const PANE = {};
PANE.rule = async (el, a) => {
  let rules = a.rules || JSON.parse(JSON.stringify(S.rules));
  const dirty = !!a.rules;
  const COLORS = ['red', 'orange', 'green', 'blue', 'gray', 'purple', 'teal'];
  el.innerHTML = `<div class="card"><div class="card-h"><div><h2>상태 분류 규칙</h2><div class="small muted" style="margin-top:4px">진행내용을 <b>최근 줄부터</b> ${num('rule_rows', S.rule_rows, 52)}줄까지 읽어서 처음 맞는 줄로 정해요 · 한 줄에 여러 규칙이 맞으면 <b>위에 있는 규칙</b> (확정일자가 있으면 확정이 가장 최근)</div></div><button class="btn sm blue" id="addRule">+ 규칙 추가</button></div>
    <div class="card-b"><table class="tbl rule"><tr><th></th><th>이런 글자가 있으면</th><th>상태</th><th>확인할 것에</th><th>기한(일)</th><th>조회에서 빼기</th><th></th></tr>
    ${rules.map((r, i) => `<tr><td class="nowrap"><button class="icon-btn" data-up="${i}" ${i ? '' : 'disabled'}>↑</button> <button class="icon-btn" data-dn="${i}" ${i < rules.length - 1 ? '' : 'disabled'}>↓</button></td>
      <td><div class="rule-words">${r.words.map(w => `<span>${esc(w)}</span>`).join('')}</div></td><td>${chip(r.status, r.color)}</td>
      <td>${tg(r.todo, `data-rt="${i}" data-k="todo"`)}</td><td>${r.todo ? `<input class="inp" type="number" min="0" data-rn="${i}" value="${r.days || 0}" style="width:56px">${r.ask ? ' <span class="small faint">확인 요청</span>' : ''}` : '<span class="faint">—</span>'}</td>
      <td>${tg(r.skip, `data-rt="${i}" data-k="skip"`)}</td><td class="nowrap"><button class="btn sm ghost" data-ed="${i}">고치기</button><button class="btn sm ghost" data-del="${i}">지우기</button></td></tr>`).join('')}
    <tr><td></td><td class="faint">그 밖의 모든 것</td><td>${chip(S.default_status, 'blue')}</td><td class="faint">안 올림</td><td></td><td></td><td class="faint small">기본값</td></tr></table>
    <div class="small muted mt8">기한(일): 그 줄의 날짜에 더해 「확인할 것」의 기한으로 잡아요. 0이면 기한 없이 올려요.</div></div></div>
    ${dirty ? '<div class="card"><div class="card-b"><div class="preview-warn" id="pv">바뀌는 사건을 세는 중…</div></div></div>' : ''}`;
  const redraw = () => go('settings', {p: 'rule', rules});
  $$('[data-up]', el).forEach(b => b.onclick = () => { const i = +b.dataset.up; [rules[i - 1], rules[i]] = [rules[i], rules[i - 1]]; redraw(); });
  $$('[data-dn]', el).forEach(b => b.onclick = () => { const i = +b.dataset.dn; [rules[i + 1], rules[i]] = [rules[i], rules[i + 1]]; redraw(); });
  $$('[data-rt]', el).forEach(t => t.onclick = () => { rules[+t.dataset.rt][t.dataset.k] = !rules[+t.dataset.rt][t.dataset.k]; redraw(); });
  $$('[data-rn]', el).forEach(t => t.onchange = () => { rules[+t.dataset.rn].days = +t.value || 0; redraw(); });
  $$('[data-del]', el).forEach(b => b.onclick = () => { rules.splice(+b.dataset.del, 1); redraw(); });
  const edit = async i => {
    const r = i === undefined ? {id: 'r_' + Date.now().toString(36), words: [], status: '', color: 'orange', todo: true, days: 0, ask: false, skip: false} : rules[i];
    const out = await modal(i === undefined ? '규칙 추가' : '규칙 고치기', `<div class="form">
      <div class="full"><label class="lb">진행내용에 이런 글자가 있으면 (쉼표로 여러 개)</label><input class="field" id="w" value="${esc(r.words.join(', '))}" placeholder="예: 공시송달, 공시송달명령"></div>
      <div><label class="lb">상태 이름</label><input class="field" id="s" value="${esc(r.status)}"></div>
      <div><label class="lb">색</label><div class="swatches" id="cl">${COLORS.map(c => `<span class="swatch ${c === r.color ? 'on' : ''}" data-c="${c}" style="background:${HEX[c]}"></span>`).join('')}</div></div>
      <div class="full"><label class="lb"><input type="checkbox" class="cbx" id="ask" ${r.ask ? 'checked' : ''}> 기한이 진행내용에 없을 수 있으니 「확인할 것」에서 기한을 넣어 달라고 표시</label></div></div><div class="err small" id="er"></div>`,
      [{text: '취소'}, {text: '적용', cls: 'primary', value: bg => {
        const words = $('#w', bg).value.split(/[,，]/).map(x => x.trim()).filter(Boolean);
        const st = $('#s', bg).value.trim();
        if (!words.length || !st) { $('#er', bg).textContent = '글자와 상태 이름을 넣어 주세요'; return false; }
        return Object.assign({}, r, {words, status: st, color: ($('#cl .on', bg) || {}).dataset?.c || r.color, ask: $('#ask', bg).checked});
      }}]);
    if (!out) return;
    if (i === undefined) rules.push(out); else rules[i] = out;
    redraw();
  };
  setTimeout(() => $$('#cl .swatch').forEach(s => s.onclick = () => { $$('#cl .swatch').forEach(x => x.classList.toggle('on', x === s)); }), 0);
  document.addEventListener('click', e => { const s = e.target.closest('#cl .swatch'); if (s) $$('#cl .swatch').forEach(x => x.classList.toggle('on', x === s)); });
  $('#addRule').onclick = () => edit();
  $$('[data-ed]', el).forEach(b => b.onclick = () => edit(+b.dataset.ed));
  if (dirty) {
    const ch = await api('rules_preview', {new_rules: rules});
    $('#pv').innerHTML = `<b>이대로 저장하면 ${ch.length}건</b>의 상태가 바뀌어요 ${ch.length ? `<span class="small">(${ch.slice(0, 3).map(c => `${esc(c.case_no)}: ${esc(c.from)} → ${esc(c.to)}`).join(', ')}${ch.length > 3 ? ' …' : ''})</span>` : ''}
      <button class="btn sm" style="margin-left:auto" id="cancelR">바꾸기 전으로</button><button class="btn sm blue" id="saveR">저장</button>`;
    $('#cancelR').onclick = () => go('settings', {p: 'rule'});
    $('#saveR').onclick = () => safe(async () => { const r = await api('rules_save', {new_rules: rules}); S = r.settings; toast(`저장했어요 · ${r.changed}건 상태 바뀜`); go('settings', {p: 'rule'}); });
  }
};
PANE.todo = async el => {
  const t = S.todo;
  el.innerHTML = `<div class="card"><div class="card-h"><h2>확인할 것 · 기한</h2></div><div class="card-b" style="padding:8px 0 4px">
    ${srow('확정 예상일 계산', '판결정본 도달일에 더할 날짜 (항소기간)', `도달일 + ${num('todo.confirm_days', t.confirm_days)}일`)}
    ${srow('기일 미리 알림', '기일이 다가오면 확인할 것에 올려요', `${num('todo.hearing_days', t.hearing_days)}일 전부터`)}
    ${srow('빨간색 표시', '기한이 이만큼 남으면 급한 것으로', `${num('todo.hot_days', t.hot_days)}일 이하`)}
    ${srow('얼마 전 진행까지 볼까요', '진행 날짜가 이보다 오래된 줄은 확인할 것에 올리지 않아요', `최근 ${num('todo.lookback_days', t.lookback_days)}일`)}
    ${srow('처리할 때 메모 남기기', '「처리함」을 누르면 한 줄 메모 칸이 떠요', sw('todo.memo_on_done', t.memo_on_done))}
    ${srow('처리한 것 숨기기', '', seg('todo.hide_done', t.hide_done, [['now', '바로'], ['day', '하루 뒤'], ['never', '숨기지 않음']]))}
    ${srow('프로그램 켤 때 첫 화면', '', seg('todo.start', t.start, [['console', '현황 콘솔'], ['home', '확인할 것'], ['ledger', '사건 대장'], ['pick', '조회하기']]))}
    ${srow('내 이름', '처리 기록·보고서 작성자, 「내 담당」 보기에 써요', `<input class="inp wide" data-set="me" value="${esc(S.me || '')}" placeholder="예: 김담당">`)}
  </div></div><div class="small muted">상태별 기한(보정명령 7일 등)은 「상태 분류 규칙」에서 바꿔요.</div>`;
};
PANE.run = async el => {
  const r = S.run;
  el.innerHTML = `<div class="card"><div class="card-h"><h2>조회 방식</h2></div><div class="card-b" style="padding:8px 0 4px">
    ${srow('숫자를 다 치면 바로 조회', '끄면 Enter를 눌러야 조회돼요', sw('run.auto_submit', r.auto_submit))}
    ${srow('숫자 칸 개수', `「자동」은 처음 Enter로 조회한 개수를 기억해요${r.learned_digits ? ` (지금 ${r.learned_digits}개)` : ''}`, seg('run.digits', r.digits, [[0, '자동'], [4, '4'], [5, '5'], [6, '6'], [7, '7']]))}
    ${srow('그림 크기', '', seg('run.zoom', r.zoom, [[1, '1배'], [1.5, '1.5배'], [2, '2배'], [2.5, '2.5배']]))}
    ${srow('사건 사이 쉬는 시간', '법원 사이트에 부담을 주지 않게 · 너무 짧으면 접속이 막힐 수 있어요', `${num('run.delay', r.delay)}초`)}
    ${srow('정기 조회 주기', '「확인할 것」에 다음 조회 권장일을 보여줘요', `${num('run.cycle_days', r.cycle_days)}일마다`)}
    ${srow('찾을 수 없을 때 이름 표기를 바꿔 다시 시도', '㈜·주식회사 표기, 띄어쓰기를 바꿔 차례로 시도 (시도할 때마다 숫자를 새로 입력)', sw('run.retry_names', r.retry_names))}
    ${srow('법원 정보 새로 받기', '법원 사이트에 새 법원·사건구분이 생기거나 사이트가 바뀌어 조회가 안 될 때', '<button class="btn sm" id="meta">새로 받기</button>')}
    ${srow('단축키', '', '<span class="kbd">F5</span>새 그림 <span class="kbd">F6</span>소리 <span class="kbd">Esc</span>건너뛰기 <span class="kbd">Enter</span>조회')}
  </div></div>
  <div class="card"><div class="card-h"><h2>경매 (법원경매정보)</h2><span class="small muted">프로그램 안 법원경매정보 창에서 가져와요</span></div><div class="card-b" style="padding:8px 0 4px">
    ${srow('「검색」도 프로그램이 누르기', '끄면 사건번호만 채워 두고 「검색」은 사람이 눌러요 (기본: 켬)', sw('auction.auto_search', (S.auction || {}).auto_search !== false))}
    ${srow('기일내역 · 문건/송달내역 탭 자동으로 열기', '사건내역이 뜨면 두 탭을 차례로 열어 함께 저장해요', sw('auction.auto_tabs', (S.auction || {}).auto_tabs !== false))}
    ${srow('저장하면 다음 사건으로', '', sw('auction.auto_next', (S.auction || {}).auto_next !== false))}
    ${srow('사건 사이 쉬는 시간', '법원경매정보에는 로봇 탐지가 있어요 · 너무 짧으면 막힐 수 있어요', `${num('auction.delay', (S.auction || {}).delay ?? 5)}초`)}
  </div></div>`;
  $('#meta').onclick = () => safe(async () => { const m = await api('meta_refresh'); toast(`법원 ${m.courts}곳 · 사건 종류 ${m.tasks}가지를 새로 받았어요`); });
};
PANE.menu = async (el, a) => {
  const hidden = new Set(S.menu_hidden || []);
  const lay = menuLayout(), fold = menuFold();
  const nm = s => { const b = $(`#nav button[data-s="${s}"]`); return b ? [...b.childNodes].filter(x => x.nodeType === 3).map(x => x.textContent).join('').trim() : s; };
  const h = lay.map((g, gi) => `<div class="grp mgrp"><input class="inp" data-gn="${gi}" value="${esc(g.name)}" style="width:150px">
      <span class="mbtns"><button class="btn sm ghost" data-gu="${gi}" ${gi ? '' : 'disabled'} title="묶음 위로">▲</button><button class="btn sm ghost" data-gd="${gi}" ${gi < lay.length - 1 ? '' : 'disabled'} title="묶음 아래로">▼</button>
      ${gi ? `<label class="small" style="display:flex;gap:5px;align-items:center">${tg(!!fold[g.name], `data-gf="${gi}"`)}접어 두기</label>` : '<span class="small faint">맨 위 · 접지 않음</span>'}</span></div>` +
    g.items.map((s, ii) => `<div class="it"><span class="m">${esc(nm(s))}${s === 'settings' ? ' <span class="small faint">· 항상 보임</span>' : ''}</span>
      <span class="mbtns"><button class="btn sm ghost" data-mu="${gi}|${ii}" title="위로 (맨 위면 위 묶음으로)">▲</button><button class="btn sm ghost" data-md="${gi}|${ii}" title="아래로 (맨 아래면 아래 묶음으로)">▼</button>
      ${s === 'settings' ? '' : tg(!hidden.has(s), `data-m="${s}"`)}</span></div>`).join('')).join('');
  el.innerHTML = `<div class="card"><div class="card-h"><div><h2>메뉴 구성</h2><div class="small muted" style="margin-top:4px">▲▼로 순서를 바꾸고, 묶음 끝에서 더 누르면 옆 묶음으로 옮겨져요. 끄면 메뉴에서 사라지고, 「접어 두기」 묶음은 이름을 눌러 펼쳐요.</div></div>
    <div class="row-gap"><button class="btn sm" id="addG">+ 묶음</button><button class="btn sm" id="reset">처음대로</button></div></div><div class="menu-ed" style="padding:12px 0 6px">${h}</div></div>`;
  const save = async L => { await setSetting('menu_layout', L.filter(g => g.items.length || g.name), '메뉴 구성'); buildNav(); go('settings', {p: 'menu'}); };
  const copy = () => lay.map(g => ({name: g.name, items: g.items.slice()}));
  $$('[data-m]', el).forEach(t => t.onclick = () => safe(async () => {
    t.classList.toggle('on');
    const set = new Set(S.menu_hidden || []);
    t.classList.contains('on') ? set.delete(t.dataset.m) : set.add(t.dataset.m);
    await setSetting('menu_hidden', [...set]);
    markNav();
  }));
  const move = (gi, ii, dir) => {
    const L = copy(), it = L[gi].items[ii];
    const j = ii + dir;
    if (j >= 0 && j < L[gi].items.length) { L[gi].items.splice(ii, 1); L[gi].items.splice(j, 0, it); }
    else if (L[gi + dir]) { L[gi].items.splice(ii, 1); dir < 0 ? L[gi + dir].items.push(it) : L[gi + dir].items.unshift(it); }
    else return;
    save(L);
  };
  $$('[data-mu]', el).forEach(b => b.onclick = () => { const [g, i] = b.dataset.mu.split('|').map(Number); move(g, i, -1); });
  $$('[data-md]', el).forEach(b => b.onclick = () => { const [g, i] = b.dataset.md.split('|').map(Number); move(g, i, 1); });
  $$('[data-gu]', el).forEach(b => b.onclick = () => { const L = copy(), i = +b.dataset.gu; [L[i - 1], L[i]] = [L[i], L[i - 1]]; save(L); });
  $$('[data-gd]', el).forEach(b => b.onclick = () => { const L = copy(), i = +b.dataset.gd; [L[i + 1], L[i]] = [L[i], L[i + 1]]; save(L); });
  $$('[data-gn]', el).forEach(i => i.onchange = () => safe(async () => {
    const L = copy(), old = L[+i.dataset.gn].name, v = i.value.trim() || old;
    if (L.some((g, k) => k !== +i.dataset.gn && g.name === v)) return toast('같은 이름의 묶음이 있어요', true);
    L[+i.dataset.gn].name = v;
    const f = menuFold(); if (old in f) { f[v] = f[old]; delete f[old]; await setSetting('look.menu_fold', f); }
    save(L);
  }));
  $$('[data-gf]', el).forEach(t => t.onclick = () => safe(async () => { const f = menuFold(); f[lay[+t.dataset.gf].name] = !t.classList.contains('on'); await setSetting('look.menu_fold', f); buildNav(); go('settings', {p: 'menu'}); }));
  $('#addG').onclick = () => { const L = copy(); let n = 1; while (L.some(g => g.name === `새 묶음 ${n}`)) n++; L.push({name: `새 묶음 ${n}`, items: []}); save(L); };
  $('#reset').onclick = () => safe(async () => { await setSetting('menu_hidden', []); await setSetting('menu_layout', []); await setSetting('look.menu_fold', {}); buildNav(); go('settings', {p: 'menu'}); });
};
PANE.look = async el => {
  const L = S.look;
  el.innerHTML = `<div class="card"><div class="card-h"><h2>화면 밝기</h2></div><div class="theme-cards">
      ${[['light', 'l', '밝게', '☀'], ['dark', 'd', '어둡게', '☾'], ['auto', 'a', 'PC 설정 따라', '◐']].map(([k, c, n, i]) => `<div class="thc ${c} ${L.theme === k ? 'on' : ''}" data-set="look.theme" data-val='"${k}"'><div class="pv"><i></i><b></b></div><div class="nm">${n} <span class="faint">${i}</span></div></div>`).join('')}</div></div>
    <div class="card"><div class="card-b" style="padding:8px 0 4px">
      ${srow('왼쪽 메뉴 접기', '아이콘만 남겨 화면을 넓게 · Ctrl+B', sw('look.side_mini', !!L.side_mini))}
      ${srow('닫은 안내 다시 보기', `「알겠어요」로 닫은 안내 ${(L.tips_off || []).length}개`, `<button class="btn sm" id="tipsOn" ${(L.tips_off || []).length ? '' : 'disabled'}>다시 보기</button>`)}
      ${srow('글자 크기', '', seg('look.font', L.font, [['normal', '보통'], ['big', '크게']]))}
      ${srow('표 줄 간격', '', seg('look.dense', L.dense, [[true, '촘촘하게'], [false, '보통']]))}
      ${srow('강조 색', '밝은 화면에서 버튼·표시에 쓰는 색', `<div class="swatches">${['', '#3355ff', '#0d9488', '#7c3aed', '#e11d48'].map(c => `<span class="swatch ${(L.accent === '#3355ff' ? '' : L.accent || '') === c ? 'on' : ''}" data-set="look.accent" data-val='"${c}"' style="background:${c || '#121212'}" title="${c ? c : '흑백 (기본)'}"></span>`).join('')}</div>`)}
    </div></div>`;
  if ($('#tipsOn', el)) $('#tipsOn', el).onclick = () => safe(async () => { await setSetting('look.tips_off', []); toast('닫은 안내를 다시 보여요'); go('settings', {p: 'look'}); });
};
PANE.excel = async el => {
  const x = S.excel;
  const SHEETS = ['요약', '일반내용', '진행내용', '당사자', '기일'];
  el.innerHTML = `<div class="card"><div class="card-h"><h2>엑셀 내보내기</h2></div><div class="card-b" style="padding:8px 0 0">
    ${srow('파일 이름', '{채권}은 채권 이름, {조건}은 조회 이름, {날짜}는 오늘 날짜(YYMMDD)로 바뀌어요', `<input class="inp wide" data-set="excel.name" value="${esc(x.name)}">`)}
    ${srow('넣을 시트', '', `<div class="row-gap">${SHEETS.map(s => `<span class="chip ${x.sheets.includes(s) ? 'now' : 'wait'} pointer" data-sheet="${s}">${s}</span>`).join('')}</div>`)}
    ${srow('새 진행이 생긴 사건만', '조회 결과 엑셀에 달라진 사건만 넣어요', sw('excel.only_changed', x.only_changed))}
    ${srow('저장 폴더', esc(INFO.export_dir), '<button class="btn sm" id="ed">바꾸기</button> <button class="btn sm ghost" id="eo">열기</button>')}
  </div><div class="small muted" style="padding:16px 22px 8px;border-top:1px solid var(--line)">「요약」 시트에 넣을 칸 · 눌러서 켜고 끄기 (켠 순서대로 들어가요)</div>
  <div class="col-list">${INFO.summary_cols.map(c => `<span class="${x.cols.includes(c) ? 'on' : ''}" data-col="${esc(c)}">${esc(c)}</span>`).join('')}</div></div>`;
  $$('[data-sheet]', el).forEach(c => c.onclick = () => safe(async () => { const s = c.dataset.sheet; await setSetting('excel.sheets', x.sheets.includes(s) ? x.sheets.filter(y => y !== s) : x.sheets.concat([s])); go('settings', {p: 'excel'}); }));
  $$('[data-col]', el).forEach(c => c.onclick = () => safe(async () => { const s = c.dataset.col; await setSetting('excel.cols', x.cols.includes(s) ? x.cols.filter(y => y !== s) : x.cols.concat([s])); go('settings', {p: 'excel'}); }));
  $('#ed').onclick = () => safe(async () => { await api('pick_folder_setting', {path: 'save.export_dir'}); await refreshPills(); go('settings', {p: 'excel'}); });
  $('#eo').onclick = () => api('open_path', {path: INFO.export_dir});
};
PANE.sihyo = async el => {
  const x = S.sihyo;
  el.innerHTML = `<div class="card"><div class="card-h"><h2>시효관리 앱 연결</h2>${x.folder ? chip('폴더 정함', 'green') : chip('폴더 안 정함', 'gray')}</div><div class="card-b" style="padding:8px 0 4px">
    ${srow('보낼 폴더', x.folder ? esc(x.folder) : '시효관리 앱이 「사건 한꺼번에 넣기」로 읽는 폴더 · 안 정하면 엑셀 저장 폴더에 만들어요', '<button class="btn sm" id="sf">고르기</button>')}
    ${srow('조회 중 확정된 사건은 자동으로 보내기', '조회가 끝나면 이번에 확정된 사건을 엑셀 파일로 그 폴더에 만들어요', sw('sihyo.auto', x.auto))}
    ${srow('계좌번호로 쓸 칸', '시효 앱에서 같은 계좌를 찾을 때 쓰는 칸', seg('sihyo.key', x.key, [['memo1', '메모 1'], ['memo2', '메모 2']]))}
  </div></div><div class="small muted">보내는 파일: 계좌번호 · 사건번호 · 법원 · 당사자 · 사건명 · 종국결과 · 확정일</div>`;
  $('#sf').onclick = () => safe(async () => { await api('pick_folder_setting', {path: 'sihyo.folder'}); await refreshPills(); go('settings', {p: 'sihyo'}); });
};
PANE.save = async el => {
  const [bk, au] = await Promise.all([api('backups'), api('autostart_get')]);
  el.innerHTML = `<div class="card"><div class="card-h"><h2>시작</h2></div><div class="card-b" style="padding:8px 0 4px">
    ${srow('PC 켤 때 자동으로 실행', au.supported ? `Windows에 로그인하면 「종합관리」가 바로 열려요 · 이 PC의 이 사용자만${au.other ? ' · <b style="color:var(--warn)">다른 위치의 프로그램이 등록돼 있어요 — 켜면 지금 프로그램으로 바꿔요</b>' : ''}` : esc(au.why),
      au.supported ? tg(au.on, 'id="autoOn"') : '<span class="chip wait">회사 PC에서</span>')}
  </div></div>
  <div class="card"><div class="card-h"><h2>저장 · 백업</h2></div><div class="card-b" style="padding:8px 0 4px">
    ${srow('자료 저장 위치', esc(INFO.data_dir) + ' · 사건 대장 · 조회 결과 · 설정', '<button class="btn sm" id="dd">바꾸기</button> <button class="btn sm ghost" id="do">열기</button>')}
    ${srow('자동 백업', '조회가 끝날 때마다 · 최근 것만 남겨요', `${num('save.backups', S.save.backups)}개`)}
    ${srow('지금 백업', '', '<button class="btn sm" id="bn">지금 백업</button>')}
    ${srow('새 판 알림 폴더', S.save.update_folder ? esc(S.save.update_folder) + ' · 여기에 새 판(종합관리_v○.○.○.zip)이 올라오면 알려줘요' : '공용 폴더를 정해 두면 새 판이 올라왔을 때 알려줘요', '<button class="btn sm" id="uf">고르기</button>')}
  </div></div>
  <div class="card"><div class="card-h"><h2>백업에서 되살리기</h2><span class="small muted">되살리기 전 지금 상태도 백업해 둬요</span></div><div class="card-b">${bk.length ? `<table class="tbl">${bk.slice(0, 15).map(b => `<tr><td>${esc(b)}</td><td class="right"><button class="btn sm ghost" data-rs="${esc(b)}">되살리기</button></td></tr>`).join('')}</table>` : '<div class="small faint">아직 백업이 없어요</div>'}</div></div>`;
  if ($('#autoOn')) $('#autoOn').onclick = () => safe(async () => { const st = await api('autostart_set', {on: !au.on}); toast(st.on ? 'PC를 켜면 자동으로 실행돼요' : '자동 실행을 껐어요'); go('settings', {p: 'save'}); });
  $('#dd').onclick = () => safe(async () => { const d = await api('data_dir_change'); if (d) { toast('자료 위치를 바꿨어요'); await refreshPills(); go('settings', {p: 'save'}); } });
  $('#do').onclick = () => api('open_path', {path: INFO.data_dir});
  $('#uf').onclick = () => safe(async () => { await api('pick_folder_setting', {path: 'save.update_folder'}); await refreshPills(); go('settings', {p: 'save'}); });
  $('#bn').onclick = () => safe(async () => { const n = await api('backup_now'); toast('백업했어요: ' + n); go('settings', {p: 'save'}); });
  $$('[data-rs]', el).forEach(b => b.onclick = () => safe(async () => {
    if (!await confirmBox('백업에서 되살리기', `「${esc(b.dataset.rs)}」 때로 사건 대장·결과·설정을 되돌려요.`, '되살리기')) return;
    await api('backup_restore', {name: b.dataset.rs});
    await refreshPills(); applyLook(); toast('되살렸어요'); go('home');
  }));
};
PANE.log = async el => {
  const log = await api('settings_log');
  el.innerHTML = `<div class="card"><div class="card-h"><h2>설정 기록</h2></div><div class="card-b">${log.length ? `<table class="tbl"><tr><th>날짜</th><th>바꾼 것</th><th></th></tr>${log.map((e, i) => `<tr><td class="muted nowrap">${esc(e.at.slice(5, 16))}</td><td class="w">${esc(e.note || e.path)}${e.note ? '' : ` <span class="faint small">${esc(JSON.stringify(e.old)).slice(0, 40)} → ${esc(JSON.stringify(e.new)).slice(0, 40)}</span>`}</td><td class="right"><button class="btn sm ghost" data-u="${i}">되돌리기</button></td></tr>`).join('')}</table>` : '<div class="small faint">아직 바꾼 설정이 없어요</div>'}</div></div>`;
  $$('[data-u]', el).forEach(b => b.onclick = () => safe(async () => { S = await api('settings_undo', {idx: +b.dataset.u}); applyLook(); toast('되돌렸어요'); go('settings', {p: 'log'}); }));
};

// ------------------------------------------------------------------ 시작
async function boot() {
  try {
    INFO = await api('info', {mode: MODE});
  } catch (e) {
    $('#view').innerHTML = empty('프로그램을 시작하지 못했어요', esc(e.message));
    return;
  }
  S = INFO.settings;
  $('#ver').textContent = 'v' + INFO.version;
  drawBook();
  applyLook();
  const start = INFO.running ? 'pick' : (S.todo.start || 'home');
  const hash = decodeURIComponent(location.hash.slice(1)).split('/');  // 점검용: #settings/look, #pick/{"xl":"..."} 처럼 바로 열기
  const harg = hash.slice(1).join('/');
  if (hash[0] && SCREENS[hash[0]]) go(hash[0], harg.startsWith('{') ? JSON.parse(harg) : hash[0] === 'settings' ? {p: harg} : {});
  else go(INFO.counts.cases ? start : 'pick');
  if (MODE === 'browser') setInterval(() => rawCall('ping', {}), 8000);
}
if (MODE === 'browser') boot();
else if (window.pywebview && window.pywebview.api) boot();
else window.addEventListener('pywebviewready', boot);
