/* NVIDIA 生態資本投資循環架構｜前端
 * 資料全部由 data/*.json 載入（後端 GitHub Actions 每週產生），本檔只負責呈現。 */

const $ = s => document.querySelector(s);
const tip = $('#tip');
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const srcHTML = arr => '<ol class="srcs">' + arr.map(s => `<li><a href="${s.u}" target="_blank" rel="noopener">${esc(s.t)}</a></li>`).join('') + '</ol>';
function showTip(e, html){tip.innerHTML=html;tip.style.display='block';tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px'}
function hideTip(){tip.style.display='none'}

/* ============================ 全域資料（載入後填入） ============================ */
let ECO, META, MARKET, SEC, NEWS, AIR;
let S = {}, CATS = [], CAT = {}, N = [], NODE = {}, XL = [], KPI = [], EV = [], LOOPS = [];
let STAMP = '';
let MKT = {}, WAR = {}, NEWS_BY = {};
const src = (...k) => k.map(x => ({t:S[x][0], u:S[x][1]}));

const fmtTPE = iso => iso ? iso.slice(0,16).replace('T',' ') : '—';
const fmtB = v => v>=1 ? '$'+(v*10).toLocaleString('zh-TW',{maximumFractionDigits:0})+'億' : '$'+(v*10).toFixed(1)+'億';
const fmtPct = v => v==null ? '—' : `<span class="${v>=0?'up':'dn'}">${v>=0?'+':''}${v.toFixed(1)}%</span>`;
const fmtNum = v => v==null ? '—' : Number(v).toLocaleString('en-US');
const fmtPx = v => v==null ? '—' : '$'+Number(v).toLocaleString('en-US',{maximumFractionDigits:v<0.01?4:2});

async function getJSON(path, optional){
  try{
    const r = await fetch(path + '?v=' + Date.now(), {cache:'no-store'});
    if(!r.ok) throw new Error(r.status + ' ' + r.statusText);
    return await r.json();
  }catch(e){ if(optional) return null; throw new Error(path + '：' + e.message); }
}

async function boot(){
  try{
    [ECO, META, MARKET, SEC, NEWS, AIR] = await Promise.all([
      getJSON('data/ecosystem.json'), getJSON('data/meta.json', true), getJSON('data/market.json', true),
      getJSON('data/sec.json', true), getJSON('data/news.json', true), getJSON('data/ai_review.json', true)]);
  }catch(e){
    $('#loading').className = 'loading err';
    $('#loading').innerHTML = `<b>資料載入失敗</b>：${esc(e.message)}<br>
      若是直接以檔案開啟（file://），瀏覽器會阻擋讀取 JSON。請在專案根目錄執行 <code>python -m http.server -d docs 8000</code> 後開啟 <code>http://localhost:8000</code>，或使用 GitHub Pages 網址。`;
    return;
  }
  S = Object.fromEntries(Object.entries(ECO.sources).map(([k,v]) => [k,[v.t,v.u]]));
  CATS = ECO.categories; CAT = Object.fromEntries(CATS.map(c => [c.id,c]));
  N = ECO.nodes.map(n => ({...n, src: src(...n.src)})); NODE = Object.fromEntries(N.map(n => [n.id,n]));
  XL = ECO.flows.map(f => [f.from, f.to, f.label]);
  KPI = ECO.kpi.map(k => [k.value, k.label, k.src]);
  EV = ECO.timeline.map(e => [e.date, e.title, e.desc, e.cat, e.src]);
  LOOPS = ECO.loops.map(l => ({...l, src: src(...l.src)}));
  STAMP = (META?.updated_at || ECO.meta.curated_at).slice(0,10);
  (MARKET?.holdings || []).forEach(h => MKT[h.node] = h);
  (MARKET?.warrants || []).forEach(w => (WAR[w.node] ||= []).push(w));
  (NEWS?.items || []).forEach(it => it.nodes.forEach(id => (NEWS_BY[id] ||= []).push(it)));

  $('#loading').style.display = 'none'; $('#app').style.display = '';
  renderStatic(); renderUpdateBadge();
  initTree(); drawTree(); showCenter(); initFlow(); drawLoop(0); initTable(); drawTable(); drawTL(); drawWatch();
  initUI();  // export.js：外觀設定與輸出選單
}

/* ============================ 靜態區塊 ============================ */
function renderStatic(){
  $('#subline').textContent = `主資料校訂：${ECO.meta.curated_at}（台北）｜涵蓋股權投資、認股權證、擔保、收購、技術授權與融資平台｜每個節點均附資訊來源`;
  $('#govBody').innerHTML = ECO.governance_html;
  $('#verifyTitle').textContent = ECO.verify.title;
  $('#verifyList').innerHTML = ECO.verify.items_html.map(h => `<li>${h}</li>`).join('');
  $('#footer').innerHTML = ECO.footer_html +
    `<br><b>自動更新：</b>後端 GitHub Actions ${esc(META?.schedule || '每週')} 執行，更新上市持股估值、權證內含價值、SEC 申報與新聞追蹤；人工主資料（金額、狀態、循環結構）不會被自動改寫。`;
  $('#legend').innerHTML = CATS.map(c => `<span><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${c.color};margin-right:4px"></i>${c.name}</span>`).join('');
  const live = MARKET ? [
    [fmtB(MARKET.totals.value_b), `上市持股最新估值（週更・收盤 ${MARKET.price_date||'—'}）`, 'watch'],
    [fmtB(MARKET.totals.warrant_intrinsic_b), '認股權證內含價值（週更）', 'watch']] : [];
  $('#kpis').innerHTML = KPI.map(k => `<div class="kpi"><div class="v mono">${k[0]}</div><div class="l">${k[1]}</div><div class="s">${k[2].map((x,i) => `<a href="${S[x][1]}" target="_blank" title="${esc(S[x][0])}">[${i+1}]</a>`).join(' ')}</div></div>`).join('')
    + live.map(k => `<div class="kpi live"><div class="v mono">${k[0]}</div><div class="l"><a href="#" data-goto="v-watch">${k[1]}</a></div><div class="s">🔄</div></div>`).join('');
  document.querySelectorAll('[data-goto]').forEach(a => a.onclick = e => {e.preventDefault(); gotoTab(a.dataset.goto)});
  document.querySelectorAll('nav.tabs button').forEach(b => b.onclick = () => gotoTab(b.dataset.v));
}
function gotoTab(v){
  document.querySelectorAll('nav.tabs button').forEach(x => x.classList.toggle('on', x.dataset.v===v));
  document.querySelectorAll('.view').forEach(x => x.classList.toggle('on', x.id===v));
  if(v==='v-tree') drawLinks();
}

/* ============================ 最新更新時間 ============================ */
function renderUpdateBadge(){
  const box = $('#upd');
  if(!META){ box.innerHTML = `<span class="badge stale">🔄 尚未執行自動更新（請到 GitHub Actions 手動執行一次 Weekly Update）</span>`; return; }
  const ageDays = (Date.now() - new Date(META.updated_at).getTime()) / 864e5;
  const stale = ageDays > 8;
  const steps = Object.entries(META.steps || {}).map(([k,s]) =>
    `<span title="${esc(s.label)}：${esc(s.message)}（${fmtTPE(s.at)}）"><i class="sdot ${s.status}"></i>${esc(s.label.replace('（選用）',''))}</span>`).join(' ');
  box.innerHTML = `<span class="badge ${stale?'stale':''}">🔄 最後更新 <b>${fmtTPE(META.updated_at)}</b>（台北）${stale?`・已 ${Math.floor(ageDays)} 天未更新`:''}</span>
    <span class="muted">下次排程：${fmtTPE(META.next_run_at)}（${esc(META.schedule)}）</span>
    <span class="muted">${steps}</span>
    ${META.run_url?`<a href="${META.run_url}" target="_blank" rel="noopener">執行紀錄</a>`:''}`;
}

/* ============================ 族譜圖 ============================ */
const NS = 'http://www.w3.org/2000/svg';
const el = (t,a={},p) => {const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e};
let activeCats, selected = null;
const barW = n => n.amt==null ? 0 : Math.max(4, Math.log10(n.amt*10+1)/Math.log10(301)*100);

function initTree(){
  activeCats = new Set(CATS.map(c => c.id).filter(c => c!=='cp'));
  const TYPES = [...new Set(N.map(n => n.type))];
  $('#typeSel').innerHTML += TYPES.map(t => `<option>${esc(t)}</option>`).join('');
  $('#catchips').innerHTML = CATS.map(c => `<span class="chip ${activeCats.has(c.id)?'':'off'}" data-c="${c.id}"><i style="background:${c.color}"></i>${c.name}</span>`).join(' ');
  document.querySelectorAll('#catchips .chip').forEach(ch => ch.onclick = () => {const c=ch.dataset.c;activeCats.has(c)?activeCats.delete(c):activeCats.add(c);ch.classList.toggle('off');drawTree()});
  $('#typeSel').onchange = drawTree; $('#q').oninput = applyHighlight;
}
function drawTree(){
  const ft = $('#typeSel').value;
  const groups = CATS.filter(c => activeCats.has(c.id)).map(c => ({c, items:N.filter(n => n.cat===c.id && (!ft||n.type===ft)).sort((a,b) => (b.amt??-1)-(a.amt??-1))})).filter(x => x.items.length);
  const rows = groups.map(({c,items}) => {
    const sum = items.reduce((s,n) => s+(n.cat==='fin'?0:(n.amt||0)),0);
    const disclosed = items.filter(n => n.amt!=null).length;
    const sub = c.id==='fin' ? '目標動員 $5,000億+ 第三方資本' : c.id==='cp' ? '非 NVIDIA 持股，僅標示資金流向' : `已揭露金額合計 ${fmtB(sum)}（${disclosed}/${items.length} 家）`;
    return `<div class="crow" data-cat="${c.id}">
      <div class="ccard" style="--c:${c.color}"><div class="cn">${c.name}</div><div class="cs">${items.length} 個節點<br>${sub}</div></div>
      <div class="leafgrid">${items.map(n => {const nb=(NEWS_BY[n.id]||[]).length; return `<div class="lcard" data-id="${n.id}" style="--c:${c.color}">
        ${n.type.includes('擔保')?'<span class="flag">擔保</span>':''}
        <div class="ln">${esc(n.name)}<small>${esc(n.tk&&n.tk!=='未上市'?n.tk:'')}</small></div>
        <div class="la">${esc(n.short||'—')}${MKT[n.id]?.value_b?` <span style="color:var(--muted);font-weight:400;font-size:.85em">→ 現值 ${fmtB(MKT[n.id].value_b)}</span>`:''}</div>
        <div class="lm">${esc(n.type)}・${esc(n.date.slice(0,7))}</div>
        <div class="bar"><i style="width:${barW(n)}%"></i></div>${nb?`<span class="nb">📰${nb}</span>`:''}</div>`}).join('')}</div></div>`}).join('');
  $('#ftree').innerHTML = `<svg class="links"></svg><div class="froot" id="froot"><b>NVIDIA</b><span>NVDA・資本中樞</span></div><div class="rows">${rows||'<p class="hint">無符合條件的節點</p>'}</div>`;
  $('#froot').onclick = showCenter;
  document.querySelectorAll('.lcard').forEach(card => card.onclick = () => {selected=card.dataset.id;showDetail(NODE[selected]);applyHighlight()});
  applyHighlight(); drawLinks();
}
function drawLinks(){
  const wrap = $('#ftree'); if(!wrap||!wrap.offsetParent) return;
  const svgL = wrap.querySelector('svg.links'); svgL.innerHTML = '';
  svgL.setAttribute('width',wrap.scrollWidth); svgL.setAttribute('height',wrap.scrollHeight);
  const W = wrap.getBoundingClientRect(); const R = e => {const r=e.getBoundingClientRect();return{l:r.left-W.left,r:r.right-W.left,t:r.top-W.top,b:r.bottom-W.top,m:(r.top+r.bottom)/2-W.top}};
  const root = R($('#froot')); const cards = [...wrap.querySelectorAll('.crow')];
  if(!cards.length) return;
  const trunkX = root.r+26;
  const mids = cards.map(r => R(r.querySelector('.ccard')).m);
  el('path',{d:`M${root.r},${root.m} H${trunkX}`,stroke:'#76b900','stroke-width':2,fill:'none'},svgL);
  el('path',{d:`M${trunkX},${Math.min(...mids,root.m)} V${Math.max(...mids,root.m)}`,stroke:'#76b900','stroke-width':2,fill:'none',opacity:.7},svgL);
  cards.forEach(row => {
    const c = CAT[row.dataset.cat].color; const cc = R(row.querySelector('.ccard')); const lg = R(row.querySelector('.leafgrid'));
    el('path',{d:`M${trunkX},${cc.m} H${cc.l}`,stroke:c,'stroke-width':2,fill:'none'},svgL);
    el('circle',{cx:trunkX,cy:cc.m,r:3.5,fill:c},svgL);
    const bx = lg.l-16;
    el('path',{d:`M${cc.r},${cc.m} H${bx}`,stroke:c,'stroke-width':1.6,fill:'none',opacity:.8},svgL);
    el('path',{d:`M${bx+8},${lg.t+4} H${bx} V${lg.b-4} H${bx+8}`,stroke:c,'stroke-width':1.6,fill:'none',opacity:.8},svgL);
  });
}
let rz; window.addEventListener('resize', () => {clearTimeout(rz);rz=setTimeout(drawLinks,120)});
function applyHighlight(){
  const q = $('#q').value.trim().toLowerCase();
  const rel = new Set(); if(selected) XL.forEach(([a,b]) => {if(a===selected)rel.add(b);if(b===selected)rel.add(a)});
  document.querySelectorAll('.lcard').forEach(card => {
    const n = NODE[card.dataset.id];
    card.classList.toggle('dim', !!q && !(n.name+n.tk+n.type).toLowerCase().includes(q));
    card.classList.toggle('sel', selected===n.id);
    card.classList.toggle('rel', rel.has(n.id));
  });
}
function liveBlock(n){
  const m = MKT[n.id], ws = WAR[n.id] || [], ns = NEWS_BY[n.id] || [];
  let h = '';
  if(m) h += `<dt>最新市值（每週自動更新・收盤 ${esc(m.price_date||'—')}）</dt><dd><b style="color:var(--nv)">${m.value_b?fmtB(m.value_b):'—'}</b>
     　股價 ${fmtPx(m.price)}（週 ${fmtPct(m.chg_w_pct)}）${m.stale?'<span class="stl">價格未更新</span>':''}<br>
     股數 ${fmtNum(m.shares)}（${esc(m.shares_src)}）${m.f13_value_b?`；相較 13F 申報市值 ${fmtB(m.f13_value_b)}：${fmtPct(m.chg_vs_13f_pct)}`:''}${m.note?`<br><span class="hint">${esc(m.note)}</span>`:''}</dd>`;
  if(ws.length) h += `<dt>認股權證內含價值（週更）</dt><dd>${ws.map(w => `${esc(w.label)}：${fmtNum(w.shares)} 股 @ ${fmtPx(w.strike)}，現價 ${fmtPx(w.price)} → <b>${w.intrinsic_b!=null?fmtB(w.intrinsic_b):'—'}</b>${w.in_the_money?'':'（價外）'}`).join('<br>')}</dd>`;
  if(ns.length) h += `<dt>本週相關新聞（${ns.length}）</dt><dd><ul style="margin:4px 0;padding-left:18px">${ns.slice(0,6).map(i => `<li><a href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title)}</a> <span class="hint">${esc(i.source)}・${esc((i.published||'').slice(5,10))}</span></li>`).join('')}</ul></dd>`;
  const ai = (AIR?.items||[]).filter(x => x.node_id===n.id);
  if(ai.length) h += `<dt>AI 建議待審核（${ai.length}）</dt><dd>${ai.map(x => `• ${esc(x.summary)}（${esc(x.confidence||'')}）`).join('<br>')}</dd>`;
  return h;
}
function showDetail(n){
  const c = CAT[n.cat];
  const rel = XL.filter(x => x[0]===n.id||x[1]===n.id).map(x => `<li>${esc(NODE[x[0]].name)} → ${esc(NODE[x[1]].name)}：${esc(x[2])}</li>`).join('');
  $('#detailBody').innerHTML = `
   <h2>${esc(n.name)}</h2>
   <span class="tag" style="border-color:${c.color};color:${c.color}">${c.name}</span><span class="tag">${esc(n.type)}</span>${n.tk?`<span class="tag mono">${esc(n.tk)}</span>`:''}
   <dl class="kv">
     <dt>投資／交易金額</dt><dd><b style="color:var(--nv)">${esc(n.short||'—')}</b>　${esc(n.amtText)}</dd>
     <dt>日期（最近關鍵事件）</dt><dd class="mono">${esc(n.date)}</dd>
     <dt>最新狀態</dt><dd>${esc(n.status)}</dd>
     ${liveBlock(n)}
     <dt>資金循環／回流機制</dt><dd>${esc(n.flow)}</dd>
     ${rel?`<dt>相關循環連線（已於左側標示「循環關聯」）</dt><dd><ul style="margin:4px 0;padding-left:18px">${rel}</ul></dd>`:''}
     <dt>資訊來源（${n.src.length}）</dt><dd>${srcHTML(n.src)}</dd>
   </dl>`;
}
function showCenter(){
  selected = null; applyHighlight();
  const t = MARKET?.totals;
  $('#detailBody').innerHTML = `<h2 style="color:var(--nv)">NVIDIA（NVDA）資本中樞</h2>
  <p class="hint">版面固定不會隨滑鼠移動。點選任一公司卡片查看金額、日期、循環機制與資訊來源；與其有資金／算力往來的公司會標示「循環關聯」。勾選上方「循環對手方」可顯示 Microsoft、Oracle 等非持股對象。</p>
  <dl class="kv">
   ${t?`<dt>每週估值（收盤 ${esc(MARKET.price_date||'—')}）</dt><dd>上市持股合計 <b style="color:var(--nv)">${fmtB(t.value_b)}</b>（13F 申報 ${fmtB(t.f13_value_b)} 之同名持股現值 ${fmtB(t.value_13f_names_b)}）；認股權證內含價值 ${fmtB(t.warrant_intrinsic_b)}。詳見「📡 每週追蹤」。</dd>`:''}
   <dt>投資策略定位</dt><dd>CFO Kress 明言投資目的在於讓新創以 NVIDIA 硬體建置算力（需求創造機制），而非純財務報酬。</dd><dd>${srcHTML(src('aiweekly'))}</dd>
   <dt>規模</dt><dd>股權投資 2026/7/26 達 $990 億（一年前約 $70 億）；未上市持股 2026/11 達 $655 億；FY27 前九個月投入 $580 億。</dd><dd>${srcHTML(src('tnw_99','tc_1117'))}</dd>
   <dt>或有負債</dt><dd>擔保最大曝險 $1,180 億（俄亥俄 $1,050 億）；新雲或有承諾 $320 億，NVIDIA 表示尚無任何擔保付款。</dd><dd>${srcHTML(src('blockspace'))}</dd>
   <dt>13F（2026/9/30）</dt><dd>SpaceX $196.8億、Intel $193.7億、CoreWeave $41.1億、Coherent $22.4億、Synopsys $18.9億、Nokia $7.4億、Nebius $2.8億、Generate Bio $0.13億。</dd><dd>${srcHTML(src('kucoin_13f','fw_13f'))}</dd>
  </dl>`;
}

