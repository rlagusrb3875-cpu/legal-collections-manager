/* 종합관리 — 경매 (법원경매정보) 화면. app.js 다음에 읽는다. */
'use strict';
// ================================================================== 경매 (법원경매정보)
let AU_TIMER = null;
const AU_SEL = new Set();  // 경매 조회 중 「이번 조회」에서 고른 사건
const ptagOf = k => /채권자/.test(k) ? 'cr' : /채무자|소유자/.test(k) ? 'db' : /법원|집행관|감정인|등기/.test(k) ? 'ct' : '';
function auStop() { if (AU_TIMER) { clearInterval(AU_TIMER); AU_TIMER = null; } }
SCREENS.auction = async (v, a) => {
  auStop();
  const arch = !!a.archived;
  const [list, st, aruns] = await Promise.all([api('auction_list', {archived: arch}), api('auction_state'), api('auction_runs')]);
  const paused = !st.active && aruns.find(r => !r.finished && r.done < r.total);
  const f = a.f || '';
  const q = (a.q || '').trim();
  const today = INFO.today;
  const soon = x => x.next_sale?.date && x.next_sale.date >= today && x.next_sale.date <= new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 10);
  const groups = {
    '': () => true, run: x => x.status && !/종국|취하|각하|기각|정지|배당/.test(x.status) && x.color !== 'gray', soon, newdoc: x => x.new_docs > 0,
    sold: x => x.color === 'green', end: x => x.color === 'gray', none: x => !x.last_checked || x.last_result === 'notfound',
  };
  const names = {'': '전체', run: '진행 중', soon: '매각기일 14일 안', newdoc: '새 문건·송달', sold: '매각·배당', end: '종국', none: '조회 전·못 찾음'};
  const rows = list.filter(groups[f] || groups['']).filter(x => !q || [x.case_no, x.court, x.debtor, x.memo1, x.csNm, x.last_doc?.text].join(' ').includes(q));
  const first = list.filter(soon).map(x => x.next_sale.date).sort()[0];
  v.innerHTML = head(`${esc(INFO.book)} · 법원경매정보 화면을 프로그램 안에서 열어 가져와요`, `${arch ? '경매 보관함' : '경매 사건'} <span class="faint" style="font-weight:500">${list.length}</span>`,
      `<button class="btn ghost" data-go="auction" data-arg='${JSON.stringify({archived: !arch})}'>${arch ? '← 경매 사건' : '보관함'}</button><button class="btn" id="auAdd">+ 사건 넣기</button><button class="btn" id="auXl">엑셀로 넣기</button><button class="btn primary" id="auAll" ${list.length && !arch ? '' : 'disabled'}>↻ 전체 조회</button>`) +
    (paused ? `<div class="notice info">멈춘 경매 조회가 있어요 · ${esc(paused.created.slice(5, 16))} ${paused.done} / ${paused.total}건 <a id="auResume">이어서 조회</a></div>` : '') +
    `<div id="auRun"></div>` +
    (arch ? '' : `<div class="stats">
      <div class="card stat pointer" data-af="run"><div class="l"><i style="background:var(--accent)"></i>진행 중</div><div class="v num">${list.filter(groups.run).length}<small>건</small></div></div>
      <div class="card stat pointer" data-af="soon"><div class="l"><i style="background:var(--warn)"></i>매각기일 14일 안</div><div class="v num">${list.filter(soon).length}<small>건</small></div><div class="d">${first ? `가장 빠른 ${md(first)} (${wd(first)})` : '&nbsp;'}</div></div>
      <div class="card stat pointer" data-af="sold"><div class="l"><i style="background:var(--ok)"></i>매각 · 배당</div><div class="v num">${list.filter(groups.sold).length}<small>건</small></div></div>
      <div class="card stat pointer" data-af="newdoc"><div class="l"><i style="background:var(--bad)"></i>새 문건 · 송달</div><div class="v num">${list.filter(groups.newdoc).length}<small>건</small></div><div class="d">지난 조회 이후</div></div></div>`) +
    `<div class="card" style="overflow:hidden">
      <div class="filters">${Object.entries(names).map(([k, n]) => `<button class="f ${f === k ? 'on' : ''}" data-af="${k}">${n}<em>${list.filter(groups[k]).length}</em></button>`).join('')}<input class="search" id="auQ" placeholder="사건번호·채무자·메모 찾기" value="${esc(q)}"></div>
      <div class="sel-bar" id="auSel" hidden><b id="auSelN"></b><button class="btn sm" id="auSelRun">고른 사건 조회</button><button class="btn sm" id="auSelXl">엑셀로 저장</button><button class="btn sm" id="auSelArch">${arch ? '경매 사건으로 되돌리기' : '보관함으로'}</button><button class="btn sm danger" id="auSelDel">삭제</button></div>
      ${rows.length ? `<div class="card-b" style="padding:10px 8px 8px"><table class="tbl"><tr><th><input type="checkbox" class="cbx" id="auAllCb"></th><th>사건</th><th>사건명 · 청구금액</th><th>진행</th><th>다음 매각기일 · 최저가</th><th>최근 문건 · 송달</th><th>연결된 소송</th></tr>
        ${rows.map(x => `<tr class="click" data-aid="${x.id}"><td><input type="checkbox" class="cbx" data-asel="${x.id}"></td>
          <td class="case"><b class="num">${esc(x.case_no)}</b><small>${esc(x.court.replace('지방법원', ''))}${x.jdbn ? ' ' + esc(x.jdbn) : ''}${x.debtor ? ' · ' + esc(x.debtor) : ''}${x.memo1 ? ' · ' + esc(x.memo1) : ''}</small></td>
          <td>${esc(x.csNm || '')}${x.claim ? `<div class="small muted">${esc(x.claim)}</div>` : ''}</td>
          <td>${x.status ? chip(x.status, x.color) : x.last_result === 'notfound' ? chip('찾을 수 없음', 'red') : chip('조회 전', 'gray')}</td>
          <td class="price">${x.next_sale?.date ? `<b>${md(x.next_sale.date)} (${wd(x.next_sale.date)}) ${esc(x.next_sale.time || '')}</b><small>최저 ${esc(x.next_sale.price || '')}</small>` : '<span class="faint">—</span>'}</td>
          <td class="w" style="max-width:300px">${x.last_doc?.date ? `<span class="lp ${x.new_docs ? 'hot' : ''}">${md(x.last_doc.date)} ${esc(x.last_doc.text)}</span>` : '<span class="faint">—</span>'}${x.new_docs ? ` <span class="newdot">새 ${x.new_docs}</span>` : ''}</td>
          <td>${(x.linked || []).map(l => `<span class="link-chip" title="${l.why === '관련사건' ? '경매의 관련사건 번호와 같아요' : '메모(계좌번호)가 같아요'}" data-go="case" data-arg='${JSON.stringify({cid: l.cid})}'>${esc(l.case_no)}</span>`).join(' ') || '<span class="faint">—</span>'}</td></tr>`).join('')}</table></div>`
        : empty(list.length ? '맞는 사건이 없어요' : '경매 사건이 없어요', list.length ? '다른 보기를 골라 보세요.' : '「+ 사건 넣기」로 법원과 「2025타경12345」 모양의 사건번호를 넣거나, 엑셀 파일을 넣어 주세요.', list.length ? '' : '<button class="btn primary" id="auAdd2">+ 사건 넣기</button>')}</div>
    <div class="small muted mt16">「연결된 소송」: 메모(계좌번호 — 하이픈·띄어쓰기는 무시)가 사건 대장의 「메모 1」과 같거나, 경매의 관련사건 번호가 사건 대장에 있으면 이어져요.</div>`;
  $$('[data-af]', v).forEach(el => el.onclick = () => go('auction', {archived: arch, f: el.dataset.af === f ? '' : el.dataset.af, q}));
  const qi = $('#auQ');
  qi.oninput = () => { clearTimeout(qi._t); qi._t = setTimeout(() => go('auction', {archived: arch, f, q: qi.value}).then(() => { const n = $('#auQ'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }), 300); };
  $$('tr[data-aid]', v).forEach(tr => tr.onclick = e => { if (!e.target.closest('input,.link-chip')) go('auction_case', {aid: tr.dataset.aid}); });
  const selected = () => $$('[data-asel]:checked', v).map(x => x.dataset.asel);
  const upd = () => { const n = selected().length; $('#auSel').hidden = !n; $('#auSelN').textContent = `${n}건 골랐어요`; };
  $$('[data-asel]', v).forEach(x => x.onchange = upd);
  if ($('#auAllCb')) $('#auAllCb').onchange = e => { $$('[data-asel]', v).forEach(x => x.checked = e.target.checked); upd(); };
  $('#auSelRun').onclick = () => auStart(selected());
  $('#auSelXl').onclick = () => safe(async () => { const p = await api('auction_export', {ids: selected()}); toast('저장했어요: ' + p.split(/[\\/]/).pop()); });
  $('#auSelArch').onclick = () => safe(async () => { const n = await api('auction_archive', {ids: selected(), archived: !arch}); toast(`${n}건 옮겼어요`); go('auction', {archived: arch}); });
  $('#auSelDel').onclick = () => safe(async () => {
    const ids = selected();
    if (!await confirmBox('경매 사건 삭제', `고른 <b>${ids.length}건</b>을 경매 사건·저장된 결과·할 일·조회 기록에서 지워요.<br>지우기 전에 자동 백업을 남겨요 (설정 → 저장·백업에서 되살리기).`, `${ids.length}건 삭제`)) return;
    const n = await api('auction_delete', {ids});
    toast(`${n}건을 지웠어요`);
    go('auction', {archived: arch, f, q});
  });
  $('#auAll').onclick = () => auStart(null);
  if ($('#auResume')) $('#auResume').onclick = () => safe(async () => { const s2 = await api('auction_start', {rid: paused.id}); auDrawRun(s2); go('auction', ARGS).then(() => auDrawRun(s2)); });
  $('#auAdd').onclick = auAddDialog;
  if ($('#auAdd2')) $('#auAdd2').onclick = auAddDialog;
  $('#auXl').onclick = () => safe(async () => {
    const p = await chooseExcel();
    if (!p) return;
    const r = await api('auction_import', {path: p});
    toast(`새로 ${r.added}건 · 이미 있던 ${r.same}건${r.bad.length ? ` · 못 읽은 줄 ${r.bad.length}` : ''}`);
    go('auction', {});
  });
  if (st.active) auDrawRun(st);
};
async function auAddDialog() {
  const r = await modal('경매 사건 넣기', `<div class="small muted mb16">한 줄에 한 건 · <b>법원 · 사건번호 (· 메모)</b> — 엑셀에서 복사해 붙여넣어도 돼요</div>
    <textarea class="field" id="t" rows="7" placeholder="서울중앙지방법원	2024타경4354	110-23-5521&#10;수원지법 성남지원, 2025타경12345&#10;인천지방법원 2025타경7781 계좌 301-77-0912"></textarea><div class="small mt8" id="i"></div>`,
    [{text: '취소'}, {text: '넣기', cls: 'primary', value: async bg => {
      const res = await api('auction_add', {text: $('#t', bg).value});
      if (!res.added && !res.same) { $('#i', bg).innerHTML = `<span class="err">${esc(res.bad[0]?.problem || '넣을 사건이 없어요')}</span>`; return false; }
      return res;
    }}], true);
  if (!r) return;
  toast(`새로 ${r.added}건${r.same ? ` · 이미 있던 ${r.same}건` : ''}${r.bad.length ? ` · 못 읽은 줄 ${r.bad.length}` : ''}`);
  go('auction', {});
}
setTimeout(() => document.addEventListener('input', async e => {
  if (e.target.id !== 't' || !e.target.closest('.modal')) return;
  const box = e.target.closest('.modal').querySelector('#i');
  if (!box || !e.target.placeholder.includes('타경')) return;
  clearTimeout(e.target._t);
  e.target._t = setTimeout(async () => {
    const r = await safe(() => api('auction_check', {text: e.target.value}));
    if (r) box.innerHTML = `<span class="ok-t">넣을 사건 ${r.good.length}건</span>${r.bad.length ? ` · <span class="err">못 읽은 줄 ${r.bad.length}: ${r.bad.slice(0, 2).map(b => `${b.line}줄 ${esc(b.problem)}`).join(', ')}</span>` : ''}`;
  }, 300);
}), 0);
async function auStart(ids) {
  await safe(async () => {
    const st = await api('auction_start', {ids});
    toast('법원경매정보 창을 열었어요. 그 창에서 「검색」을 눌러 주세요');
    if (CUR !== 'auction') await go('auction', {});
    auDrawRun(st);
  });
}
function auDrawRun(st) {
  const box = $('#auRun');
  if (!box) return;
  if (!st.active) { box.innerHTML = ''; auStop(); return; }
  const P = st.parts || {};
  const steps = [['gnrl', '사건내역'], ['dates', '기일내역'], ['docs', '문건/송달내역']];
  const guide = {
    load: '법원경매정보 검색 화면으로 돌아가는 중이에요…',
    wait: st.auto_search ? '사건번호를 넣고 <b>「검색」</b>을 눌렀어요 · 결과를 기다리는 중…' : '법원경매정보 창에서 <b>「검색」</b>을 눌러 주세요',
    tabs: '기일내역 · 문건/송달내역을 여는 중이에요…',
    saved: st.msg ? esc(st.msg) : (st.wait ? `저장했어요 · ${st.wait}초 뒤 다음 사건` : '저장했어요'),
    robot: '법원경매정보가 자동 접속으로 판단했어요 · 잠시 쉬었다가 「다시 시도」',
    closed: '법원경매정보 창이 닫혔어요 · 「다시 시도」를 누르면 다시 열어요',
    finished: `${st.total}건 조회를 마쳤어요`,
  }[st.phase] || '';
  const cur = st.current;
  [...AU_SEL].forEach(a => { if (!st.done.some(d => d.aid === a)) AU_SEL.delete(a); });
  const dn = st.done.slice().reverse();
  box.innerHTML = `<div class="au-run ${FOLD.au ? 'side-folded' : ''}"><div class="card" style="padding:20px 24px">
      <div class="row-gap" style="justify-content:space-between"><div><div class="small muted">경매 조회 ${Math.min(st.idx + 1, st.total)} / ${st.total}${cur ? ` · ${esc(cur.court)}` : ''}</div>
        <div class="case-no num" style="font-size:24px;margin:4px 0">${cur ? esc(cur.case_no) : '끝'}</div></div>
        <div class="row-gap">${st.phase === 'finished' ? '<button class="btn primary" id="auDone">닫기</button>' : `<button class="btn sm" id="auRetry">다시 시도</button><button class="btn sm" id="auSkip">건너뛰기</button><button class="btn sm" id="auWin">창 보기</button><button class="btn sm ghost" id="auStopB">멈추기</button>`}</div></div>
      <div class="au-guide ${st.phase === 'robot' ? 'err' : ''}">${guide}</div>
      ${st.phase !== 'finished' ? `<div class="au-steps">${steps.map(([k, n]) => `<span class="${P[k] ? 'ok' : (st.phase === 'tabs' || st.phase === 'wait') ? 'now' : ''}">${P[k] ? '✓ ' : ''}${n}</span>`).join('')}</div>` : ''}
      ${st.msg && st.phase !== 'saved' ? `<div class="small muted mt8">${esc(st.msg)}</div>` : ''}
    </div><div class="side-col run-side ${FOLD.au ? 'folded' : ''}" id="auSide"><button class="fold-btn" id="auFold" title="${FOLD.au ? '목록 펼치기' : '목록 접기'}">${FOLD.au ? `‹ 목록 펼치기 <b>${st.done.length}</b>` : '오른쪽 목록 접기 ›'}</button>
      <div class="card fold-card ${FOLD.au_list ? 'closed' : ''}"><div class="card-h"><h2 class="fold-h" id="auFoldH">이번 조회 <span class="small muted">${st.done.length}건</span></h2><div class="row-gap">${!dn.length ? '' : AU_SEL.size
        ? `<button class="btn sm primary" id="auRm">선택 빼기 ${AU_SEL.size}</button><button class="btn sm ghost" id="auRmNone">해제</button>`
        : `<button class="btn sm ghost" id="auRmAll">전체 선택</button><button class="btn sm" id="auRmClear">비우기</button>`}</div></div>
      <div class="done-list" style="max-height:170px">${dn.map(d => `<div class="dl ${AU_SEL.has(d.aid) ? 'picked' : ''}" data-go="auction_case" data-arg='${JSON.stringify({aid: d.aid})}'><input type="checkbox" class="cbx ck" data-auck="${d.aid}" ${AU_SEL.has(d.aid) ? 'checked' : ''} title="골라서 빼기"><div class="m"><b class="num">${esc(d.case_no)}</b></div>${d.state === 'ok' ? (d.new ? `<span class="newdot">새 ${d.new}</span>` : chip('저장', 'green')) : chip(d.state === 'notfound' ? '없음' : '건너뜀', d.state === 'notfound' ? 'red' : 'gray')}</div>`).join('') || '<div class="small faint" style="padding:10px 14px">아직 없어요</div>'}</div></div></div></div>`;
  const keepFold = () => { try { localStorage.setItem('run-fold', JSON.stringify(FOLD)); } catch (e) { /* 저장 못 해도 화면은 그대로 */ } auDrawRun(st); };
  $('#auFold').onclick = () => { FOLD.au = !FOLD.au; keepFold(); };
  $('#auFoldH').onclick = () => { FOLD.au_list = !FOLD.au_list; keepFold(); };
  $$('[data-auck]', box).forEach(c => c.onclick = e => { e.stopPropagation(); c.checked ? AU_SEL.add(c.dataset.auck) : AU_SEL.delete(c.dataset.auck); auDrawRun(st); });
  const auRm = (args, msg) => safe(async () => { const r = await api('auction_run_remove', args); AU_SEL.clear(); toast(msg); auDrawRun(r); });
  const on = (id, fn) => { const x = $('#' + id, box); if (x) x.onclick = fn; };
  on('auRmAll', () => { dn.forEach(d => AU_SEL.add(d.aid)); auDrawRun(st); });
  on('auRmNone', () => { AU_SEL.clear(); auDrawRun(st); });
  on('auRm', () => auRm({aids: [...AU_SEL]}, `${AU_SEL.size}건을 이번 조회 목록에서 뺐어요`));
  on('auRmClear', () => auRm({scope: 'done'}, `${dn.length}건을 이번 조회 목록에서 비웠어요`));
  const b = id => $('#' + id, box);
  if (b('auDone')) b('auDone').onclick = () => safe(async () => { await api('auction_stop'); go('auction', ARGS); });
  if (b('auRetry')) b('auRetry').onclick = () => safe(async () => auDrawRun(await api('auction_retry')));
  if (b('auSkip')) b('auSkip').onclick = () => safe(async () => auDrawRun(await api('auction_next', {skip: true})));
  if (b('auWin')) b('auWin').onclick = () => safe(() => api('auction_window'));
  if (b('auStopB')) b('auStopB').onclick = () => safe(async () => { await api('auction_stop'); auStop(); go('auction', ARGS); });
  if (!AU_TIMER && st.phase !== 'finished') {
    let lastDone = st.done.length;
    AU_TIMER = setInterval(async () => {
      if (CUR !== 'auction') { auStop(); return; }
      try {
        const s2 = await api('auction_state');
        if (s2.done.length !== lastDone || s2.phase === 'finished') { lastDone = s2.done.length; auStop(); await go('auction', ARGS); return; }
        auDrawRun(s2);
      } catch (e) { auStop(); }
    }, 900);
  }
  if (st.phase === 'finished') auStop();
}

