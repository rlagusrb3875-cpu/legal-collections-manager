/* 법조치 화면 — 현황 · 채무자 원장 · 기본 서류 · 송달·보정 관리 · 회생·파산 · 기준표 */
'use strict';
const won = n => Math.round(+n || 0).toLocaleString('ko-KR');
const man = n => { const v = Math.round((+n || 0) / 10000); return v >= 10000 ? `${Math.floor(v / 10000)}억${v % 10000 ? ' ' + (v % 10000).toLocaleString('ko-KR') + '만' : ''}` : v.toLocaleString('ko-KR') + '만'; };
const LGC = {red: 'bad', orange: 'warn', gray: 'wait', green: 'ok'};
const lgFlag = f => `<span class="chip ${LGC[f[1]] || 'wait'}">${esc(f[0])}</span>`;
const stTag = s => chip(s, s === '회생·파산' ? 'red' : s === '준비' ? 'gray' : s === '종결' ? 'gray' : 'blue');
const kdate = d => d ? d.split('-').map(Number).join('. ') + '.' : '';
const dots = () => '';
function kpi(icon, title, val, unit, badge, label) {
  return `<div class="card kpi"><div class="kh">${icon}${title}</div><div class="kb"><b class="num">${val}<small>${unit}</small></b>${badge || ''}<span class="kl">${label || ''}</span></div></div>`;
}
const IC = {
  file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="9"/><path d="M8 8l8 8"/></svg>',
  users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/></svg>',
  coin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="8"/><path d="M9 10h6M9 14h6"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17v.5"/></svg>',
  target: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/></svg>',
};

// 메뉴 숫자
NAV_PILLS.push(i => {
  const L = i.legal || {};
  const s = $('#pillStop'); if (s) { s.hidden = !L.stop; s.textContent = `멈춤 ${L.stop}`; }
  const d = $('#pillDlv'); if (d) { d.hidden = !L.dlv; d.textContent = L.dlv; }
  const r = $('#pillRehab'); if (r) { r.hidden = !L.rehab; r.textContent = L.rehab; }
});
Object.assign(NAV_OF, {lg_debtor: 'lg_debtors'});

// ================================================================== 법조치 현황
SCREENS.lg_home = async v => {
  const d = await api('lg_home');
  const k = d.kpi;
  const max = Math.max(6, ...d.chart.map(c => c.docs + c.dlv + c.rehab));
  const rate = d.dlv_rate.total ? d.dlv_rate.done / d.dlv_rate.total * 100 : 0;
  const tot = Math.max(1, d.stages.reduce((a, s) => a + s[1], 0));
  const due = d.todos.filter(t => t.due).map(t => ({t: `${t.party} · ${t.kind}`, s: t.text, due: t.due, go: t.go, arg: t.arg}))
    .concat(d.dlv_due.map(x => ({t: `${x.party} · 주소보정`, s: x.case_no, due: x.due, go: 'lg_dlv', arg: {key: x.key}})))
    .sort((a, b) => a.due < b.due ? -1 : 1).slice(0, 5);
  const left = s => Math.round((new Date(s + 'T00:00') - new Date(INFO.today + 'T00:00')) / 864e5);
  v.innerHTML = head(`${esc(INFO.book)} · ${fullDate(INFO.today)} (${wd(INFO.today)})`, '법조치 현황',
    `<button class="btn" data-go="lg_debtors">채무자 원장</button><button class="btn primary" data-go="lg_doc">서류 작성 →</button>`) +
    (!d.creditor_ok ? `<div class="notice">서류에 들어갈 <b>우리 회사(채권자) 정보</b>가 비어 있어요. <a data-act="cr">지금 넣기</a></div>` : '') +
    (d.std_unchecked ? `<div class="notice info">기준표에 <b>확인 안 된 법령 값 ${d.std_unchecked}개</b>가 있어요. 쓰기 전에 확인해 주세요. <a data-go="lg_std">기준표 열기</a></div>` : '') +
    `<div class="kpi4">
      ${kpi(IC.file, '진행 중 법조치', k.active, '명', `<span class="delta ${k.docs_week ? 'up' : ''}">이번 주 서류 ${k.docs_week}</span>`, '독촉~집행')}
      ${kpi(IC.file, '최근 4주 서류', d.chart.slice(-4).reduce((s, c) => s + c.docs, 0), '건', `<span class="delta">그 전 4주 ${d.chart.slice(-8, -4).reduce((s, c) => s + c.docs, 0)}</span>`, '만든 서류')}
      ${kpi(IC.clock, '송달 처리율', Math.round(rate), '%', `<span class="delta">${d.dlv_rate.done} / ${d.dlv_rate.total}건</span>`, '송달 안 됨 → 처리')}
      ${kpi(IC.users, '원장 채무자', k.debtors, '명', '', S.legal && S.legal.creditor && S.legal.creditor.name ? esc(S.legal.creditor.name).slice(0, 10) : '')}
    </div>
    <div class="lg-dash">
      <div class="card"><div class="card-h"><div><h2>법조치 추이</h2><div class="lg-legend"><span><i style="background:var(--b1)"></i>서류 만듦</span><span><i style="background:var(--b2)"></i>송달 처리</span><span><i style="background:var(--b3)"></i>회생·파산 등록</span></div></div><span class="small faint">최근 10주</span></div>
        <div class="card-b"><div class="lg-chart"><div class="yax"><span>${max}</span><span>${Math.round(max / 2)}</span><span>0</span></div><div class="cols">
          ${d.chart.map((c, i) => `<div class="col ${i === 9 ? 'now' : ''}" title="${c.label} 주 — 서류 ${c.docs} · 송달 처리 ${c.dlv} · 회생·파산 ${c.rehab}"><div class="stack">
            <i style="height:${c.rehab / max * 100}%;background:var(--b3)"></i><i style="height:${c.dlv / max * 100}%;background:var(--b2)"></i><i style="height:${c.docs / max * 100}%;background:var(--b1)"></i></div><span>${c.label}</span></div>`).join('')}
        </div></div></div></div>
      <div class="card"><div class="card-h"><h2>할 일은 「확인할 것」에서</h2></div><div class="card-b">
        <div class="small muted" style="margin-bottom:10px">보정 · 회생·파산 · 시효 할 일은 확인할 것 한곳에 모여요. 숫자도 현황 콘솔과 같아요.</div>
        <div class="lg-go"><button class="btn" data-go="home" data-arg='{"cat":"보정·송달","today":false}'>보정·송달 →</button><button class="btn" data-go="home" data-arg='{"cat":"회생·파산","today":false}'>회생·파산 →</button><button class="btn" data-go="home" data-arg='{"cat":"시효","today":false}'>시효 →</button></div>
        <div class="small faint" style="margin:14px 0 6px">가장 급한 것</div>
        ${d.todos.slice(0, 3).map(t => `<div class="lg-ins ${t.color === 'red' ? 'red' : ''}" data-go="${t.go}" data-arg='${JSON.stringify(t.arg || {})}'><div class="ii">${t.color === 'red' ? IC.stop : IC.clock}</div><div><b>${esc(t.party)} — ${esc(t.kind)}</b><span>${esc(t.text)}</span></div></div>`).join('') || '<div class="small faint" style="padding:18px 0">급한 법조치 할 일이 없어요</div>'}
        <button class="btn" style="width:100%;justify-content:center" data-go="home">확인할 것 모두 보기 →</button></div></div>
    </div>
    <div class="lg-bottom">
      <div class="card" hidden><div class="card-h"><div><h2>기한 임박</h2><div class="small muted">끝날이 토·일·공휴일이면 다음 평일</div></div></div><div class="card-b">
        ${due.map(x => `<div class="lg-li" data-go="${x.go}" data-arg='${JSON.stringify(x.arg || {})}'><div class="w"><b>${esc(x.t)}</b><small>${esc(x.s)} · ${md(x.due)}(${wd(x.due)})</small></div>${dday(left(x.due))}</div>`).join('') || '<div class="small faint">기한이 정해진 일이 없어요</div>'}</div></div>
      <div class="card"><div class="card-h"><div><h2>송달 처리율</h2><div class="small muted">처리함에 들어온 「송달 안 됨」 중</div></div></div><div class="card-b">${gauge(rate, `${d.dlv_rate.done} / ${d.dlv_rate.total}건`)}</div></div>
      <div class="card"><div class="card-h"><div><h2>단계별 채무자</h2><div class="small muted">원장 ${k.debtors}명</div></div></div><div class="card-b">
        ${d.stages.map(s => `<div class="lg-hb"><div class="t"><span>${s[0]}</span><b class="num">${s[1]} <span class="faint" style="font-weight:400">(${Math.round(s[1] / tot * 100)}%)</span></b></div><div class="bar"><i style="width:${s[1] / tot * 100}%;background:${s[0] === '회생·파산' ? 'var(--bad)' : s[0] === '준비' ? 'var(--b3)' : 'var(--b1)'}"></i></div></div>`).join('')}</div></div>
    </div>`;
  const a = $('[data-act="cr"]', v); if (a) a.onclick = () => docInfoModal().then(() => go('lg_home'));
};
function gauge(p, sub) {
  const R = 92, cx = 120, cy = 112, ang = Math.PI * (1 - Math.min(100, p) / 100);
  const x = cx + R * Math.cos(ang), y = cy - R * Math.sin(ang);
  return `<svg viewBox="0 0 240 150" style="width:100%;max-width:290px;display:block;margin:0 auto">
    <path d="M${cx - R - 14} ${cy} A${R + 14} ${R + 14} 0 0 1 ${cx + R + 14} ${cy}" fill="none" stroke="var(--b3)" stroke-width="7" stroke-dasharray="1.5 3.5"/>
    <path d="M${cx - R} ${cy} A${R} ${R} 0 0 1 ${cx + R} ${cy}" fill="none" stroke="var(--track)" stroke-width="20" stroke-linecap="round"/>
    ${p > 0 ? `<path d="M${cx - R} ${cy} A${R} ${R} 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}" fill="none" stroke="var(--b1)" stroke-width="20" stroke-linecap="round"/>` : ''}
    <text x="${cx}" y="${cy - 14}" text-anchor="middle" font-size="27" font-weight="650" fill="var(--text)">${p.toFixed(1)}%</text>
    <text x="${cx}" y="${cy + 6}" text-anchor="middle" font-size="11" fill="var(--sub)">${sub}</text>
    <text x="${cx - R - 8}" y="${cy + 26}" font-size="10.5" fill="var(--faint)">0%</text><text x="${cx + R - 16}" y="${cy + 26}" font-size="10.5" fill="var(--faint)">100%</text></svg>`;
}

