/* 배당기일 — ① 조회·매칭 · ② 배당기일 현황 · ③ 배당 관리 대장 · ④ 배당 통계 · 오늘 할 일(현황 콘솔) */
'use strict';
const DVW = n => (n === '' || n === null || n === undefined) ? '' : Math.round(+n).toLocaleString('ko-KR');
const DVM = n => Math.round((+n || 0) / 10000).toLocaleString('ko-KR');
const DVR = {'대기': '대기', '발송': '발송', '수령': '수령완료'};
const dvD = d => d ? d.slice(2).replace(/-/g, '.') : '—';
const dvLeft = d => d ? Math.round((new Date(d + 'T00:00') - new Date(INFO.today + 'T00:00')) / 864e5) : null;
function dvDd(d) {
  const n = dvLeft(d);
  if (n === null) return '';
  const c = n < 0 ? 'faint' : n <= 7 ? 'dv-red' : n <= 21 ? 'dv-warn' : 'faint';
  return `<span class="dv-dd ${c}">${n < 0 ? '지남' : n === 0 ? '오늘' : 'D-' + n}</span>`;
}
const dvTag = (t, c = '') => `<span class="dv-tag ${c}">${esc(t)}</span>`;
const dvMac = () => /Mac/.test(navigator.platform) ? '⌘' : 'Ctrl';
function dvCopy(text, msg) {
  const done = () => toast(msg || '복사했어요');
  const fallback = () => { const t = document.createElement('textarea'); t.value = text; t.style.cssText = 'position:fixed;left:-9999px'; document.body.appendChild(t); t.select(); try { document.execCommand('copy'); } catch (e) { /* 무시 */ } t.remove(); done(); };
  try { navigator.clipboard.writeText(text).then(done, fallback); } catch (e) { fallback(); }
}
function dvUndo(msg, fn) {
  let u = $('#dvUndo');
  if (!u) { u = document.createElement('div'); u.id = 'dvUndo'; u.className = 'dv-undo'; document.body.appendChild(u); }
  u.innerHTML = `<span>${msg}</span><button class="btn sm">되돌리기</button>`;
  u.classList.add('on');
  clearTimeout(u._t);
  $('button', u).onclick = () => safe(async () => { u.classList.remove('on'); await fn(); toast('되돌렸어요'); });
  u._t = setTimeout(() => u.classList.remove('on'), 7000);
}
// 줄 끌기: ⋮⋮ 손잡이를 잡고 위아래로
const DV_GRIP = '<span class="dv-grip" title="끌어서 순서 바꾸기">⋮⋮</span>';
function dvDrag(tbody, onMove) {
  if (!tbody) return;
  $$('tr[data-rk]', tbody).forEach(tr => {
    const g = $('.dv-grip', tr);
    if (!g) return;
    g.onmousedown = () => { tr.draggable = true; };
    tr.ondragstart = e => { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', tr.dataset.rk); tr.classList.add('dragging'); tbody._from = tr.dataset.rk; };
    tr.ondragend = () => { tr.draggable = false; tr.classList.remove('dragging'); $$('.dropb,.dropa', tbody).forEach(x => x.classList.remove('dropb', 'dropa')); };
    tr.ondragover = e => { if (!tbody._from) return; e.preventDefault(); const r = tr.getBoundingClientRect(); const after = e.clientY > r.top + r.height / 2;
      $$('.dropb,.dropa', tbody).forEach(x => x !== tr && x.classList.remove('dropb', 'dropa')); tr.classList.toggle('dropa', after); tr.classList.toggle('dropb', !after); };
    tr.ondrop = e => { e.preventDefault(); const from = tbody._from; tbody._from = null; const after = tr.classList.contains('dropa'); if (from && from !== tr.dataset.rk) onMove(from, tr.dataset.rk, after); };
  });
}
function dvMove(keys, from, to, after) { const a = keys.filter(k => k !== from); const i = a.indexOf(to); if (i < 0) return keys; a.splice(after ? i + 1 : i, 0, from); return a; }

// 메뉴
NAV_PILLS.push(i => {
  const D = i.dividend || {};
  const p = $('#pillDv'); if (p) { p.hidden = !D.ledger; p.textContent = D.ledger; }
});
MENU_DEFAULT.splice(3, 0, {name: '배당기일', items: ['dv_run', 'dv_board', 'dv_ledger', 'dv_stats']});
MENU_FOLD_DEFAULT['배당기일'] = false;

// ================================================================== ① 조회 · 매칭
let DVS = null, DVTAB = 'search';
SCREENS.dv_run = async (v, a) => {
  DVS = await api('dv_state');
  if (a && a.tab) DVTAB = a.tab;
  if (DVS.matched && !a.tab && DVTAB === 'search' && DVS.search.total && DVS.search.done === DVS.search.total) DVTAB = 'match';
  dvRunDraw(v);
  if (a && a.pick) dvPick();
};
function dvRunDraw(v) {
  const d = DVS, S_ = d.search, M_ = d.matched, x = d.xlsm;
  document.body.classList.add('dv-fit');
  v.innerHTML = head(`${esc(INFO.book)} · 배당기일 · ①`, `조회 · 매칭<span class="dv-h1d">배당사건 붙여넣기 → 사건검색 → 법조치 자료와 법원+사건번호로 매칭</span>`,
    `<span class="dv-dgrp"><button class="btn" id="dvData" title="${x.ok ? esc(x.path) + ' — 엑셀로 열기' : '경로를 먼저 정해 주세요'}"><i class="dv-dot ${x.ok ? 'ok' : 'no'}"></i>DATA 가공</button><button class="btn dv-dset" id="dvDataSet" title="매크로 엑셀 경로">경로</button></span><button class="btn" id="dvReset" title="붙여넣기 칸 · 사건검색 결과 · 매칭 결과를 비워요 (대장은 그대로)">초기화</button>`) +
    `<div class="dv-ins">
      <div class="card dv-icard ${S_.total && S_.done === S_.total ? 'done' : ''}">
        <div class="dv-ih"><span class="dv-bn">1</span><div class="dv-it"><h2>배당사건 → 사건검색</h2><div class="small faint">채무자 · 법원 · 사건번호<br>「서울남부지법」「2026 타배 99005」도 맞춰 읽어요</div></div>
          <div class="dv-ib"><button class="btn sm" id="dvPick">다시 조회할 건 고르기</button><button class="btn sm" id="dvF1">엑셀 파일로</button></div></div>
        <textarea id="dv1" class="dv-ta" spellcheck="false" placeholder="채무자\t법원\t사건번호&#10;한○민\t부산지방법원\t2026타배99004">${esc(d.case_text || '')}</textarea>
        <div class="dv-if"><button class="btn primary" id="dvGo1">${d.running ? `조회 화면으로 (${S_.done}/${S_.total})` : '사건검색 시작'}</button><div class="dv-fi" id="dvSum1">${S_.total ? `<span class="small faint">지난 조회 ${S_.done}/${S_.total}건 · 성공 ${S_.ok}${S_.fail ? ` · <b style="color:var(--bad)">실패 ${S_.fail}</b>` : ''}</span>` : '<span class="small faint">나의사건검색으로 하나씩 조회 → 배당기일 · 관련사건 · 공탁자 · 숫자는 사람이 입력</span>'}</div></div>
      </div>
      <div class="card dv-icard ${M_ ? 'done' : ''}">
        <div class="dv-ih"><span class="dv-bn">2</span><div class="dv-it"><h2>당사 법조치 자료 → 매칭</h2><div class="small faint">채무자키 · 법조치키 · 채무자명 · 담당자명<br>법원 · 사건번호(타채 등) · 청구액 있으면 함께</div></div>
          <div class="dv-ib"><button class="btn sm" id="dvLast" ${d.law.n ? '' : 'disabled'} title="${esc(d.law.src)} · ${d.law.n}줄">지난번 자료${d.law.at ? ' (' + md(d.law.at.slice(0, 10)) + ')' : ''}</button><button class="btn sm" id="dvF2">엑셀 파일로</button></div></div>
        <textarea id="dv2" class="dv-ta" spellcheck="false" placeholder="채무자키\t법조치키\t채무자명\t담당자명\t법원\t사건번호">${esc(d.law.text || '')}</textarea>
        <div class="dv-if"><button class="btn primary" id="dvGo2" ${S_.done ? '' : 'disabled'}>자동 매칭</button><div class="dv-fi" id="dvSum2">${d.law.n && !d.law.hidden ? dvSum(d.law.n, d.law.missing, d.law.guessed) : `<span class="small faint">${S_.done ? '<b>법원 + 사건번호</b>로 배당사건 · 관련사건 전부를 찾아요' : '1번 사건검색이 끝나면 눌러요 (자료는 먼저 넣어 둬도 돼요)'}</span>`}</div></div>
      </div></div>
    ${dvResult()}`;
  dvRunBind(v);
}
const dvSum = (n, miss, guessed) => `<span class="small faint"><b style="color:var(--text)">${n}줄</b> 읽음</span>` + (miss && miss.length ? miss.map(m => `<span class="dv-ck no">✕ ${esc(m)} 칸 없음</span>`).join('') : guessed ? '<span class="dv-ck no" style="background:var(--warn-soft);color:var(--warn)">? 머리글 없어 값 모양으로 짐작</span>' : '<span class="dv-ck">✓ 채무자키 · 법조치키 · 사건번호 칸 찾음</span>') + '<a class="small" data-lawmap style="cursor:pointer;margin-left:4px">칸 맞추기</a>';
function dvResult() {
  const S_ = DVS.search, M_ = DVS.matched;
  const tabs = `<button data-dvt="search" class="${DVTAB === 'search' ? 'on' : ''}" ${S_.total ? '' : 'disabled'}>사건검색 결과 ${S_.total ? `<em>${S_.total}</em>` : ''}${S_.fail ? dvTag('실패 ' + S_.fail, 'bad') : ''}</button>
    <button data-dvt="match" class="${DVTAB === 'match' ? 'on' : ''}" ${M_ ? '' : 'disabled'}>매칭 결과 ${M_ ? `<em>${M_.rows.length}줄</em>` : ''}</button>`;
  let right = '', body = '';
  if (DVTAB === 'match' && M_) {
    const c = M_.count;
    right = `${c.remembered ? dvTag('직접 연결 기억 ' + c.remembered, 'now') : ''}${c.notours ? dvTag('우리 사건 아님(기억) ' + c.notours + ' 뺌') : ''}${dvTag('맞음 ' + c.ok, 'ok')}${dvTag('키 여러 개 ' + c.multi, 'now')}${dvTag('못 찾음 ' + c.none, 'warn')}
      <button class="btn sm" id="dvDiag" title="매칭이 안 될 때 원인 찾기용 파일 (이름 등 개인정보 빼고)">진단 저장</button><button class="btn sm" id="dvXl1">엑셀로</button><button class="btn sm primary" id="dvSave">②·③에 저장 (${new Set(M_.rows.map(r => r.court + r.no)).size}건)</button>`;
    body = dvOutTable(M_.rows, true, 'm');
  } else if (S_.total) {
    right = '<span class="small faint">실패 건은 다시 조회하거나 대장에서 배당기일을 직접 써 넣어요 · ⋮⋮ 끌어서 순서</span>';
    body = `<table class="dv-t" id="dvTS"><thead><tr><th class="dv-gc"></th><th>채무자</th><th>법원</th><th>사건번호</th><th>배당기일</th><th>공탁자(제3채무자)</th><th>관련사건 (뽑은 것)</th><th class="dv-dc"></th></tr></thead><tbody>
      ${S_.rows.map(x => `<tr data-rk="${esc(x.court + '|' + x.no)}"><td class="dv-gc">${DV_GRIP}</td><td>${esc(x.debtor)}</td><td>${esc(x.court)}</td><td><b>${esc(x.no)}</b></td>
        <td>${x.state === 'wait' ? '<span class="faint">조회 전</span>' : x.ok ? (x.date ? `${fullDate(x.date)} ${dvDd(x.date)}` : dvTag('아직 안 잡힘', 'warn')) : dvTag(x.state === 'notfound' ? '찾을 수 없음' : '조회 못 함', 'bad') + (x.msg ? ` <span class="small faint">${esc(x.msg).slice(0, 40)}</span>` : '')}</td>
        <td>${esc(x.third) || '—'}</td><td class="dv-rel">${x.rel.map(r => `${r[0] === x.court ? '' : esc(r[0]) + ' '}${esc(r[1])} <span class="faint">${esc(r[2] || r[3] || '')}</span>`).join(' · ') || (x.ok ? '<span style="color:var(--warn)">못 찾음</span>' : '—')}</td>
        <td class="dv-dc"><button class="dv-del" data-del-s="${esc(x.court + '|' + x.no)}" title="이 줄 지우기">✕</button></td></tr>`).join('')}</tbody></table>`;
  } else {
    body = `<div class="dv-empty"><b>1 → 2 순서로 하면 결과가 여기 나와요</b><span>사건검색 결과와 매칭 결과를 탭으로 바꿔 봐요 · 저장하면 ② 현황과 ③ 대장에 바로 들어가요</span></div>`;
  }
  return `<div class="card dv-rcard"><div class="dv-rtabs">${tabs}<div class="sp"></div><div class="dv-rr">${right}</div></div><div class="dv-rscroll">${body}</div></div>`;
}
// 매칭 결과 · 현황 표 (법조치키 하나당 한 줄)
function dvOutTable(rows, via, kind) {
  let last = '';
  return `<table class="dv-t" id="${kind === 'm' ? 'dvTM' : 'dvTB'}"><thead><tr><th class="dv-gc"></th><th>채무자키</th><th>법조치키</th><th>채무자명</th><th>담당자명</th><th>법원</th><th>사건번호</th><th>제3채무자</th><th>배당기일</th><th>배당관련사건</th><th class="dv-dc"></th></tr></thead><tbody>
  ${rows.map(r => { const first = r.court + r.no !== last; last = r.court + r.no;
    return `<tr data-rk="${esc(r.rk)}" class="${first ? '' : 'dv-cont'}"><td class="dv-gc">${DV_GRIP}</td>
    <td>${r.dkey ? `<b>${esc(r.dkey)}</b>` : dvTag('못 찾음', 'warn')}${first && r.multi ? `<div>${dvTag('한 사람 · 키 여러 개', 'now')}</div>` : ''}</td>
    <td>${esc(r.lkey) || '—'}${via && r.via ? `<div class="small faint">↳ ${esc(r.via.replace(' · 법원 확인', ''))}${r.court_check ? ' ' + dvTag('법원 확인', 'warn') : ''}</div>` : ''}</td>
    <td>${esc(r.debtor)}</td><td>${esc(r.mgr) || '—'}</td>
    <td>${first ? esc(r.court) : '<span class="faint">〃</span>'}</td><td>${first ? `<b>${esc(r.no)}</b>` : '<span class="faint">〃</span>'}</td>
    <td class="dv-w">${esc(r.third) || '—'}${r.third_diff ? `<div>${dvTag('공탁자 ' + r.third_diff + '와 다름', 'warn')}</div>` : ''}</td>
    <td>${first ? `${fullDate(r.date) || '—'} ${dvDd(r.date)}` : ''}</td>
    <td class="dv-rel dv-w">${first ? r.rel_out.map(x => `<span class="${x.hit ? 'hit' : 'faint'}">${x.hit ? '✓ ' : ''}${esc(x.no)}</span>`).join(', ') : ''}
      ${first && r.name_note.length ? `<div>${dvTag('같은 이름 다른 키 ' + r.name_note.join(', ') + ' · 사건번호 안 맞아 뺌', 'warn')}</div>` : ''}
      ${first && !r.dkey && r.case_status === 'none' ? `<div class="small" style="color:var(--warn);margin-top:3px">${r.rel_out.length ? `뽑은 관련사건 ${r.rel_out.length}개(${r.rel_out.map(x => esc(x.no)).join(', ')})가 법조치 자료 사건번호에 없어요` : '사건검색 결과에서 관련사건 번호를 못 찾았어요 — 「진단 저장」 파일을 보내 주세요'}</div>` : ''}</td>
    <td class="dv-dc"><button class="dv-del" data-del-${kind}="${esc(r.rk)}" title="이 줄 지우기">✕</button></td></tr>`; }).join('')}</tbody></table>`;
}
function dvRunBind(v) {
  const S_ = DVS.search;
  let tm;
  $('#dv1', v).oninput = () => { clearTimeout(tm); tm = setTimeout(async () => {
    const t = $('#dv1', v).value; if (!t.trim()) { $('#dvSum1', v).innerHTML = ''; return; }
    try { const c = await api('dv_check', {text: t}); $('#dvSum1', v).innerHTML = `<span class="small faint"><b style="color:var(--text)">${c.n}줄</b> 읽음</span>` +
      (c.missing.length ? c.missing.map(m => `<span class="dv-ck no">✕ ${esc(m)} 칸 없음</span>`).join('') : `<span class="dv-ck">✓ 조회 가능 ${c.good}건</span>`) + (c.bad.length ? `<span class="dv-ck no" title="${esc(c.bad.map(b => b.line + '줄: ' + b.problem).join('\n'))}">✕ 못 읽은 줄 ${c.bad.length}</span>` : ''); } catch (e) { /* 무시 */ }
  }, 350); };
  $('#dvGo1', v).onclick = () => safe(async () => {
    if (DVS.running) return go('run', {});
    const st = await api('dv_search', {text: $('#dv1', v).value});
    if (st.skipped && st.skipped.length) toast(`못 읽은 줄 ${st.skipped.length}개는 빼고 조회해요`);
    go('run', {state: st});
  });
  $('#dvGo2', v).onclick = () => safe(async () => {
    const t = $('#dv2', v).value;
    if (!t.trim() && DVS.law.hidden) return toast('2번 칸에 법조치 자료를 넣거나 「지난번 자료」를 눌러 주세요', true);
    if (t.trim() && t !== DVS.law.text) {
      const info = await api('dv_law_text', {text: t});
      if (info.missing.length || info.guessed) { const ok = await dvLawMap(info, true); if (!ok) return; }
    }
    try { DVS = await api('dv_match'); } catch (e) {
      if (/^칸 맞추기/.test(e.message)) { const ok = await dvLawMap(await api('dv_law_info'), true); if (!ok) return; DVS = await api('dv_match'); } else throw e;
    }
    DVTAB = 'match'; dvRunDraw(v);
  });
  $('#dvF1', v).onclick = () => safe(async () => { const p = await chooseExcel(); if (!p) return; $('#dv1', v).value = await api('dv_case_file', {path: p}); $('#dv1', v).oninput(); });
  $('#dvF2', v).onclick = () => safe(async () => { const p = await chooseExcel(); if (!p) return; const r = await api('dv_law_file', {path: p}); toast(`${r.n}줄 읽었어요`); if (r.missing.length || r.guessed) await dvLawMap(r); DVS = await api('dv_state'); dvRunDraw(v); });
  $('#dvLast', v).onclick = () => safe(async () => { const t = await api('dv_law_last'); $('#dv2', v).value = t; DVS.law.text = t; DVS.law.hidden = false; $('#dvSum2', v).innerHTML = dvSum(DVS.law.n, DVS.law.missing, DVS.law.guessed); dvLawMapBind(v); toast(`지난번 자료 ${DVS.law.n}줄을 넣었어요 · 「자동 매칭」을 누르세요`); });
  $('#dvPick', v).onclick = () => dvPick();
  dvLawMapBind(v);
  $('#dvReset', v).onclick = () => safe(async () => {
    if (DVS.running) return toast('조회 중에는 초기화할 수 없어요. 조회를 멈춘 뒤 해 주세요', true);
    if (!await confirmBox('조회·매칭 초기화', '1번 · 2번 붙여넣기 칸과 아래 <b>사건검색 결과 · 매칭 결과</b>를 비워요.<br><b>배당 관리 대장 · 배당기일 현황은 그대로</b> 남아요.<br>법조치 자료는 「지난번 자료」로 다시 불러올 수 있어요.', '초기화')) return;
    DVS = await api('dv_reset'); DVTAB = 'search'; dvRunDraw(v); toast('초기화했어요 · 대장은 그대로예요');
  });
  $('#dvData', v).onclick = () => safe(async () => { if (!DVS.xlsm.ok) return dvXlsm(); const x = await api('dv_xlsm_open'); toast(`엑셀에서 「${x.path.split(/[\\/]/).pop()}」을 열었어요 · 작업 후 저장한 파일은 「엑셀 파일로」로 넣으세요`); });
  $('#dvDataSet', v).onclick = () => dvXlsm();
  $$('[data-dvt]', v).forEach(b => b.onclick = () => { DVTAB = b.dataset.dvt; dvRunDraw(v); });
  $$('[data-del-s]', v).forEach(b => b.onclick = () => safe(async () => { const k = b.dataset.delS; DVS = await api('dv_search_del', {key: k}); dvRunDraw(v);
    dvUndo(`${k.split('|')[1]} 조회 결과에서 지웠어요`, async () => { DVS = await api('dv_search_del', {key: k, undo: true}); dvRunDraw(v); }); }));
  $$('[data-del-m]', v).forEach(b => b.onclick = () => safe(async () => { const k = b.dataset.delM; DVS = await api('dv_match_del', {rk: k}); dvRunDraw(v);
    dvUndo(`${k.split('|').slice(1).join(' · ')} 매칭 결과에서 지웠어요 (저장·엑셀에서 빠짐)`, async () => { DVS = await api('dv_match_del', {rk: k, undo: true}); dvRunDraw(v); }); }));
  dvDrag($('#dvTS tbody', v), (f, t, a) => safe(async () => { DVS = await api('dv_search_order', {keys: dvMove(S_.rows.map(x => x.court + '|' + x.no), f, t, a)}); dvRunDraw(v); }));
  dvDrag($('#dvTM tbody', v), (f, t, a) => safe(async () => { DVS = await api('dv_match_order', {keys: dvMove(DVS.matched.rows.map(r => r.rk), f, t, a)}); dvRunDraw(v); }));
  if ($('#dvDiag', v)) $('#dvDiag', v).onclick = () => safe(async () => { const r = await api('dv_diag'); dvSaved(r.path); });
  if ($('#dvXl1', v)) $('#dvXl1', v).onclick = () => safe(async () => { const r = await api('dv_export', {what: 'match', rks: DVS.matched.rows.map(x => x.rk)}); dvSaved(r.path); });
  if ($('#dvSave', v)) $('#dvSave', v).onclick = () => safe(async () => {
    const r = await api('dv_save'); toast(`현황 ${r.board}건 · 대장 새로 ${r.add}줄 · 기일 바뀐 것 ${r.upd}줄${r.diffs ? ` · 법조치 자료와 다른 값 ${r.diffs}건` : ''}`); go('dv_ledger');
  });
}
function dvSaved(p) { toast('엑셀로 저장했어요'); modal('엑셀로 저장했어요', `<div class="small" style="word-break:break-all">${esc(p)}</div>`, [{text: '폴더 열기', value: () => api('reveal', {path: p})}, {text: '파일 열기', cls: 'primary', value: () => api('open_path', {path: p})}]); }

// 칸 맞추기: 법조치 자료의 칸마다 채무자키 · 법조치키 · 사건번호 … 를 고른다 (같은 머리글이면 다음에도 기억)
function dvLawMapBind(v) { $$('[data-lawmap]', v).forEach(a => a.onclick = () => safe(async () => { await dvLawMap(await api('dv_law_info')); DVS = await api('dv_state'); dvRunDraw($('#view')); })); }
async function dvLawMap(info, forMatch) {
  if (!info || !info.head || !info.head.length) { toast('법조치 자료를 먼저 넣어 주세요', true); return false; }
  const opts = [['', '안 씀']].concat(info.fields);
  const body = `<div class="small" style="line-height:1.7;margin-bottom:8px">${info.missing.length ? `<b style="color:var(--bad)">${info.missing.map(esc).join(' · ')}</b> 칸을 못 찾았어요. ` : info.guessed ? '<b style="color:var(--warn)">머리글이 없어 값 모양으로 짐작했어요.</b> ' : ''}칸마다 무엇인지 골라 주세요.
      <b>채무자키 · 법조치키 · 사건번호(당사 사건번호)</b>는 꼭 있어야 하고, 법원 · 채무자명 · 담당자명 · 청구액은 있으면 같이 붙어요. 같은 머리글이면 다음부터 자동이에요.</div>
    <label class="small" style="display:flex;gap:6px;align-items:center;margin-bottom:8px"><input type="checkbox" id="lmHead" ${info.has_head ? 'checked' : ''}> 첫 줄은 머리글 (칸 이름)</label>
    <div style="overflow:auto;max-height:46vh"><table class="dv-t"><thead><tr>${info.head.map((h, i) => `<th style="min-width:110px"><div class="small faint" style="margin-bottom:4px">${esc(h)}</div>
      <select class="field dv-sel" data-lm="${i}" style="width:100%">${opts.map(([k, t]) => `<option value="${k}" ${(info.map[i] || '') === k ? 'selected' : ''}>${t}</option>`).join('')}</select></th>`).join('')}</tr></thead>
      <tbody>${info.sample.map(r => `<tr>${info.head.map((_, i) => `<td>${esc(r[i] || '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  const r = await modal('칸 맞추기 · 당사 법조치 자료', body, [{text: '취소'}, {text: forMatch ? '이대로 읽고 매칭' : '이대로 읽기', cls: 'primary', value: async bg => {
    const m = $$('[data-lm]', bg).map(s => s.value);
    const need = {dkey: '채무자키', lkey: '법조치키'};
    const lack = Object.keys(need).filter(k => !m.includes(k)).map(k => need[k]);
    if (!m.includes('no') && !m.includes('dno')) lack.push('사건번호');
    if (lack.length) { toast(lack.join(' · ') + ' 칸을 골라 주세요', true); return false; }
    const dup = m.filter(k => k).find((k, i, a) => a.indexOf(k) !== i);
    if (dup) { toast('같은 항목을 두 칸에 고를 수 없어요', true); return false; }
    return api('dv_law_map', {mapping: m, has_head: $('#lmHead', bg).checked});
  }}], true);
  if (r) toast(`${r.n}줄을 고른 칸대로 읽었어요 · 다음에도 이 칸 짝을 써요`);
  return !!r;
}

// 다시 조회할 건 고르기
async function dvPick() {
  const P = await api('dv_pick');
  const groups = ['기일 미정', '30일 안 기일', '지난 조회 실패', '새로 들어옴'];
  const outG = {}; P.out.forEach(x => { outG[x.why] = (outG[x.why] || 0) + 1; });
  const on = new Set(P.in.map(x => x.k));
  const body = () => `<div class="small faint" style="margin-bottom:8px">${P.last ? `마지막 조회 ${fullDate(P.last)} · ` : ''}대장 ${P.in.length + P.out.length}건 중 필요한 것만 · 숫자 입력이 ${P.in.length + P.out.length}번 → <b id="pkN">${on.size}</b>번</div>
    <div class="dv-pk">${groups.map(g => { const L = P.in.filter(x => x.why === g); if (!L.length) return ''; return `<div class="dv-pkg"><div class="dv-pkh"><b>${g}</b><span class="small faint">${L.length}건</span></div>${L.map(x => `<label class="dv-pki"><input type="checkbox" data-pk="${esc(x.k)}" checked><span>${esc(x.debtor)}</span><span>${esc(x.court)}</span><b>${esc(x.no)}</b><span class="small faint">${x.date ? fullDate(x.date) : ''}</span></label>`).join('')}</div>`; }).join('') || '<div class="small faint">다시 조회할 건이 없어요</div>'}</div>
    <div class="dv-pkout"><b>뺀 것 ${P.out.length}건</b> ${Object.entries(outG).map(([k, n]) => dvTag(k + ' ' + n)).join(' ')}</div>`;
  const r = await modal('다시 조회할 건 고르기', body(), [{text: '취소'}, {text: '고른 건 1번 칸에 넣기', cls: 'primary', value: bg => {
    const L = P.in.filter(x => $(`[data-pk="${CSS.escape(x.k)}"]`, bg).checked);
    return '채무자\t법원\t사건번호\n' + L.map(x => `${x.debtor}\t${x.court}\t${x.no}`).join('\n');
  }}], true);
  if (r) { if (CUR !== 'dv_run') await go('dv_run'); $('#dv1').value = r; $('#dv1').oninput(); toast('1번 칸에 넣었어요 · 「사건검색 시작」을 누르세요'); }
}

// DATA 가공 경로
async function dvXlsm() {
  let X = DVS ? DVS.xlsm : (await api('dv_state')).xlsm;
  const draw = () => `<div class="dv-xh"><b>연결할 파일</b><span class="dv-xst ${X.ok ? 'ok' : 'no'}"><i class="dv-dot ${X.ok ? 'ok' : 'no'}"></i>${X.ok ? '연결됨' : '연결 안 됨'}</span></div>
    <div class="dv-xpath"><input class="field" id="xPath" value="${esc(X.path)}" spellcheck="false" placeholder="C:\\...\\배당_데이터가공.xlsm"><button class="btn sm" id="xPick">파일 고르기</button><button class="btn sm" id="xChk">연결 확인</button></div>
    <div class="small faint" style="margin-top:6px;word-break:break-all">${X.ok ? `마지막 수정 ${X.info.mod} · ${X.info.size}` : X.path ? '<span style="color:var(--bad)">이 경로에 파일이 없어요. 매크로를 고쳐 다른 곳에 저장했다면 「파일 고르기」로 새 파일을 연결하세요.</span>' : '조회 전에 쓰는 매크로 엑셀을 정해 두면 「DATA 가공」 한 번에 엑셀로 열려요'}</div>
    ${X.recent.length ? `<div class="dv-xrec"><span class="small faint">최근 연결한 파일 · 눌러서 바꾸기</span>${X.recent.map(r => `<button class="dv-xr ${r.path === X.path ? 'on' : ''}" data-xr="${esc(r.path)}"><i class="dv-dot ${r.ok ? 'ok' : 'no'}"></i><span>${esc(r.path)}</span><span class="small faint">${esc(r.when)}${r.ok ? '' : ' · 파일 없음'}</span></button>`).join('')}</div>` : ''}
    <div class="dv-xflow"><div><b>1</b>「DATA 가공」 → 매크로 엑셀이 열려요</div><div><b>2</b>엑셀에서 매크로 작업 · 복호화 후 저장</div><div><b>3</b>1·2번 칸 「엑셀 파일로」로 넣기</div></div>`;
  const bg = document.createElement('div');
  const p = modal('DATA 가공 · 매크로 엑셀 경로', `<div id="xBody">${draw()}</div>`, [{text: '닫기'}, {text: '엑셀로 열기', cls: 'primary', value: async () => { const x = await api('dv_xlsm_open'); toast(`「${x.path.split(/[\\/]/).pop()}」을 열었어요`); return true; }}], true);
  const bind = () => {
    const b = $('#xBody'); if (!b) return;
    $('#xPick', b).onclick = () => safe(async () => { X = await api('dv_xlsm_pick'); b.innerHTML = draw(); bind(); });
    $('#xChk', b).onclick = () => safe(async () => { X = await api('dv_xlsm_set', {path: $('#xPath', b).value}); b.innerHTML = draw(); bind(); toast(X.ok ? '연결됐어요' : '이 경로에서 파일을 못 찾았어요'); });
    $$('[data-xr]', b).forEach(x => x.onclick = () => safe(async () => { X = await api('dv_xlsm_set', {path: x.dataset.xr}); b.innerHTML = draw(); bind(); }));
  };
  setTimeout(bind, 30);
  await p;
  if (CUR === 'dv_run') { DVS = await api('dv_state'); dvRunDraw($('#view')); }
}

// 사건 조회(숫자 입력) 화면 위에 「배당 조회」 안내
const _dvRun = SCREENS.run;
SCREENS.run = async (v, a) => {
  await _dvRun(v, a);
  if (INFO && INFO.running && INFO.running.name === '배당 조회' || (a && a.state && a.state.name === '배당 조회')) {
    v.insertAdjacentHTML('afterbegin', `<div class="notice info" style="display:flex;align-items:center;gap:10px">배당 조회예요 — 다 끝나면 <b>배당기일 · 조회·매칭</b>에서 이어서 매칭해요.<button class="btn sm primary" style="margin-left:auto" data-go="dv_run">조회·매칭으로 →</button></div>`);
  }
};

// ================================================================== ② 배당기일 현황
let DVB = {view: 'table', filt: 'all', q: '', mgr: '', mon: null};
SCREENS.dv_board = async v => {
  document.body.classList.remove('dv-fit');
  const d = await api('dv_board');
  const C = d.cases;
  const F = {all: c => true, week: c => c.date && dvLeft(c.date) >= 0 && dvLeft(c.date) <= 7, soon: c => c.date && dvLeft(c.date) >= 0 && dvLeft(c.date) <= 30,
    none: c => !c.hits, nodate: c => !c.date};
  const keep = new Set(C.filter(F[DVB.filt]).map(c => c.court + '|' + c.no));
  let rows = d.rows.filter(r => keep.has(r.court + '|' + r.no)).filter(r => !DVB.q || [r.no, r.debtor, r.court, r.dkey, r.lkey, r.third].join(' ').includes(DVB.q)).filter(r => !DVB.mgr || r.mgr === DVB.mgr);
  const mgrs = [...new Set(d.rows.map(r => r.mgr).filter(Boolean))];
  v.innerHTML = head(`${esc(INFO.book)} · 배당기일 · ②`, `배당기일 현황<span class="dv-h1d">다가오는 배당기일 · 표/달력 · 다시 조회로 바뀐 기일 찾기</span>`,
    `<span class="small faint">${d.last ? '마지막 조회 ' + fullDate(d.last) + ' · ' : ''}${C.length}건</span><button class="btn" id="dbPick">다시 조회할 건 고르기</button><button class="btn primary" id="dbXl">엑셀로 내보내기</button>`) +
    (C.length ? `<div class="dv-stats">${[['all', '전체'], ['week', '7일 안'], ['soon', '30일 안'], ['none', '우리 사건 못 찾음'], ['nodate', '기일 안 잡힘']].map(([k, t]) => `<button data-bf="${k}" class="${DVB.filt === k ? 'on' : ''} ${k === 'week' || k === 'none' ? 'red' : ''}"><span>${t}</span><b>${C.filter(F[k]).length}</b></button>`).join('')}</div>
    <div class="dv-tb"><div class="seg">${[['table', '표'], ['cal', '달력']].map(([k, t]) => `<button data-bv="${k}" class="${DVB.view === k ? 'on' : ''}">${t}</button>`).join('')}</div>
      <input class="field dv-search" id="dbQ" placeholder="사건번호 · 채무자 · 채무자키 · 제3채무자" value="${esc(DVB.q)}">
      <select class="field dv-sel" id="dbM"><option value="">담당자 전체</option>${mgrs.map(m => `<option ${DVB.mgr === m ? 'selected' : ''}>${esc(m)}</option>`).join('')}</select>
      ${DVB.view === 'table' ? `<div class="seg">${[['date', '배당기일순'], ['manual', '직접 정한 순']].map(([k, t]) => `<button data-bs="${k}" class="${d.sort === k ? 'on' : ''}">${t}</button>`).join('')}</div>` : ''}
      <span class="small faint">${rows.length}줄 · ⋮⋮ 끌어서 순서 · 엑셀도 이 순서</span></div>
    ${DVB.view === 'table' ? `<div class="card dv-sticky">${dvOutTable(rows, false, 'b')}</div>` : dvCal(C.filter(F[DVB.filt]))}`
    : empty('아직 저장된 배당기일이 없어요', '① 조회·매칭에서 「②·③에 저장」을 누르면 여기에 나와요.', '<button class="btn primary" data-go="dv_run">① 조회·매칭으로</button>'));
  $$('[data-bf]', v).forEach(b => b.onclick = () => { DVB.filt = b.dataset.bf; go('dv_board', {}, {back: true}); });
  $$('[data-bv]', v).forEach(b => b.onclick = () => { DVB.view = b.dataset.bv; go('dv_board', {}, {back: true}); });
  $$('[data-bs]', v).forEach(b => b.onclick = () => safe(async () => { await api('dv_board_order', {sort: b.dataset.bs}); go('dv_board', {}, {back: true}); }));
  if ($('#dbQ', v)) { $('#dbQ', v).onchange = e => { DVB.q = e.target.value.trim(); go('dv_board', {}, {back: true}); }; $('#dbM', v).onchange = e => { DVB.mgr = e.target.value; go('dv_board', {}, {back: true}); }; }
  $('#dbPick', v).onclick = () => dvPick();
  $('#dbXl', v).onclick = () => safe(async () => { const r = await api('dv_export', {what: 'board', rks: rows.map(x => x.rk)}); dvSaved(r.path); });
  $$('[data-del-b]', v).forEach(b => b.onclick = () => safe(async () => { const r = await api('dv_board_del', {rk: b.dataset.delB}); go('dv_board', {}, {back: true});
    dvUndo('현황에서 지웠어요 (대장은 그대로)', async () => { await api('dv_board_del', {rk: '', undo_snapshot: r.undo}); go('dv_board', {}, {back: true}); }); }));
  dvDrag($('#dvTB tbody', v), (f, t, a) => safe(async () => { await api('dv_board_order', {keys: dvMove(rows.map(r => r.rk), f, t, a)}); go('dv_board', {}, {back: true}); }));
  $$('[data-calm]', v).forEach(b => b.onclick = () => { DVB.mon = b.dataset.calm; go('dv_board', {}, {back: true}); });
  $$('[data-calq]', v).forEach(b => b.onclick = () => { DVB.q = b.dataset.calq; DVB.view = 'table'; go('dv_board', {}, {back: true}); });
};
function dvCal(C) {
  const m = DVB.mon || INFO.today.slice(0, 7);
  const [y, mo] = m.split('-').map(Number);
  const first = new Date(y, mo - 1, 1), days = new Date(y, mo, 0).getDate();
  let cells = WEEK.map(w => `<div class="h">${w}</div>`).join('');
  for (let i = 0; i < first.getDay(); i++) cells += '<div class="x"></div>';
  for (let dd = 1; dd <= days; dd++) {
    const ds = `${y}-${String(mo).padStart(2, '0')}-${String(dd).padStart(2, '0')}`;
    const ev = C.filter(c => c.date === ds && (!DVB.mgr || c.mgrs.includes(DVB.mgr)));
    cells += `<div class="${ds === INFO.today ? 'today' : ''}"><b>${dd}</b>${ev.map(c => `<em class="${dvLeft(c.date) >= 0 && dvLeft(c.date) <= 7 ? '' : 'g'}" data-calq="${esc(c.no)}" title="${esc(c.court)} ${esc(c.no)}">${esc(c.debtor)} ${esc(c.no.replace(/^\d{4}/, ''))}</em>`).join('')}</div>`;
  }
  const mv = k => { const d = new Date(y, mo - 1 + k, 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`; };
  const up = C.filter(c => c.date && dvLeft(c.date) >= 0).sort((a, b) => a.date < b.date ? -1 : 1).slice(0, 10);
  return `<div class="dv-calw"><div class="card"><div class="card-h"><h2>${y}년 ${mo}월</h2><div class="row-gap"><button class="btn sm" data-calm="${mv(-1)}">‹</button><button class="btn sm" data-calm="${mv(1)}">›</button></div></div><div class="card-b"><div class="dv-cal">${cells}</div></div></div>
    <div class="card"><div class="card-h"><h2>다가오는 배당기일</h2></div><div class="card-b">${up.map(c => `<div class="dv-up" data-calq="${esc(c.no)}"><div class="row-gap" style="justify-content:space-between"><b>${fullDate(c.date)}</b>${dvDd(c.date)}</div><div class="small faint">${esc(c.debtor)} · ${esc(c.court)} ${esc(c.no)}</div><div class="small faint">${esc(c.dkeys.join(', ')) || '우리 사건 못 찾음'}</div></div>`).join('') || '<div class="small faint">없어요</div>'}</div></div></div>`;
}

// ================================================================== ③ 배당 관리 대장
let DVL = {lf: 'doing', q: '', mgr: '', year: '', mon: '', sel: new Set(), data: null, rows: [], carry: new Set(), open: null};
const DV_COLS = [
  {k: 'date', t: '배당기일', v: r => r.date, h: r => `${DVL.carry.has(r.id) ? dvTag('이월', 'warn') + ' ' : ''}${dvD(r.date)}${r.done || !r.date ? '' : ' ' + dvDd(r.date)}`},
  {k: 'debtor', t: '채무자명', v: r => r.debtor, h: r => `<b>${esc(r.debtor)}</b>${r.fresh ? ' ' + dvTag('새로', 'now') : ''}${r.changed || r.dif ? ' ' + dvTag('바뀜', 'warn') : ''}${r.memo ? ` <span class="dv-memo" title="${esc(r.memo)}">메모</span>` : ''}`},
  {k: 'dkey', t: '채무자키', v: r => r.dkey, h: r => esc(r.dkey) || dvTag('없음', 'bad')},
  {k: 'lkey', t: '법조치키', v: r => r.lkey, h: r => esc(r.lkey) || '—'},
  {k: 'mgr', t: '담당', v: r => r.mgr, h: r => esc(r.mgr) || '—'},
  {k: 'court', t: '배당법원', v: r => r.court, h: r => esc(r.court)},
  {k: 'no', t: '배당사건번호', v: r => r.no, h: r => `<b>${esc(r.no)}</b>`},
  {k: 'oc', t: '당사 법원', v: r => r.ours_court, h: r => esc(r.ours_court) || '—'},
  {k: 'on', t: '당사 사건번호', v: r => r.ours_no, h: r => r.ours_no ? `<span class="dv-ours"><b>${esc(r.ours_no)}</b><button class="btn sm dv-ic" data-dec="${esc(r.ours)}" title="결정문 열기 (결정문 폴더에서 사건번호로 찾기)">결정문</button></span>` : dvTag('없음', 'warn')},
  {k: 'third', t: '제3채무자', v: r => r.third, h: r => `<span title="두 번 누르면 바로 고쳐요">${r.third ? esc(r.third) : dvTag('없음', 'warn')}</span>`, w: 1},
  {k: 'stage', t: '단계', v: r => r.stage, w: 1, h: r => `${dvTag(r.stage, r.stage_c)}<div class="small faint" style="margin-top:2px">${r.check === '완료' ? '검수 ✓' : r.check === '보류' ? '<span style="color:var(--bad)">검수 보류</span>' : '검수 전'}${r.recv === '발송' && r.send_at ? ' · 발송 ' + r.send_at.slice(5).replace('-', '.') : ''}${r.recv === '수령' && r.recv_at ? ' · 수령 ' + r.recv_at.slice(5).replace('-', '.') : ''}</div>`},
  {k: 'amt', t: '배당액', num: 1, v: r => r.amt, h: r => r.amt !== '' && r.amt !== null && r.amt !== undefined ? DVW(r.amt) : '—'},
];
function dvScope(all) {
  const y = DVL.year || INFO.today.slice(0, 4);
  const a = DVL.mon ? `${y}-${DVL.mon}-01` : `${y}-01-01`;
  const b = DVL.mon ? `${y}-${DVL.mon}-${String(new Date(+y, +DVL.mon, 0).getDate()).padStart(2, '0')}` : `${y}-12-31`;
  DVL.carry = new Set();
  return all.filter(r => {
    if (r.deleted) return false;
    if (!r.date) return true;
    if (r.date >= a && r.date <= b) return true;
    if (r.date < a && r.recv !== '수령') { DVL.carry.add(r.id); return true; }
    return false;
  });
}
SCREENS.dv_ledger = async (v, a) => {
  document.body.classList.add('dv-fit');
  if (a && a.lf) DVL.lf = a.lf;
  if (a && a.mgr !== undefined) DVL.mgr = a.mgr;
  if (a && a.q !== undefined) DVL.q = a.q;
  DVL.data = await api('dv_ledger');
  dvLedDraw(v);
  if (a && a.open) dvRowOpen(a.open);
};
function dvLedDraw(v) {
  const D = DVL.data, all = D.rows;
  const yr = dvScope(all);
  const nopay = r => r.recv === '발송' && r.send_at && dvLeft(r.send_at) < -D.nopay_n;
  const F = {doing: r => !r.done, check: r => r.check === '대기' || r.check === '보류', send: r => r.need_send, fresh: r => r.fresh || r.changed || r.dif, done: r => r.done, all: () => true, trash: r => r.deleted};
  let rows = DVL.lf === 'trash' ? all.filter(r => r.deleted) : yr.filter(F[DVL.lf] || F.all);
  rows = rows.filter(r => !DVL.mgr || r.mgr === DVL.mgr).filter(r => !DVL.q || [r.no, r.debtor, r.dkey, r.lkey, r.court, r.third, r.ours].join(' ').includes(DVL.q));
  DVL.rows = rows;
  const y = DVL.year || INFO.today.slice(0, 4), monKey = `${y}-${DVL.mon || INFO.today.slice(5, 7)}`;
  const got = r => r.recv === '수령' ? (+r.amt || 0) : 0;
  const thisMon = all.filter(r => !r.deleted && (r.recv_at || '').startsWith(monKey)).reduce((s, r) => s + got(r), 0);
  const yearSum = all.filter(r => !r.deleted && (r.recv_at || '').startsWith(y)).reduce((s, r) => s + got(r), 0);
  const exp = yr.filter(r => !r.done).reduce((s, r) => s + (+r.amt || 0), 0);
  const mgrs = [...new Set(all.map(r => r.mgr).filter(Boolean))];
  const years = [...new Set(all.map(r => (r.date || '').slice(0, 4)).filter(Boolean).concat([INFO.today.slice(0, 4)]))].sort().reverse();
  const trashN = all.filter(r => r.deleted).length;
  v.innerHTML = head(`${esc(INFO.book)} · 배당기일 · ③`, `배당 관리 대장<span class="dv-h1d">검수 → 발송 → 수령완료 · 결정문 · 끝난 줄도 쌓임</span>`,
    `<button class="btn" id="lPaste">붙여넣어 고치기</button><button class="btn" id="lImp">기존 엑셀 대장 가져오기</button><button class="btn" id="lAdd">직접 한 줄 넣기</button><button class="btn primary" id="lXl">엑셀로 내보내기</button>`) +
    `<div class="dv-stats s6">${[['doing', '진행 중'], ['check', '검수 대기'], ['send', '기일 지남 · 발송 전'], ['fresh', '새로 · 바뀜'], ['done', '끝난 것']].map(([k, t]) => `<button data-lf="${k}" class="${DVL.lf === k ? 'on' : ''} ${k === 'check' || k === 'send' ? 'red' : ''}"><span>${t}</span><b>${yr.filter(F[k]).length}</b></button>`).join('')}
      <button data-lf="all" class="${DVL.lf === 'all' ? 'on' : ''}"><span>수령 · ${DVL.mon ? +DVL.mon + '월' : '이번 달'} / ${y}년</span><b>${DVM(thisMon)}<small>만</small> <small>/ ${DVM(yearSum)}만</small></b></button></div>
    ${DVL.sel.size ? `<div class="dv-bulk"><b>${DVL.sel.size}줄 고름</b><button class="btn sm" data-bulk="check">검수 완료</button><button class="btn sm" data-bulk="send">발송 처리</button><button class="btn sm" data-bulk="recv">수령완료 처리</button><button class="btn sm" data-bulk="none">배당 없음 (0원)</button><button class="btn sm" data-bulk="dec">결정문 모아 열기</button><button class="btn sm" data-bulk="copy">고른 줄 복사 (엑셀 칸)</button><button class="btn sm" data-bulk="xl">고른 줄 엑셀로</button><button class="btn sm" data-bulk="clear" style="margin-left:auto">고르기 풀기</button></div>` : ''}
    ${D.diffs ? `<div class="dv-dfbar">${dvTag('확인', 'warn')} 법조치 자료와 다른 값 <b>${D.diffs}건</b> (담당자·채무자키) — 대장에 반영할지 골라 주세요<button class="btn sm primary" id="lDiff">확인하고 반영</button></div>` : ''}
    <div class="dv-tb"><select class="field dv-sel" id="lY">${years.map(x => `<option value="${x}" ${y === x ? 'selected' : ''}>${x}년</option>`).join('')}</select>
      <select class="field dv-sel" id="lM"><option value="">전체 월</option>${Array.from({length: 12}, (_, i) => { const m = String(i + 1).padStart(2, '0'); const n = all.filter(r => !r.deleted && (r.date || '').startsWith(y + '-' + m)).length; return `<option value="${m}" ${DVL.mon === m ? 'selected' : ''}>${i + 1}월${n ? ` (${n})` : ''}</option>`; }).join('')}</select>
      ${DVL.mon && DVL.carry.size ? dvTag('이월 ' + DVL.carry.size + '줄 포함', 'warn') : ''}
      <input class="field dv-search" id="lQ" placeholder="사건번호 · 채무자 · 채무자키 · 제3채무자" value="${esc(DVL.q)}">
      <select class="field dv-sel" id="lMg"><option value="">담당자 전체</option>${mgrs.map(m => `<option ${DVL.mgr === m ? 'selected' : ''}>${esc(m)}</option>`).join('')}</select>
      <div class="seg">${[['date', '배당기일순'], ['manual', '직접 정한 순']].map(([k, t]) => `<button data-ls="${k}" class="${D.sort === k ? 'on' : ''}">${t}</button>`).join('')}</div>
      <button class="btn sm ${DVL.lf === 'trash' ? 'primary' : ''}" data-lf="${DVL.lf === 'trash' ? 'doing' : 'trash'}">${DVL.lf === 'trash' ? '지운 줄 닫기' : '지운 줄 ' + trashN}</button>
      <span class="small faint">${rows.length}줄 · 남은 배당액 ${DVW(exp)}원</span><span class="dv-hint">⋮⋮ 끌어서 순서 · 칸 끌어 고르고 ${dvMac()}+C 복사 · Delete 비우기 · ${dvMac()}+V 붙여넣어 고치기 · 제3채무자 두 번 = 바로 고치기 · 다른 칸 두 번 = 자세히</span></div>
    <div class="card dv-gridwrap"><table class="dv-t dv-grid"><thead><tr><th class="dv-ckc"><input type="checkbox" id="lAll"></th>${DV_COLS.map((c, i) => `<th class="dv-cph ${c.num ? 'num' : ''}" data-ci="${i}" title="눌러서 이 열 고르기 · Shift로 여러 열">${c.t}</th>`).join('')}</tr></thead><tbody>
      ${rows.map((r, ri) => `<tr data-lr="${r.id}" data-rk="${r.id}" data-ri="${ri}" class="${DVL.open === r.id ? 'sel' : ''}"><td class="dv-ckc">${DV_GRIP}<input type="checkbox" data-ck="${r.id}" ${DVL.sel.has(r.id) ? 'checked' : ''}></td>
        ${DV_COLS.map((c, ci) => `<td class="gc ${c.num ? 'num' : ''} ${c.w ? 'wr' : ''}" data-ci="${ci}">${c.h(r)}${ci === DV_COLS.length - 1 ? `<span class="dv-rowact">${r.deleted ? `<button class="dv-opn ok" data-restore="${r.id}" title="되살리기">↺</button>` : `<button class="dv-del" data-ldel="${r.id}" title="이 줄 지우기 (지운 줄로)">✕</button>`}<button class="dv-opn" data-open="${r.id}" title="자세히 · 고치기">›</button></span>` : ''}</td>`).join('')}</tr>`).join('') ||
        `<tr><td colspan="${DV_COLS.length + 1}" class="faint" style="text-align:center;padding:30px">해당하는 줄이 없어요</td></tr>`}</tbody></table></div>`;
  dvLedBind(v);
}
function dvLedBind(v) {
  const re = () => dvLedDraw(v);
  const reload = async () => { DVL.data = await api('dv_ledger'); re(); };
  $$('[data-lf]', v).forEach(b => b.onclick = () => { DVL.lf = b.dataset.lf; re(); });
  $('#lY', v).onchange = e => { DVL.year = e.target.value; re(); };
  $('#lM', v).onchange = e => { DVL.mon = e.target.value; re(); };
  $('#lMg', v).onchange = e => { DVL.mgr = e.target.value; re(); };
  $('#lQ', v).oninput = e => { DVL.q = e.target.value; const p = e.target.selectionStart; re(); const n = $('#lQ'); n.focus(); n.setSelectionRange(p, p); };
  $$('[data-ls]', v).forEach(b => b.onclick = () => safe(async () => { await api('dv_ledger_order', {sort: b.dataset.ls}); await reload(); }));
  $('#lAll', v).onchange = e => { DVL.rows.forEach(r => e.target.checked ? DVL.sel.add(r.id) : DVL.sel.delete(r.id)); re(); };
  $$('[data-ck]', v).forEach(c => c.onchange = () => { c.checked ? DVL.sel.add(c.dataset.ck) : DVL.sel.delete(c.dataset.ck); re(); });
  $$('[data-bulk]', v).forEach(b => b.onclick = () => safe(async () => {
    const k = b.dataset.bulk, ids = [...DVL.sel];
    if (k === 'clear') { DVL.sel.clear(); return re(); }
    if (k === 'copy') { const L = DVL.data.rows.filter(r => DVL.sel.has(r.id)); return dvCopy(dvTsv(L, true), `${L.length}줄 복사 — 엑셀에 붙이면 칸마다 들어가요`); }
    if (k === 'xl') { const r = await api('dv_export', {what: 'drill', ids: DVL.rows.filter(r => DVL.sel.has(r.id)).map(r => r.id)}); return dvSaved(r.path); }
    if (k === 'dec') { let n = 0; for (const r of DVL.data.rows.filter(r => DVL.sel.has(r.id) && r.ours)) { try { await api('dv_decision', {ours: r.ours}); n++; } catch (e) { /* 다음 */ } } return toast(`결정문 ${n}건을 열었어요`); }
    const r = await api('dv_bulk', {ids, action: k}); DVL.sel.clear(); toast(`${r.n}줄 바꿨어요 · 변경 기록에 남김`); await reload();
  }));
  $('#lPaste', v).onclick = () => dvPaste('');
  $('#lImp', v).onclick = () => dvImport();
  $('#lAdd', v).onclick = () => safe(async () => { const r = await api('dv_row_add'); await reload(); dvRowOpen(r.id); });
  $('#lXl', v).onclick = () => safe(async () => { const r = await api('dv_export', {what: 'ledger', ids: DVL.rows.map(x => x.id)}); dvSaved(r.path); });
  if ($('#lDiff', v)) $('#lDiff', v).onclick = () => dvDiffs();
  $$('[data-open]', v).forEach(b => b.onclick = e => { e.stopPropagation(); dvRowOpen(b.dataset.open); });
  $$('tr[data-lr]', v).forEach(t => t.ondblclick = e => {
    if (e.target.closest('button,input')) return;
    const td = e.target.closest('td.gc');
    if (td && DV_COLS[+td.dataset.ci].k === 'third' && !DVL.data.rows.find(r => r.id === t.dataset.lr).deleted) return dvEditThird(td, t.dataset.lr);
    dvRowOpen(t.dataset.lr);
  });
  $$('[data-ldel]', v).forEach(b => b.onclick = e => safe(async () => { e.stopPropagation(); const id = b.dataset.ldel; await api('dv_bulk', {ids: [id], action: 'delete'}); DVL.sel.delete(id); await reload();
    dvUndo('지웠어요 · 「지운 줄」에서 되살릴 수 있어요', async () => { await api('dv_bulk', {ids: [id], action: 'restore'}); await reload(); }); }));
  $$('[data-restore]', v).forEach(b => b.onclick = e => safe(async () => { e.stopPropagation(); await api('dv_bulk', {ids: [b.dataset.restore], action: 'restore'}); toast('되살렸어요'); await reload(); }));
  $$('[data-dec]', v).forEach(b => b.onclick = e => { e.stopPropagation(); dvDecision(b.dataset.dec); });
  dvDrag($('.dv-grid tbody', v), (f, t, a) => safe(async () => {
    const order = dvMove(DVL.data.rows.map(r => r.id), f, t, a);
    await api('dv_ledger_order', {ids: order}); await reload();
  }));
  dvGridBind(v);
}
// 제3채무자 칸 바로 고치기 (Enter 저장 · Esc 취소 · 밖을 누르면 저장)
function dvEditThird(td, id) {
  const r = DVL.data.rows.find(x => x.id === id);
  DVG.a = DVG.f = null; dvGPaint();
  td.classList.add('editing');
  td.innerHTML = `<input class="dv-cell-in" value="${esc(r.third || '')}" placeholder="제3채무자">`;
  const inp = $('input', td);
  inp.focus(); inp.select();
  let done = false;
  const finish = async save => {
    if (done) return; done = true;
    const val = inp.value.trim();
    if (save && val !== (r.third || '')) {
      try { await api('dv_row_save', {rid: id, fields: {third: val}}); toast('제3채무자를 고쳤어요 · 변경 기록에 남김'); } catch (e) { toast(e.message, true); }
    }
    DVL.data = await api('dv_ledger'); dvLedDraw($('#view'));
  };
  inp.onkeydown = e => { e.stopPropagation(); if (e.key === 'Enter') finish(true); if (e.key === 'Escape') finish(false); };
  inp.onblur = () => finish(true);
  inp.onmousedown = e => e.stopPropagation();
}
async function dvDecision(ours, print) {
  try { const r = await api('dv_decision', {ours, action: print ? 'print' : 'open'}); toast(`${print ? '인쇄기로 보냄' : '열었어요'} · ${r.path.split(/[\\/]/).pop()}`); }
  catch (e) {
    if (/폴더를 먼저/.test(e.message)) {
      const ok = await confirmBox('결정문 폴더', '결정문 PDF가 모여 있는 폴더를 정하면, 당사 사건번호가 이름에 들어간 PDF를 찾아 열어요.', '폴더 고르기');
      if (ok) { const d = await api('dv_decision_dir'); if (d) { toast('결정문 폴더를 정했어요'); dvDecision(ours, print); } }
    } else toast(e.message, true);
  }
}
function dvTsv(L, head) {
  const H = ['채무자키', '법조치키', '채무자명', '담당자명', '배당법원', '배당사건번호', '배당기일', '당사 법원', '당사 사건번호', '제3채무자', '청구액', '검수', '배당액', '수령 단계', '발송일', '수령일', '메모'];
  const V = r => [r.dkey, r.lkey, r.debtor, r.mgr, r.court, r.no, r.date, r.ours_court, r.ours_no, r.third, r.claim, r.check, r.amt, DVR[r.recv] || r.recv, r.send_at, r.recv_at, r.memo];
  return (head ? [H.join('\t')] : []).concat(L.map(r => V(r).map(x => String(x ?? '').replace(/[\t\n]/g, ' ')).join('\t'))).join('\n');
}

// 엑셀처럼 칸 고르기 · ⌘/Ctrl+C
const DVG = {a: null, f: null, drag: false};
const dvGRows = () => $$('.dv-grid tbody tr[data-lr]');
function dvGRect() { if (!DVG.a || !DVG.f) return null; return {r1: Math.min(DVG.a.r, DVG.f.r), r2: Math.max(DVG.a.r, DVG.f.r), c1: Math.min(DVG.a.c, DVG.f.c), c2: Math.max(DVG.a.c, DVG.f.c)}; }
function dvGVal(r, c) { const id = dvGRows()[r].dataset.lr; const row = DVL.rows.find(x => x.id === id); const v = DV_COLS[c].v(row); return v === null || v === undefined ? '' : v; }
function dvGPaint() {
  const R = dvGRect();
  $$('.dv-grid td.gc').forEach(td => { const r = +td.parentNode.dataset.ri, c = +td.dataset.ci; const on = R && r >= R.r1 && r <= R.r2 && c >= R.c1 && c <= R.c2;
    td.classList.toggle('gs', !!on); td.classList.toggle('gt', !!on && r === R.r1); td.classList.toggle('gb', !!on && r === R.r2); td.classList.toggle('gl', !!on && c === R.c1); td.classList.toggle('gr', !!on && c === R.c2); });
  $$('.dv-grid th.dv-cph').forEach(th => th.classList.toggle('gs', !!R && +th.dataset.ci >= R.c1 && +th.dataset.ci <= R.c2));
  let bar = $('#dvGBar');
  if (!bar) { bar = document.createElement('div'); bar.id = 'dvGBar'; bar.className = 'dv-gbar'; document.body.appendChild(bar); }
  if (!R || CUR !== 'dv_ledger') { bar.classList.remove('on'); return; }
  let sum = 0, cnt = 0;
  if (DV_COLS.slice(R.c1, R.c2 + 1).some(c => c.num)) for (let r = R.r1; r <= R.r2; r++) for (let c = R.c1; c <= R.c2; c++) if (DV_COLS[c].num) { const x = dvGVal(r, c); if (x !== '') { sum += +x; cnt++; } }
  const n = R.r2 - R.r1 + 1, m = R.c2 - R.c1 + 1;
  bar.innerHTML = `<b>${n}줄 × ${m}칸</b>${n * m === 1 ? ` <span class="gv">${esc(String(dvGVal(R.r1, R.c1)))}</span>` : ''}${cnt > 1 ? ` <span class="gv">합계 ${DVW(sum)}원</span>` : ''}<span class="gk">${dvMac()}+C 복사 · Delete 비우기</span><button class="btn sm" data-gc="0">복사</button><button class="btn sm" data-gc="del">칸 비우기</button><button class="btn sm" data-gc="1">머리글 포함 복사</button><button class="btn sm" data-gc="x">✕</button>`;
  bar.classList.add('on');
  $$('[data-gc]', bar).forEach(b => b.onmousedown = e => { e.preventDefault(); e.stopPropagation(); if (b.dataset.gc === 'x') { DVG.a = DVG.f = null; dvGPaint(); } else if (b.dataset.gc === 'del') safe(dvGClear); else dvGCopy(b.dataset.gc === '1'); });
}
function dvGCopy(head) {
  const R = dvGRect(); if (!R) return;
  const out = head ? [DV_COLS.slice(R.c1, R.c2 + 1).map(c => c.t).join('\t')] : [];
  for (let r = R.r1; r <= R.r2; r++) { const l = []; for (let c = R.c1; c <= R.c2; c++) l.push(String(dvGVal(r, c)).replace(/[\t\n]/g, ' ')); out.push(l.join('\t')); }
  dvCopy(out.join('\n'), `${R.r2 - R.r1 + 1}줄 × ${R.c2 - R.c1 + 1}칸 복사 — 엑셀에 그대로 붙여넣기`);
  $$('.dv-grid td.gs').forEach(td => { td.classList.add('flash'); setTimeout(() => td.classList.remove('flash'), 350); });
}
// 고른 칸 비우기 (배당법원 · 배당사건번호 · 단계는 지키고 나머지 값만)
async function dvGClear() {
  const R = dvGRect(); if (!R) return;
  const rows = dvGRows(), cells = [];
  for (let r = R.r1; r <= R.r2; r++) for (let c = R.c1; c <= R.c2; c++) cells.push({id: rows[r].dataset.lr, k: DV_COLS[c].k});
  const res = await api('dv_cells_clear', {cells});
  if (!res.n) return toast(res.skip ? '배당법원 · 배당사건번호 · 단계 칸은 비울 수 없어요 (줄째 지우려면 ✕)' : '비울 값이 없어요');
  DVL.data = await api('dv_ledger'); dvLedDraw($('#view'));
  dvUndo(`${res.n}칸 비웠어요${res.skip ? ` · 비울 수 없는 칸 ${res.skip}개는 그대로` : ''}`, async () => { await api('dv_cells_set', {cells: res.undo}); DVL.data = await api('dv_ledger'); dvLedDraw($('#view')); });
}
function dvGridBind(v) {
  const t = $('.dv-grid', v); if (!t) return;
  $$('td.gc', t).forEach(td => {
    td.onmousedown = e => { if (e.button !== 0 || e.target.closest('button,input,a')) return; e.preventDefault(); const p = {r: +td.parentNode.dataset.ri, c: +td.dataset.ci}; if (e.shiftKey && DVG.a) DVG.f = p; else { DVG.a = p; DVG.f = p; } DVG.drag = true; dvGPaint(); };
    td.onmouseenter = () => { if (!DVG.drag) return; DVG.f = {r: +td.parentNode.dataset.ri, c: +td.dataset.ci}; dvGPaint(); };
  });
  $$('th.dv-cph', t).forEach(th => {
    th.onmousedown = e => { e.preventDefault(); const c = +th.dataset.ci, last = dvGRows().length - 1; if (last < 0) return; if (e.shiftKey && DVG.a) { DVG.f = {r: last, c}; DVG.a = {r: 0, c: DVG.a.c}; } else { DVG.a = {r: 0, c}; DVG.f = {r: last, c}; } DVG.drag = 'col'; dvGPaint(); };
    th.onmouseenter = () => { if (DVG.drag !== 'col') return; DVG.f = {r: dvGRows().length - 1, c: +th.dataset.ci}; dvGPaint(); };
  });
  if (DVG.a && (DVG.a.r >= dvGRows().length || DVG.f.r >= dvGRows().length)) DVG.a = DVG.f = null;
  dvGPaint();
}
document.addEventListener('mouseup', () => { DVG.drag = false; });
document.addEventListener('keydown', e => {
  if (CUR !== 'dv_ledger' || $('.modal-bg') || !DVG.a) return;
  if (/INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || '')) return;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') { e.preventDefault(); dvGCopy(false); return; }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') { e.preventDefault(); DVG.a = {r: 0, c: 0}; DVG.f = {r: dvGRows().length - 1, c: DV_COLS.length - 1}; dvGPaint(); return; }
  if (e.key === 'Escape') { DVG.a = DVG.f = null; dvGPaint(); return; }
  if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); safe(dvGClear); return; }
  const mv = {ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1]}[e.key];
  if (mv) { e.preventDefault(); const n = dvGRows().length, m = DV_COLS.length; const b = e.shiftKey ? DVG.f : DVG.a; const p = {r: Math.max(0, Math.min(n - 1, b.r + mv[0])), c: Math.max(0, Math.min(m - 1, b.c + mv[1]))};
    if (e.shiftKey) DVG.f = p; else { DVG.a = p; DVG.f = p; } dvGPaint(); const td = $(`.dv-grid tr[data-ri="${p.r}"] td[data-ci="${p.c}"]`); if (td) td.scrollIntoView({block: 'nearest', inline: 'nearest'}); }
});
document.addEventListener('mousedown', e => { if (CUR === 'dv_ledger' && DVG.a && !e.target.closest('.dv-grid,#dvGBar,.dv-drawer')) { DVG.a = DVG.f = null; dvGPaint(); } });
document.addEventListener('paste', e => {
  if (CUR !== 'dv_ledger' || $('.modal-bg')) return;
  if (/INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || '')) return;
  const t = e.clipboardData && e.clipboardData.getData('text');
  if (!t || !t.includes('\t')) return;
  e.preventDefault(); dvPaste(t);
});