/* ============================ 資金循環圖 ============================ */
const fsvg = $('#flow');
let curLoop = 0;
const FS = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--fs')) || 1;
function initFlow(){
  $('#looplist').innerHTML = '<div class="hint" style="margin-bottom:10px">選擇一個循環，查看資金 → 算力 → 營收如何回到 NVIDIA。實線＝循環主路徑，虛線＝內部捷徑（擔保、反向承購等）。</div>' +
    LOOPS.map((l,i) => `<button data-i="${i}" class="${i?'':'on'}">${l.title}<small>${l.sub}</small></button>`).join('');
  document.querySelectorAll('#looplist button').forEach(b => b.onclick = () => {document.querySelectorAll('#looplist button').forEach(x => x.classList.toggle('on',x===b));drawLoop(+b.dataset.i)});
}
function multiText(parent,x,y,str,attrs,lh=15*FS()){
  const lines = str.split('\n'); const t = el('text',{x,y:y-(lines.length-1)*lh/2,'text-anchor':'middle','dominant-baseline':'middle',...attrs},parent);
  lines.forEach((ln,i) => {const s=el('tspan',{x,dy:i?lh:0},t);s.textContent=ln});return t;
}
function drawLoop(i){
  curLoop = i; const L = LOOPS[i]; fsvg.innerHTML = '';
  const defs = el('defs',{},fsvg);
  const mk = (id,col) => {const m=el('marker',{id,viewBox:'0 0 10 10',refX:8,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'},defs);el('path',{d:'M0,0 L10,5 L0,10 z',fill:col},m)};
  mk('fa','#76b900'); mk('fb','#f87171');
  const R = 270, n = L.nodes.length, P = L.nodes.map((_,k) => {const a=-Math.PI/2+k*2*Math.PI/n;return{x:R*Math.cos(a)*1.25,y:R*Math.sin(a),a}});
  el('ellipse',{cx:0,cy:0,rx:R*1.25,ry:R,fill:'none',style:'stroke:var(--line2)','stroke-dasharray':'2 8'},fsvg);
  const NR = 74*Math.max(1,FS());
  L.edges.forEach(([a,b,lab,kind],k) => {
    const p = P[a], q = P[b]; const dx = q.x-p.x, dy = q.y-p.y, d = Math.hypot(dx,dy);
    const sx = p.x+dx/d*NR, sy = p.y+dy/d*NR, ex = q.x-dx/d*(NR+6), ey = q.y-dy/d*(NR+6);
    let path, lx, ly;
    if(kind==='chord'){
      const mx=(sx+ex)/2, my=(sy+ey)/2; const nx=-dy/d, ny=dx/d; const off=-40;
      path=`M${sx},${sy} Q${mx+nx*off},${my+ny*off} ${ex},${ey}`; lx=mx+nx*off*0.6; ly=my+ny*off*0.6;
    } else {
      const mx=(sx+ex)/2, my=(sy+ey)/2; const len=Math.hypot(mx,my)||1; const bow=70;
      const cx=mx+mx/len*bow, cy=my+my/len*bow; path=`M${sx},${sy} Q${cx},${cy} ${ex},${ey}`; lx=mx+mx/len*(bow+38); ly=my+my/len*(bow+30);
    }
    const col = kind==='chord'?'#f87171':'#76b900';
    el('path',{d:path,fill:'none',stroke:col,'stroke-width':kind==='chord'?1.8:2.6,'stroke-dasharray':kind==='chord'?'6 5':'','marker-end':`url(#${kind==='chord'?'fb':'fa'})`,opacity:.9},fsvg);
    const anim = el('circle',{r:4,fill:col},fsvg); el('animateMotion',{dur:(3+k*0.4)+'s',repeatCount:'indefinite',path},anim);
    const bg = el('g',{},fsvg);
    const t = multiText(bg,lx,ly,lab,{style:kind==='chord'?'fill:var(--chord-t)':'fill:var(--edge-t)','font-size':12.5*FS()});
    try{const bb=t.getBBox();bg.insertBefore(el('rect',{x:bb.x-6,y:bb.y-4,width:bb.width+12,height:bb.height+8,rx:6,style:'fill:var(--node)',stroke:col,'stroke-opacity':.4}),t)}catch(e){}
  });
  L.nodes.forEach(([name,col],k) => {
    const p = P[k]; const g = el('g',{},fsvg);
    el('circle',{cx:p.x,cy:p.y,r:NR,style:'fill:var(--node)',stroke:col,'stroke-width':3},g);
    multiText(g,p.x,p.y,name,{fill:col,'font-size':(name.includes('\n')?11:15)*FS(),'font-weight':700},13.5*FS());
  });
  $('#loopBody').innerHTML = `<h2>${L.title}</h2><p class="hint" style="color:var(--text)">${esc(L.text)}</p><dl class="kv"><dt>資訊來源（${L.src.length}）</dt><dd>${srcHTML(L.src)}</dd></dl>
   <dl class="kv"><dt>判讀提醒</dt><dd class="hint">循環結構本身不代表需求虛假；關鍵在於終端客戶（企業、消費者）的付費能否支撐上游承諾。NVIDIA 官方主張需求來自多元客戶，批評者（如 Axios 引述的債市反應）則擔憂連鎖違約風險。</dd><dd>${srcHTML(src('nv_blog_asset','axios_circ'))}</dd></dl>`;
}

/* ============================ 明細表 ============================ */
const COLS = [['name','公司'],['tk','代號'],['cat','類別'],['type','交易型態'],['amt','金額 (US$億)'],['live','最新市值 (週更)'],['date','日期'],['status','最新狀態'],['flow','循環／回流機制'],['src','資訊來源']];
let sortK = 'amt', sortD = -1;
function initTable(){
  $('#tcat').innerHTML += CATS.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  ['#tq','#tcat','#tcp'].forEach(s => $(s).addEventListener('input', drawTable));
}
function drawTable(){
  const q = $('#tq').value.trim().toLowerCase(), fc = $('#tcat').value, cp = $('#tcp').checked;
  let rows = N.filter(n => (!fc||n.cat===fc) && (cp||n.cat!=='cp') && (!q||JSON.stringify(n).toLowerCase().includes(q)));
  const val = (n,k) => k==='cat' ? CAT[n.cat].name : k==='live' ? (MKT[n.id]?.value_b ?? null) : n[k];
  rows.sort((a,b) => {const x=val(a,sortK), y=val(b,sortK); if(x==null)return 1; if(y==null)return -1; return (x>y?1:x<y?-1:0)*sortD});
  $('#tbl thead').innerHTML = '<tr>' + COLS.map(([k,l]) => `<th data-k="${k}">${l}${sortK===k?(sortD>0?' ▲':' ▼'):''}</th>`).join('') + '</tr>';
  $('#tbl tbody').innerHTML = rows.map(n => {const m=MKT[n.id]; return `<tr>
    <td><b>${esc(n.name)}</b></td><td class="mono">${esc(n.tk)}</td>
    <td><span style="color:${CAT[n.cat].color}">●</span> ${CAT[n.cat].name}</td><td>${esc(n.type)}</td>
    <td class="amt">${n.amt==null?'—':(n.amt*10).toLocaleString('zh-TW',{maximumFractionDigits:1})}<div style="color:var(--muted);font-size:calc(11px*var(--fs));text-align:right">${esc(n.short)}</div></td>
    <td class="amt">${m?.value_b?(m.value_b*10).toLocaleString('zh-TW',{maximumFractionDigits:1}):'—'}<div style="font-size:calc(11px*var(--fs));text-align:right">${m?fmtPct(m.chg_w_pct)+' 週':''}</div></td>
    <td class="mono">${esc(n.date)}</td><td>${esc(n.status)}</td><td style="min-width:240px">${esc(n.amtText)}<br><span style="color:var(--muted)">${esc(n.flow)}</span></td>
    <td class="srcmini" style="min-width:150px">${n.src.map((s,i) => `<a href="${s.u}" target="_blank" title="${esc(s.t)}">[${i+1}] ${esc(s.t.split('｜')[0])}</a>`).join('<br>')}</td></tr>`}).join('');
  window.tableRows = rows; $('#tcount').textContent = `共 ${rows.length} 筆`;
  document.querySelectorAll('#tbl th').forEach(th => th.onclick = () => {const k=th.dataset.k; if(k==='src'||k==='flow')return; sortD=sortK===k?-sortD:-1; sortK=k; drawTable()});
}

/* ============================ 時間軸 ============================ */
function drawTL(){
  const col = c => c==='gov' ? '#f87171' : CAT[c].color;
  let html = '', yr = '';
  EV.slice().sort((a,b) => a[0]<b[0]?-1:1).forEach(([d,t,x,c,s]) => {
    const y = d.slice(0,4); if(y!==yr){html+=`<div class="yr">${y}</div>`; yr=y}
    html += `<div class="ev"><div class="d">${d}</div><div class="dot" style="background:${col(c)}"></div><div><div class="t">${esc(t)}</div><div class="x">${esc(x)}　${s.map((k,i) => `<a href="${S[k][1]}" target="_blank" title="${esc(S[k][0])}">[來源${s.length>1?i+1:''}]</a>`).join(' ')}</div></div></div>`;
  });
  // 本週 SEC 新申報（自動）
  const newF = (SEC?.filings||[]).filter(f => f.is_new);
  if(newF.length) html += `<div class="yr">🔄 本週新申報（自動）</div>` + newF.map(f => `<div class="ev"><div class="d">${f.filing_date}</div><div class="dot" style="background:#f87171"></div><div><div class="t">SEC ${esc(f.form)}</div><div class="x">${esc(f.desc)} ${f.items?`（Items ${esc(f.items)}）`:''}　<a href="${f.url}" target="_blank">[來源]</a></div></div></div>`).join('');
  $('#tl').innerHTML = '<p class="hint">紅點＝公司治理／財報事件；其餘顏色對應投資類別。</p>' + html;
}

/* ============================ 每週追蹤 ============================ */
function drawWatch(){
  const st = s => s ? `<i class="sdot ${s.status}"></i>${s.status==='ok'?'正常':s.status==='skipped'?'略過':'失敗'}` : '';
  const steps = META?.steps || {};
  $('#watchHint').textContent = META ? `最後更新 ${fmtTPE(META.updated_at)}（台北）・下次 ${fmtTPE(META.next_run_at)}・${META.schedule}` : '尚未執行排程';
  const nm = id => NODE[id]?.name || id;
  let h = '';

  // 持股估值
  if(MARKET){
    h += `<div class="wcard full"><h3><span>📈 上市持股估值 ${st(steps.market)}</span><span class="hint">收盤日 ${esc(MARKET.price_date||'—')}</span></h3>
      <div class="wsub">股數優先採用最新 13F；未揭露精確股數者以「13F 市值 ÷ 申報日收盤」推算。合計 <b style="color:var(--nv)">${fmtB(MARKET.totals.value_b)}</b>（13F 申報基準 ${fmtB(MARKET.totals.f13_value_b)}）。</div>
      <div style="overflow:auto"><table><tr><th>公司</th><th>代號</th><th style="text-align:right">股數</th><th>股數來源</th><th style="text-align:right">13F 市值</th><th style="text-align:right">最新股價</th><th style="text-align:right">週漲跌</th><th style="text-align:right">最新市值</th><th style="text-align:right">vs 13F</th></tr>
      ${MARKET.holdings.map(r => `<tr><td><a href="#" data-node="${r.node}">${esc(nm(r.node))}</a></td><td class="mono">${esc(r.ticker)}</td><td class="amt">${fmtNum(r.shares)}</td><td class="hint">${esc(r.shares_src)}</td>
        <td class="amt">${r.f13_value_b?fmtB(r.f13_value_b):'—'}</td><td class="amt">${fmtPx(r.price)}${r.stale?'<span class="stl">未更新</span>':''}</td><td class="amt">${fmtPct(r.chg_w_pct)}</td>
        <td class="amt"><b>${r.value_b?fmtB(r.value_b):'—'}</b></td><td class="amt">${fmtPct(r.chg_vs_13f_pct)}</td></tr>`).join('')}</table></div></div>`;
    h += `<div class="wcard"><h3><span>🎟️ 認股權證內含價值</span></h3><div class="wsub">內含價值＝max(0, 現價−行使價)×股數；未計時間價值。合計 <b style="color:var(--nv)">${fmtB(MARKET.totals.warrant_intrinsic_b)}</b></div>
      <table><tr><th>公司</th><th>權證</th><th style="text-align:right">股數</th><th style="text-align:right">行使價</th><th style="text-align:right">現價</th><th style="text-align:right">內含價值</th></tr>
      ${MARKET.warrants.map(w => `<tr><td><a href="#" data-node="${w.node}">${esc(nm(w.node))}</a></td><td>${esc(w.label)}</td><td class="amt">${fmtNum(w.shares)}</td><td class="amt">${fmtPx(w.strike)}</td><td class="amt">${fmtPx(w.price)}${w.stale?'<span class="stl">未更新</span>':''}</td><td class="amt"><b>${w.intrinsic_b!=null?fmtB(w.intrinsic_b):'—'}</b>${w.in_the_money?'':' <span class="hint">價外</span>'}</td></tr>`).join('')}</table></div>`;
  } else h += `<div class="wcard"><h3>📈 上市持股估值</h3><p class="hint">尚無資料（排程第一次執行後產生）。</p></div>`;

  // SEC
  const f13 = SEC?.f13;
  h += `<div class="wcard"><h3><span>🏛️ SEC 申報 ${st(steps.sec)}</span><span class="hint">近 120 天</span></h3>
    ${f13?`<div class="wsub">最新 13F：申報期 <b>${esc(f13.report_date)}</b>、申報日 ${esc(f13.filing_date)}，${f13.positions} 列、總市值 ${fmtB(f13.total_value_usd/1e9)} ${f13.is_new?'<span class="newtag">NEW</span>':''}
      ${f13.unmatched_new_positions?.length?`<br><b style="color:var(--fin)">⚠ 13F 出現設定檔未追蹤的持股：</b>${f13.unmatched_new_positions.map(u => esc(u.issuer)+'（'+fmtB(u.value_usd/1e9)+'）').join('、')}——請評估是否新增節點。`:''}
      <a href="${f13.url}" target="_blank">[13F 原始檔]</a></div>`:''}
    <ul class="nlist">${(SEC?.filings||[]).map(f => `<li>${f.is_new?'<span class="newtag">NEW</span>':''}<b>${esc(f.form)}</b> ${f.desc&&f.desc!==f.form?esc(f.desc):''}${f.items?` <span class="hint">Items ${esc(f.items)}</span>`:''}<br><span class="nm">${f.filing_date}</span> <a href="${f.url}" target="_blank">開啟</a></li>`).join('') || `<li class="hint">${esc(steps.sec?.message||'尚無資料')}</li>`}</ul></div>`;

  // 新聞
  const items = NEWS?.items || [];
  h += `<div class="wcard"><h3><span>📰 本週新聞追蹤 ${st(steps.news)}</span><span><label class="tg"><input type="checkbox" id="nOnly" checked> 只看涉及節點</label></span></h3>
    <div class="wsub">Google News（英文＋繁中）近 7 天「NVIDIA × 投資／入股／收購／權證／擔保」標題；點標籤跳到該節點。新聞僅供線索，需人工查證後才會寫入主資料。</div>
    <ul class="nlist" id="newsList"></ul></div>`;

  // AI
  if(AIR || steps.ai){
    h += `<div class="wcard"><h3><span>🤖 AI 建議待審核 ${st(steps.ai)}</span><span class="hint">${esc(AIR?.model||'')}</span></h3>
      <div class="wsub">${esc(AIR?.disclaimer || steps.ai?.message || '')}</div>
      <ul class="nlist">${(AIR?.items||[]).map(x => `<li><b>${esc(x.name||nm(x.node_id))}</b>　<span class="tag">${esc(x.change_type)}</span><span class="tag">信心：${esc(x.confidence)}</span><br>${esc(x.summary)}
        ${x.proposed?`<br><span class="hint">建議：${esc(Object.entries(x.proposed).filter(([,v]) => v).map(([k,v]) => k+'='+v).join('；'))}</span>`:''}
        <br>${(x.sources||[]).map((s,i) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">[${i+1}] ${esc(s.title)}</a>`).join(' ')}</li>`).join('') || '<li class="hint">本週無建議</li>'}</ul></div>`;
  }

  // 執行紀錄
  h += `<div class="wcard full"><h3><span>⚙️ 排程執行紀錄</span>${META?.run_url?`<a href="${META.run_url}" target="_blank" class="hint">GitHub Actions</a>`:''}</h3>
    <div class="wsub">${META?`最後更新 ${fmtTPE(META.updated_at)}（台北）・觸發方式：${esc(META.trigger)}・排程：${esc(META.schedule)}・下次：${fmtTPE(META.next_run_at)}・主資料校訂：${esc(META.curated_at)}`:'尚未執行'}</div>
    <div class="steps">${Object.values(steps).map(s => `<div class="step">${st(s)}　<b>${esc(s.label)}</b><br>${esc(s.message)}<br><span class="hint">${fmtTPE(s.at)}${s.secs!=null?`・${s.secs}s`:''}${s.status==='error'&&s.kept_previous?'・沿用上次成功資料':''}</span></div>`).join('')}</div></div>`;

  $('#watch').innerHTML = h;
  const drawNews = () => {
    const only = $('#nOnly').checked;
    const list = items.filter(i => !only || i.nodes.length);
    $('#newsList').innerHTML = list.map(i => `<li>${i.is_new?'<span class="newtag">NEW</span>':''}<a href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title)}</a><br>
      <span class="nm">${esc((i.published||'').replace('T',' ').slice(0,16))}・${esc(i.source)}</span> <span class="ntags">${i.nodes.map(id => `<a data-node="${id}">${esc(nm(id))}</a>`).join('')}</span></li>`).join('')
      || `<li class="hint">${esc(steps.news?.message || '無符合新聞')}</li>`;
    bindNodeLinks($('#newsList'));
  };
  $('#nOnly').onchange = drawNews; drawNews();
  bindNodeLinks($('#watch'));
}
function bindNodeLinks(root){
  root.querySelectorAll('[data-node]').forEach(a => a.onclick = e => {
    e.preventDefault(); const id = a.dataset.node; if(!NODE[id]) return;
    if(!activeCats.has(NODE[id].cat)){activeCats.add(NODE[id].cat); document.querySelector(`#catchips .chip[data-c="${NODE[id].cat}"]`)?.classList.remove('off'); drawTree();}
    gotoTab('v-tree'); selected = id; showDetail(NODE[id]); applyHighlight();
    document.querySelector(`.lcard[data-id="${id}"]`)?.scrollIntoView({behavior:'smooth', block:'center'});
  });
}

boot();