SCREENS.auction_case = async (v, a) => {
  auStop();
  const d = await api('auction_detail', {aid: a.aid});
  const c = d.case;
  const tab = a.tab || 't1';
  const ns = c.next_sale || {};
  const newDocs = d.docs.filter(x => x.new).length + d.dlvr.filter(x => x.new).length;
  const who = a.who || '';
  const whoList = ['채권자', '채무자·소유자', '이해관계인', '법원·집행관·감정인'];
  const docsF = d.docs.filter(x => !who || (who === '새로' ? x.new : x.who === who));
  const dlvrF = d.dlvr.filter(x => !who || (who === '새로' ? x.new : x.who === who));
  const dq = (a.dq || '').trim();
  const fq = x => !dq || x.text.includes(dq);
  v.innerHTML = `<div class="head"><div><div class="crumb"><a data-go="auction">경매 사건</a> · 법원경매정보${c.last_checked ? ' · ' + esc(c.last_checked.slice(0, 16)) + ' 조회' : ''}</div>
      <div class="detail-head"><h1 class="num">${esc(c.case_no)}</h1>${c.status ? chip(c.status, c.color) : chip('조회 전', 'gray')}${c.new_docs ? `<span class="newdot">새 문건·송달 ${c.new_docs}</span>` : ''}</div>
      <div class="muted" style="margin-top:6px">${esc(c.court)}${c.csNm ? ' · ' + esc(c.csNm) : ''}${c.debtor ? ' · 채무자 ' + esc(c.debtor) : ''}${d.linked.length ? ' · 연결된 소송 ' + d.linked.map(l => `<a data-go="case" data-arg='${JSON.stringify({cid: l.cid})}'>${esc(l.case_no)}</a>`).join(', ') : ''}</div></div>
    <div class="row-gap"><button class="btn" id="aMemo">메모</button><button class="btn" id="aNow">↻ 지금 다시 조회</button><button class="btn primary" id="aXl">엑셀</button></div></div>
    ${d.checked ? `<div class="au-sum">
      <div><span>청구금액</span><b class="num">${esc(c.claim || '—')}</b></div>
      <div><span>접수 · 개시결정</span><b>${esc((d.basic.find(b => b.label === '접수일자') || {}).value || '—')}</b><div class="small muted">${esc((d.basic.find(b => b.label === '개시결정일자') || {}).value || '')}</div></div>
      <div><span>담당</span><b>${esc(c.jdbn || '—')}</b></div>
      <div><span>배당요구종기</span><b>${esc(d.demand[0]?.date || '—')}</b></div>
      <div><span>다음 매각기일</span><b style="color:${ns.date && (new Date(ns.date) - new Date(INFO.today)) / 864e5 <= (S.todo.hot_days || 3) ? 'var(--bad)' : 'var(--text)'}">${ns.date ? `${md(ns.date)} (${wd(ns.date)}) ${esc(ns.time || '')}` : '—'}</b></div>
      <div><span>최저매각가격</span><b class="num">${esc(ns.price || '—')}</b></div></div>
    <div class="au-tabs"><button data-t="t1" class="${tab === 't1' ? 'on' : ''}">사건내역</button><button data-t="t2" class="${tab === 't2' ? 'on' : ''}">기일내역</button><button data-t="t3" class="${tab === 't3' ? 'on' : ''}">문건/송달내역${newDocs ? `<em>새 ${newDocs}</em>` : ''}</button></div>
    ${tab === 't1' ? `<div class="g2e mb16" style="grid-template-columns:1fr 1fr">
        <div class="card"><div class="card-h"><h2>사건기본내역</h2></div><div class="card-b"><div class="gen-grid">${d.basic.map(b => `<div><span>${esc(b.label)}</span>${esc(b.value)}</div>`).join('')}${d.basic.length % 2 ? '<div></div>' : ''}</div></div></div>
        <div class="card"><div class="card-h"><h2>배당요구종기내역</h2></div><div class="card-b">
          ${d.demand.length ? `<table class="list-tbl"><tr><th>목록</th><th>소재지</th><th>배당요구종기일</th></tr>${d.demand.map(x => `<tr><td>${esc(x.seq)}</td><td>${esc(x.addr)}</td><td><b>${esc(x.date)}</b></td></tr>`).join('')}</table>` : '<div class="small faint">없음</div>'}
          <div class="sub-h">관련사건 · 중복/병합/이송</div>${d.related.length ? `<table class="list-tbl"><tr><th>법원</th><th>사건번호</th><th>구분</th></tr>${d.related.map(x => `<tr><td>${esc(x.court)}</td><td>${esc(x.no)}</td><td>${esc(x.kind)}</td></tr>`).join('')}</table>` : '<div class="small faint">없음</div>'}
          <div class="sub-h">항고내역</div>${d.appeal.length ? d.appeal.map(x => `<div class="small">${esc(x.text)}</div>`).join('') : '<div class="small faint">없음</div>'}
        </div></div></div>
      <div class="card mb16"><div class="card-h"><h2>물건내역</h2><span class="small muted">${d.goods.length}건</span></div><div class="card-b">
        ${d.goods.length ? `<table class="list-tbl"><tr><th>물건</th><th>소재지</th><th>감정평가액</th><th>최저매각가격</th><th>매각기일</th><th>매각금액</th><th>비고</th></tr>${d.goods.map(x => `<tr><td><b>${esc(x.seq)}</b></td><td>${esc(x.addr)}</td><td class="price">${esc(x.eval)}</td><td class="price"><b>${esc(x.min)}</b></td><td class="nowrap">${esc(x.sale)} ${esc(x.time)}</td><td class="price">${esc(x.amount)}</td><td class="small">${esc(x.rmk)}</td></tr>`).join('')}</table>` : '<div class="small faint">없음</div>'}</div></div>
      <div class="card"><div class="card-h"><h2>당사자내역</h2><span class="small muted">${d.parties.length}명</span></div><div class="card-b">
        <table class="list-tbl"><tr><th>구분</th><th>이름</th><th>구분</th><th>이름</th></tr>${Array.from({length: Math.ceil(d.parties.length / 2)}, (_, i) => d.parties.slice(i * 2, i * 2 + 2)).map(pair => `<tr>${pair.map(x => `<td><span class="ptag ${ptagOf(x.kind)}">${esc(x.kind)}</span></td><td>${esc(x.name)}</td>`).join('')}${pair.length < 2 ? '<td></td><td></td>' : ''}</tr>`).join('')}</table></div></div>` : ''}
    ${tab === 't2' ? `<div class="card"><div class="card-h"><h2>기일내역</h2><span class="small muted">${d.dates.length}건</span></div><div class="card-b">
        ${d.dates.length ? `<table class="tbl"><tr><th>물건</th><th>기일</th><th>기일종류</th><th>장소</th><th>감정평가액</th><th>최저매각가격</th><th>결과</th></tr>${d.dates.map(x => `<tr><td>${esc(x.seq)}</td><td class="nowrap"><b>${esc(x.time)}</b></td><td>${esc(x.kind)}</td><td>${esc(x.place)}</td><td class="price">${esc(x.eval)}</td><td class="price"><b>${esc(x.min)}</b></td><td>${x.result ? chip(x.result, /유찰/.test(x.result) ? 'orange' : /변경|연기|정지/.test(x.result) ? 'gray' : /매각|허가|납부/.test(x.result) ? 'green' : 'blue') : chip('예정', 'blue')}</td></tr>`).join('')}</table>` : '<div class="small faint">기일내역이 없어요 (종국된 사건은 기일 정보를 주지 않아요)</div>'}
        <div class="small muted mt8">다음 매각기일은 「기일·기한」 달력에도 나와요.</div></div></div>` : ''}
    ${tab === 't3' ? `<div class="filters" style="padding:0 0 14px;border:0"><button class="f ${!who ? 'on' : ''}" data-w="">전체<em>${d.docs.length + d.dlvr.length}</em></button>${whoList.map(w => `<button class="f ${who === w ? 'on' : ''}" data-w="${w}">${w}<em>${d.docs.filter(x => x.who === w).length + d.dlvr.filter(x => x.who === w).length}</em></button>`).join('')}<button class="f ${who === '새로' ? 'on' : ''}" data-w="새로">새로<em>${newDocs}</em></button><input class="search" id="dq" placeholder="문건 내용 찾기" value="${esc(dq)}"></div>
      <div class="g2e" style="grid-template-columns:1.25fr 1fr">
        <div class="card"><div class="card-h"><h2>문건처리내역</h2><span class="small muted">${docsF.filter(fq).length}건 · 최근 순</span></div><div class="card-b">
          ${docsF.filter(fq).length ? `<table class="tbl"><tr><th>접수일</th><th>접수내역</th><th>결과</th></tr>${docsF.filter(fq).map(x => `<tr class="doc-row ${x.new ? 'new' : ''}"><td class="nowrap">${x.new ? '<b>' : ''}${fullDate(x.date)}${x.new ? '</b>' : ''}</td><td class="w"><span class="ptag ${ptagOf(x.who)}">${esc(x.who.split('·')[0])}</span>${x.new ? `<b class="lp hot">${esc(x.text)}</b>` : esc(x.text)}</td><td>${x.new ? '<span class="newdot">새로</span> ' : ''}${esc(x.result)}</td></tr>`).join('')}</table>` : '<div class="small faint">없음</div>'}</div></div>
        <div class="card"><div class="card-h"><h2>송달내역</h2><span class="small muted">${dlvrF.filter(fq).length}건 · 최근 순</span></div><div class="card-b">
          ${dlvrF.filter(fq).length ? `<table class="tbl"><tr><th>송달일</th><th>송달내역</th><th>송달결과</th></tr>${dlvrF.filter(fq).map(x => `<tr class="doc-row ${x.new ? 'new' : ''}"><td class="nowrap">${fullDate(x.date)}</td><td class="w">${x.new ? `<b>${esc(x.text)}</b>` : esc(x.text)}</td><td class="nowrap">${/도달/.test(x.result) ? `${esc(x.result.replace('도달', ''))}<b class="ok-t">도달</b>` : x.result ? `<b class="err">${esc(x.result)}</b>` : ''}</td></tr>`).join('')}</table>` : '<div class="small faint">없음</div>'}</div></div></div>` : ''}`
    : `<div class="card">${empty(c.last_result === 'notfound' ? '법원경매정보에서 찾지 못했어요' : '아직 조회하지 않았어요', '「지금 다시 조회」를 누르면 법원경매정보 창이 열려요.')}</div>`}`;
  $$('.au-tabs button', v).forEach(b => b.onclick = () => go('auction_case', {aid: a.aid, tab: b.dataset.t}));
  $$('[data-w]', v).forEach(b => b.onclick = () => go('auction_case', {aid: a.aid, tab: 't3', who: b.dataset.w}));
  if ($('#dq')) { const q = $('#dq'); q.oninput = () => { clearTimeout(q._t); q._t = setTimeout(() => go('auction_case', {aid: a.aid, tab: 't3', who, dq: q.value}).then(() => { const n = $('#dq'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }), 300); }; }
  $('#aNow').onclick = () => auStart([c.id]);
  $('#aXl').onclick = () => safe(async () => { const p = await api('auction_export', {ids: [c.id]}); toast('저장했어요: ' + p.split(/[\\/]/).pop()); });
  $('#aMemo').onclick = () => safe(async () => {
    const m = await modal('메모 (계좌번호 등)', `<input class="field" id="m" value="${esc(c.memo1 || '')}"><div class="small muted mt8">사건 대장의 「메모 1」과 같으면 그 소송 사건과 연결돼요.</div>`, [{text: '취소'}, {text: '저장', cls: 'primary', value: bg => $('#m', bg).value.trim()}]);
    if (m === null) return;
    await api('auction_memo', {aid: c.id, memo1: m});
    go('auction_case', a);
  });
};