// 오른쪽 창: 한 줄 자세히 · 고치기
function dvDrawer() { let d = $('#dvDrawer'); if (!d) { d = document.createElement('div'); d.id = 'dvDrawer'; d.className = 'dv-drawer'; document.body.appendChild(d); } return d; }
async function dvRowOpen(id, lq) {
  const r = DVL.data.rows.find(x => x.id === id);
  if (!r) return;
  DVL.open = id;
  $$('.dv-grid tr[data-lr]').forEach(x => x.classList.toggle('sel', x.dataset.lr === id));
  const chip = (name, vals, cur, lab = x => x) => `<div class="dv-chips" data-chip="${name}">${vals.map(x => `<button class="${cur === x ? 'on' : ''}" data-v="${x}">${lab(x)}</button>`).join('')}</div>`;
  let link = '';
  if (!r.dkey) {
    const q = lq ?? r.debtor;
    const L = await api('dv_link_search', {q});
    link = `<div class="dv-lk"><div class="dv-sec" style="margin-top:0">우리 사건 못 찾음 — 법조치 자료에서 찾기</div><input class="field" id="lkQ" value="${esc(q)}" placeholder="채무자명 · 사건번호 · 키">
      <div class="dv-lkl">${L.map(x => `<div class="dv-lki"><div><b>${esc(x.debtor)}</b> ${esc(x.dkey)} · ${esc(x.lkey)}<div class="small faint">${esc(x.court)} ${esc(x.no)} · ${esc(x.mgr)} · ${esc(x.third || '')}</div></div><button class="btn sm" data-lk="${esc(x.lkey)}">연결</button></div>`).join('') || '<div class="small faint">찾는 값이 없어요 (법조치 자료는 ①에서 넣은 것을 써요)</div>'}</div>
      <div class="row-gap" style="margin-top:8px"><span class="small faint">연결하면 다음 매칭 때 자동으로 연결돼요</span><button class="btn sm" id="lkNot" style="margin-left:auto">우리 사건 아님</button></div></div>`;
  }
  const d = dvDrawer();
  d.innerHTML = `<div class="dv-dh"><div class="row-gap" style="justify-content:space-between"><span class="small faint">${esc(r.court)}</span><button class="btn sm" id="dvDc">닫기</button></div>
      <h2 style="font-size:18px;margin:4px 0 0">${esc(r.no) || '(새 줄)'} ${dvTag(r.stage, r.stage_c)}</h2>
      <div class="small faint" style="margin-top:4px">${esc(r.debtor)} · ${esc(r.dkey) || '채무자키 없음'} · ${esc(r.lkey) || '법조치키 없음'} · 담당 ${esc(r.mgr) || '—'}</div></div>
    <div class="dv-db">
      <div class="dv-kv"><span>배당기일</span><b>${fullDate(r.date) || '—'} ${r.done ? '' : dvDd(r.date)}</b><span>관련사건</span><span>${esc(r.rel) || '—'}</span><span>당사 관련사건</span><span>${r.ours ? `<b>${esc(r.ours)}</b><span class="row-gap" style="margin-top:6px"><button class="btn sm" id="dvDo">결정문 열기</button><button class="btn sm" id="dvDp">결정문 출력</button></span>` : '—'}</span><span>들어온 곳</span><span>${esc(r.src)}</span></div>
      ${link}
      <div class="dv-sec">키 · 사건</div>
      <div class="dv-fg"><label class="w">제3채무자 ${r.third_src ? `<span class="small faint">· ${esc(r.third_src)}</span>` : ''}<input class="field" data-f="third" value="${esc(r.third)}"></label>
        <label class="w">당사 관련사건 (법원 사건번호)<input class="field" data-f="ours" value="${esc(r.ours)}" placeholder="서울중앙지방법원 2025타채1234"></label>
        <label>채무자키<input class="field" data-f="dkey" value="${esc(r.dkey)}"></label><label>법조치키<input class="field" data-f="lkey" value="${esc(r.lkey)}"></label>
        <label>담당자명<input class="field" data-f="mgr" value="${esc(r.mgr)}"></label><label>채무자명<input class="field" data-f="debtor" value="${esc(r.debtor)}"></label>
        <label>배당법원<input class="field" data-f="court" value="${esc(r.court)}"></label><label>배당사건번호<input class="field" data-f="no" value="${esc(r.no)}"></label>
        <label>배당기일<input class="field" type="date" data-f="date" value="${esc(r.date)}"></label><label>청구액 (계산서)<input class="field" data-f="claim" value="${DVW(r.claim)}" placeholder="원"></label></div>
      <div class="dv-sec">검수</div>${chip('check', ['대기', '완료', '보류'], r.check)}
      <div class="small faint" style="margin-top:5px">${r.check === '완료' ? '검수 끝' : '키·사건번호·배당표 금액이 맞는지 보고 완료로'}</div>
      <div class="dv-fg"><label class="w">배당액 (배당표 금액 · 수령하면 이 금액을 받은 것으로)<input class="field" data-f="amt" value="${DVW(r.amt)}" placeholder="원"></label></div>
      <div class="dv-sec">수령 단계</div>${chip('recv', ['대기', '발송', '수령'], r.recv, x => DVR[x])}
      <div class="small faint" style="margin-top:5px">대기 → 발송(배당금교부신청서 보냄) → 수령완료 · 배당 없음은 배당액 0원으로 수령완료</div>
      <div class="dv-fg"><label>발송일<input class="field" type="date" data-f="send_at" value="${esc(r.send_at)}"></label><label>수령일<input class="field" type="date" data-f="recv_at" value="${esc(r.recv_at)}"></label>
        <label class="w">메모<input class="field" data-f="memo" value="${esc(r.memo)}"></label></div>
      <div class="dv-sec">변경 기록</div><div class="dv-log">${(r.log || []).map(l => `<div><span>${esc((l[0] || '').slice(2, 16))} · ${esc(l[1])}</span>${esc(l[2])}</div>`).join('') || '<div class="faint">없어요</div>'}</div>
    </div>
    <div class="dv-df"><button class="btn" id="dvForm" style="margin-right:auto">배당금교부신청서</button><button class="btn" id="dvDc2">닫기</button><button class="btn primary" id="dvDs">저장</button></div>`;
  d.classList.add('on');
  const close = () => { d.classList.remove('on'); DVL.open = null; $$('.dv-grid tr.sel').forEach(x => x.classList.remove('sel')); };
  $('#dvDc', d).onclick = $('#dvDc2', d).onclick = close;
  $$('[data-chip] button', d).forEach(b => b.onclick = () => { $$('button', b.parentNode).forEach(x => x.classList.remove('on')); b.classList.add('on');
    if (b.parentNode.dataset.chip === 'recv') { const f = b.dataset.v === '수령' ? 'recv_at' : b.dataset.v === '발송' ? 'send_at' : ''; const t = f && $(`[data-f=${f}]`, d); if (t && !t.value) t.value = INFO.today; } });
  if ($('#dvDo', d)) { $('#dvDo', d).onclick = () => dvDecision(r.ours); $('#dvDp', d).onclick = () => dvDecision(r.ours, true); }
  $('#dvForm', d).onclick = () => toast(r.third ? '배당금교부신청서 회사 양식을 「서류 작성 → 양식함」에 넣으면 이 줄 값(법원·사건번호·제3채무자·채무자·배당액)으로 채워 드려요' : '제3채무자를 먼저 넣어 주세요');
  if ($('#lkQ', d)) {
    $('#lkQ', d).onchange = e => dvRowOpen(id, e.target.value);
    $$('[data-lk]', d).forEach(b => b.onclick = () => safe(async () => { await api('dv_link', {rid: id, lkey: b.dataset.lk}); toast('연결했어요 · 다음 매칭 때 자동으로 연결돼요'); DVL.data = await api('dv_ledger'); dvLedDraw($('#view')); dvRowOpen(id); }));
    $('#lkNot', d).onclick = () => safe(async () => { await api('dv_notours', {rid: id}); close(); toast(`${r.no} — 우리 사건 아님으로 기억 · 다음 조회·매칭에서 빼요`); DVL.data = await api('dv_ledger'); dvLedDraw($('#view')); });
  }
  $('#dvDs', d).onclick = () => safe(async () => {
    const f = {};
    $$('[data-f]', d).forEach(i => { f[i.dataset.f] = i.value; });
    $$('[data-chip]', d).forEach(c => { const o = $('.on', c); if (o) f[c.dataset.chip] = o.dataset.v; });
    const res = await api('dv_row_save', {rid: id, fields: f});
    toast(res.changed ? `저장 · ${res.changed}가지 바뀜 (변경 기록에 남김)` : '바뀐 것 없음');
    close(); DVL.data = await api('dv_ledger'); dvLedDraw($('#view'));
  });
}

