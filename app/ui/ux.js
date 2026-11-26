// 사용성 공통 — 안내 한 번만 · 엑셀 단추 묶기 · 조회 탭 · 조회 중 띠 · 이어진 것 · 배당 자세히 다음 줄
// 화면을 그린 뒤(go 다음) 손질하는 방식이라, 각 화면 코드는 그대로 두고 모든 화면에 같은 규칙을 씌운다.

// ------------------------------------------------------------------ 안내는 한 번만 (알겠어요 → 다시 안 보임)
const TIPS = [  // [화면, 안내 글에 들어 있는 말, 기억할 이름]
  ['lg_dlv', '지급명령은 공시송달을', 'dlv_gongsi'],
  ['cal', '보정 기한은 진행내용에', 'cal_dlv'],
  ['lg_rehab', '면책 확정·기각·폐지 확정은', 'rehab_close'],
  ['xl', '각 화면(사건 대장', 'xl_where'],
  ['auction', '「연결된 소송」은', 'auc_link'],
];
const tipsOff = () => (S.look && S.look.tips_off) || [];
function uxTips(v) {
  TIPS.forEach(([scr, word, key]) => {
    if (CUR !== scr) return;
    const el = [...v.querySelectorAll('.notice, .small, .muted, p, div')].find(e => e.children.length < 6 && e.textContent.includes(word) && !e.querySelector('.card'));
    if (!el) return;
    if (tipsOff().includes(key)) { el.remove(); return; }
    if (el.querySelector('.tip-x')) return;
    el.classList.add('has-tip');
    el.insertAdjacentHTML('beforeend', `<button class="tip-x" data-tip="${key}" title="다시 안 보기 · 설정 → 화면에서 다시 켤 수 있어요">알겠어요</button>`);
  });
}
document.addEventListener('click', e => {
  const b = e.target.closest('.tip-x'); if (!b) return;
  e.stopPropagation();
  const el = b.closest('.has-tip'); if (el) el.remove();
  safe(() => setSetting('look.tips_off', [...new Set(tipsOff().concat(b.dataset.tip))]));
});

// ------------------------------------------------------------------ 엑셀 단추: 「엑셀 ▾」(넣기 · 양식) + 「엑셀로 저장」 + 「+ 한 건 넣기」 늘 같은 순서
const XL_IN = /^(엑셀로 넣기|엑셀로 추가·갱신|엑셀 불러오기|엑셀 넣기|공공정보 엑셀|기존 엑셀 대장 가져오기|양식 받기)$/;
const XL_OUT = /^(엑셀로 내보내기|엑셀로 저장|엑셀|통계 엑셀로)$/;
const ADD_NAME = {'+ 한 건 넣기': '+ 한 건 넣기', '+ 직접 등록': '+ 한 건 넣기', '직접 한 줄 넣기': '+ 한 건 넣기', '+ 채무자 추가': '+ 채무자 넣기', '+ 받은 문서 등록': '+ 받은 문서 넣기', '+ 사건 넣기': '+ 사건 넣기'};
const IN_NAME = {'엑셀로 넣기': '엑셀 넣기', '엑셀로 추가·갱신': '엑셀 넣기 (추가·갱신)', '엑셀 불러오기': '엑셀 넣기', '엑셀 넣기': '엑셀 넣기', '공공정보 엑셀': '공공정보 엑셀 넣기',
  '기존 엑셀 대장 가져오기': '기존 엑셀 대장 넣기', '양식 받기': '빈 양식 받기'};
function uxHeadButtons(v) {
  const box = $('.head > .row-gap', v);
  if (!box || box.dataset.ux) return;
  box.dataset.ux = '1';
  const btns = [...box.querySelectorAll(':scope > button')];
  const t = b => b.textContent.trim().replace(/\s+/g, ' ');
  const ins = btns.filter(b => XL_IN.test(t(b)));
  const outs = btns.filter(b => XL_OUT.test(t(b)));
  const adds = btns.filter(b => ADD_NAME[t(b)]);
  if (!ins.length && !outs.length && !adds.length) return;
  // 이름 맞추기
  outs.forEach(b => { b.textContent = '엑셀로 저장'; b.classList.remove('primary', 'blue'); });
  adds.forEach(b => { b.textContent = ADD_NAME[t(b)]; b.classList.add('primary'); b.classList.remove('blue'); });
  btns.filter(b => !adds.includes(b) && b.classList.contains('primary') && (ins.includes(b) || outs.includes(b))).forEach(b => b.classList.remove('primary'));
  // 넣기 · 양식은 한 단추(▾)로
  if (ins.length === 1) {  // 하나뿐이면 그냥 단추로
    ins[0].textContent = IN_NAME[t(ins[0])] || t(ins[0]); ins[0].classList.remove('primary', 'blue'); box.appendChild(ins[0]);
  } else if (ins.length) {
    const dd = document.createElement('div'); dd.className = 'xl-dd';
    dd.innerHTML = `<button class="btn">엑셀 넣기 ▾</button><div class="xl-menu">${ins.map((b, i) => `<button data-i="${i}">${IN_NAME[t(b)] || t(b)}</button>`).join('')}</div>`;
    ins.forEach(b => { b.hidden = true; });
    $('button', dd).onclick = e => { e.stopPropagation(); $$('.xl-dd.open').forEach(x => x !== dd && x.classList.remove('open')); dd.classList.toggle('open'); };
    $$('.xl-menu button', dd).forEach(m => m.onclick = () => { dd.classList.remove('open'); ins[+m.dataset.i].click(); });
    box.appendChild(dd);
  }
  outs.forEach(b => box.appendChild(b));
  adds.forEach(b => box.appendChild(b));  // 맨 오른쪽 = 이 화면에서 가장 자주 쓰는 것
}
document.addEventListener('click', () => $$('.xl-dd.open').forEach(x => x.classList.remove('open')));