// ================================================================== 채무자 원장
const DFORM = [['name', '채무자'], ['birth', '생년월일 (앞 6자리)'], ['key', '계좌·고객번호'], ['principal', '원금'], ['interest', '이자'],
  ['addr', '주소', 'full'], ['sihyo', '시효 완성일', 'date'], ['default_date', '기한이익 상실일', 'date'], ['rate', '연체이율(%)'], ['contract_date', '대출일', 'date'],
  ['court', '관할 법원'], ['title_no', '집행권원 사건번호'], ['memo', '메모', 'full']];
async function debtorForm(d) {
  d = d || {};
  const body = `<div class="form">${DFORM.map(f => `<div class="${f[2] === 'full' ? 'full' : ''}"><label class="lb">${f[1]}</label><input class="field" data-k="${f[0]}" ${f[2] === 'date' ? 'type="date"' : ''} value="${esc(d[f[0]] ?? '')}"></div>`).join('')}
    <div><label class="lb">단계 (직접)</label><select class="field" data-k="stage">${['준비', '독촉', '소송', '확정', '집행', '종결'].map(s => `<option ${d.stage === s ? 'selected' : ''}>${s}</option>`).join('')}</select></div></div>
    <div class="small muted mt8">주민등록번호를 넣어도 앞 6자리(생년월일)만 남겨요. 사건 대장의 「메모 1」에 같은 계좌번호가 있거나 당사자 이름이 같으면 사건과 이어져요.</div>`;
  return modal(d.id ? `${esc(d.name)} 고치기` : '채무자 추가', body, [{text: '취소'}, {text: '저장', cls: 'primary', value: async bg => {
    const data = {id: d.id || ''};
    $$('[data-k]', bg).forEach(i => data[i.dataset.k] = i.value);
    try { return await api('lg_debtor_save', {data}); } catch (e) { toast(e.message, true); return false; }
  }}], true);
}
SCREENS.lg_debtors = async (v, a) => {
  const flt = a.f || '전체', q = a.q || '';
  const d = await api('lg_debtors', {q, flt});
  const cur = a.did ? await api('lg_debtor', {did: a.did}).catch(() => null) : null;
  v.innerHTML = head(`${esc(INFO.book)} · 모든 법조치 화면이 같이 쓰는 장부`, `채무자 원장 <span class="faint" style="font-weight:500">${d.total}</span>`,
    `<button class="btn" id="dTpl">양식 받기</button><button class="btn" id="dImp">엑셀 불러오기</button><button class="btn primary" id="dAdd">+ 채무자 추가</button>`) +
    `<div class="lg-split" style="grid-template-columns:${cur ? 'minmax(0,1fr) 360px' : '1fr'}"><div class="card" style="overflow:hidden">
      <div class="filters"><input class="field" id="dq" placeholder="이름·계좌번호" value="${esc(q)}" style="width:200px;padding:7px 11px">
      ${['전체', '할 일', '멈춤', '준비', '독촉', '소송', '확정', '집행', '종결'].map(f => `<button class="f ${f === flt ? 'on' : ''}" data-f="${f}">${f}</button>`).join('')}
      <span class="small faint" style="margin-left:auto">${d.items.length}명</span></div>
      ${d.items.length ? `<table class="tbl lg-tbl"><thead><tr><th>채무자</th><th>계좌·고객번호</th><th class="right">청구액</th><th>단계</th><th>사건</th><th>시효 완성</th><th>표시</th></tr></thead><tbody>
      ${d.items.map(x => `<tr class="click ${cur && cur.id === x.id ? 'sel' : ''}" data-did="${x.id}"><td><b>${esc(x.name)}</b> <span class="small faint">${esc((x.birth || '').slice(0, 2))}${x.birth ? '년생' : ''}</span></td>
        <td class="num muted">${esc(x.key || '—')}</td><td class="right num">${won(x.claim)}</td><td>${stTag(x.stage_view)}</td>
        <td class="small muted">${x.cases.length ? esc(x.cases[0].case_no) + (x.cases.length > 1 ? ` 외 ${x.cases.length - 1}` : '') : '—'}</td>
        <td class="num small muted">${x.sihyo ? fullDate(x.sihyo) : '—'}</td><td>${x.flags.map(lgFlag).join(' ')}</td></tr>`).join('')}</tbody></table>`
      : empty('채무자가 없어요', '채권 엑셀을 불러오거나 직접 추가하세요. 칸 이름(고객명·대출번호·원금 등)은 자동으로 찾아요.', '<button class="btn primary" id="dImp2">엑셀 불러오기</button>')}
    </div>${cur ? debtorPanel(cur) : ''}</div>`;
  $$('[data-f]', v).forEach(b => b.onclick = () => go('lg_debtors', {f: b.dataset.f, q}));
  $('#dq').onchange = e => go('lg_debtors', {f: flt, q: e.target.value.trim()});
  $$('tr[data-did]', v).forEach(tr => tr.onclick = () => go('lg_debtors', {f: flt, q, did: tr.dataset.did}));
  $('#dAdd').onclick = () => safe(async () => { const id = await debtorForm(); if (id) go('lg_debtors', {did: id}); });
  $('#dTpl').onclick = () => safe(async () => toast('양식을 저장했어요: ' + await api('lg_template_save')));
  [$('#dImp'), $('#dImp2')].forEach(b => b && (b.onclick = () => debtorImport()));
  bindDebtorPanel(v, cur, {f: flt, q});
};
function debtorPanel(c) {
  return `<div class="card lg-panel"><div class="card-h"><div><h2>${esc(c.name)} <span class="small faint">${esc(c.birth || '')}</span></h2><div class="small muted">${esc(c.key || '')} · ${stTag(c.stage_view)}</div></div><button class="btn sm ghost" id="pClose">✕</button></div>
  <div class="card-b">${c.stage_view === '회생·파산' ? `<div class="notice bad" style="margin:0 0 12px">회생·파산 중이에요. 이 채무자의 새 법조치는 모든 화면에서 막혀 있어요.</div>` : ''}
    <div class="lg-kv"><span>청구액</span><b class="num">${won(c.claim)}원</b><span>원금 · 이자</span><span class="num">${won(c.principal)} · ${won(c.interest)}</span>
    <span>주소</span><span>${esc(c.addr || '') || '<span class="chip wait">없음 — 초본 필요</span>'}</span><span>시효 완성</span><span>${c.sihyo ? fullDate(c.sihyo) : '—'}</span>
    <span>연체이율</span><span>${c.rate ? esc(c.rate) + '%' : '—'} ${c.default_date ? '· 기한이익 상실 ' + fullDate(c.default_date) : ''}</span>${c.court ? `<span>관할</span><span>${esc(c.court)}</span>` : ''}</div>
    ${(c.addr_hist || []).length ? `<div class="lg-sec">주소 기록</div><div class="lg-tl">${c.addr_hist.map(h => `<div class="a"><b>${esc(h.addr)}</b><small>${esc(h.note)} · ${esc(h.at)}</small></div>`).join('')}<div class="a now"><b>${esc(c.addr)}</b><small>지금 주소${c.addr_changed ? ' · ' + esc(c.addr_changed) + ' 바뀜' : ''}</small></div></div>` : ''}
    <div class="lg-sec">이어진 사건 (사건 대장)</div>
    ${c.cases.length ? c.cases.map(x => `<div class="lg-li" data-go="case" data-arg='${JSON.stringify({cid: x.id})}'><div class="w"><b class="num">${esc(x.case_no)}</b><small>${esc(x.kind)} · ${esc(x.last || '')}</small></div>${chip(x.status, x.color)}</div>`).join('') : '<div class="small faint">이어진 사건이 없어요 — 사건 대장의 메모 1에 계좌번호를 넣으면 이어져요</div>'}
    <div class="lg-sec">기록</div>${(c.log || []).map(l => `<div class="small" style="padding:3px 0">· ${esc(l.text)} <span class="faint">${esc(l.at.slice(5, 16))}</span></div>`).join('') || '<div class="small faint">아직 없어요</div>'}
    <div class="row-gap mt16"><button class="btn sm primary" id="pEdit">고치기</button>${c.stage_view === '준비' ? '<button class="btn sm" data-go="lg_doc">지급명령</button>' : ''}
${c.stage_view !== '회생·파산' ? '<button class="btn sm" id="pRehab">회생 문서 등록</button>' : ''}<button class="btn sm ghost" id="pArc">보관</button></div>
  </div></div>`;
}
function bindDebtorPanel(v, c, back) {
  if (!c) return;
  $('#pClose').onclick = () => go('lg_debtors', back);
  $('#pEdit').onclick = () => safe(async () => { if (await debtorForm(c)) go('lg_debtors', Object.assign({}, back, {did: c.id})); });
  if ($('#pRehab')) $('#pRehab').onclick = () => rehabRegister(c.id);
  $('#pArc').onclick = () => safe(async () => { if (await confirmBox('보관', `${esc(c.name)}을(를) 원장에서 보관함으로 옮겨요.`, '보관')) { await api('lg_debtor_archive', {ids: [c.id]}); go('lg_debtors', back); } });
}
async function debtorImport(path) {
  path = path || await api('choose_file');
  if (!path) return;
  let p = await api('lg_import_preview', {path});
  const draw = () => `<div class="small muted" style="margin-bottom:12px">${esc(p.name)} · ${p.rows}줄 → 새로 <b>${p.new}</b> · 고침 <b>${p.update}</b>${p.skip ? ` · 이름 없어 건너뜀 ${p.skip}` : ''}</div>
    <div class="form">${p.fields.map(([k, t]) => `<div><label class="lb">${t} ${p.mapping[k] !== undefined ? '' : '<span class="faint">(없음)</span>'}</label><select class="field" data-m="${k}"><option value="">— 안 씀</option>${p.header.map((h, j) => `<option value="${j}" ${p.mapping[k] === j ? 'selected' : ''}>${esc(h || excelCol(j))}</option>`).join('')}</select></div>`).join('')}</div>
    <div class="small muted mt8">칸 이름으로 자동으로 맞췄어요. 틀린 칸만 고르세요. 주민등록번호는 앞 6자리만 남겨요.</div>`;
  await modal('채무자 엑셀 불러오기', `<div id="impBox">${draw()}</div>`, [{text: '취소'}, {text: '불러오기', cls: 'primary', value: async bg => {
    const mapping = {}; $$('[data-m]', bg).forEach(s => { if (s.value !== '') mapping[s.dataset.m] = +s.value; });
    const r = await api('lg_import_apply', {path, mapping});
    toast(`${r.count}명을 원장에 넣었어요 (새로 ${r.new} · 고침 ${r.update})`);
    go('lg_debtors');
    return true;
  }}], true);
}
const excelCol = j => { let s = ''; j++; while (j) { s = String.fromCharCode(65 + (j - 1) % 26) + s; j = Math.floor((j - 1) / 26); } return s + ' 칸'; };