// 붙여넣어 고치기
async function dvPaste(text) {
  let R = text ? await api('dv_paste_preview', {text}) : null;
  const fv = (f, x) => f === 'amt' || f === 'claim' ? (x === '' || x === null ? '—' : DVW(x)) : f === 'recv' ? (DVR[x] || x || '—') : (x || '—');
  const body = () => `<div class="small faint" style="margin-bottom:8px">엑셀에서 머리글째 복사해 붙여넣으세요 · 법조치키(또는 배당사건번호·채무자키)로 줄을 찾고, 나머지 칸 값으로 바꿔요<br>바꿀 수 있는 칸: 배당액 · 청구액 · 제3채무자 · 담당자 · 수령 단계 · 발송일 · 수령일 · 배당기일 · 메모 · 검수</div>
    <textarea class="field dv-ta" id="psT" style="height:110px" spellcheck="false">${esc(text || '')}</textarea>
    <div class="row-gap" style="margin-top:8px"><button class="btn sm" id="psGo">미리 보기</button></div>
    <div id="psR">${dvPasteRes(R, fv)}</div>`;
  const p = modal('붙여넣어 고치기', body(), [{text: '닫기'}, {text: '고른 칸 반영', cls: 'primary', value: async bg => {
    if (!R || !R.ch) { toast('먼저 「미리 보기」를 눌러 주세요', true); return false; }
    const ch = R.ch.filter((c, i) => $(`[data-ps="${i}"]`, bg).checked);
    if (!ch.length) { toast('바꿀 칸이 없어요', true); return false; }
    const r = await api('dv_paste_apply', {changes: ch}); toast(`${r.n}칸 바꿨어요 · 변경 기록에 남김`); return true;
  }}], true);
  setTimeout(() => { const b = $('#psGo'); if (b) b.onclick = () => safe(async () => { text = $('#psT').value; R = await api('dv_paste_preview', {text}); $('#psR').innerHTML = dvPasteRes(R, fv); }); }, 30);
  if (await p) { DVL.data = await api('dv_ledger'); dvLedDraw($('#view')); }
}
function dvPasteRes(R, fv) {
  if (!R) return '';
  if (R.err) return `<div class="notice bad" style="margin-top:10px">${esc(R.err)}</div>`;
  return `<div class="row-gap" style="margin:12px 0 6px;flex-wrap:wrap">${dvTag('줄 찾기: ' + R.keys.join(' + '))}${dvTag('바꿀 칸: ' + R.fields.join(' · '), 'now')}${dvTag('바뀜 ' + R.ch.length + '칸', 'ok')}${R.same ? dvTag('같은 값 ' + R.same + '칸 건너뜀') : ''}${R.miss.length ? dvTag('못 찾은 줄 ' + R.miss.length, 'bad') : ''}</div>
    <div style="max-height:34vh;overflow:auto"><table class="dv-t"><thead><tr><th></th><th>배당사건번호</th><th>법조치키</th><th>칸</th><th>지금</th><th></th><th>바뀔 값</th></tr></thead><tbody>
    ${R.ch.map((c, i) => `<tr><td><input type="checkbox" data-ps="${i}" checked></td><td>${esc(c.no)}</td><td>${esc(c.lkey)}</td><td><b>${esc(c.n)}</b></td><td class="faint">${esc(fv(c.f, c.from))}</td><td>→</td><td><b>${esc(fv(c.f, c.to))}</b></td></tr>`).join('')}
    ${R.miss.map(m => `<tr><td></td><td colspan="6" style="color:var(--bad)">못 찾음 · ${esc(m)}</td></tr>`).join('')}</tbody></table></div>`;
}