// ------------------------------------------------------------------ 조회는 한곳에서 시작 (사건 · 회생·파산 · 배당 · 경매)
const QTABS = [['pick', '사건', '나의사건검색 · 진행내용'], ['lg_rehab', '회생·파산', '관리 가부 (가능 · 정지 · 금지)'], ['dv_run', '배당', '배당기일 · 관련사건 → 키 매칭'], ['auction', '경매', '법원경매정보 · 문건 · 매각기일']];
function uxQTabs(v) {
  if (!['pick', 'lg_rehab', 'dv_run'].includes(CUR) || $('.qtabs', v)) return;
  const h = $('.head', v); if (!h) return;
  h.insertAdjacentHTML('afterend', `<div class="qtabs">${QTABS.map(([s, n, d]) => `<button class="${s === CUR ? 'on' : ''}" data-q="${s}"><b>${n} 조회</b><span>${d}</span></button>`).join('')}</div>`);
  $$('.qtabs button', v).forEach(b => b.onclick = () => { if (b.dataset.q !== CUR) go(b.dataset.q); });
}
// 사건 · 회생·파산 직접 입력 칸은 탭을 오가도 남게
const KEEP = {};
const KEEP_IDS = ['qCourt', 'qNo', 'qParty', 'qCourts', 'rCourt', 'rNo', 'rParty', 'rCourts'];
function uxKeepSave() { if (!['pick', 'lg_rehab'].includes(CUR)) return; const o = {}; KEEP_IDS.forEach(id => { const el = document.getElementById(id); if (el && el.value) o[id] = el.value; }); KEEP[CUR] = o; }
function uxKeepLoad() { const o = KEEP[CUR]; if (!o) return; Object.entries(o).forEach(([id, val]) => { const el = document.getElementById(id); if (el && !el.value) { el.value = val; el.dispatchEvent(new Event('input')); } }); }

// ------------------------------------------------------------------ 조회 중이면 어느 화면에서든 위에 띠
function uxRunStrip(v) {
  const r = INFO.running;
  if (!r || CUR === 'run' || $('.run-strip', v)) return;
  v.insertAdjacentHTML('afterbegin', `<div class="run-strip"><span class="dot"></span><b>조회 중 ${r.done} / ${r.total}</b><span class="muted">${esc(r.name || '')}</span><button class="btn sm primary" data-go="run">이어서 →</button></div>`);
}

// ------------------------------------------------------------------ 이어진 것 (사건 · 채무자 · 배당 어디서 열어도 같은 한 줄)
async function linksBar(args) {
  let L = [];
  try { L = await api('links', args); } catch (e) { return null; }
  if (!L.some(x => !x.on)) return null;  // 자기 자신밖에 없으면 줄을 띄우지 않음
  const el = document.createElement('div');
  el.className = 'lkbar';
  el.innerHTML = `<span class="lkh">이어진 것</span>${L.map((x, i) => `<button class="lkc ${x.on ? 'on' : ''} ${x.warn ? 'warn' : ''}" data-i="${i}" title="${esc(x.k)} 열기${x.list && x.list.length > 1 ? ' · ' + x.list.map(y => y.t).join(', ') : ''}"><span>${esc(x.k)}</span>${esc(x.v)}</button>`).join('')}`;
  $$('.lkc', el).forEach(b => b.onclick = e => {
    e.stopPropagation();
    const x = L[+b.dataset.i];
    if (x.list && x.list.length > 1) {  // 사건이 여럿이면 골라서
      $$('.lk-menu').forEach(m => m.remove());
      const m = document.createElement('div'); m.className = 'lk-menu';
      m.innerHTML = x.list.map((y, j) => `<button data-j="${j}">${esc(y.t)}</button>`).join('');
      const r = b.getBoundingClientRect(); m.style.left = r.left + 'px'; m.style.top = (r.bottom + 4) + 'px';
      document.body.appendChild(m);
      $$('button', m).forEach(y => y.onclick = () => { m.remove(); const z = x.list[+y.dataset.j]; closeDvDrawer(); go(z.go, z.arg); });
      setTimeout(() => document.addEventListener('click', () => m.remove(), {once: true}), 0);
      return;
    }
    if (x.on) return;
    closeDvDrawer(); go(x.go, x.arg);
  });
  return el;
}
function closeDvDrawer() { const d = $('#dvDrawer'); if (d) d.classList.remove('on', 'wide'); }
async function uxLinks(v, a) {
  if (CUR === 'case' && a.cid) { const b = await linksBar({cid: a.cid}); const h = $('.head', v); if (b && h && !$('.lkbar', v)) h.after(b); }
  if (CUR === 'lg_debtors' && a.did) {
    const card = $('#pClose') && $('#pClose').closest('.card');
    const b = await linksBar({did: a.did});
    if (b && card && !$('.lkbar', card)) { b.classList.add('in-card'); const first = card.firstElementChild; first.after(b); }
  }
}