// ================================================================== 서류 작성
const LGD = {type: '지급명령', sel: {}, cur: null, opts: null};
async function docInfoModal() {
  const info = (await api('lg_doc_rows', {kind: '지급명령', opts: {}})).info || {};
  const L = S.legal || {}, cr = L.creditor || {};
  const f = (k, t, v, type) => `<div><label class="lb">${t}</label><input class="field" data-${k} ${type ? `type="${type}"` : ''} value="${esc(v || '')}"></div>`;
  return modal('서류 정보', `<div class="lg-sec" style="margin-top:0">우리 회사 (채권자) — 모든 채권 공통</div>
    <div class="form">${f('c="name"', '이름', cr.name)}${f('c="rep"', '대표이사', cr.rep)}<div class="full">${f('c="addr"', '주소', cr.addr).replace('<div>', '').replace(/<\/div>$/, '')}</div>${f('c="phone"', '전화', cr.phone)}${f('g="court"', '기본 관할 법원', L.court)}</div>
    <div class="lg-sec">이 채권 (${esc(INFO.book)})의 청구 원인</div>
    <div class="form"><div><label class="lb">청구 원인</label><select class="field" data-i="cause">${['양수금', '대여금', '구상금'].map(x => `<option ${info.cause === x ? 'selected' : ''}>${x}</option>`).join('')}</select></div>
    ${f('i="assignor"', '양도인 (원래 채권자)', info.assignor)}${f('i="assign_date"', '양도일', info.assign_date, 'date')}${f('i="notice_date"', '양도 통지 도달일', info.notice_date, 'date')}${f('i="contract_date"', '대출일 (원장에 없을 때)', info.contract_date, 'date')}</div>`,
    [{text: '취소'}, {text: '저장', cls: 'primary', value: async bg => {
      const c = {}; $$('[data-c]', bg).forEach(i => c[i.dataset.c] = i.value.trim());
      const inf = {}; $$('[data-i]', bg).forEach(i => inf[i.dataset.i] = i.value);
      await setSetting('legal.creditor', c, '서류 정보: 우리 회사');
      await setSetting('legal.court', $('[data-g]', bg).value.trim());
      await api('lg_info_save', {info: inf});
      toast('서류 정보를 저장했어요');
      return true;
    }}], true);
}
SCREENS.lg_doc = async (v, a) => {
  if (a.type) { LGD.type = a.type; LGD.sel = {}; LGD.cur = a.cur || null; }
  if (LGD.type === '채권압류') LGD.type = '지급명령';
  const L = S.legal || {};
  LGD.opts = LGD.opts || {ecfs: L.ecfs !== false, basis: L.basis || '약정'};
  const d = await api('lg_doc_rows', {kind: LGD.type, opts: LGD.opts});
  const rows = d.rows;
  rows.forEach(r => { if (LGD.sel[r.id] === undefined) LGD.sel[r.id] = r.st[0] === 'ok' || r.st[0] === 'warn'; if (['no', 'made'].includes(r.st[0])) LGD.sel[r.id] = false; });
  const sel = rows.filter(r => LGD.sel[r.id]);
  const cur = rows.find(r => r.id === LGD.cur) || sel[0] || rows[0];
  const sum = sel.reduce((s, r) => [s[0] + r.stamp, s[1] + r.svc], [0, 0]);
  const T = [['지급명령', '지급명령 신청서'], ['주소보정', '주소보정서 · 소제기 신청']];
  const tg = {ok: 'ok', warn: 'warn', no: 'bad', made: 'wait'};
  const isAddr = LGD.type === '주소보정';
  v.innerHTML = head(`${esc(INFO.book)} · 원장에서 대상을 골라 여러 건을 한 번에`, '서류 작성',
    `<button class="btn" id="docInfo">서류 정보${d.creditor.name ? '' : ' <span class="chip bad">비어 있음</span>'}</button><button class="btn" data-go="lg_debtors">원장에 엑셀 넣기</button>`) +
    `<div class="lg-split" style="grid-template-columns:minmax(0,1fr) 400px"><div style="display:flex;flex-direction:column;gap:14px;min-width:0">
      <div class="card"><div class="card-b lg-opts">
        <div><div class="lg-sec" style="margin:0 0 6px">서류</div><div class="seg">${T.map(t => `<button class="${LGD.type === t[0] ? 'on' : ''}" data-t="${t[0]}">${t[1]}</button>`).join('')}</div></div>
        ${LGD.type === '지급명령' ? `<div><div class="lg-sec" style="margin:0 0 6px">내는 곳</div><div class="seg"><button class="${LGD.opts.ecfs ? 'on' : ''}" data-e="1">전자소송</button><button class="${!LGD.opts.ecfs ? 'on' : ''}" data-e="0">종이</button></div></div>
        <div><div class="lg-sec" style="margin:0 0 6px">지연손해금 근거</div><select class="field" id="basis" style="width:220px">${[['약정', '약정 연체이율 (원장 값)'], ['소촉', '소송촉진법 연 12%'], ['상사', '상사 법정이율 연 6%'], ['민사', '민사 법정이율 연 5%']].map(b => `<option value="${b[0]}" ${LGD.opts.basis === b[0] ? 'selected' : ''}>${b[1]}</option>`).join('')}</select></div>` : ''}
        <div><div class="lg-sec" style="margin:0 0 6px">저장</div><span class="chip wait">워드(.docx) · 한글에서 열림</span></div>
      </div></div>
      <div class="card" style="overflow:hidden">
        ${rows.length ? `<table class="tbl lg-tbl"><thead><tr><th style="width:36px"><input type="checkbox" class="cbx" id="selAll"></th><th>채무자</th>${isAddr ? '<th>사건번호</th><th>조치</th>' : '<th class="right">청구액</th><th>법원</th><th class="right">인지대</th><th class="right">송달료</th>'}<th>점검</th></tr></thead><tbody>
        ${rows.map(r => { const off = ['no', 'made'].includes(r.st[0]); return `<tr class="click ${cur && cur.id === r.id ? 'sel' : ''} ${off ? 'off' : ''}" data-id="${esc(r.id)}"><td><input type="checkbox" class="cbx" data-c="${esc(r.id)}" ${LGD.sel[r.id] ? 'checked' : ''} ${off ? 'disabled' : ''}></td>
          <td><b>${esc(r.name)}</b> <span class="small faint">${esc(isAddr ? '' : r.key)}</span></td>
          ${isAddr ? `<td class="num">${esc(r.case_no)}</td><td class="small">${esc(r.st[1])}</td>` : `<td class="right num">${won(r.claim)}</td><td class="small muted">${esc(r.court || '—')}</td><td class="right num">${won(r.stamp)}</td><td class="right num">${won(r.svc)}</td>`}
          <td>${isAddr ? chip('조치 정함', 'green') : `<span class="chip ${tg[r.st[0]]}">${esc(r.st[1])}</span>`}${r.warn.length && !off ? ` <span class="chip warn" title="${esc(r.warn.join('\n'))}">빈칸 ${r.warn.length}</span>` : ''}</td></tr>`; }).join('')}</tbody></table>`
        : empty('대상이 없어요', isAddr ? '「송달·주소보정」에서 조치를 고르면 여기로 와요.' : LGD.type === '지급명령' ? '원장에서 「준비」 단계인 채무자가 대상이에요.' : '확정된 채무자 중 집행 대상(제3채무자)을 넣은 사람이 대상이에요.')}
        <div class="lg-foot"><span>선택 <b>${sel.length}건</b></span>${isAddr ? '' : `<span class="muted">인지대 <b class="num">${won(sum[0])}</b>원 · 송달료 <b class="num">${won(sum[1])}</b>원 · 합계 <b class="num">${won(sum[0] + sum[1])}</b>원</span>`}
        <button class="btn primary" style="margin-left:auto" id="make" ${sel.length ? '' : 'disabled'}>${sel.length}건 만들기</button></div>
      </div>
      <div class="notice info" style="margin:0">${LGD.type === '지급명령' ? `인지대 = 소장 인지의 1/10${LGD.opts.ecfs ? ` × ${d.std.ecfs} (전자소송)` : ''}, 100원 미만 버림 · 송달료 = 2명 × ${d.std.pay_times}회분 × ${won(d.std.svc)}원` : LGD.type === '채권압류' ? `인지대 = 압류 2,000원 + 추심 2,000원 · 송달료 = (채권자·채무자 + 제3채무자 수) × ${d.std.garn_times}회분 × ${won(d.std.svc)}원` : '주소보정서는 인지·송달료 없이 만들어요 (특별송달은 집행관 수수료를 따로 냄)'}. 값은 <a data-go="lg_std">기준표</a>에서 바꿔요.</div>
    </div>
    <div id="docPrev">${cur ? '<div class="card"><div class="card-b small faint">미리보기를 불러오는 중…</div></div>' : ''}</div></div>`;
  $$('[data-t]', v).forEach(b => b.onclick = () => go('lg_doc', {type: b.dataset.t}));
  $$('[data-e]', v).forEach(b => b.onclick = () => { LGD.opts.ecfs = b.dataset.e === '1'; go('lg_doc'); });
  if ($('#basis')) $('#basis').onchange = e => { LGD.opts.basis = e.target.value; go('lg_doc'); };
  $('#docInfo').onclick = () => safe(async () => { if (await docInfoModal()) go('lg_doc'); });
  $$('[data-c]', v).forEach(c => c.onclick = e => { e.stopPropagation(); LGD.sel[c.dataset.c] = c.checked; go('lg_doc'); });
  const all = $('#selAll');
  if (all) { const can = rows.filter(r => !['no', 'made'].includes(r.st[0])); all.checked = can.length && can.every(r => LGD.sel[r.id]); all.onclick = () => { can.forEach(r => LGD.sel[r.id] = all.checked); go('lg_doc'); }; }
  $$('tr[data-id]', v).forEach(tr => tr.onclick = () => { LGD.cur = tr.dataset.id; go('lg_doc'); });
  $('#make').onclick = () => safe(async () => {
    const r = await api('lg_doc_make', {kind: LGD.type, ids: sel.map(x => x.id), opts: LGD.opts});
    LGD.sel = {};
    toast(`${r.count}건 만들었어요 — ${r.folder}`);
    go('lg_doc');
  });
  if (cur) {
    const p = await api('lg_doc_preview', {kind: LGD.type, rid: cur.id, opts: LGD.opts}).catch(e => ({error: e.message}));
    $('#docPrev').innerHTML = p.error ? `<div class="card"><div class="card-b err">${esc(p.error)}</div></div>` :
      `<div class="card"><div class="card-h"><div><h2>미리보기</h2><div class="small muted">${esc(cur.name)} · 노란 칸이 원장·설정에서 채운 곳</div></div></div><div class="card-b">
        ${p.warn.length ? `<div class="notice" style="margin:0 0 10px">${p.warn.map(esc).join('<br>')}</div>` : ''}<div class="lg-paper">${paperHtml(p.paras)}</div></div></div>
      ${p.paste ? `<div class="card" style="margin-top:14px"><div class="card-h"><div><h2>전자소송 붙여넣기</h2><div class="small muted">입력칸에 그대로 붙여 넣는 글</div></div><button class="btn sm" id="cp">복사</button></div><div class="card-b"><textarea class="field" id="paste" readonly style="min-height:110px;font-size:12px;line-height:1.6">${esc(p.paste)}</textarea></div></div>` : ''}`;
    if ($('#cp')) $('#cp').onclick = () => { const t = $('#paste'); t.select(); document.execCommand('copy'); toast('복사했어요'); };
  }
};
function paperHtml(paras) {
  const hl = s => esc(s).replace(/(금 [\d,]+원|[\d]{4}\. \d{1,2}\. \d{1,2}\.|연 [\d.]+%|\([^)]*(주소|이름|양도인|사건번호|집행권원|약정 연체이율|기한이익)[^)]*\))/g, '<span class="f">$1</span>');
  return paras.map(p => {
    if (p[0] === 'title') return `<h2>${esc(p[1])}</h2>`;
    if (p[0] === 'h') return `<h4>${esc(p[1])}</h4>`;
    if (p[0] === 'center') return `<div style="text-align:center;font-weight:600">${hl(p[1])}</div>`;
    if (p[0] === 'right') return `<div style="text-align:right">${hl(p[1])}</div>`;
    if (p[0] === 'party') return `<div class="p"><b>${esc(p[1])}</b><span>${hl(p[2])}</span></div>`;
    if (p[0] === 'li') return `<div class="li"><span>${esc(p[1])}</span><span>${hl(p[2])}</span></div>`;
    if (p[0] === 'gap') return '<div style="height:8px"></div>';
    return `<p>${hl(p[1])}</p>`;
  }).join('');
}

