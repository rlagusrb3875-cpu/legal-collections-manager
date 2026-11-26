// 현황 콘솔 · 찾기(Ctrl K) · 둘러보기
// ================================================================== 현황 콘솔
SCREENS.console = async v => {
  const d = await api('console');
  const k = d.kpi;
  const tile = (go_, l, val, s, badge = '', arg = null) => `<div class="card con-kpi" data-go="${go_}" ${arg ? `data-arg='${JSON.stringify(arg)}'` : ''}><div class="l">${l}${badge}</div><div class="v num">${val}</div><div class="s">${s}</div></div>`;
  const col = {red: 'var(--bad)', orange: 'var(--warn)', green: 'var(--ok)', blue: 'var(--accent)', gray: 'var(--faint)'};
  const target = i => i.legal ? `data-go="${i.go}" data-arg='${JSON.stringify(i.arg || {})}'` : i.aid ? `data-go="auction_case" data-arg='${JSON.stringify({aid: i.aid, tab: 't3'})}'` : `data-go="case" data-arg='${JSON.stringify({cid: i.cid})}'`;
  const row = i => `<div class="con-todo" ${target(i)} data-key="${esc(i.key)}"><span class="bar" style="background:${col[i.color] || col.blue}"></span>
    <div class="m"><div class="t">${todoTitle(i)}</div><div class="s">${i.date && i.date !== i.due ? `<span>${md(i.date)}</span>` : ''}<span class="tx">${esc(i.text)}</span></div></div>
    ${todoDue(i, false)}
    <button class="con-done" data-cdone="${esc(i.key)}" title="처리함으로 표시">✓ 처리</button></div>`;
  const ago = s => { if (!s) return ''; const t = s.slice(0, 10) === INFO.today ? s.slice(11, 16) : md(s.slice(0, 10)); return t; };
  v.innerHTML = head(`${esc(INFO.book)} · ${fullDate(INFO.today)} (${wd(INFO.today)})${d.last_run ? ' · 마지막 조회 ' + esc(d.last_run.slice(5, 16).replace('-', '.')) : ''}`, '현황 콘솔',
    `<button class="btn" id="conTour">둘러보기</button><button class="btn" id="conFind">⌕ 찾기 <span class="kbd">Ctrl K</span></button><button class="btn primary" data-go="pick">조회하기 →</button>`) +
    `<div class="con-kpis">${tile('home', '확인할 것', k.todo, `오늘·지난 기한·새로 ${k.hot}건`, k.hot ? '<span class="chip bad">급함</span>' : '')}
      ${tile('home', '보정 기한 3일 안', k.soon, `확인할 것 › 보정·송달 ${k.dlv}건`, k.soon ? '<span class="chip warn">D-3</span>' : '', {cat: '보정·송달', today: false})}
      ${tile('home', '회생·파산', k.stop, k.stop_pending ? `멈춤 확인 안 한 것 ${k.stop_pending}건` : '확인할 것 › 회생·파산', k.stop_pending ? '<span class="chip bad">확인</span>' : '', {cat: '회생·파산', today: false})}
      ${tile('home', '배당 할 일', k.dv, k.dv ? `확인할 것 › 배당 · 급한 것 ${k.dv_hot}건` : '확인할 것 › 배당', k.dv_hot ? '<span class="chip bad">발송</span>' : '', {cat: '배당', today: false})}</div>
    <div class="card con-flow">${[['pick', '① 조회', `${d.flow.cases}건`, '사건 대장'], ['home', '② 판단', `${d.flow.todo}건`, '확인할 것'], ['lg_dlv', '③ 보정 관리', `${d.flow.dlv}건`, '송달·보정'],
      ['fm', '④ 서류', `양식 ${d.flow.forms}개`, '회사 양식'], ['cal', '⑤ 기한', `${d.flow.soon}건 임박`, '기일·기한']].map(([g, t, n, s]) => `<div data-go="${g}"><span>${t}</span><b>${n}</b><span class="faint">${s}</span></div>`).join('')}</div>
    <div class="g2"><div class="card" style="overflow:hidden"><div class="card-h" style="padding-bottom:12px"><h2>오늘 할 것</h2><a data-go="home" data-arg='{"today":true,"cat":""}'>모두 보기 →</a></div>
      ${d.today.length ? d.today.map(row).join('') : empty('오늘 할 것이 없어요', d.next_run ? `다음 조회 권장 ${md(d.next_run)} (${wd(d.next_run)})` : '사건을 넣고 조회해 보세요.')}</div>
    <div class="card" style="overflow:hidden"><div class="card-h" style="padding-bottom:12px"><h2>작업 기록</h2><span class="small faint">이 채권에서 한 일</span></div>
      ${d.log.length ? d.log.map(l => `<div class="con-log ${l.go ? 'pointer' : ''}" ${l.go ? `data-go="${esc(l.go)}" data-arg='${JSON.stringify(l.arg || {})}'` : ''}><time>${ago(l.at)}</time><span>${esc(l.text)}${l.by ? ` <span class="faint">· ${esc(l.by)}</span>` : ''}</span></div>`).join('')
        : '<div class="card-b small faint">조회를 마치거나 보정·서류·엑셀 넣기를 하면 여기에 쌓여요.</div>'}</div></div>`;
  $$('[data-cdone]', v).forEach(b => b.onclick = e => { e.stopPropagation(); e.preventDefault(); safe(async () => {
    let note = '';
    if (S.todo.memo_on_done) { note = await modal('처리함으로 표시', '<label class="lb">한 줄 메모 (사건 메모에도 남아요)</label><input class="field" id="m" placeholder="예: 주소보정서 제출함">', [{text: '취소'}, {text: '처리함', cls: 'primary', value: bg => $('#m', bg).value.trim()}]); if (note === null) return; }
    await api('todo_done', {key: b.dataset.cdone, note}); toast('처리함으로 표시했어요 · 「확인할 것 › 처리한 것 보기」에서 되돌릴 수 있어요'); await refreshPills(); go('console', {}, {back: true}); }); });
  $('#conTour').onclick = () => tourStart();
  $('#conFind').onclick = () => palette();
};