// ------------------------------------------------------------------ 배당 자세히 창: 이어진 것 + ‹ 앞 줄 · 다음 줄 › (↑↓)
if (typeof dvRowOpen === 'function') {
  const _open = dvRowOpen;
  dvRowOpen = async function (id, lq) {
    const r = await _open(id, lq);
    const d = $('#dvDrawer'); if (!d) return r;
    const db = $('.dv-db', d);
    $$('.dv-grid tr.dv-cur').forEach(t => t.classList.remove('dv-cur'));
    const tr = document.querySelector(`.dv-grid tr[data-lr="${CSS.escape(id)}"]`); if (tr) { tr.classList.add('dv-cur'); tr.scrollIntoView({block: 'nearest'}); }
    const ids = (typeof DVL !== 'undefined' && DVL.rows) ? DVL.rows.map(x => x.id) : [];
    const i = ids.indexOf(id);
    if (i >= 0 && !$('.dv-nav', d)) {
      const nav = document.createElement('div'); nav.className = 'dv-nav';
      nav.innerHTML = `<button class="btn sm" data-dn="-1" ${i ? '' : 'disabled'}>‹ 앞 줄</button><span class="small faint">${i + 1} / ${ids.length} · ↑↓</span><button class="btn sm" data-dn="1" ${i < ids.length - 1 ? '' : 'disabled'}>다음 줄 ›</button>`;
      $$('[data-dn]', nav).forEach(b => b.onclick = () => dvRowOpen(ids[i + +b.dataset.dn]));
      (db || d).prepend(nav);
    }
    if (db && !$('.lkbar', db)) { const b = await linksBar({dv: id}); if (b) { b.classList.add('in-card'); const nav = $('.dv-nav', db); (nav || db.firstChild) && (nav ? nav.after(b) : db.prepend(b)); } }
    d.dataset.cur = id;
    return r;
  };
  document.addEventListener('keydown', e => {
    const d = $('#dvDrawer');
    if (!d || !d.classList.contains('on') || !d.dataset.cur || /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || '') || $('.modal-bg')) return;
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    const b = $(`.dv-nav [data-dn="${e.key === 'ArrowDown' ? 1 : -1}"]`, d);
    if (b && !b.disabled) { e.preventDefault(); b.click(); }
  });
}