// 기존 엑셀 대장 가져오기
async function dvImport() {
  const path = await chooseExcel();
  if (!path) return;
  const P = await api('dv_import_preview', {path});
  const body = `<div class="small faint" style="margin-bottom:8px">${esc(path.split(/[\\/]/).pop())} · ${P.n}줄 · 같은 줄 판단: 법원 + 사건번호 + 법조치키</div>
    <div class="dv-labs">${P.head.map((h, i) => `<span class="dv-lab ${P.names[i] ? '' : 'none'}"><s>${esc(h)} →</s>${P.names[i] ? esc(P.names[i]) : '안 씀'}</span>`).join('')}</div>
    <div class="row-gap" style="margin:10px 0">${dvTag('새로 ' + P.new + '줄', 'now')}${dvTag('이미 있음 ' + P.same + '줄 → 빈 칸만 채움', 'ok')}${P.conflicts.length ? dvTag('다른 값 ' + P.conflicts.length + '칸', 'warn') : ''}</div>
    ${P.conflicts.length ? `<div class="small" style="margin-bottom:6px">대장과 파일 값이 다른 칸 — 파일 값으로 바꿀 것만 고르세요</div><div style="max-height:30vh;overflow:auto"><table class="dv-t"><thead><tr><th></th><th>사건번호</th><th>칸</th><th>대장</th><th>파일</th></tr></thead><tbody>
      ${P.conflicts.map((c, i) => `<tr><td><input type="checkbox" data-ic="${i}"></td><td>${esc(c.no)}</td><td>${esc(c.n)}</td><td>${esc(String(c.mine))}</td><td><b>${esc(String(c.file))}</b></td></tr>`).join('')}</tbody></table></div>` : ''}`;
  const r = await modal('기존 엑셀 대장 가져오기', body, [{text: '취소'}, {text: '가져오기', cls: 'primary', value: async bg => {
    const take = P.conflicts.filter((c, i) => $(`[data-ic="${i}"]`, bg).checked).map(c => [c.id, c.f]);
    return api('dv_import_apply', {path, take_file: take});
  }}], true);
  if (r) { toast(`새로 ${r.new}줄 · 채움 ${r.fill}줄`); DVL.lf = 'all'; DVL.data = await api('dv_ledger'); dvLedDraw($('#view')); }
}

