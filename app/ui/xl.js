// 엑셀 넣기 한 곳 · 연결 기준(키) — 각 화면의 엑셀 넣기도 그대로 쓰고, 짝지은 열은 어디서든 함께 기억
const LINK_INFO = {
  debtor: {t: '채무자 원장 엑셀 → 같은 채무자 찾기', s: '원장에 이미 있는 사람이면 새로 만들지 않고 고쳐요.', by: ['key', 'name_birth', 'name'], key: '원장의 「계좌·고객번호」로 쓸 엑셀 열'},
  case_debtor: {t: '사건 대장 ↔ 채무자 원장 잇기', s: '사건이 어느 채무자의 것인지 찾는 방법이에요. 송달·회생·서류가 모두 이걸로 이어져요.', by: ['key', 'name'],
    names: {key: '사건 대장 「메모 1」 = 원장 계좌·고객번호', name: '당사자 이름 = 채무자 이름'}},
  case: {t: '사건 대장 엑셀 → 키(메모 1)', s: '사건 대장의 「메모 1」에 넣을 키 열이에요. 원장과 잇는 데 써요.', key: '「메모 1」(키)로 쓸 엑셀 열'},
  dlv: {t: '송달·보정 관리 엑셀 → 같은 건 찾기', s: '대장에 이미 있는 건이면 새로 만들지 않고 갱신해요.', sel: [['case_recv', '사건번호 + 보정명령 받은 날 (없으면 사건번호)'], ['case', '사건번호만'], ['none', '찾지 않음 — 줄마다 새로 넣기']]},
  rehab: {t: '회생·파산 공공정보 → 원장의 채무자 찾기', s: '공공정보에는 계좌번호가 없어서 이름·생년월일로 찾아요.', by: ['name_birth', 'name']},
  form: {t: '회사 양식 서류 엑셀 → 원장의 채무자 찾기', s: '원장에서 찾으면 엑셀에 빈 값(사건번호·법원·주소)을 원장 값으로 채워요.', by: ['key', 'name'], key: '「관리번호」로 쓸 엑셀 열'},
};
const LINK_OF = {case: ['case', 'case_debtor'], debtor: ['debtor'], dlv: ['dlv'], rehab: ['rehab'], form: ['form']};
function linkBox(what, cur, methods, header) {
  const I = LINK_INFO[what];
  let h = `<div class="lk" data-lk="${what}"><b>${esc(I.t)}</b><div class="small muted" style="margin:2px 0 8px">${esc(I.s)}</div>`;
  if (I.by) {
    const on = cur.by || [], order = on.concat(I.by.filter(m => !on.includes(m)));
    h += `<div class="lk-by">${order.map((m, i) => `<div class="lk-m ${on.includes(m) ? 'on' : ''}"><label><input type="checkbox" class="cbx" data-lm="${m}" ${on.includes(m) ? 'checked' : ''}>${on.includes(m) ? `<span class="n">${on.indexOf(m) + 1}</span>` : ''}${esc((I.names || {})[m] || methods[m])}</label>
      ${on.includes(m) ? `<span><button class="btn sm ghost" data-lu="${m}" ${on.indexOf(m) ? '' : 'disabled'}>▲</button><button class="btn sm ghost" data-ld="${m}" ${on.indexOf(m) < on.length - 1 ? '' : 'disabled'}>▼</button></span>` : ''}</div>`).join('')}</div>
      <div class="small faint" style="margin-top:6px">${on.length ? '위에서부터 차례로 찾아요.' : '<b style="color:var(--warn)">모두 껐어요 — 같은 사람을 찾지 않고 늘 새로 넣어요.</b>'}${on.includes('name') ? ' 「이름만」으로 찾으면 동명이인일 수 있어 화면에 알려줘요.' : ''}</div>`;
  }
  if (I.sel) h += `<select class="field" data-ls>${I.sel.map(([k, n]) => `<option value="${k}" ${cur.by === k ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select>`;
  if (I.key) {
    const opts = (header || []).filter(Boolean);
    h += `<label class="lb" style="margin-top:10px">${esc(I.key)}</label><div style="display:flex;gap:6px"><input class="field" data-lk-col list="lkc-${what}" value="${esc(cur.key_col || '')}" placeholder="비우면 열 이름으로 자동 (예: 대출번호)">
      ${opts.length ? `<datalist id="lkc-${what}">${opts.map(o => `<option value="${esc(o)}">`).join('')}</datalist>` : ''}</div>`;
  }
  return h + '</div>';
}
function bindLink(root, after) {
  $$('.lk', root).forEach(box => {
    const what = box.dataset.lk;
    const cur = () => $$('[data-lm]', box).filter(c => c.checked).map(c => c.dataset.lm);
    const save = v => safe(async () => { await api('link_set', {what, value: v}); toast('연결 기준을 저장했어요'); after(); });
    $$('[data-lm]', box).forEach(c => c.onchange = () => save({by: cur()}));
    $$('[data-lu]', box).forEach(b => b.onclick = () => { const o = cur(), i = o.indexOf(b.dataset.lu); [o[i - 1], o[i]] = [o[i], o[i - 1]]; save({by: o}); });
    $$('[data-ld]', box).forEach(b => b.onclick = () => { const o = cur(), i = o.indexOf(b.dataset.ld); [o[i + 1], o[i]] = [o[i], o[i + 1]]; save({by: o}); });
    const s = $('[data-ls]', box); if (s) s.onchange = () => save({by: s.value});
    const k = $('[data-lk-col]', box); if (k) k.onchange = () => save({key_col: k.value.trim()});
  });
}

// ================================================================== 엑셀 넣기 (한 곳)
let XLS = null;
SCREENS.xl = async (v, a) => {
  if (a.path) XLS = {path: a.path, dest: a.dest || '', mapping: null};
  if (!XLS) {
    v.innerHTML = head(`${esc(INFO.book)} · 엑셀 하나를 넣을 곳에 맞춰 넣어요 · 짝지은 열은 모든 화면이 기억해요`, '엑셀 넣기') + `
      <div class="fm-drop" id="xlPick"><div class="ic">⇪</div><div style="flex:1"><b>엑셀 파일 고르기</b><div class="small muted" style="margin-top:3px">.xlsx · .xls · .csv · 맨 위에 제목 줄이 있어도 돼요. 머리글을 보고 넣을 곳과 열을 먼저 맞춰 둬요.</div></div></div>
      <div class="xl-dests">${[['case', '사건 대장', '조회할 사건 목록 (법원·사건번호·당사자)'], ['debtor', '채무자 원장', '채권 엑셀 (이름·계좌번호·원금·주소)'], ['dlv', '송달·보정 관리', '보정 대장 (사건번호·보정명령일·기한·조치)'],
        ['rehab', '회생·파산 등재', '신용정보 공공정보 (성명·생년월일·등록 사유)'], ['form', '회사 양식 서류 대상', '서류에 채울 값']].map(([k, n, s]) => `<div class="card xl-d"><b>${n}</b><div class="small muted">${s}</div></div>`).join('')}</div>
      <div class="notice info" style="margin-top:14px">각 화면(사건 대장 · 채무자 원장 · 보정 관리 · 회생·파산 · 서류 만들기)의 엑셀 넣기도 그대로 쓸 수 있어요. 어디서 짝지어도 여기와 같이 기억해요. 같은 사람을 찾는 기준은 <a data-go="settings" data-arg='{"p":"link"}'>설정 → 연결 기준</a>에서 바꿔요.</div>`;
    $('#xlPick').onclick = () => safe(async () => { const p = await chooseExcel(); if (p) go('xl', {path: p}); });
    return;
  }
  const d = await api('xl_open', {path: XLS.path, dest: XLS.dest, mapping: XLS.mapping});
  XLS.dest = d.dest;
  XLS.mapping = d.mapping;
  const colOf = k => d.mapping[k] === undefined ? '' : d.mapping[k];
  const used = Object.entries(d.mapping).sort((x, y) => x[1] - y[1]);
  const lk = await api('link_get');
  v.innerHTML = head(`<a id="xlNew">엑셀 넣기</a> · ${esc(d.name)}`, '엑셀 넣기', `<button class="btn" id="xlOther">다른 파일</button>`) + `
    <div class="xl-dests sel">${d.dests.map(([k, n, s]) => `<div class="card xl-d ${d.dest === k ? 'on' : ''}" data-dest="${k}"><b>${n}</b><div class="small muted">${s}</div></div>`).join('')}</div>
    <div class="xl-g"><div style="display:flex;flex-direction:column;gap:14px;min-width:0">
      <div class="card"><div class="card-h"><h2>열 짝짓기</h2><span class="small muted">${esc(d.name)} · ${d.rows}줄 · 머리글 ${d.header.length}칸</span></div><div class="card-b">
        <div class="dl-map">${d.fields.map(([k, n]) => `<div><b>${esc(n)}</b><select class="field" data-xm="${k}"><option value="">안 씀</option>${d.header.map((h, j) => `<option value="${j}" ${String(colOf(k)) === String(j) ? 'selected' : ''}>${esc(h || excelCol(j))}</option>`).join('')}</select>
          ${d.src[k] === 'mem' ? '<span class="chip now" title="전에 짝지은 열 이름이라 기억했어요">기억</span>' : d.mapping[k] !== undefined ? '<span class="chip ok">자동</span>' : ''}</div>`).join('')}</div>
        <div class="small faint" style="margin-top:8px">「기억」은 전에 다른 화면에서 같은 열 이름을 짝지어 둔 것이에요. 넣기를 누르면 이번 짝짓기도 기억해요.</div></div></div>
      <div class="card" style="overflow:hidden"><div class="card-h" style="padding-bottom:12px"><h2>처음 몇 줄</h2><span class="small muted">짝지은 칸만</span></div>
        <div style="overflow:auto"><table class="tbl lg-tbl"><thead><tr>${used.map(([k]) => `<th>${esc((d.fields.find(f => f[0] === k) || [k, k])[1])}</th>`).join('')}</tr></thead>
        <tbody>${d.peek.map(r => `<tr>${used.map(([, j]) => `<td class="small">${esc(r[j] || '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>
    </div>
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="card"><div class="card-h"><h2>넣기 전에</h2></div><div class="card-b">
        <div class="xl-sum">${esc(d.summary)}</div>
        ${d.dest === 'dlv' ? '<label class="small" style="display:flex;gap:8px;align-items:center;margin-top:10px"><input type="checkbox" class="cbx" id="xlOw">이미 있는 건도 엑셀 값으로 바꾸기</label>' : ''}
        ${d.dest === 'case' ? '<label class="small" style="display:flex;gap:8px;align-items:center;margin-top:10px"><input type="checkbox" class="cbx" id="xlGone">엑셀에 없는 사건은 보관함으로</label>' : ''}
        ${d.dest === 'form' ? `<label class="lb" style="margin-top:10px">양식</label><select class="field" id="xlForm">${(d.forms || []).map(f => `<option value="${f.id}">${esc(f.name)}</option>`).join('') || '<option value="">(양식함이 비어 있어요)</option>'}</select>` : ''}
        <button class="btn primary" id="xlGo" style="width:100%;justify-content:center;margin-top:14px">${d.dest === 'form' ? '서류 만들기로 →' : `${esc(d.dests.find(x => x[0] === d.dest)[1])}에 넣기`}</button></div></div>
      <div class="card"><div class="card-h"><h2>연결 기준 (키)</h2><a class="small" data-go="settings" data-arg='{"p":"link"}'>전체 보기</a></div><div class="card-b">
        ${LINK_OF[d.dest].map(w => linkBox(w, lk.link[w], lk.methods, d.header)).join('<div style="height:14px"></div>')}</div></div>
    </div></div>`;
  $('#xlNew').onclick = () => { XLS = null; go('xl', {}); };
  $('#xlOther').onclick = () => safe(async () => { const p = await chooseExcel(); if (p) { XLS = {path: p, dest: '', mapping: null}; go('xl', {}); } });
  $$('[data-dest]', v).forEach(c => c.onclick = () => { XLS.dest = c.dataset.dest; XLS.mapping = null; go('xl', {}); });
  $$('[data-xm]', v).forEach(s => s.onchange = () => {
    const m = {};
    $$('[data-xm]', v).forEach(x => { if (x.value !== '') m[x.dataset.xm] = +x.value; });
    if (s.value !== '') Object.keys(m).forEach(k => { if (k !== s.dataset.xm && m[k] === +s.value) delete m[k]; });
    XLS.mapping = m; go('xl', {});
  });
  bindLink(v, () => { XLS.mapping = null; go('xl', {}); });
  $('#xlGo').onclick = () => safe(async () => {
    const opts = {overwrite: !!($('#xlOw') || {}).checked, gone_action: ($('#xlGone') || {}).checked ? 'archive' : 'keep', fid: ($('#xlForm') || {}).value || ''};
    if (opts.gone_action === 'archive' && !await confirmBox('엑셀에 없는 사건', '이 엑셀에 없는 사건 대장의 사건을 보관함으로 옮겨요. 계속할까요?', '옮기기')) return;
    const r = await api('xl_apply', {path: XLS.path, dest: XLS.dest, mapping: XLS.mapping, opts});
    toast(r.text);
    XLS = null;
    go(r.go, r.arg || {});
  });
};

// ================================================================== 설정 → 연결 기준
PANE.link = async el => {
  const lk = await api('link_get');
  el.innerHTML = `<div class="card"><div class="card-h"><div><h2>연결 기준 (키)</h2><div class="small muted" style="margin-top:4px">기능마다 같은 사람·같은 건을 무엇으로 찾을지, 어떤 엑셀 열을 키로 쓸지 정해요.</div></div></div>
    <div class="card-b lk-all">${Object.keys(LINK_INFO).map(w => linkBox(w, lk.link[w], lk.methods, [])).join('')}</div></div>
    <div class="card"><div class="card-h"><div><h2>기억한 엑셀 열 이름</h2><div class="small muted" style="margin-top:4px">어느 화면에서 짝지었든 같은 열 이름이면 다음에 자동으로 짝지어요.</div></div><span class="chip wait">${lk.mem}개</span></div>
    <div class="card-b"><button class="btn sm" id="xlForget" ${lk.mem ? '' : 'disabled'}>기억 지우기</button> <a class="small" data-go="xl" style="margin-left:8px">엑셀 넣기로 →</a></div></div>`;
  bindLink(el, () => go('settings', {p: 'link'}));
  $('#xlForget').onclick = () => safe(async () => { if (await confirmBox('기억 지우기', '기억한 엑셀 열 이름을 모두 지워요. 다음부터는 열 이름 사전으로만 짝지어요.', '지우기')) { await api('xl_forget'); go('settings', {p: 'link'}); } });
};