// ------------------------------------------------------------------ 확인할 것: 줄 누르면 자세히 · 여러 줄 한꺼번에 · 키보드
const TSEL = new Set();
function uxHome(v, a) {
  if (CUR !== 'home') return;
  const rows = $$('.todo', v);
  rows.forEach(el => {
    const k = el.dataset.key;
    if (!el.querySelector('.tsel')) el.insertAdjacentHTML('afterbegin', `<input type="checkbox" class="cbx tsel" title="골라서 한꺼번에 처리" ${TSEL.has(k) ? 'checked' : ''}>`);
    const det = [...el.querySelectorAll('button')].find(b => b.textContent.trim() === '자세히');
    if (det) { det.classList.add('ux-det', 'ghost'); }
    // 고르기(앞 칸)와 처리(✓)가 붙어 있으면 잘못 누르기 쉬워서, 처리는 오른쪽 끝 단추로
    const chk = $('.chk', el);
    if (chk && !el.classList.contains('done') && !chk.classList.contains('chk-r')) { chk.classList.add('chk-r'); chk.textContent = '✓ 처리'; chk.title = '처리함으로 표시 (Space)'; el.appendChild(chk); }
    else if (chk && el.classList.contains('done')) chk.hidden = true;
    $$('[data-act="due"]', el).forEach(b => { if (b.textContent.trim() === '기한') { b.textContent = '기한 넣기'; } });
    $('.m', el).onclick = e => { if (e.target.closest('button,a,input')) return; if (det) det.click(); };
    $('.m', el).style.cursor = 'pointer';
    $('.tsel', el).onclick = e => { e.stopPropagation(); e.target.checked ? TSEL.add(k) : TSEL.delete(k); uxBulk(v, a); };
  });
  const list = $('.g2 > .card', v);
  if (list && rows.length && !$('.kbd-foot', list)) list.insertAdjacentHTML('beforeend', '<div class="kbd-foot"><span class="kbd-hint" title="마우스 없이 처리할 수 있어요"><kbd>↑↓</kbd> 이동 <kbd>Space</kbd> 처리 <kbd>Enter</kbd> 자세히 <kbd>X</kbd> 고르기</span></div>');
  uxBulk(v, a);
}
function uxBulk(v, a) {
  let bar = $('.todo-bulk', v);
  const keys = [...TSEL].filter(k => v.querySelector(`.todo[data-key="${CSS.escape(k)}"]`));
  if (!keys.length) { if (bar) bar.remove(); return; }
  if (!bar) { bar = document.createElement('div'); bar.className = 'todo-bulk'; const f = $('.g2 .card .filters', v); (f || $('.g2', v)).after(bar); }
  bar.innerHTML = `<b>${keys.length}개 고름</b><button class="btn sm" data-b="done">✓ 처리함</button><button class="btn sm" data-b="due">기한 넣기</button><button class="btn sm ghost" data-b="all">보이는 것 모두</button><button class="btn sm ghost" data-b="clr">고르기 풀기</button>`;
  $$('[data-b]', bar).forEach(b => b.onclick = () => safe(async () => {
    const k = b.dataset.b;
    if (k === 'clr') { TSEL.clear(); return go('home', a, {back: true}); }
    if (k === 'all') { $$('.todo:not(.done)', v).forEach(el => TSEL.add(el.dataset.key)); return go('home', a, {back: true}); }
    if (k === 'done') { for (const key of keys) await api('todo_done', {key, note: ''}); toast(`${keys.length}개를 처리함으로 표시했어요 · 「처리한 것 보기」에서 되돌릴 수 있어요`); }
    if (k === 'due') {
      const date = await modal('기한 넣기', `<div class="small muted mb16">고른 ${keys.length}개에 같은 기한을 넣어요</div><label class="lb">기한 날짜</label><input class="field" type="date" id="dt">`, [{text: '취소'}, {text: '저장', cls: 'primary', value: bg => $('#dt', bg).value || false}]);
      if (!date) return;
      for (const key of keys) await api('deadline_set', {key, date});
      toast('기한을 넣었어요');
    }
    TSEL.clear(); await refreshPills(); go('home', a, {back: true});
  }));
}
// 키보드: ↑↓ 이동 · Space 처리함 · Enter 자세히 · X 고르기
document.addEventListener('keydown', e => {
  if (CUR !== 'home' || $('.modal-bg') || /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || '') || e.ctrlKey || e.metaKey || e.altKey) return;
  const rows = $$('#view .todo'); if (!rows.length) return;
  let i = rows.findIndex(r => r.classList.contains('kf'));
  const set = j => { rows.forEach(r => r.classList.remove('kf')); const r = rows[Math.max(0, Math.min(rows.length - 1, j))]; r.classList.add('kf'); r.scrollIntoView({block: 'nearest'}); };
  if (e.key === 'ArrowDown' || e.key === 'j') { e.preventDefault(); set(i + 1); }
  else if (e.key === 'ArrowUp' || e.key === 'k') { e.preventDefault(); set(i < 0 ? 0 : i - 1); }
  else if (i >= 0 && e.key === ' ') { e.preventDefault(); const c = $('[data-act="done"]', rows[i]); if (c) c.click(); }
  else if (i >= 0 && e.key === 'Enter') { e.preventDefault(); const d = $('.ux-det', rows[i]); if (d) d.click(); }
  else if (i >= 0 && (e.key === 'x' || e.key === 'X')) { e.preventDefault(); const c = $('.tsel', rows[i]); if (c) c.click(); }
});

// ------------------------------------------------------------------ go 다음에 손질
const _goUx = go;
go = async function (id, args, opt) {
  uxKeepSave();
  if (id !== 'home') TSEL.clear();
  const r = await _goUx(id, args, opt);
  const v = $('#view'), a = args || {};
  try {
    $$('.card > .filters', v).forEach(f => f.parentElement.style.setProperty('--fh', f.offsetHeight + 'px'));
    uxRunStrip(v); uxQTabs(v); uxHeadButtons(v); uxTips(v); uxHome(v, a); uxKeepLoad();
    await uxLinks(v, a);
  } catch (e) { console.warn('ux', e); }
  return r;
};