// ================================================================== 찾기 (Ctrl K)
const PAL_ACTS = [
  {t: '+ 보정 직접 등록', s: '할 일', run: async () => { await go('lg_dlv'); dlvAdd(); }},
  {t: '보정 관리 엑셀로 내보내기', s: '할 일', run: async () => { await go('lg_dlv'); const b = $('#dlExp'); if (b) b.click(); }},
  {t: '회사 양식으로 서류 만들기', s: '할 일', run: () => go('fm_make', {reset: 1})},
  {t: '엑셀 넣기', s: '할 일', run: () => go('xl', {})},
  {t: '회생·파산 정지·금지·주의 다시 조회', s: '할 일', run: () => safe(async () => { const st = await api('lg_rehab_recheck', {scope: 'blocking'}); go('run', {state: st}); })},
  {t: '오늘 할 것만 보기', s: '할 일', run: () => go('home', {today: true, cat: ''})},
];
function palette() {
  if ($('.pal')) return;
  const screens = $$('#nav button[data-s]').filter(b => !b.classList.contains('hide')).map(b => ({t: [...b.childNodes].filter(x => x.nodeType === 3).map(x => x.textContent).join('').trim(), s: '화면', run: () => go(b.dataset.s)}));
  const bg = document.createElement('div');
  bg.className = 'pal';
  bg.innerHTML = '<div class="box"><input placeholder="화면 · 사건번호 · 당사자 · 채무자 · 할 일 찾기"><div class="list"></div><div class="foot small faint">↑↓ 고르기 · Enter 열기 · Esc 닫기</div></div>';
  document.body.appendChild(bg);
  const inp = $('input', bg), list = $('.list', bg);
  let sel = 0, L = [], seq = 0;
  const draw = async () => {
    const q = inp.value.trim(), my = ++seq;
    const local = screens.concat(PAL_ACTS).filter(i => !q || i.t.replace(/\s/g, '').includes(q.replace(/\s/g, '')));
    let far = [];
    if (q.length >= 2) {
      const r = await api('palette', {q}).catch(() => ({cases: [], debtors: []}));
      if (my !== seq) return;
      far = r.cases.map(c => ({t: c.t, s: '사건', sub: c.s, run: () => go('case', {cid: c.id})})).concat(r.debtors.map(d => ({t: d.t, s: '채무자', sub: d.s, run: () => go('lg_debtors', {did: d.id})})));
    }
    L = local.slice(0, 8).concat(far).slice(0, 14);
    sel = Math.max(0, Math.min(sel, L.length - 1));
    list.innerHTML = L.map((i, k) => `<div class="it ${k === sel ? 'on' : ''}" data-k="${k}"><span>${esc(i.t)}</span>${i.sub ? `<span class="faint small">${esc(i.sub)}</span>` : ''}<small>${i.s}</small></div>`).join('') || '<div class="it faint">찾은 것이 없어요</div>';
  };
  const close = () => bg.remove();
  inp.oninput = () => { sel = 0; clearTimeout(bg.t); bg.t = setTimeout(draw, 120); };
  inp.onkeydown = e => {
    if (e.key === 'ArrowDown') { sel = Math.min(sel + 1, L.length - 1); $$('.it', list).forEach((x, k) => x.classList.toggle('on', k === sel)); e.preventDefault(); }
    if (e.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); $$('.it', list).forEach((x, k) => x.classList.toggle('on', k === sel)); e.preventDefault(); }
    if (e.key === 'Enter' && L[sel]) { e.preventDefault(); close(); L[sel].run(); }
    if (e.key === 'Escape') close();
  };
  bg.onclick = e => { const it = e.target.closest('[data-k]'); if (it) { close(); L[+it.dataset.k].run(); } else if (e.target === bg) close(); };
  draw();
  setTimeout(() => inp.focus(), 20);
}
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k' && !$('.modal-bg')) { e.preventDefault(); palette(); }
});
document.addEventListener('click', e => { if (e.target.closest('#navFind')) palette(); });