// 법조치 자료와 다른 값
async function dvDiffs() {
  const L = await api('dv_diffs');
  const body = `<div class="small faint" style="margin-bottom:8px">이번에 넣은 법조치 자료 기준 · 고른 것만 대장에 반영하고 변경 기록에 남겨요</div>
    <table class="dv-t"><thead><tr><th></th><th>배당사건번호</th><th>법조치키</th><th>칸</th><th>대장 (지금)</th><th></th><th>법조치 자료 (새 값)</th></tr></thead><tbody>
    ${L.map(d => `<tr><td><input type="checkbox" data-df="${d.i}" checked></td><td>${esc(d.no)}</td><td>${esc(d.lkey)}</td><td><b>${esc(d.n)}</b></td><td class="faint">${esc(d.from) || '(비어 있음)'}</td><td>→</td><td><b>${esc(d.to)}</b></td></tr>`).join('')}</tbody></table>`;
  const r = await modal(`법조치 자료와 다른 값 ${L.length}건`, body, [{text: '이번엔 그대로 두기', value: () => api('dv_diffs_apply', {skip: true})},
    {text: '고른 것 반영', cls: 'primary', value: bg => api('dv_diffs_apply', {idx: $$('[data-df]', bg).filter(c => c.checked).map(c => +c.dataset.df)})}], true);
  if (r) toast(r.n ? `${r.n}칸 반영했어요 · 변경 기록에 남김` : '그대로 뒀어요');
  DVL.data = await api('dv_ledger'); dvLedDraw($('#view'));
}