// ================================================================== 송달·주소보정 (보정 관리 대장)
const LGS = {tab: 'todo', flt: '', q: '', sel: {}, cur: null, sib: true};
const DL_ST = {'접수': 's0', '조치 정함': 's1', '제출함': 's2', '완료': 's3'};
const dlSt = s => `<span class="dl-st ${DL_ST[s] || 's0'}">${esc(s)}</span>`;
const dlSrc = x => x.src === 'auto' ? '<span class="chip wait" title="사건 조회 결과에서 자동으로">조회</span>' : x.src === 'xl' ? '<span class="chip now">엑셀</span>' : '<span class="chip now">직접</span>';
SCREENS.lg_dlv = async (v, a) => {
  if (a.key) { LGS.cur = a.key; LGS.tab = 'all'; }
  const d = await api('lg_dlv', {tab: LGS.tab, flt: LGS.flt, q: LGS.q});
  const cur = d.items.find(x => x.key === LGS.cur) || d.items[0];
  const sel = d.items.filter(x => LGS.sel[x.key]);
  const c = d.counts;
  v.innerHTML = head(`${esc(INFO.book)} · 사건 조회 · 엑셀 · 직접 등록을 한 대장에서`, '송달·보정 관리',
    `<div class="seg">${[['todo', '처리할 것', d.todo], ['done', '끝난 것', d.done], ['all', '전체', d.all]].map(([k, n, m]) => `<button class="${LGS.tab === k ? 'on' : ''}" data-tab="${k}">${n} ${m}</button>`).join('')}</div>
     <button class="btn" id="dlImp">엑셀 넣기</button><button class="btn" id="dlExp">엑셀로 내보내기</button><button class="btn primary" id="dlvAdd">+ 직접 등록</button>`) +
    `<div class="lg-split" style="grid-template-columns:minmax(0,1fr) 360px"><div class="card" style="overflow:hidden">
      <div class="dl-filters"><input class="field" id="dlQ" placeholder="사건번호·당사자·담당·메모" value="${esc(LGS.q)}" style="width:210px;padding:6px 11px">
        ${[['', '모두'], ['over', '기한 지남', c.over], ['soon', '3일 안', c.soon], ['nodue', '기한 없음', c.nodue]].map(([k, n, m]) => `<button class="f ${LGS.flt === k ? 'on' : ''}" data-flt="${k}">${n}${m !== undefined ? `<b>${m}</b>` : ''}</button>`).join('')}
        <span class="small faint" style="margin-left:auto">${d.items.length}건</span></div>
      ${sel.length ? `<div class="lg-bulk">선택 ${sel.length}건<span style="flex:1"></span><button class="btn sm primary" id="bForm">회사 양식으로 만들기</button><button class="btn sm" id="bRec">기본 서류로</button>
        <button class="btn sm" id="bDone">완료</button><button class="btn sm" id="bExp">엑셀로</button><button class="btn sm danger" id="bDel">지우기</button><button class="btn sm ghost" id="bClr">해제</button></div>` : ''}
      ${d.items.length ? `<div style="max-height:calc(100vh - 290px);overflow:auto"><table class="tbl lg-tbl"><thead><tr><th style="width:36px"><input type="checkbox" class="cbx" id="dlAll"></th><th>당사자</th><th>사건번호</th><th>불능 사유</th><th>기한</th><th>조치 · 진행</th></tr></thead><tbody>
      ${d.items.map(x => `<tr class="click ${cur && cur.key === x.key ? 'sel' : ''}" data-k="${esc(x.key)}"><td><input type="checkbox" class="cbx" data-s="${esc(x.key)}" ${LGS.sel[x.key] ? 'checked' : ''}></td>
        <td class="nw"><b>${esc(x.debtor ? x.debtor.name : x.party || '—')}</b><div class="small faint">${dlSrc(x)}${x.owner ? ' ' + esc(x.owner) : ''}</div></td>
        <td class="num nw">${esc(x.case_no)}<div class="small faint">${esc(x.court || x.kind || '')}</div></td>
        <td class="nw">${esc(x.reason || '—')}${x.cnt > 1 ? ` <span class="faint">(${x.cnt}회)</span>` : ''}<div class="small faint">${x.date ? md(x.date) : ''}${x.doc ? ' · ' + esc(x.doc) : ''}</div></td>
        <td class="num nw">${x.due ? `${md(x.due.due)}(${wd(x.due.due)}) ${x.done ? '' : dday(x.left)}` : '<span class="chip warn">보정명령 날 넣기</span>'}<div class="small faint">${x.recv ? `명령 ${md(x.recv)} +${x.days}일` : x.due && x.due.set ? '기한 직접 넣음' : ''}</div></td>
        <td class="dl-act">${dlSt(x.status)}<div class="small ${x.act ? '' : 'faint'}">${esc(x.act || '추천 ' + x.rec)}</div></td></tr>`).join('')}</tbody></table></div>`
      : empty(LGS.tab === 'done' ? '끝난 것이 없어요' : '처리할 보정이 없어요', '사건 조회에서 폐문부재·이사불명·수취인불명이 나오면 자동으로 들어와요. 엑셀로 넣거나 「+ 직접 등록」으로 넣을 수도 있어요.', '<button class="btn" id="dlImp2">엑셀 넣기</button>')}
      <div class="lg-foot small muted">지급명령은 공시송달을 할 수 없어요(민사소송법 제462조 단서). 주소를 더 찾을 수 없으면 「소제기 신청」으로 소송으로 바꾼 뒤 공시송달해요.</div>
    </div>${cur ? dlvPanel(cur) : '<div></div>'}</div>`;
  $$('[data-tab]', v).forEach(b => b.onclick = () => { LGS.tab = b.dataset.tab; LGS.sel = {}; go('lg_dlv'); });
  $$('[data-flt]', v).forEach(b => b.onclick = () => { LGS.flt = b.dataset.flt; go('lg_dlv'); });
  $('#dlQ').oninput = e => { LGS.q = e.target.value; clearTimeout(LGS.t); LGS.t = setTimeout(async () => { await go('lg_dlv'); const i = $('#dlQ'); i.focus(); i.setSelectionRange(99, 99); }, 300); };
  $$('[data-s]', v).forEach(cb => cb.onclick = e => { e.stopPropagation(); LGS.sel[cb.dataset.s] = cb.checked; go('lg_dlv'); });
  if ($('#dlAll')) { $('#dlAll').checked = d.items.length && d.items.every(x => LGS.sel[x.key]); $('#dlAll').onclick = e => { d.items.forEach(x => LGS.sel[x.key] = e.target.checked); go('lg_dlv'); }; }
  $$('tr[data-k]', v).forEach(tr => tr.onclick = () => { LGS.cur = tr.dataset.k; go('lg_dlv'); });
  $('#dlvAdd').onclick = () => dlvAdd();
  $('#dlImp').onclick = () => dlvImport();
  if ($('#dlImp2')) $('#dlImp2').onclick = () => dlvImport();
  $('#dlExp').onclick = () => dlvExport(d, []);
  if ($('#bExp')) $('#bExp').onclick = () => dlvExport(d, sel.map(x => x.key));
  if ($('#bClr')) $('#bClr').onclick = () => { LGS.sel = {}; go('lg_dlv'); };
  if ($('#bDone')) $('#bDone').onclick = () => safe(async () => { const n = await api('lg_dlv_done', {keys: sel.map(x => x.key)}); LGS.sel = {}; toast(`${n}건을 완료로 바꿨어요`); go('lg_dlv'); });
  if ($('#bDel')) $('#bDel').onclick = () => safe(async () => {
    if (!await confirmBox('보정 관리에서 지우기', `선택한 ${sel.length}건을 대장에서 지워요. 사건 조회에서 자동으로 온 건은 다시 들어오지 않아요. 끝난 일이면 「완료」를 누르는 게 기록이 남아 좋아요.`, '지우기')) return;
    const n = await api('lg_dlv_delete', {keys: sel.map(x => x.key)}); LGS.sel = {}; toast(`${n}건을 지웠어요`); go('lg_dlv');
  });
  if ($('#bForm')) $('#bForm').onclick = () => safe(() => fmFromDlv(sel.map(x => x.key)));
  if ($('#bRec')) $('#bRec').onclick = () => safe(async () => {
    for (const x of sel) if (!x.act) await api('lg_dlv_set', {key: x.key, field: 'act', value: x.rec});
    LGS.sel = {}; go('lg_doc', {type: '주소보정'});
  });
  if (cur) bindDlvPanel(v, cur, d);
};
function dlvPanel(x) {
  const act = x.act || x.rec, D = x.debtor;
  const f = (k, t, val, type = '', ph = '') => `<div><label class="lb">${t}</label><input class="field" data-f="${k}" ${type ? `type="${type}"` : ''} value="${esc(val || '')}" placeholder="${esc(ph)}" ${x.done ? 'disabled' : ''}></div>`;
  return `<div class="card lg-panel"><div class="card-h"><div><h2>${esc(D ? D.name : x.party || '당사자 없음')} · ${esc(x.case_no)}</h2><div class="small muted">${esc(x.kind || '')} · ${esc(x.src_label)}${x.text ? ' · ' + esc(x.text) : ''}</div></div>${dlSt(x.status)}</div>
  <div class="card-b dl-form" style="max-height:calc(100vh - 230px);overflow:auto">
    <div class="dl-due">${x.due ? `<span>기한</span><b>${kdate(x.due.due)}(${wd(x.due.due)})</b>${x.done ? '' : dday(x.left)}<span class="small muted" style="flex-basis:100%">${x.due.set ? '직접 넣은 기한' : `받은 다음 날부터 ${x.days}일${x.due.moved ? ` — 끝날 ${md(x.due.raw)}이 쉬는 날이라 다음 평일로` : ''}`} · 「기일·기한」「확인할 것」에도 보여요</span>`
      : '<span class="small muted">보정명령 받은 날을 넣으면 기한을 계산해요 (민법 제157·161조). 기한을 바로 넣어도 돼요.</span>'}</div>
    <div class="form">${f('recv', '보정명령 받은 날', x.recv, 'date')}${f('days', '보정 기간 (일)', x.days, 'number')}
      ${f('due_set', '기한 직접 (있으면 이것으로)', x.due_set, 'date')}${f('submit', '제출한 날', x.submit, 'date')}
      ${f('case_no', '사건번호', x.case_no)}${f('court', '법원', x.court)}${f('party', '당사자', x.party)}${f('doc', '송달 서류', x.doc, '', '예: 소장부본')}
      <div><label class="lb">불능 사유</label><select class="field" data-f="reason" ${x.done ? 'disabled' : ''}><option value="">—</option>${['폐문부재', '이사불명', '수취인불명', '주소불명', '수취인부재', '송달불능'].map(r => `<option ${x.reason === r ? 'selected' : ''}>${r}</option>`).join('')}</select></div>
      ${f('date', '불능일', x.date, 'date')}${f('owner', '담당', x.owner)}${f('new_addr', '새 주소', x.new_addr, '', '초본 보고 넣기')}
      <div class="full"><label class="lb">메모</label><input class="field" data-f="memo" value="${esc(x.memo || '')}" placeholder="예: 초본 신청함, 집행관 접수"></div></div>
    ${D && (D.hist || []).length ? `<div class="lg-sec">주소 기록 (원장)</div><div class="lg-tl">${(D.hist || []).map(h => `<div class="a"><b>${esc(h.addr)}</b><small>${esc(h.note)} · ${esc(h.at)}</small></div>`).join('')}<div class="a now"><b>${esc(D.addr || '(주소 없음)')}</b><small>원장 주소</small></div></div>` : ''}
    <div class="lg-sec">조치 <span class="faint">· 추천 ${esc(x.rec)}</span></div>
    ${x.acts.map(o => `<div class="lg-opt ${act === o.name && x.act ? 'on' : ''} ${o.ok ? '' : 'dis'}" data-act="${esc(o.name)}" title="${esc(o.why)}"><span class="rd"></span><div><b>${esc(o.name)}</b>${o.why ? `<small>${esc(o.why)}</small>` : ''}</div></div>`).join('')}
    ${x.siblings.length && !x.done ? `<label class="small" style="display:flex;gap:8px;margin:8px 0"><input type="checkbox" class="cbx" id="sib" ${LGS.sib ? 'checked' : ''}>같은 채무자의 다른 사건 ${x.siblings.length}건도 같이</label>` : ''}
    <div class="row-gap mt16" style="flex-wrap:wrap">${x.done ? `<button class="btn" id="undo">완료 되돌리기</button>` : `<button class="btn primary" id="toForm" style="flex:1;justify-content:center">회사 양식으로</button><button class="btn" id="toDoc">기본 서류</button><button class="btn" id="fin">완료</button>`}
      <button class="btn danger" id="del">지우기</button></div>
  </div></div>`;
}
function bindDlvPanel(v, x) {
  const set = (field, value) => safe(async () => { await api('lg_dlv_set', {key: x.key, field, value}); go('lg_dlv'); });
  $$('.dl-form [data-f]', v).forEach(i => i.onchange = () => set(i.dataset.f, i.value));
  $$('.lg-opt', v).forEach(o => o.onclick = () => o.classList.contains('dis') ? toast(o.title) : (!x.done && set('act', o.dataset.act)));
  if ($('#sib')) $('#sib').onchange = e => { LGS.sib = e.target.checked; };
  const keys = () => [x.key].concat(LGS.sib ? x.siblings : []);
  if ($('#toForm')) $('#toForm').onclick = () => safe(async () => {
    for (const k of keys()) await api('lg_dlv_set', {key: k, field: 'act', value: x.act || x.rec});
    fmFromDlv(keys());
  });
  if ($('#toDoc')) $('#toDoc').onclick = () => safe(async () => {
    if ((x.act || x.rec) === '초본 발급 요청') return toast('초본을 떼서 「새 주소」를 넣으면 「새 주소로 보정」 서류를 만들 수 있어요');
    for (const k of keys()) await api('lg_dlv_set', {key: k, field: 'act', value: x.act || x.rec});
    go('lg_doc', {type: '주소보정', cur: x.key});
  });
  if ($('#fin')) $('#fin').onclick = () => safe(async () => { const n = await api('lg_dlv_done', {keys: keys()}); toast(`${n}건을 완료로 바꿨어요`); go('lg_dlv'); });
  if ($('#undo')) $('#undo').onclick = () => safe(async () => { await api('lg_dlv_undo', {key: x.key}); go('lg_dlv'); });
  $('#del').onclick = () => safe(async () => {
    if (!await confirmBox('보정 관리에서 지우기', `${esc(x.case_no)} 건을 대장에서 지워요.${x.src === 'auto' ? ' 사건 조회에서 다시 들어오지 않아요.' : ''}`, '지우기')) return;
    await api('lg_dlv_delete', {keys: [x.key]}); LGS.cur = null; toast('지웠어요'); go('lg_dlv');
  });
}
async function dlvAdd() {
  const L = S.legal || {};
  const body = `<div class="form dl-form">
    <div><label class="lb">사건번호 *</label><input class="field" id="a_case_no" placeholder="2026가소12345"></div><div><label class="lb">법원</label><input class="field" id="a_court" placeholder="사건 대장에 있으면 자동"></div>
    <div><label class="lb">당사자</label><input class="field" id="a_party" placeholder="원장에 있으면 이어져요"></div><div><label class="lb">송달 서류</label><input class="field" id="a_doc" placeholder="예: 소장부본, 지급명령정본"></div>
    <div><label class="lb">불능 사유</label><select class="field" id="a_reason">${['폐문부재', '이사불명', '수취인불명', '주소불명', '수취인부재', '송달불능'].map(r => `<option>${r}</option>`).join('')}</select></div>
    <div><label class="lb">불능일</label><input class="field" id="a_date" type="date"></div>
    <div><label class="lb">보정명령 받은 날</label><input class="field" id="a_recv" type="date"></div><div><label class="lb">보정 기간 (일)</label><input class="field" id="a_days" type="number" value="${L.days || 7}" min="1"></div>
    <div><label class="lb">기한 직접 (명령서에 날짜가 있으면)</label><input class="field" id="a_due_set" type="date"></div><div><label class="lb">담당</label><input class="field" id="a_owner" value="${esc(S.me || '')}"></div>
    <div class="full"><label class="lb">메모</label><input class="field" id="a_memo"></div></div>
    <div class="small faint" style="margin-top:10px">기한은 보정명령 받은 다음 날부터 세고, 끝날이 토·일·공휴일이면 다음 평일로 옮겨요. 여러 건은 「엑셀 넣기」가 빨라요.</div>`;
  const ks = ['case_no', 'court', 'party', 'doc', 'reason', 'date', 'recv', 'days', 'due_set', 'owner', 'memo'];
  const save = async (bg, again) => {
    const data = {}; ks.forEach(k => data[k] = $('#a_' + k, bg).value.trim());
    try { const key = await api('lg_dlv_add', {data}); LGS.cur = key; LGS.tab = 'todo'; toast('등록했어요'); return again ? 'again' : true; } catch (e) { toast(e.message, true); return false; }
  };
  const r = await modal('보정 직접 등록', body, [{text: '취소'}, {text: '저장하고 하나 더', value: bg => save(bg, true)}, {text: '저장', cls: 'primary', value: bg => save(bg, false)}], true);
  if (r === 'again') return dlvAdd();
  if (r) go('lg_dlv');
}
async function dlvImport(path, mapping) {
  path = path || await chooseExcel();
  if (!path) return;
  const p = await api('lg_dlv_import_preview', {path, mapping: mapping || null}).catch(e => { toast(e.message, true); return null; });
  if (!p) return;
  const colOpts = j => `<option value="">안 씀</option>${p.header.map((h, i) => `<option value="${i}" ${+j === i && j !== undefined ? 'selected' : ''}>${esc(h || excelCol(i))}</option>`).join('')}`;
  const body = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><b>${esc(p.name)} · ${p.rows}건</b>
      <span>${p.need ? '<span class="chip bad">사건번호 칸을 골라 주세요</span>' : `<span class="chip ok">새로 ${p.new}건</span> <span class="chip now">이미 있는 건 갱신 ${p.update}건</span>`}</span></div>
    <div class="dl-map">${p.fields.map(([k, t]) => `<div><b>${esc(t)}${k === 'case_no' ? ' *' : ''}</b><select class="field" data-m="${k}">${colOpts(p.mapping[k])}</select>${p.auto[k] !== undefined && +p.auto[k] === +p.mapping[k] ? '<span class="chip ok">자동</span>' : ''}</div>`).join('')}</div>
    ${p.sample.length ? `<div class="lg-sec">처음 몇 줄</div><div style="overflow:auto"><table class="tbl lg-tbl"><thead><tr><th></th><th>사건번호</th><th>당사자</th><th>사유</th><th>보정명령</th><th>기한</th></tr></thead><tbody>${p.sample.map(s => `<tr><td>${s._upd ? '<span class="chip now">갱신</span>' : '<span class="chip ok">새로</span>'}</td><td class="num">${esc(s.case_no)}</td><td>${esc(s.party || '')}</td><td>${esc(s.reason || '')}</td><td class="num">${esc(s.recv || '')}</td><td class="num">${esc(s.due || '')}</td></tr>`).join('')}</tbody></table></div>` : ''}
    <label class="small" style="display:flex;gap:8px;align-items:center;margin-top:12px"><input type="checkbox" class="cbx" id="ow">이미 있는 건도 엑셀 값으로 바꾸기 <span class="faint">(끄면 빈 칸만 채워요)</span></label>
    <div class="small faint" style="margin-top:8px">같은 사건번호(보정명령 받은 날이 같으면 그 건)가 이미 대장에 있으면 새로 만들지 않고 갱신해요. 「진행」 칸에 「완료」가 있으면 완료로 바꿔요. <a id="dlTpl">엑셀 양식 받기</a></div>`;
  let remap = null;
  const r = await modal('보정 관리 엑셀 넣기', body, [{text: '취소'}, {text: '칸 다시 보기', value: bg => { remap = {}; $$('[data-m]', bg).forEach(s => { if (s.value !== '') remap[s.dataset.m] = +s.value; }); return 'remap'; }},
    {text: '넣기', cls: 'primary', value: async bg => {
      const m = {}; $$('[data-m]', bg).forEach(s => { if (s.value !== '') m[s.dataset.m] = +s.value; });
      try { const x = await api('lg_dlv_import_apply', {path, mapping: m, overwrite: $('#ow', bg).checked}); toast(`엑셀을 넣었어요 — 새로 ${x.new}건 · 갱신 ${x.update}건`); return true; } catch (e) { toast(e.message, true); return false; }
    }}], true);
  if (r === 'remap') return dlvImport(path, remap);
  if (r) { LGS.tab = 'todo'; go('lg_dlv'); }
}
document.addEventListener('click', e => { if (e.target.id === 'dlTpl') safe(async () => { const p = await api('lg_dlv_template'); toast('양식을 저장했어요: ' + p.split(/[\\/]/).pop()); }); });
async function dlvExport(d, keys) {
  const on = new Set(d.cols_on);
  const order = d.cols_on.concat(d.cols.map(c => c[0]).filter(k => !on.has(k)));
  const name = Object.fromEntries(d.cols);
  const body = `<div class="small muted" style="margin-bottom:10px">내보낼 칸을 고르세요. 고른 칸은 다음에도 기억해요. ${keys.length ? `<b>선택한 ${keys.length}건</b>만 내보내요.` : `지금 목록(<b>${{todo: '처리할 것', done: '끝난 것', all: '전체'}[LGS.tab]}${LGS.flt ? ' · 거른 것' : ''}</b> ${d.items.length}건)을 내보내요.`}</div>
    <div class="dl-cols">${order.map(k => `<label><input type="checkbox" class="cbx" data-c="${k}" ${on.has(k) ? 'checked' : ''}>${esc(name[k])}</label>`).join('')}</div>
    <div class="row-gap" style="margin-top:10px"><button class="btn sm" id="cAll">모두</button><button class="btn sm" id="cBase">기본 칸으로</button></div>
    <div class="notice" style="margin:12px 0 0" id="pi" ${on.has('new_addr') ? '' : 'hidden'}>「새 주소」는 개인정보예요. 회사 밖으로 보내는 자료라면 빼 주세요.</div>`;
  const r = await modal('보정 관리 엑셀로 내보내기', body, [{text: '취소'}, {text: '내보내기', cls: 'primary', value: bg => {
    const cols = $$('[data-c]', bg).filter(c => c.checked).map(c => c.dataset.c);
    return cols.length ? cols : (toast('칸을 하나 이상 골라 주세요', true), false);
  }}], true);
  if (!r) return;
  const x = await api('lg_dlv_export', {cols: r, tab: LGS.tab, flt: LGS.flt, q: LGS.q, keys: keys.length ? keys : null});
  toast(`${x.count}건을 엑셀로 저장했어요: ${x.path.split(/[\\/]/).pop()}`);
}
document.addEventListener('change', e => {
  if (e.target.matches('.dl-cols [data-c]')) { const pi = document.getElementById('pi'); if (pi) pi.hidden = !document.querySelector('.dl-cols [data-c="new_addr"]').checked; }
});
document.addEventListener('click', e => {
  const b = e.target.closest('#cAll, #cBase');
  if (!b) return;
  const base = ['case_no', 'court', 'party', 'reason', 'recv', 'due', 'left', 'act', 'status', 'submit', 'owner', 'memo'];
  document.querySelectorAll('.dl-cols [data-c]').forEach(c => { c.checked = b.id === 'cAll' || base.includes(c.dataset.c); });
  const pi = document.getElementById('pi'); if (pi) pi.hidden = !document.querySelector('.dl-cols [data-c="new_addr"]').checked;
});

// ================================================================== 회생·파산 관리 (관리 가부 추적)
const LGR = {cur: null, closed: false, f: '', q: '', multi: false};
const MG_SHORT = {ok: '가능', warn: '주의', stop: '정지', ban: '금지', end: '불가'};
const MG_CAP = {stop: '명령으로 멈춤', ban: '절차 진행 중', warn: '신청만 접수', ok: '회수 가능', end: '면책'};
const mgChip = m => `<span class="mg ${m.code}">${MG_SHORT[m.code]}</span>`;
function mgBanner(m, small) {
  return `<div class="mg-banner ${m.code} ${small ? 'sm' : ''}"><div class="big">${MG_SHORT[m.code]}</div><div class="w">
    <b>${esc(m.label)}${m.note ? ` <span class="nt">${esc(m.note)}</span>` : ''}</b><div class="d">${esc(m.desc)}</div>
    <div class="why">${m.row ? `판단 근거: ${m.date ? md(m.date) + ' ' : ''}${esc(m.row)}` : esc(m.source === '받은 문서' ? `받은 문서: ${m.event}` : '진행내용이 아직 없어요')} · ${esc(m.basis)}</div></div></div>`;
}
async function rehabRegister(did) {
  const d = await api('lg_rehab');
  const body = `<div class="small muted" style="margin-bottom:14px">법원에서 받은 문서를 보고 넣어 주세요. 사건번호와 법원을 넣으면 사건 대장에도 들어가 「사건 조회」로 관리 가부를 확인해요.</div>
    <div class="form"><div><label class="lb">받은 문서</label><select class="field" id="rd">${d.docs.filter(x => x !== '공공정보 등재').map(x => `<option>${x}</option>`).join('')}</select></div>
    <div><label class="lb">절차</label><select class="field" id="rk">${d.kinds.map(x => `<option>${x}</option>`).join('')}</select></div>
    <div class="full"><label class="lb">채무자 (원장)</label><select class="field" id="rdid"><option value="">— 원장에 없음 (아래에 이름)</option>${d.candidates.map(x => `<option value="${x.id}" ${x.id === did ? 'selected' : ''}>${esc(x.name)} · ${esc(x.birth || '')} · ${esc(x.key || '')} · ${x.stage}</option>`).join('')}</select></div>
    <div><label class="lb">원장에 없으면 이름</label><input class="field" id="rn"></div><div><label class="lb">생년월일</label><input class="field" id="rb"></div>
    <div><label class="lb">사건번호</label><input class="field" id="rno" placeholder="2026개회12345"></div><div><label class="lb">법원</label><input class="field" id="rc" list="qCourts2" placeholder="서울회생법원"><datalist id="qCourts2">${[...new Set(INFO.courts)].filter(n => /회생|지방법원/.test(n)).map(n => `<option value="${esc(n)}">`).join('')}</datalist></div>
    <div><label class="lb">받은 날</label><input class="field" type="date" id="rg" value="${INFO.today}"></div><div><label class="lb">이의·신고 기한 (있으면)</label><input class="field" type="date" id="rdue"></div></div>`;
  const rd = () => { const doc = $('#rd').value; const k = {파산선고: '파산·면책', '면책 심리 통지': '파산·면책', 보전처분: '법인회생'}[doc]; if (k) $('#rk').value = k; };
  setTimeout(() => { const s = $('#rd'); if (s) s.onchange = rd; }, 30);
  const rid = await modal('받은 문서 등록', body, [{text: '취소'}, {text: '등록', cls: 'primary', value: async bg => {
    try {
      return await api('lg_rehab_register', {data: {doc: $('#rd', bg).value, kind: $('#rk', bg).value, did: $('#rdid', bg).value, name: $('#rn', bg).value,
        birth: $('#rb', bg).value, no: $('#rno', bg).value, court: $('#rc', bg).value, got: $('#rg', bg).value, due: $('#rdue', bg).value}});
    } catch (e) { toast(e.message, true); return false; }
  }}], true);
  if (rid) { LGR.cur = rid; toast('등록했어요 — 정지·금지면 서류 작성 대상에서 자동으로 빠져요'); go('lg_rehab'); }
}
SCREENS.lg_rehab = async (v, a) => {
  if (a.rid) LGR.cur = a.rid;
  if (a.f !== undefined) LGR.f = a.f;
  const d = await api('lg_rehab', {closed: LGR.closed, flt: LGR.f, q: LGR.q});
  const cur = d.items.find(x => x.id === LGR.cur) || d.items[0];
  const c = d.counts;
  const multi = LGR.multi;
  v.innerHTML = head(`${esc(INFO.book)} · 회생·파산으로 넘어간 채권의 관리 가부를 추적해요`, `회생·파산 관리 <span class="faint" style="font-weight:500">${d.total}</span>`,
    `<div class="seg"><button class="${!LGR.closed ? 'on' : ''}" data-cl="0">추적 중</button><button class="${LGR.closed ? 'on' : ''}" data-cl="1">끝낸 것</button></div><button class="btn" id="pub">공공정보 엑셀</button><button class="btn" id="reg">+ 받은 문서 등록</button>`) +
    `<div class="pick-grid"><div class="side-col">
      <div class="card main-card" id="rq"><div class="card-h"><div class="mc-h"><span class="mc-ic">✎</span><div><h2>회생·파산 사건 조회</h2><div class="small muted">개회 · 하단 · 하면 · 회단 사건번호로 바로 조회해 관리 가부를 판단해요</div></div></div><a class="small" id="rqMode">${multi ? '한 건씩 넣기' : '여러 건 붙여넣기'}</a></div><div class="card-b">
        ${multi ? `<textarea class="field" id="rqText" rows="4" placeholder="한 줄에 한 건 — 엑셀에서 복사해 붙여넣어도 돼요&#10;서울회생법원	2026개회12345	홍길동&#10;수원회생법원, 2025하단4410, 김가나"></textarea>`
          : `<div class="q-row"><input class="field" id="rqCourt" list="rqCourts" placeholder="법원 (예: 서울회생법원)"><datalist id="rqCourts">${[...new Set(INFO.courts)].map(n => `<option value="${esc(n)}">`).join('')}</datalist>
          <input class="field" id="rqNo" placeholder="사건번호 (2026개회12345)"><input class="field" id="rqParty" placeholder="채무자 이름"></div>`}
        <div class="small err mt8" id="rqInfo"></div>
        <div class="row-gap" style="margin-top:12px"><span class="small muted" style="flex:1">조회 순서는 「사건 조회」와 같아요 — 그림 숫자를 치면 바로 조회되고, 결과에 관리 가부가 크게 나와요.</span>
          <button class="btn blue big-btn" id="rqGo">바로 조회 →</button></div></div></div>
      <div class="card main-card"><div class="card-h"><div class="mc-h"><span class="mc-ic">▦</span><div><h2>엑셀 넣어서 대량 조회</h2><div class="small muted">법원 · 사건번호 · 채무자 칸을 자동으로 찾아요</div></div></div></div>
        <div class="card-b"><div class="xdrop" id="rqDrop" style="padding:26px 20px"><b>회생·파산 사건 목록 엑셀을 골라 주세요</b><div class="muted mt8">.xlsx .xls .csv · 칸을 확인한 뒤 바로 조회해요</div></div></div></div>
    </div>
    <div class="side-col"><div class="card"><div class="card-h"><h2>추적 중인 사건 다시 확인</h2></div>
      <div class="mg-tiles">${['stop', 'ban', 'warn', 'ok', 'end'].map(k => `<button class="mg-tile ${k} ${LGR.f === k ? 'on' : ''}" data-mf="${k}"><span class="mg ${k}">${MG_SHORT[k]}</span><b class="num">${c[k] || 0}</b><small>${MG_CAP[k]}</small></button>`).join('')}</div>
      <div class="card-b" style="border-top:1px solid var(--line);display:flex;flex-direction:column;gap:8px">
        <button class="btn blue" id="reBlock" ${d.blocking.length ? '' : 'disabled'} style="justify-content:center">정지·금지·주의 ${d.blocking.length}건 다시 조회 →</button>
        <div class="row-gap"><button class="btn sm" id="reStale" ${d.stale.length ? '' : 'disabled'} style="flex:1;justify-content:center">${d.stale_days}일 넘게 안 본 ${d.stale.length}건</button><button class="btn sm" id="reAll" ${d.all_ids.length ? '' : 'disabled'} style="flex:1;justify-content:center">전체 ${d.all_ids.length}건</button></div>
        <div class="small faint">면책 확정·기각·폐지 확정은 「끝내기」로 닫으면 목록에서 빠져요.</div></div></div></div></div>
    <div class="lg-split mt16" style="grid-template-columns:minmax(0,1fr) 380px"><div class="card" style="overflow:hidden">
      <div class="filters">${[['', '전체', d.total], ...['stop', 'ban', 'warn', 'ok', 'end'].map(k => [k, MG_SHORT[k], c[k] || 0])].map(([k, n, cnt]) => `<button class="f ${LGR.f === k ? 'on' : ''}" data-mf="${k}">${n}<em>${cnt}</em></button>`).join('')}
        <input class="search" id="rqQ" placeholder="채무자·사건번호 찾기" value="${esc(LGR.q)}"></div>
      ${d.items.length ? `<table class="tbl lg-tbl"><thead><tr><th>관리 가부</th><th>채무자</th><th>사건</th><th>판단 근거 (최근 진행)</th><th>마지막 조회</th></tr></thead><tbody>
      ${d.items.map(x => `<tr class="click ${cur && cur.id === x.id ? 'sel' : ''}" data-r="${x.id}"><td class="nw">${mgChip(x.m)}${x.change ? ' <span class="newdot">바뀜</span>' : ''}${!x.stop_ok && ['stop', 'ban', 'end'].includes(x.m.code) ? '<div class="small" style="color:var(--bad);margin-top:3px">멈춤 확인 필요</div>' : ''}</td>
        <td class="nw"><b>${esc(x.debtor.name)}</b>${x.debtor.id ? '' : '<div class="small faint">원장 없음</div>'}</td>
        <td class="nw"><span class="num">${esc(x.no) || '<span class="chip warn">사건번호 확인</span>'}</span><div class="small muted">${esc(x.m.kind || x.kind)} · ${esc((x.court || '').replace('지방법원', ''))}</div></td>
        <td class="small">${x.m.row ? `<b>${esc(x.m.event)}</b> · ${x.m.date ? md(x.m.date) + ' ' : ''}${esc(x.m.row)}` : `<span class="faint">${esc(x.m.source === '받은 문서' ? '받은 문서: ' + x.m.event : '조회 전')}</span>`}</td>
        <td class="nw small muted">${x.case ? (x.case.checked ? md(x.case.checked.slice(0, 10)) : '<span class="chip warn">조회 전</span>') : '<span class="faint">사건 대장 없음</span>'}</td></tr>`).join('')}</tbody></table>`
      : empty(d.total ? '맞는 사건이 없어요' : '추적 중인 회생·파산 사건이 없어요', d.total ? '다른 보기를 골라 보세요.' : '위에서 사건번호로 조회하거나, 법원에서 받은 문서를 등록해 주세요. 사건 대장의 개회·하단·하면 사건도 자동으로 여기 모여요.')}</div>
    ${cur ? rehabPanel(cur) : '<div></div>'}</div>`;
  $$('[data-cl]', v).forEach(b => b.onclick = () => { LGR.closed = b.dataset.cl === '1'; LGR.cur = null; go('lg_rehab'); });
  $$('[data-mf]', v).forEach(b => b.onclick = () => { LGR.f = LGR.f === b.dataset.mf ? '' : b.dataset.mf; go('lg_rehab'); });
  $$('tr[data-r]', v).forEach(tr => tr.onclick = () => { LGR.cur = tr.dataset.r; go('lg_rehab'); });
  const qq = $('#rqQ');
  qq.oninput = () => { clearTimeout(qq._t); qq._t = setTimeout(() => { LGR.q = qq.value.trim(); go('lg_rehab').then(() => { const n = $('#rqQ'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }); }, 300); };
  $('#rqMode').onclick = () => { LGR.multi = !LGR.multi; go('lg_rehab'); };
  const text = () => multi ? $('#rqText').value : [$('#rqCourt').value, $('#rqNo').value, $('#rqParty').value].map(x => x.trim()).join('\t');
  $$('#rqCourt,#rqNo,#rqParty', v).forEach(i => i.onkeydown = e => { if (e.key === 'Enter') $('#rqGo').click(); });
  $('#rqGo').onclick = () => safe(async () => {
    try {
      const st = await api('lg_rehab_search', {text: text(), keep: true});
      if (st.skipped && st.skipped.length) toast(`회생·파산이 아니거나 못 읽은 줄 ${st.skipped.length}개는 빼고 조회해요`);
      go('run', {state: st});
    } catch (e) { $('#rqInfo').textContent = e.message; }
  });
  $('#rqDrop').onclick = () => safe(async () => { const p = await chooseExcel(); if (p) go('pick', {xl: p}); });
  const recheck = scope => safe(async () => go('run', {state: await api('lg_rehab_recheck', {scope})}));
  $('#reBlock').onclick = () => recheck('blocking');
  $('#reStale').onclick = () => recheck('stale');
  $('#reAll').onclick = () => recheck('all');
  $('#reg').onclick = () => rehabRegister();
  $('#pub').onclick = () => safe(async () => {
    const path = await chooseExcel(); if (!path) return;
    const p = await api('lg_rehab_public_preview', {path});
    const ok = await modal('공공정보 엑셀 넣기', `<div class="small muted" style="margin-bottom:10px">${p.rows.length}줄 중 원장과 맞은 새 채무자 <b>${p.matched}</b>명 · 사건번호가 있으면 조회해서 관리 가부를 확인해 주세요</div>
      <table class="tbl"><tr><th>이름</th><th>생년</th><th>내용</th><th>원장</th></tr>${p.rows.slice(0, 30).map(x => `<tr><td>${esc(x.name)}</td><td>${esc(x.birth)}</td><td>${esc(x.kindtxt || x.kind)}</td><td>${x.already ? chip('이미 추적 중', 'gray') : x.did ? chip('맞음', 'green') : chip('원장에 없음', 'gray')}</td></tr>`).join('')}</table>`,
      [{text: '취소'}, {text: `${p.matched}명 등록`, cls: 'primary', value: () => true}], true);
    if (ok) { const n = await api('lg_rehab_public_apply', {path}); toast(`${n}명 등록했어요`); go('lg_rehab'); }
  });
  if (cur) bindRehabPanel(v, cur);
};
function rehabPanel(r) {
  const f = (k, t, val, type) => `<div><label class="lb">${t}</label><input class="field" data-rf="${k}" ${type ? `type="${type}"` : ''} value="${esc(val ?? '')}" ${r.closed ? 'disabled' : ''}></div>`;
  const ch = r.change;
  return `<div class="card lg-panel"><div class="card-h"><div><h2>${esc(r.debtor.name)} · ${esc(r.no || '사건번호 없음')}</h2><div class="small muted">${esc(r.m.kind || r.kind)} · ${esc(r.court || '')}${r.case && r.case.checked ? ' · 마지막 조회 ' + esc(r.case.checked.slice(5, 16)) : ''}</div></div>${r.due ? dday(r.left) : ''}</div>
  <div class="card-b">
    ${mgBanner(r.m)}
    ${ch ? `<div class="notice" style="margin:12px 0 0">관리 가부가 바뀌었어요: <b>${esc(MG_SHORT[ch.from])} → ${esc(MG_SHORT[ch.to])}</b> (${esc(ch.event)}) <a id="seen">확인함</a></div>` : ''}
    ${!r.stop_ok && ['stop', 'ban', 'end'].includes(r.m.code) ? `<div class="notice bad" style="margin:12px 0 0"><b>멈춰야 할 우리 법조치 ${r.live.length}건</b>${r.live.map(c => `<br>· ${esc(c.case_no)} ${esc(c.kind)} (${esc(c.status)})`).join('') || '<br>· 진행 중인 법조치 없음'}<div class="mt8"><button class="btn sm" id="stopOk">멈춤 확인함</button></div></div>` : ''}
    <div class="lg-steps mt16">${r.flow.map((s, i) => `<div class="${i < r.stage ? 'done' : i === r.stage ? 'now' : ''}"><i>${i < r.stage ? '✓' : i + 1}</i>${esc(s.replace(' (관재인 선임 시)', ''))}</div>`).join('')}</div>
    <div class="form mt16">${f('no', '사건번호', r.no)}${f('court', '법원', r.court)}${f('due', '이의·신고 기한', r.due, 'date')}${r.kind === '개인회생' ? f('list_amt', '채권자목록 금액', r.list_amt ? won(r.list_amt) : '') : '<div></div>'}</div>
    ${r.list_amt ? `<div class="lg-kv mt16"><span>목록 금액</span><span class="num">${won(r.list_amt)}원</span><span>우리 금액</span><b class="num">${won(r.debtor.claim)}원</b><span>차이</span><b class="num" style="color:${r.debtor.claim - r.list_amt ? 'var(--bad)' : 'var(--ok)'}">${won(r.debtor.claim - r.list_amt)}원</b></div>` : ''}
    ${r.closed ? `<div class="notice info mt16">끝냄 · ${esc(r.close_reason || '')} ${esc((r.closed || '').slice(0, 10))}</div>` : `<div class="row-gap mt16">${r.case ? '<button class="btn primary" id="reOne">다시 조회</button>' : ''}${r.case ? `<button class="btn" data-go="case" data-arg='${JSON.stringify({cid: r.case.id})}'>사건 상세</button>` : ''}${r.actions.map(x => `<button class="btn" data-ra="${esc(x)}">${esc(x)}</button>`).join('')}<button class="btn ghost" id="rClose">끝내기</button></div>`}
    <div class="small faint mt8" style="line-height:1.6">관리 가부는 진행내용으로 판단한 예상이에요. 결정의 확정 여부와 송달은 사건 상세에서 확인해 주세요.</div>
    ${(r.log || []).length ? `<div class="lg-sec">기록</div>${r.log.slice(0, 6).map(l => `<div class="small">· ${esc(l.text)} <span class="faint">${esc(l.at.slice(5, 16))}</span></div>`).join('')}` : ''}
  </div></div>`;
}
function bindRehabPanel(v, r) {
  $$('[data-rf]', v).forEach(i => i.onchange = () => safe(async () => { await api('lg_rehab_set', {rid: r.id, field: i.dataset.rf, value: i.value}); go('lg_rehab'); }));
  if ($('#stopOk')) $('#stopOk').onclick = () => safe(async () => { await api('lg_rehab_stop_ok', {rid: r.id}); toast('멈춤 확인을 기록했어요'); go('lg_rehab'); });
  if ($('#seen')) $('#seen').onclick = () => safe(async () => { await api('lg_rehab_seen', {rid: r.id}); go('lg_rehab'); });
  if ($('#reOne')) $('#reOne').onclick = () => safe(async () => go('run', {state: await api('run_start', {name: '회생·파산 확인', case_ids: [r.case.id]})}));
  $$('[data-ra]', v).forEach(b => b.onclick = () => safe(async () => {
    let note = '';
    if (b.dataset.ra.includes('사유')) {
      note = await modal('사유 기록', '<label class="lb">사유</label><input class="field" id="rs">', [{text: '취소'}, {text: '기록', cls: 'primary', value: bg => $('#rs', bg).value.trim() || false}]);
      if (!note) return;
    }
    const res = await api('lg_rehab_do', {rid: r.id, action: b.dataset.ra, note});
    toast(res.file ? '서류를 만들었어요: ' + res.file : '기록했어요');
    go('lg_rehab');
  }));
  if ($('#rClose')) $('#rClose').onclick = () => safe(async () => {
    const why = await modal('끝내기', `<label class="lb">끝난 이유</label><select class="field" id="cw">${['면책 확정', '폐지 확정', '기각 확정', '취하', '그 밖'].map(x => `<option>${x}</option>`).join('')}</select><div class="small muted mt8">면책 확정이면 채무자 단계를 「종결」로 바꿔요. 그 밖의 이유면 멈춤이 풀려 다시 회수를 검토할 수 있어요.</div>`,
      [{text: '취소'}, {text: '끝내기', cls: 'primary', value: bg => $('#cw', bg).value}]);
    if (!why) return;
    await api('lg_rehab_close', {rid: r.id, reason: why});
    go('lg_rehab');
  });
}

// ================================================================== 기준표
SCREENS.lg_std = async v => {
  const d = await api('lg_std');
  const unchecked = d.items.filter(i => !i.check).length;
  v.innerHTML = head('법령이 바뀌는 값은 여기 한곳에 · 모든 채권이 같이 씀', '기준표 (법령 값)', `<button class="btn" id="sUndo" ${d.log.length ? '' : 'disabled'}>되돌리기</button>`) +
    `<div class="notice ${unchecked ? '' : 'info'}">값마다 <b>시행일</b>이 있어요. 계산은 신청하는 날(오늘)에 맞는 줄을 써요. ${unchecked ? `<b>확인 안 된 값 ${unchecked}개</b> — 법령·고시로 확인하고 「확인함」을 눌러 주세요.` : '모든 값에 확인 기록이 있어요.'} 처음 값은 2026. 11. 1. 웹 자료로 확인한 것이에요(출처는 각 칸에).</div>
    <div class="lg-std">${d.items.map(it => `<div class="card"><div class="card-b">
      <div style="display:flex;justify-content:space-between;gap:8px"><b>${esc(it.name)}</b>${it.check ? chip('확인함', 'green') : chip('확인 필요', 'orange')}</div>
      <div class="lg-big num" style="margin:8px 0 2px">${it.key === 'ecfs' ? it.cur : won(it.cur)} <small class="muted" style="font-size:13px;font-weight:500">${esc(it.unit)}</small></div>
      <div class="small faint">${esc(it.cur_from)}부터 · ${esc(it.basis)}</div>
      <table class="tbl mt8 lg-stbl"><tr><th>시행일</th><th class="right">값</th><th></th></tr>${it.rows.map((r, i) => `<tr><td><input class="field" type="date" data-k="${it.key}" data-i="${i}" data-f="from" value="${r.from}"></td><td><input class="field num" style="text-align:right" data-k="${it.key}" data-i="${i}" data-f="v" value="${it.key === 'ecfs' ? r.v : won(r.v)}"></td><td><button class="btn sm ghost" data-sdel="${it.key}|${i}" title="${esc(r.check || '확인 기록 없음')}">✕</button></td></tr>`).join('')}</table>
      <div class="row-gap mt8"><button class="btn sm" data-add="${it.key}">+ 새 시행일</button><button class="btn sm" data-chk="${it.key}">확인함</button></div>
      <div class="small faint mt8" style="line-height:1.5">${it.check ? '확인: ' + esc(it.check) : '이 값은 아직 확인 기록이 없어요'}</div></div></div>`).join('')}
      <div class="card"><div class="card-b"><b>기한 계산 쉬는 날</b><div class="small muted mt8">토·일요일은 자동이에요. 공휴일·대체공휴일을 한 줄에 하나씩 (YYYY-MM-DD)</div><textarea class="field mt8" id="hol" style="min-height:150px;font-size:13px">${d.holidays.join('\n')}</textarea><button class="btn sm mt8" id="holSave">저장</button></div></div>
    </div>
    <div class="card mt16" style="overflow:hidden"><div class="card-h"><div><h2>소액임차인 최우선변제 기준</h2><div class="small muted">선순위 담보물권(근저당 등) 설정일이 속한 줄을 써요 · 보증금 한도 / 최우선 금액 (만 원) · 지역 구분은 그때 시행령 기준</div></div><button class="btn sm" id="smSave">저장</button></div>
      <div class="card-b"><table class="tbl lg-stbl"><tr><th>시행일</th>${d.zones.map(z => `<th class="right" colspan="2">${z}</th>`).join('')}<th>확인</th></tr>
      ${d.small.map((r, i) => `<tr><td><input class="field" type="date" data-sm="${i}" data-f="from" value="${r.from}"></td>${r.v.map((p, j) => `<td><input class="field num" style="text-align:right" data-sm="${i}" data-z="${j}" data-p="0" value="${Math.round(p[0] / 1e4).toLocaleString('ko-KR')}"></td><td><input class="field num" style="text-align:right;font-weight:600" data-sm="${i}" data-z="${j}" data-p="1" value="${Math.round(p[1] / 1e4).toLocaleString('ko-KR')}"></td>`).join('')}
        <td class="small w" style="max-width:220px">${r.check ? esc(r.check) : '<span class="chip warn">확인 필요</span>'}</td></tr>`).join('')}</table></div></div>
    ${d.log.length ? `<div class="card mt16"><div class="card-h"><h2>바꾼 기록</h2></div><div class="card-b">${d.log.map(l => `<div class="small" style="padding:3px 0">· ${esc(l.text)} <span class="faint">${esc(l.at)} ${esc(l.by)}</span></div>`).join('')}</div></div>` : ''}`;
  const rowsOf = k => { const it = d.items.find(i => i.key === k); return it.rows.map((r, i) => ({from: $(`[data-k="${k}"][data-i="${i}"][data-f="from"]`).value, v: String($(`[data-k="${k}"][data-i="${i}"][data-f="v"]`).value).replace(/,/g, ''), check: r.check})); };
  const save = (k, rows) => safe(async () => { await api('lg_std_set', {key: k, rows}); toast('기준표를 바꿨어요 — 모든 계산에 바로 반영돼요'); go('lg_std'); });
  $$('[data-k]', v).forEach(i => i.onchange = () => { const rows = rowsOf(i.dataset.k); rows[+i.dataset.i].check = ''; save(i.dataset.k, rows); });
  $$('[data-add]', v).forEach(b => b.onclick = () => { const rows = rowsOf(b.dataset.add); rows.push({from: INFO.today, v: rows[rows.length - 1].v, check: ''}); save(b.dataset.add, rows); });
  $$("[data-sdel]", v).forEach(b => b.onclick = () => { const [k, i] = b.dataset.sdel.split('|'); const rows = rowsOf(k); rows.splice(+i, 1); save(k, rows); });
  $$('[data-chk]', v).forEach(b => b.onclick = () => safe(async () => {
    const src = await modal('확인함', '<label class="lb">무엇으로 확인했나요 (예: 국가법령정보센터, 법원 공지)</label><input class="field" id="src">', [{text: '취소'}, {text: '확인함', cls: 'primary', value: bg => $('#src', bg).value.trim() || '확인'}]);
    if (!src) return;
    await api('lg_std_check', {key: b.dataset.chk, src}); go('lg_std');
  }));
  $('#holSave').onclick = () => safe(async () => { await api('lg_std_holidays', {days: $('#hol').value.split(/\s+/).filter(Boolean)}); toast('쉬는 날을 저장했어요'); go('lg_std'); });
  $('#smSave').onclick = () => safe(async () => {
    const rows = d.small.map((r, i) => ({from: $(`[data-sm="${i}"][data-f="from"]`).value, check: r.check,
      v: r.v.map((p, j) => [0, 1].map(k => (+String($(`[data-sm="${i}"][data-z="${j}"][data-p="${k}"]`).value).replace(/,/g, '') || 0) * 1e4))}));
    await api('lg_std_small', {rows}); toast('소액임차인 기준을 저장했어요'); go('lg_std');
  });
  $('#sUndo').onclick = () => safe(async () => { await api('lg_std_undo'); toast('되돌렸어요'); go('lg_std'); });
};