// ================================================================== 둘러보기
const TOUR = [
  ['console', '현황 콘솔', '숫자 네 칸과 업무 흐름(조회 → 판단 → 보정 → 서류 → 기한)을 한눈에 봐요. 칸을 누르면 그 화면으로 가요. 왼쪽 위 「찾기」나 Ctrl K로 화면·사건·채무자를 바로 찾아요.'],
  ['pick', '조회하기', '법원·사건번호·당사자를 넣거나 엑셀로 여러 건을 넣고, 법원 사이트의 그림 숫자를 사람이 넣어 조회해요.'],
  ['home', '확인할 것', '보정명령·송달불능·선고·회생·시효가 모여요. 위쪽 묶음과 「오늘 할 것만」으로 걸러요.'],
  ['lg_dlv', '송달·보정 관리', '보정명령 받은 날을 넣으면 기한을 계산해요(쉬는 날이면 다음 평일). 엑셀 넣기·직접 등록·칸 골라 내보내기가 돼요.'],
  ['fm', '서류 작성', '회사 양식 PDF를 그대로 쓰고 바뀌는 칸만 채워요. 검수에서 빈 칸·넘침만 고치고, 인쇄기를 골라 저장해요.'],
  ['lg_rehab', '회생·파산 관리', '관리 가부(가능 · 주의 · 정지 · 금지 · 불가)를 크게 보여줘요. 정지·금지·불가인 채무자는 서류 대상에서 빠져요.'],
  ['cal', '기일·기한', '기일·확정 예상·보정 기한이 한 달력에. 보정 기한은 그 자리에서 「완료」해요.'],
  ['xl', '엑셀 넣기', '엑셀 하나를 넣을 곳(사건 대장 · 원장 · 보정 · 회생 · 서류)에 맞춰 넣어요. 짝지은 열은 다음에 기억해요.'],
  ['settings', '설정', '메뉴 순서·접기, 연결 기준(키), PC 켤 때 자동 실행은 여기서 바꿔요.'],
];
let TI = -1;
function tourStart() { TI = 0; tourShow(); }
async function tourShow() {
  $$('.tour').forEach(t => t.remove());
  if (TI < 0 || TI >= TOUR.length) { TI = -1; return; }
  const [p, t, m] = TOUR[TI];
  await go(p, p === 'settings' ? {p: 'menu'} : p === 'xl' ? {} : {});
  const d = document.createElement('div');
  d.className = 'tour';
  d.innerHTML = `<b>${TI + 1}/${TOUR.length} · ${esc(t)}</b><p>${esc(m)}</p><div class="row-gap"><button class="btn sm ghost" data-t="x">그만</button><span style="flex:1"></span>${TI ? '<button class="btn sm" data-t="p">이전</button>' : ''}<button class="btn sm primary" data-t="n">${TI === TOUR.length - 1 ? '끝' : '다음'}</button></div>`;
  document.body.appendChild(d);
  d.onclick = e => { const b = e.target.closest('[data-t]'); if (!b) return; TI = b.dataset.t === 'x' ? -1 : TI + (b.dataset.t === 'n' ? 1 : -1); if (TI >= TOUR.length) TI = -1; tourShow(); };
}