// ================================================================== ④ 배당 통계
let DVF = {period: null, basis: null, third: '', mgr: '', court: '', metric: 'amt'}, DVST = {third: 'chart', mgr: 'chart', court: 'chart'}, DVD = null;
const DV_BLOCKS = {kpi: '요약 칸', month: '월별 막대', forecast: '앞으로 들어올 돈', aging: '미수령 경과', oldest: '오래된 미수령', third: '제3채무자별', mgr: '담당자별', court: '법원별'};
const dvPct = v => v === null || v === undefined ? '—' : (v * 100).toFixed(0) + '%';
const DV_KPI = {
  amt: {t: '배당액', v: (A) => [DVM(A.amt), '만원'], s: (A, P, d) => d(A.amt, P && P.amt)},
  got: {t: '회수액 (수령)', v: A => [DVM(A.got), '만원'], s: A => `<div class="dv-meter"><i style="width:${(A.rate * 100).toFixed(1)}%"></i></div><span class="small faint">배당액의 ${dvPct(A.rate)} 받음</span>`},
  yield: {t: '배당률', v: A => [A.yld === null ? '—' : (A.yld * 100).toFixed(0), '%'], s: () => '<span class="small faint">배당액 ÷ 청구액(계산서)</span>'},
  unpaid: {t: '미수령 잔액', v: (A, D) => [DVM(D.unpaid), '만원'], s: (A, P, d, D) => `<span class="small faint">${D.late ? `<span style="color:var(--bad);font-weight:600">${D.dash.lateD}일 넘음 ${DVM(D.late)}만</span>` : '오래된 미수령 없음'}</span>`, warn: D => D.late > 0},
  none: {t: '배당 없음', v: A => [A.none, '건'], s: A => `<span class="small faint">전체의 ${dvPct(A.zero)}</span>`},
  d2r: {t: '기일 → 수령', v: A => [A.m_d2r ?? '—', '일'], s: A => `<span class="small faint">중앙값 · 발송까지 ${A.m_d2s ?? '—'}일 + 입금 ${A.m_s2r ?? '—'}일</span>`},
  n: {t: '배당 건수', v: A => [A.n, '건'], s: (A, P, d) => d(A.n, P && P.n)},
  avg: {t: '건당 배당액', v: A => [A.n ? DVM(A.amt / A.n) : 0, '만원'], s: () => '<span class="small faint">배당액 ÷ 건수</span>'},
  rate: {t: '회수율', v: A => [(A.rate * 100).toFixed(0), '%'], s: () => '<span class="small faint">회수액 ÷ 배당액</span>'},
};
SCREENS.dv_stats = async v => {
  document.body.classList.remove('dv-fit');
  const D = await api('dv_stats', {f: dvF()});
  DVD = D;
  if (!DVF.period) { DVF.period = D.f.period; DVF.basis = D.f.basis; }
  const dash = D.dash, show = k => !dash.hide.includes(k);
  const vis = dash.order.filter(show), pan = vis.filter(k => ['third', 'mgr', 'court'].includes(k)).length;
  const span = k => k === 'kpi' ? 6 : k === 'month' ? (show('forecast') ? 4 : 6) : k === 'forecast' ? (show('month') ? 2 : 6) : k === 'aging' ? (show('oldest') ? 3 : 6) : k === 'oldest' ? (show('aging') ? 3 : 6) : 6 / pan;
  const delta = (a, b) => { if (!b) return '<span class="small faint">전년 자료 없음</span>'; const x = (a - b) / b * 100; return `<span class="dv-delta ${x >= 0 ? 'up' : 'down'}">${x >= 0 ? '▲' : '▼'} ${Math.abs(x).toFixed(0)}% <em>전년 같은 기간</em></span>`; };
  const A = D.total, P = D.prev;
  const chips = [['third', '제3채무자'], ['mgr', '담당자'], ['court', '법원']].filter(([k]) => DVF[k]).map(([k, t]) => `<button class="dv-fchip" data-clr="${k}">${t} · ${esc(DVF[k])} ✕</button>`).join('');
  const B = {
    kpi: () => `<div class="dv-kpis" style="grid-template-columns:repeat(${dash.kpis.length},1fr)">${dash.kpis.map(id => { const K = DV_KPI[id]; const [x, u] = K.v(A, D); return `<button class="card dv-kpi ${K.warn && K.warn(D) ? 'warnk' : ''}" data-drill="kpi|${id}" title="눌러서 근거 목록 보기"><span>${K.t}<i class="dv-dr">목록 ›</i></span><b>${x}<small>${u}</small></b>${K.s(A, P, delta, D)}</button>`; }).join('')}</div>`,
    month: () => dvMonthly(D), forecast: () => dvForecast(D), aging: () => dvAging(D), oldest: () => dvOldest(D),
    third: () => dvPanel(D, 'third', '제3채무자별', '배당액 순 · 배당률 · 0원 비율'), mgr: () => dvPanel(D, 'mgr', '담당자별', '배당액 · 처리 속도 · 할 일'), court: () => dvPanel(D, 'court', '법원별', '배당액 · 기일→수령 걸린 날'),
  };
  v.innerHTML = head(`${esc(INFO.book)} · 배당기일 · ④`, `배당 통계<span class="dv-h1d">숫자·막대를 누르면 근거 목록 · 회수 실적 · 미수령 · 처리 속도</span>`,
    `<button class="btn" id="sSet">대시보드 설정</button><button class="btn" id="sXl">통계 엑셀로</button><button class="btn primary" id="sRep">보고서 (HTML)</button>`) +
    `<div class="dv-sbar"><div class="seg">${Object.entries(D.periods).map(([k, t]) => `<button data-per="${k}" class="${DVF.period === k ? 'on' : ''}">${t}</button>`).join('')}</div>
      <div class="seg" title="배당기일 기준 = 언제 배당됐나 · 수령일 기준 = 언제 돈이 들어왔나(회수 실적)">${[['date', '배당기일 기준'], ['recv', '수령일 기준']].map(([k, t]) => `<button data-basis="${k}" class="${DVF.basis === k ? 'on' : ''}">${t}</button>`).join('')}</div>
      <div class="seg">${[['amt', '금액'], ['n', '건수']].map(([k, t]) => `<button data-met="${k}" class="${DVF.metric === k ? 'on' : ''}">${t}</button>`).join('')}</div>${chips}${chips ? '<button class="btn sm" data-clr="all">조건 모두 풀기</button>' : ''}</div>
    <div class="dv-dgrid">${vis.map(k => `<div class="dv-dcell" style="grid-column:span ${span(k)}">${B[k]()}</div>`).join('')}</div>`;
  $$('[data-per]', v).forEach(b => b.onclick = () => { DVF.period = b.dataset.per; go('dv_stats', {}, {back: true}); });
  $$('[data-basis]', v).forEach(b => b.onclick = () => { DVF.basis = b.dataset.basis; go('dv_stats', {}, {back: true}); });
  $$('[data-met]', v).forEach(b => b.onclick = () => { DVF.metric = b.dataset.met; go('dv_stats', {}, {back: true}); });
  $$('[data-stab]', v).forEach(b => b.onclick = () => { const [d, k] = b.dataset.stab.split('|'); DVST[d] = k; go('dv_stats', {}, {back: true}); });
  $$('[data-clr]', v).forEach(b => b.onclick = () => { const k = b.dataset.clr; if (k === 'all') DVF.third = DVF.mgr = DVF.court = ''; else DVF[k] = ''; go('dv_stats', {}, {back: true}); });
  $$('[data-drill]', v).forEach(b => b.onclick = e => { e.stopPropagation(); dvDrill(b.dataset.drill); });
  $$('[data-goled]', v).forEach(b => b.onclick = () => go('dv_ledger', {lf: 'all', q: '', open: b.dataset.goled}));
  $('#sSet', v).onclick = () => dvDashSet();
  $('#sXl', v).onclick = () => safe(async () => { const r = await api('dv_stats_xl', {f: dvF()}); dvSaved(r.path); });
  $('#sRep', v).onclick = () => dvReport();
  dvTips(v);
};
const dvF = () => ({period: DVF.period || undefined, basis: DVF.basis || undefined, third: DVF.third, mgr: DVF.mgr, court: DVF.court});
const dvVal = (g, part) => DVF.metric === 'amt' ? (part === 'got' ? g.got : part === 'wait' ? g.wait : g.amt) : (part === 'got' ? g.n_got : part === 'wait' ? g.n_wait : g.n);
const dvFmt = x => DVF.metric === 'amt' ? DVM(x) + '만' : x + '건';
function dvNice(x) { if (x <= 0) return 1; const p = Math.pow(10, Math.floor(Math.log10(x))); const f = x / p; return [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find(s => f <= s) * p; }
const dvTip = o => esc(JSON.stringify(o));
function dvMonthly(D) {
  const data = D.monthly, recv = DVF.basis === 'recv';
  const mx = dvNice(Math.max(0, ...data.map(g => dvVal(g, 'got') + dvVal(g, 'wait'))) * 1.12);
  const ticks = [0, .25, .5, .75, 1].map(f => mx * f);
  const best = data.reduce((a, b) => dvVal(b, 'got') + dvVal(b, 'wait') > dvVal(a, 'got') + dvVal(a, 'wait') ? b : a, data[0]);
  const sum = data.reduce((s, g) => s + dvVal(g, 'got') + dvVal(g, 'wait'), 0);
  return `<div class="card dv-chart"><div class="card-h"><div><h2>월별 ${recv ? '회수액' : DVF.metric === 'amt' ? '배당액' : '배당 건수'}</h2><div class="small faint">${recv ? '수령일' : '배당기일'} 기준 · 합계 ${dvFmt(sum)} · 가장 많은 달 ${+best.k.slice(5)}월 · 막대를 누르면 목록</div></div>
    <div class="dv-legend"><span><i class="sw got"></i>수령</span>${recv ? '' : '<span><i class="sw wait"></i>아직 안 받음</span>'}</div></div>
    <div class="card-b"><div class="dv-mchart" style="--n:${data.length}"><div class="yax">${ticks.map(t => `<span style="bottom:calc(30px + (100% - 30px) * ${t / mx})">${DVF.metric === 'amt' ? (t ? DVM(t) + '만' : '0') : Math.round(t)}</span>`).join('')}</div>
    <div class="plot">${ticks.map(t => `<div class="gl" style="bottom:calc(30px + (100% - 30px) * ${t / mx})"></div>`).join('')}
      ${data.map(g => { const a = dvVal(g, 'got'), w = dvVal(g, 'wait'), tot = a + w;
        return `<div class="col ${g.k === INFO.today.slice(0, 7) ? 'now' : ''}" data-drill="month|${g.k}" data-tip="${dvTip({t: g.k.replace('-', '년 ') + '월', rows: [['수령', dvFmt(a), 'got'], ...(recv ? [] : [['아직 안 받음', dvFmt(w), 'wait']]), ['배당 없음', g.none + '건'], ['건수', g.n + '건'], ['배당률', dvPct(g.yld)]]})}">
          <div class="area">${g === best && tot > 0 ? `<b class="cap" style="bottom:calc(${tot / mx * 100}% + 4px)">${dvFmt(tot)}</b>` : ''}<div class="stack" style="height:${tot / mx * 100}%">${w ? `<i class="wait" style="flex:${w}"></i>` : ''}${a ? `<i class="got" style="flex:${a}"></i>` : ''}</div></div>
          <span class="xl2">${data.length <= 12 || g.k.slice(5) === '01' || +g.k.slice(5) % 3 === 1 ? (+g.k.slice(5)) + '월' : ''}${g.k.slice(5) === '01' && data.length > 12 ? `<em>${g.k.slice(2, 4)}년</em>` : ''}</span></div>`; }).join('')}</div></div></div></div>`;
}
function dvForecast(D) {
  const FC = D.forecast, mx = Math.max(1, ...FC.rows.map(x => x.known + x.est)), tot = FC.rows.reduce((s, x) => s + x.known + x.est, 0);
  return `<div class="card"><div class="card-h"><div><h2>앞으로 들어올 돈</h2><div class="small faint">아직 안 받은 배당 · 합계 약 ${DVM(tot)}만</div></div></div><div class="card-b">
    ${FC.rows.map((x, i) => `<button class="dv-fr" data-drill="fc|${i}"><span class="nm">${x.t}<em>${x.n}건</em></span><span class="track"><span class="stack h" style="width:${(x.known + x.est) / mx * 100}%">${x.known ? `<i class="got" style="flex:${x.known}"></i>` : ''}${x.est ? `<i class="est" style="flex:${x.est}"></i>` : ''}</span></span><span class="vv">${DVM(x.known + x.est)}만 <i class="dv-dr">›</i></span></button>`).join('')}
    <div class="dv-legend" style="margin-top:8px"><span><i class="sw got"></i>배당액 확정</span><span><i class="sw est"></i>추정 (청구액 × 평균 배당률 ${dvPct(FC.avg)})</span></div></div></div>`;
}
function dvAging(D) {
  const AG = D.aging, mx = Math.max(1, ...AG.buckets.map(b => b.amt));
  return `<div class="card"><div class="card-h"><div><h2>미수령 경과</h2><div class="small faint">배당기일 지났는데 아직 안 받은 돈 · 줄을 누르면 목록 → 바로 처리</div></div></div><div class="card-b">
    ${AG.buckets.map((b, i) => `<button class="dv-fr" data-drill="ag|${i}"><span class="nm">${b.t}${b.from >= D.dash.lateD ? ' ' + dvTag('확인 필요', 'bad') : ''}<em>${b.n}건</em></span><span class="track"><span class="stack h" style="width:${b.amt / mx * 100}%">${b.amt ? `<i class="${b.from >= D.dash.lateD ? 'late' : 'wait'}" style="flex:1"></i>` : ''}</span></span><span class="vv">${DVM(b.amt)}만 <i class="dv-dr">›</i></span></button>`).join('')}</div></div>`;
}
function dvOldest(D) {
  const L = D.old_rows || [];
  return `<div class="card"><div class="card-h"><div><h2>오래된 미수령</h2><div class="small faint">조치가 필요한 순 · 누르면 대장에서 열려요</div></div><button class="btn sm" data-drill="old|0">전체 ${D.aging.old.length}건 목록</button></div><div class="card-b" style="padding-top:8px">
    <table class="dv-t"><thead><tr><th>배당사건번호</th><th>채무자키</th><th>담당</th><th>단계</th><th class="num">지난 날</th><th class="num">배당액</th></tr></thead><tbody>
    ${L.slice(0, D.dash.oldN).map(x => `<tr class="click" data-goled="${x.id}"><td>${esc(x.no)}</td><td>${esc(x.dkey)}</td><td>${esc(x.mgr)}</td><td>${x.recv === '발송' ? '발송 · 입금 대기' : '발송 전'}</td><td class="num"><b>${x.days}일</b></td><td class="num">${DVW(x.amt) || '—'}</td></tr>`).join('') || '<tr><td colspan="6" class="faint">없어요</td></tr>'}</tbody></table></div></div>`;
}
function dvPanel(D, dim, title, sub) {
  const G = D.by[dim].slice().sort((a, b) => dvVal(b) - dvVal(a)), top = D.dash.top;
  const total = G.reduce((s, g) => s + dvVal(g), 0);
  let shown = G.slice(0, top); const rest = G.slice(top);
  if (rest.length) shown = shown.concat([rest.reduce((a, g) => ({...a, n: a.n + g.n, amt: a.amt + g.amt, got: a.got + g.got, wait: a.wait + g.wait, n_got: a.n_got + g.n_got, n_wait: a.n_wait + g.n_wait, none: a.none + g.none}), {k: `그 외 ${rest.length}곳`, other: 1, n: 0, amt: 0, got: 0, wait: 0, n_got: 0, n_wait: 0, none: 0})]);
  const mx = Math.max(1, ...shown.map(g => dvVal(g)));
  const extra = g => dim === 'third' ? `배당률 ${dvPct(g.yld)} · 0원 ${dvPct(g.zero)}` : dim === 'mgr' ? `기일→발송 ${g.m_d2s ?? '—'}일 · 할 일 ${g.todo}` : `기일→수령 ${g.m_d2r ?? '—'}일`;
  const body = DVST[dim] === 'chart' ? `<div class="dv-hbars">${shown.map(g => { const a = dvVal(g, 'got'), w = dvVal(g, 'wait'); const sel = DVF[dim] === g.k;
      return `<div class="dv-hb ${sel ? 'sel' : ''} ${DVF[dim] && !sel ? 'dim' : ''} ${g.other ? 'other' : ''}" ${g.other ? '' : `data-drill="dim|${dim}|${esc(g.k)}"`} data-tip="${dvTip({t: g.k, rows: [['수령', dvFmt(a), 'got'], ['아직 안 받음', dvFmt(w), 'wait'], ['건수', g.n + '건'], ['배당률', dvPct(g.yld)], ['배당 없음', g.none + '건'], ['기일→수령', (g.m_d2r ?? '—') + '일']]})}">
        <span class="nm">${esc(g.k)}${g.other ? '' : `<em>${extra(g)}</em>`}</span><span class="track"><span class="stack h" style="width:${(a + w) / mx * 100}%">${a ? `<i class="got" style="flex:${a}"></i>` : ''}${w ? `<i class="wait" style="flex:${w}"></i>` : ''}</span></span>
        <span class="vv">${dvFmt(a + w)}<em>${total ? ((a + w) / total * 100).toFixed(0) : 0}%</em></span></div>`; }).join('') || '<div class="small faint">자료 없음</div>'}</div>`
    : `<div style="overflow:auto"><table class="dv-t"><thead><tr><th>${title.replace('별', '')}</th><th class="num">건수</th><th class="num">배당액</th><th class="num">회수율</th><th class="num">배당률</th><th class="num">0원</th><th class="num">기일→발송</th><th class="num">기일→수령</th>${dim === 'mgr' ? '<th class="num">할 일</th>' : ''}</tr></thead><tbody>
      ${G.map(g => `<tr class="click" data-drill="dim|${dim}|${esc(g.k)}"><td>${esc(g.k)}</td><td class="num">${g.n}</td><td class="num">${DVM(g.amt)}만</td><td class="num">${dvPct(g.rate)}</td><td class="num">${dvPct(g.yld)}</td><td class="num">${g.none}</td><td class="num">${g.m_d2s ?? '—'}일</td><td class="num">${g.m_d2r ?? '—'}일</td>${dim === 'mgr' ? `<td class="num">${g.todo}</td>` : ''}</tr>`).join('')}</tbody></table></div>`;
  return `<div class="card"><div class="card-h"><div><h2>${title}</h2><div class="small faint">${sub} · ${G.length}곳</div></div><div class="seg">${[['chart', '막대'], ['table', '표']].map(([k, t]) => `<button data-stab="${dim}|${k}" class="${DVST[dim] === k ? 'on' : ''}">${t}</button>`).join('')}</div></div><div class="card-b">${body}</div></div>`;
}
function dvTips(v) {
  let tt = $('#dvTT'); if (!tt) { tt = document.createElement('div'); tt.id = 'dvTT'; tt.className = 'dv-tt'; document.body.appendChild(tt); }
  tt.style.display = 'none';
  $$('[data-tip]', v).forEach(el => {
    el.onmousemove = e => { const o = JSON.parse(el.dataset.tip); tt.innerHTML = `<b>${esc(o.t)}</b>${o.rows.map(r => `<div>${r[2] ? `<i class="sw ${r[2]}"></i>` : '<i class="sw"></i>'}<span>${esc(r[0])}</span><em>${esc(r[1])}</em></div>`).join('')}<div class="ttf">눌러서 목록 보기</div>`;
      tt.style.display = 'block'; const w = tt.offsetWidth, h = tt.offsetHeight; let x = e.clientX + 14, y = e.clientY + 14; if (x + w > innerWidth - 8) x = e.clientX - w - 14; if (y + h > innerHeight - 8) y = e.clientY - h - 14; tt.style.left = x + 'px'; tt.style.top = y + 'px'; };
    el.onmouseleave = () => { tt.style.display = 'none'; };
  });
}
// 근거 목록
async function dvDrill(key) {
  const tt = $('#dvTT'); if (tt) tt.style.display = 'none';
  const D = await api('dv_drill', {f: dvF(), key});
  const sel = new Set();
  const ctxH = {claim: '청구액', age: '지난 날', d2r: '기일→수령', est: '추정액'}[D.ctx] || '';
  const age = r => r.recv === '발송' && r.send_at ? `발송 ${-dvLeft(r.send_at)}일째` : r.date && dvLeft(r.date) < 0 && r.recv !== '수령' ? `기일 ${-dvLeft(r.date)}일 지남` : '';
  const ctxV = r => D.ctx === 'claim' ? (DVW(r.claim) || '—') : D.ctx === 'age' ? age(r) : D.ctx === 'd2r' ? (r.recv_at && r.date ? Math.round((new Date(r.recv_at) - new Date(r.date)) / 864e5) + '일' : '—') : D.ctx === 'est' ? (r.amt === '' || r.amt === null ? '약 ' + DVW(Math.round((+r.claim || 0) * D.avg_yield / 1e4) * 1e4) : '—') : '';
  const d = dvDrawer();
  d.classList.add('wide');
  d.innerHTML = `<div class="dv-dh"><div class="row-gap" style="justify-content:space-between;align-items:flex-start"><div><div class="small faint">근거 목록 · ${esc(D.cond)}</div><h2 style="font-size:18px;margin:3px 0 0">${esc(D.title)} <span class="small faint">${D.count}건</span></h2></div><button class="btn sm" id="drC">닫기</button></div>
      <div class="dv-chk ${D.ok ? 'ok' : 'no'}">${D.ok ? '✓' : '!'} ${D.sum === 'n' ? `목록 ${D.count}건` : `목록 합계 ${DVW(D.total)}원`} ${D.ok ? '= 대시보드 값과 같아요' : `· 대시보드 ${D.sum === 'n' ? D.show + '건' : DVW(D.show) + '원'}과 달라요 (추정액·조건 확인)`}</div>
      <div class="small faint" style="margin-top:4px">${esc(D.why)}</div></div>
    <div class="dv-drbar"><label class="small faint"><input type="checkbox" id="drAll"> 모두 고르기</label><span class="small faint" id="drSel"></span><span style="margin-left:auto"></span>
      ${D.act === 'send' ? '<button class="btn sm primary" data-da="send">고른 것 발송 처리</button>' : ''}${D.act === 'recv' ? '<button class="btn sm primary" data-da="recv">고른 것 수령완료</button>' : ''}
      <button class="btn sm" data-da="copy">복사 (엑셀 칸)</button><button class="btn sm" data-da="xl">엑셀로</button>${D.dim ? '<button class="btn sm" data-da="filter">이 조건으로 대시보드 거르기</button>' : ''}</div>
    <div class="dv-db" style="padding:0 12px 12px"><table class="dv-t dv-drt"><thead><tr><th></th><th>배당기일</th><th>채무자키</th><th>법조치키</th><th>담당</th><th>배당법원</th><th>배당사건번호</th><th>제3채무자</th><th>단계</th>${ctxH ? `<th class="num">${ctxH}</th>` : ''}<th class="num">배당액</th></tr></thead><tbody>
      ${D.rows.map(r => `<tr data-dr="${r.id}"><td><input type="checkbox" data-dck="${r.id}"></td><td>${dvD(r.date)}</td><td><b>${esc(r.dkey)}</b></td><td>${esc(r.lkey)}</td><td>${esc(r.mgr)}</td><td>${esc(r.court)}</td><td>${esc(r.no)}</td><td>${esc(r.third)}</td><td>${dvTag(r.stage, r.stage_c)}</td>${ctxH ? `<td class="num">${ctxV(r)}</td>` : ''}<td class="num">${DVW(r.amt) || '—'}</td></tr>`).join('') || '<tr><td colspan="11" class="faint" style="padding:20px;text-align:center">없어요</td></tr>'}
    </tbody><tfoot><tr><td></td><td colspan="${ctxH ? 9 : 8}"><b>합계 ${D.count}건</b></td><td class="num"><b>${DVW(D.total)}</b></td></tr></tfoot></table>
    <div class="small faint" style="margin-top:8px">줄을 두 번 누르면 대장에서 열려요</div></div>`;
  d.classList.add('on');
  const upd = () => { $('#drSel', d).textContent = sel.size ? `${sel.size}건 고름` : ''; };
  $('#drC', d).onclick = () => d.classList.remove('on', 'wide');
  $$('[data-dck]', d).forEach(c => c.onchange = () => { c.checked ? sel.add(c.dataset.dck) : sel.delete(c.dataset.dck); upd(); });
  $('#drAll', d).onchange = e => { $$('[data-dck]', d).forEach(c => { c.checked = e.target.checked; e.target.checked ? sel.add(c.dataset.dck) : sel.delete(c.dataset.dck); }); upd(); };
  $$('[data-dr]', d).forEach(t => t.ondblclick = () => { d.classList.remove('on', 'wide'); go('dv_ledger', {lf: 'all', q: '', open: t.dataset.dr}); });
  $$('[data-da]', d).forEach(b => b.onclick = () => safe(async () => {
    const k = b.dataset.da, L = sel.size ? D.rows.filter(r => sel.has(r.id)) : D.rows;
    if (k === 'copy') return dvCopy(dvTsv(L, true), `${L.length}줄 복사 — 엑셀에 그대로 붙여넣기`);
    if (k === 'xl') { const r = await api('dv_export', {what: 'drill', ids: L.map(x => x.id)}); return dvSaved(r.path); }
    if (k === 'filter') { DVF[D.dim[0]] = D.dim[1]; d.classList.remove('on', 'wide'); return go('dv_stats', {}, {back: true}); }
    if (!sel.size) return toast('먼저 줄을 골라 주세요', true);
    const r = await api('dv_bulk', {ids: [...sel], action: k});
    toast(`${r.n}건 ${k === 'send' ? '발송' : '수령완료'} 처리 · 대시보드 다시 계산`);
    await go('dv_stats', {}, {back: true}); dvDrill(key);
  }));
}
// 대시보드 설정
async function dvDashSet() {
  const S0 = JSON.parse(JSON.stringify(DVD.dash));
  let np = DVD.nopay_n;
  const draw = () => `<div class="dv-ds2"><div class="dv-xsec"><div class="dv-xh"><b>보일 칸과 순서</b><span class="small faint">↑↓ 순서 · 끄면 숨김</span></div>
      ${S0.order.map((k, i) => `<div class="dv-dsr"><label><input type="checkbox" data-dsh="${k}" ${S0.hide.includes(k) ? '' : 'checked'}> ${DV_BLOCKS[k]}</label><span><button class="btn sm" data-dsm="${i}|-1" ${i ? '' : 'disabled'}>↑</button><button class="btn sm" data-dsm="${i}|1" ${i < S0.order.length - 1 ? '' : 'disabled'}>↓</button></span></div>`).join('')}</div>
    <div><div class="dv-xsec"><div class="dv-xh"><b>요약 칸</b><span class="small faint">${S0.kpis.length}개 · 4~8개 · 고른 순서대로</span></div>
      <div class="dv-dsk">${Object.entries(DV_KPI).map(([id, K]) => `<label class="${S0.kpis.includes(id) ? 'on' : ''}"><input type="checkbox" data-dsk="${id}" ${S0.kpis.includes(id) ? 'checked' : ''}> ${K.t}${S0.kpis.includes(id) ? ` <em>${S0.kpis.indexOf(id) + 1}</em>` : ''}</label>`).join('')}</div></div>
    <div class="dv-xsec"><div class="dv-xh"><b>기준 값</b></div><div class="dv-dsv">
      <label>처음 열 때 기간<select class="field" data-dsv="period">${Object.entries(DVD.periods).map(([k, t]) => `<option value="${k}" ${S0.period === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
      <label>처음 열 때 기준<select class="field" data-dsv="basis"><option value="date" ${S0.basis === 'date' ? 'selected' : ''}>배당기일 기준</option><option value="recv" ${S0.basis === 'recv' ? 'selected' : ''}>수령일 기준</option></select></label>
      <label>미수령 「확인 필요」 기준<select class="field" data-dsv="lateD">${[15, 31, 61].map(x => `<option value="${x}" ${S0.lateD === x ? 'selected' : ''}>발송 후 ${x}일부터</option>`).join('')}</select></label>
      <label>제3채무자·담당자·법원 보일 곳 수<select class="field" data-dsv="top">${[5, 8, 10, 15].map(x => `<option ${S0.top === x ? 'selected' : ''}>${x}</option>`).join('')}</select></label>
      <label>오래된 미수령 보일 줄 수<select class="field" data-dsv="oldN">${[5, 6, 10, 15].map(x => `<option ${S0.oldN === x ? 'selected' : ''}>${x}</option>`).join('')}</select></label>
      <label>입금 없음 기준 (오늘 할 일)<input class="field" type="number" min="1" data-dsv="np" value="${np}"></label></div></div></div></div>`;
  const p = modal('대시보드 설정', `<div id="dsB">${draw()}</div>`, [{text: '기본값으로', value: async () => { await api('dv_dash_save', {dash: {}}); DVF.period = DVF.basis = null; return true; }}, {text: '취소'},
    {text: '적용', cls: 'primary', value: async () => { await api('dv_dash_save', {dash: S0, nopay_n: np}); DVF.period = S0.period; DVF.basis = S0.basis; toast('대시보드 설정을 적용했어요 (이 채권에 저장)'); return true; }}], true);
  const bind = () => { const b = $('#dsB'); if (!b) return;
    $$('[data-dsh]', b).forEach(c => c.onchange = () => { const k = c.dataset.dsh; S0.hide = c.checked ? S0.hide.filter(x => x !== k) : S0.hide.concat([k]); b.innerHTML = draw(); bind(); });
    $$('[data-dsm]', b).forEach(x => x.onclick = () => { const [i, d] = x.dataset.dsm.split('|').map(Number); [S0.order[i], S0.order[i + d]] = [S0.order[i + d], S0.order[i]]; b.innerHTML = draw(); bind(); });
    $$('[data-dsk]', b).forEach(c => c.onchange = () => { const id = c.dataset.dsk; if (c.checked) { if (S0.kpis.length >= 8) { toast('요약 칸은 8개까지', true); c.checked = false; return; } S0.kpis.push(id); } else { if (S0.kpis.length <= 4) { toast('요약 칸은 4개 이상', true); c.checked = true; return; } S0.kpis = S0.kpis.filter(x => x !== id); } b.innerHTML = draw(); bind(); });
    $$('[data-dsv]', b).forEach(c => c.onchange = () => { const k = c.dataset.dsv; if (k === 'np') { np = +c.value || np; return; } S0[k] = ['lateD', 'top', 'oldN'].includes(k) ? +c.value : c.value; });
  };
  setTimeout(bind, 30);
  if (await p) go('dv_stats', {}, {back: true});
}
// 보고서
async function dvReport() {
  const r = await api('dv_report', {f: dvF()});
  const p = modal('보고서 미리 보기', `<div class="small faint" style="margin-bottom:8px">지금 고른 기간·기준·조건 그대로 · 한 파일 HTML (인터넷 없이 열림) · 열어서 「인쇄 · PDF로 저장」도 돼요</div><iframe id="repF" style="width:100%;height:62vh;border:1px solid var(--line);border-radius:10px;background:#f5f5f4"></iframe>`,
    [{text: '닫기'}, {text: 'HTML로 저장', cls: 'primary', value: async () => { const s = await api('dv_report', {f: dvF(), save: true}); dvSaved(s.path); return true; }}], true);
  setTimeout(() => { const f = $('#repF'); if (f) f.srcdoc = r.html; const m = f && f.closest('.modal'); if (m) m.style.width = 'min(1000px,94vw)'; }, 30);
  await p;
}

// ================================================================== 오늘 할 일 (현황 콘솔에 배당 한 줄)
// 자세한 목록은 「확인할 것 › 배당」에 있어요. 콘솔에는 종류별 건수만 한 줄로 두어 「오늘 할 것」이 첫 화면에 보이게.
const _dvCon = SCREENS.console;
SCREENS.console = async (v, a) => {
  await _dvCon(v, a);
  try {
    const T = await api('dv_today', {mine: false});
    const box = document.createElement('div');
    box.className = 'card dv-tline';
    box.innerHTML = `<h2>배당 할 일 <span class="small faint">${T.total}건</span></h2>` +
      T.groups.map(g => `<button class="dv-tc ${g.n ? g.c : 'zero'}" data-dvk="${g.k}" title="${esc(g.sub)}">${esc(g.t)} <b>${g.n}</b></button>`).join('') +
      `<span class="sp"></span><label class="small faint dv-np">입금 없음 기준 <input class="field" type="number" min="1" id="dvNp" value="${T.nopay_n}" title="발송→입금 중앙값 ${T.lag}일 × 1.5 (바꿀 수 있어요)" style="width:56px">일</label>
      <button class="btn sm" data-go="home" data-arg='{"cat":"배당","today":false}'>확인할 것에서 보기 →</button><button class="btn sm ghost" data-go="dv_ledger">대장 →</button>`;
    const anchor = $('.con-kpis', v);
    if (anchor) anchor.after(box); else v.appendChild(box);
    $('#dvNp', box).onchange = e => safe(async () => { await api('dv_nopay_set', {n: +e.target.value}); go('console', {}, {back: true}); });
    $$('[data-dvk]', box).forEach(b => b.onclick = () => { const k = b.dataset.dvk; go('dv_ledger', {lf: k === 'check' ? 'check' : k === 'send' ? 'send' : 'doing', q: ''}); });
  } catch (e) { /* 배당 자료가 없으면 건너뜀 */ }
};

// 다른 화면으로 가면 한 화면 배치·떠 있는 막대 정리
const _dvGo = go;
go = async function (id, args = {}, opt = {}) {
  if (!['dv_run', 'dv_ledger'].includes(id)) document.body.classList.remove('dv-fit');
  const g = $('#dvGBar'); if (g) g.classList.remove('on');
  const d = $('#dvDrawer'); if (d && id !== CUR) d.classList.remove('on', 'wide');
  const t = $('#dvTT'); if (t) t.style.display = 'none';
  return _dvGo(id, args, opt);
};
