/* 外觀設定與各區塊輸出工具（原版第二段 script） */

/* ============================ 外觀設定 ============================ */
const ROOT=document.documentElement;
const PREF_KEY='nvmap_prefs_v1';
let prefs={theme:'',bg:'',fs:1};
try{prefs={...prefs,...JSON.parse(localStorage.getItem(PREF_KEY)||'{}')}}catch(e){}
function savePrefs(){try{localStorage.setItem(PREF_KEY,JSON.stringify(prefs))}catch(e){}}
function redrawAll(){try{drawLinks()}catch(e){} try{drawLoop(curLoop)}catch(e){}}
function applyPrefs(){
  if(prefs.theme) ROOT.dataset.theme=prefs.theme; else delete ROOT.dataset.theme;
  if(prefs.bg) ROOT.style.setProperty('--bg',prefs.bg); else ROOT.style.removeProperty('--bg');
  ROOT.style.setProperty('--fs',prefs.fs);
  $('#themeSel').value=prefs.theme;
  $('#bgPick').value=prefs.bg||getComputedStyle(ROOT).getPropertyValue('--bg').trim().slice(0,7)||'#0a0e13';
  $('#fsVal').textContent=Math.round(prefs.fs*100)+'%';
  savePrefs(); if(N.length) requestAnimationFrame(redrawAll);
}
$('#themeSel').onchange=e=>{prefs.theme=e.target.value;prefs.bg='';applyPrefs()};
$('#bgPick').oninput=e=>{prefs.bg=e.target.value;applyPrefs()};
$('#fsDown').onclick=()=>{prefs.fs=Math.max(0.8,Math.round((prefs.fs-0.1)*10)/10);applyPrefs()};
$('#fsUp').onclick=()=>{prefs.fs=Math.min(1.6,Math.round((prefs.fs+0.1)*10)/10);applyPrefs()};
$('#prefReset').onclick=()=>{prefs={theme:'',bg:'',fs:1};applyPrefs()};

applyPrefs();  // 資料載入前先套用主題，避免閃爍

/* ============================ 輸出工具（資料載入後由 app.js 呼叫 initUI） ============================ */
function initUI(){

function toast(m){const t=$('#toast');t.textContent=m;t.style.display='block';clearTimeout(t._h);t._h=setTimeout(()=>t.style.display='none',2200)}
function download(name,data,mime){const b=data instanceof Blob?data:new Blob([data],{type:mime});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),4000);toast('已輸出：'+name)}
const csvCell=v=>`"${String(v??'').replace(/"/g,'""')}"`;
const toCSV=rows=>'﻿'+rows.map(r=>r.map(csvCell).join(',')).join('\r\n');
const mdEsc=v=>String(v??'').replace(/\|/g,'\\|').replace(/\n/g,' ');
const toMDTable=(head,rows)=>`| ${head.join(' | ')} |\n| ${head.map(()=>'---').join(' | ')} |\n`+rows.map(r=>`| ${r.map(mdEsc).join(' | ')} |`).join('\n');
const srcMD=arr=>arr.map((x,i)=>`${i+1}. [${x.t}](${x.u})`).join('\n');
function toXLS(sheets){ // sheets:[{name,head,rows}]
  const tb=sh=>`<h3>${esc(sh.name)}</h3><table border="1"><tr>${sh.head.map(h=>`<th style="background:#e2efda">${esc(h)}</th>`).join('')}</tr>${sh.rows.map(r=>`<tr>${r.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</table><br>`;
  return `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel"><head><meta charset="UTF-8"></head><body>${sheets.map(tb).join('')}</body></html>`;
}
const nodeRow=n=>[n.name,n.tk,CAT[n.cat].name,n.type,n.amt??'',n.short,n.amtText,n.date,n.status,n.flow,n.src.map(x=>x.t+' '+x.u).join(' ; ')];
const NODE_HEAD=['公司','代號','類別','交易型態','金額(US$十億)','金額(顯示)','金額說明','日期','最新狀態','循環/回流機制','資訊來源'];
const nodeMD=n=>`### ${n.name}（${n.tk||'—'}）\n- 類別：${CAT[n.cat].name}\n- 交易型態：${n.type}\n- 金額：${n.short||'—'}｜${n.amtText}\n- 日期：${n.date}\n- 最新狀態：${n.status}\n- 循環／回流：${n.flow}\n- 來源：\n${srcMD(n.src).replace(/^/gm,'  ')}\n`;
const kpiRows=()=>KPI.map(k=>[k[0],k[1],k[2].map(x=>S[x][0]+' '+S[x][1]).join(' ; ')]);
const evRows=()=>EV.slice().sort((a,b)=>a[0]<b[0]?-1:1).map(e=>[e[0],e[1],e[2],e[3]==='gov'?'治理／財報':CAT[e[3]].name,e[4].map(k=>S[k][0]+' '+S[k][1]).join(' ; ')]);
const EV_HEAD=['日期','事件','說明','類別','來源'];
const loopMD=L=>`## ${L.title}\n${L.sub}\n\n${L.text}\n\n**資金流向**\n${L.edges.map(([a,b,lab,k])=>`- ${L.nodes[a][0].replace(/\n/g,' ')} → ${L.nodes[b][0].replace(/\n/g,' ')}：${lab.replace(/\n/g,' ')}${k==='chord'?'（內部捷徑）':''}`).join('\n')}\n\n**來源**\n${srcMD(L.src)}\n`;
const visibleNodes=()=>[...document.querySelectorAll('#ftree .lcard')].map(c=>NODE[c.dataset.id]);
const blockText=el=>el.innerText.replace(/⬇ 輸出 ▾/g,'').trim();

/* 列印單一區塊 */
function printBlock(el){
  document.body.classList.add('printing');el.classList.add('print-target');
  const done=()=>{document.body.classList.remove('printing');el.classList.remove('print-target');window.removeEventListener('afterprint',done)};
  window.addEventListener('afterprint',done);window.print();setTimeout(done,1500);
}
/* 區塊轉 PNG（foreignObject；失敗時改輸出 SVG） */
async function elToPNG(el,name){
  const w=Math.ceil(Math.max(el.scrollWidth,el.getBoundingClientRect().width)), h=Math.ceil(el.scrollHeight);
  const clone=el.cloneNode(true);
  clone.querySelectorAll('.xwrap,.xslot').forEach(x=>x.remove());
  Object.assign(clone.style,{margin:'0',width:w+'px',maxHeight:'none',overflow:'visible'});
  if(getComputedStyle(el).position==='sticky') clone.style.position='static';
  const css=[...document.querySelectorAll('style')].map(x=>x.textContent).join('\n').replace(/:root/g,':root,.xroot').replace(/&/g,'&amp;').replace(/</g,'&lt;');
  const vars=(ROOT.getAttribute('style')||'').replace(/"/g,"'");
  const theme=ROOT.dataset.theme||'';
  const body=new XMLSerializer().serializeToString(clone);
  const svgStr=`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><foreignObject x="0" y="0" width="${w}" height="${h}"><div xmlns="http://www.w3.org/1999/xhtml" class="xroot" ${theme?`data-theme="${theme}"`:''} style="${vars};width:${w}px;height:${h}px;background:var(--bg);color:var(--text);font-family:'Noto Sans TC','PingFang TC','Microsoft JhengHei',system-ui,sans-serif;font-size:calc(14px*var(--fs))"><style>${css}</style>${body}</div></foreignObject></svg>`;
  const url='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svgStr);
  try{
    const img=new Image(); img.src=url; await img.decode();
    const k=2, cv=document.createElement('canvas'); cv.width=w*k; cv.height=h*k;
    const ctx=cv.getContext('2d'); ctx.scale(k,k); ctx.drawImage(img,0,0);
    const blob=await new Promise((res,rej)=>{try{cv.toBlob(b=>b?res(b):rej(new Error('blob')),'image/png')}catch(e){rej(e)}});
    download(name+'.png',blob);
  }catch(e){ download(name+'.svg',svgStr,'image/svg+xml'); toast('此瀏覽器限制 PNG 轉換，已改輸出 SVG（可用瀏覽器開啟）'); }
}
/* 循環圖 SVG（將 CSS 變數解析為實際色彩） */
function flowSVGString(){
  const cs=getComputedStyle(ROOT); const vars=['--bg','--node','--line2','--edge-t','--chord-t','--text'].map(v=>`${v}:${cs.getPropertyValue(v).trim()}`).join(';');
  const c=$('#flow').cloneNode(true); const vb=c.getAttribute('viewBox').split(' ').map(Number);
  c.setAttribute('xmlns','http://www.w3.org/2000/svg'); c.setAttribute('width',vb[2]*1.4); c.setAttribute('height',vb[3]*1.4);
  c.setAttribute('style',vars+";font-family:'Noto Sans TC','PingFang TC','Microsoft JhengHei',sans-serif");
  c.querySelectorAll('animateMotion').forEach(a=>a.parentNode.remove());
  const bg=document.createElementNS(NS,'rect'); Object.entries({x:vb[0],y:vb[1],width:vb[2],height:vb[3],style:'fill:var(--bg)'}).forEach(([k,v])=>bg.setAttribute(k,v)); c.insertBefore(bg,c.firstChild);
  const t=document.createElementNS(NS,'text'); Object.entries({x:vb[0]+16,y:vb[1]+28,'font-size':18,'font-weight':700,style:'fill:var(--text)'}).forEach(([k,v])=>t.setAttribute(k,v)); t.textContent='NVIDIA 資金循環｜'+LOOPS[curLoop].title; c.appendChild(t);
  return {str:new XMLSerializer().serializeToString(c),w:vb[2]*1.4,h:vb[3]*1.4};
}
async function flowPNG(){
  const {str,w,h}=flowSVGString(); const img=new Image(); img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(str); await img.decode();
  const cv=document.createElement('canvas'); cv.width=w*2; cv.height=h*2; const ctx=cv.getContext('2d'); ctx.scale(2,2); ctx.drawImage(img,0,0);
  cv.toBlob(b=>download(`NVIDIA_資金循環_${LOOPS[curLoop].id}_${STAMP}.png`,b),'image/png');
}

/* 各區塊輸出選單 */
const X={
 all:[
  ['全部資料 JSON',()=>download(`NVIDIA_生態資本_全部資料_${STAMP}.json`,JSON.stringify({asOf:STAMP,meta:META,market:MARKET,sec:SEC,news:NEWS,categories:CATS,nodes:N,flows:XL,kpi:KPI.map(k=>({value:k[0],label:k[1],sources:k[2].map(x=>({t:S[x][0],u:S[x][1]}))})),loops:LOOPS,timeline:EV,sources:S},null,2),'application/json')],
  ['全部資料 Excel（.xls 多表）',()=>download(`NVIDIA_生態資本_全部資料_${STAMP}.xls`,toXLS([{name:'投資節點',head:NODE_HEAD,rows:N.map(nodeRow)},{name:'資金循環連線',head:['From','To','說明'],rows:XL.map(([a,b,l])=>[NODE[a].name,NODE[b].name,l])},{name:'關鍵指標',head:['數值','說明','來源'],rows:kpiRows()},{name:'時間軸',head:EV_HEAD,rows:evRows()}]),'application/vnd.ms-excel')],
  ['完整報告 Markdown',()=>download(`NVIDIA_生態資本_報告_${STAMP}.md`,`# NVIDIA 生態資本投資循環架構（${STAMP}）\n\n## 關鍵指標\n${toMDTable(['數值','說明','來源'],kpiRows())}\n\n## 投資節點\n${CATS.map(c=>`\n### ${c.name}\n`+N.filter(n=>n.cat===c.id).map(nodeMD).join('\n')).join('')}\n\n## 資金循環\n${LOOPS.map(loopMD).join('\n')}\n\n## 時間軸\n${toMDTable(EV_HEAD,evRows())}\n`,'text/markdown')],
  ['列印／存成 PDF（整頁）',()=>window.print()]
 ],
 gov:[['Markdown',()=>download(`NVIDIA_治理動態_${STAMP}.md`,'## 治理動態\n\n'+blockText($('#gov')),'text/markdown')],['PNG 圖片',()=>elToPNG($('#gov'),`NVIDIA_治理動態_${STAMP}`)],['列印／PDF',()=>printBlock($('#gov'))]],
 kpi:[['CSV',()=>download(`NVIDIA_關鍵指標_${STAMP}.csv`,toCSV([['數值','說明','來源'],...kpiRows()]),'text/csv')],
      ['JSON',()=>download(`NVIDIA_關鍵指標_${STAMP}.json`,JSON.stringify(KPI.map(k=>({value:k[0],label:k[1],sources:k[2].map(x=>({t:S[x][0],u:S[x][1]}))})),null,2),'application/json')],
      ['Markdown',()=>download(`NVIDIA_關鍵指標_${STAMP}.md`,toMDTable(['數值','說明','來源'],kpiRows()),'text/markdown')],
      ['PNG 圖片',()=>elToPNG($('#kpis'),`NVIDIA_關鍵指標_${STAMP}`)],['列印／PDF',()=>printBlock($('#kpis'))]],
 tree:[['PNG 圖片（族譜圖）',()=>elToPNG($('#ftree'),`NVIDIA_投資族譜_${STAMP}`)],
       ['CSV（目前顯示節點）',()=>download(`NVIDIA_投資族譜_${STAMP}.csv`,toCSV([NODE_HEAD,...visibleNodes().map(nodeRow)]),'text/csv')],
       ['JSON（目前顯示節點）',()=>download(`NVIDIA_投資族譜_${STAMP}.json`,JSON.stringify(visibleNodes(),null,2),'application/json')],
       ['Markdown（依類別分層）',()=>{const v=new Set(visibleNodes().map(n=>n.id));download(`NVIDIA_投資族譜_${STAMP}.md`,`# NVIDIA 投資族譜（${STAMP}）\n`+CATS.map(c=>{const it=N.filter(n=>n.cat===c.id&&v.has(n.id));return it.length?`\n## ${c.name}\n`+it.map(nodeMD).join('\n'):''}).join(''),'text/markdown')}],
       ['列印／PDF',()=>printBlock($('#ftree'))]],
 detail:[['Markdown',()=>download(`NVIDIA_節點_${selected||'NVIDIA'}_${STAMP}.md`,selected?nodeMD(NODE[selected]):blockText($('#detailBody')),'text/markdown')],
         ['JSON',()=>download(`NVIDIA_節點_${selected||'NVIDIA'}_${STAMP}.json`,JSON.stringify(selected?{...NODE[selected],relatedFlows:XL.filter(x=>x.includes(selected))}:{note:blockText($('#detailBody'))},null,2),'application/json')],
         ['PNG 圖片',()=>elToPNG($('#detail'),`NVIDIA_節點_${selected||'NVIDIA'}_${STAMP}`)],['列印／PDF',()=>printBlock($('#detail'))]],
 flow:[['SVG 向量圖（本循環）',()=>download(`NVIDIA_資金循環_${LOOPS[curLoop].id}_${STAMP}.svg`,flowSVGString().str,'image/svg+xml')],
       ['PNG 圖片（本循環）',()=>flowPNG()],
       ['Markdown（本循環說明）',()=>download(`NVIDIA_資金循環_${LOOPS[curLoop].id}_${STAMP}.md`,loopMD(LOOPS[curLoop]),'text/markdown')],
       ['Markdown（全部 6 個循環）',()=>download(`NVIDIA_資金循環_全部_${STAMP}.md`,`# NVIDIA 資金循環架構（${STAMP}）\n\n`+LOOPS.map(loopMD).join('\n'),'text/markdown')],
       ['JSON（全部循環）',()=>download(`NVIDIA_資金循環_${STAMP}.json`,JSON.stringify(LOOPS,null,2),'application/json')],
       ['列印／PDF',()=>printBlock(document.querySelector('.flowwrap'))]],
 table:[['CSV（目前篩選）',()=>download(`NVIDIA_投資明細_${STAMP}.csv`,toCSV([NODE_HEAD,...(window.tableRows||N).map(nodeRow)]),'text/csv')],
        ['Excel（.xls）',()=>download(`NVIDIA_投資明細_${STAMP}.xls`,toXLS([{name:'NVIDIA 投資明細（'+STAMP+'）',head:NODE_HEAD,rows:(window.tableRows||N).map(nodeRow)}]),'application/vnd.ms-excel')],
        ['JSON',()=>download(`NVIDIA_投資明細_${STAMP}.json`,JSON.stringify(window.tableRows||N,null,2),'application/json')],
        ['Markdown 表格',()=>download(`NVIDIA_投資明細_${STAMP}.md`,toMDTable(NODE_HEAD,(window.tableRows||N).map(nodeRow)),'text/markdown')],
        ['PNG 圖片',()=>elToPNG($('#tbl'),`NVIDIA_投資明細_${STAMP}`)],['列印／PDF',()=>printBlock($('.tablewrap'))]],
 tl:[['CSV',()=>download(`NVIDIA_時間軸_${STAMP}.csv`,toCSV([EV_HEAD,...evRows()]),'text/csv')],
     ['Markdown',()=>download(`NVIDIA_時間軸_${STAMP}.md`,toMDTable(EV_HEAD,evRows()),'text/markdown')],
     ['JSON',()=>download(`NVIDIA_時間軸_${STAMP}.json`,JSON.stringify(evRows().map(r=>Object.fromEntries(EV_HEAD.map((h,i)=>[h,r[i]]))),null,2),'application/json')],
     ['PNG 圖片',()=>elToPNG($('#tl'),`NVIDIA_時間軸_${STAMP}`)],['列印／PDF',()=>printBlock($('#tl'))]],
 watch:[['CSV（持股估值）',()=>download(`NVIDIA_持股估值_${STAMP}.csv`,toCSV([['公司','代號','股數','股數來源','13F市值(US$B)','股價','收盤日','週漲跌%','最新市值(US$B)','vs13F%'],...(MARKET?.holdings||[]).map(r=>[NODE[r.node]?.name||r.node,r.ticker,r.shares,r.shares_src,r.f13_value_b,r.price,r.price_date,r.chg_w_pct?.toFixed(2),r.value_b?.toFixed(3),r.chg_vs_13f_pct?.toFixed(2)])]),'text/csv')],
        ['CSV（本週新聞）',()=>download(`NVIDIA_新聞追蹤_${STAMP}.csv`,toCSV([['時間','標題','來源','涉及節點','連結'],...(NEWS?.items||[]).map(i=>[i.published,i.title,i.source,i.nodes.map(id=>NODE[id]?.name||id).join('、'),i.link])]),'text/csv')],
        ['JSON（每週追蹤全部）',()=>download(`NVIDIA_每週追蹤_${STAMP}.json`,JSON.stringify({meta:META,market:MARKET,sec:SEC,news:NEWS,ai_review:AIR},null,2),'application/json')],
        ['PNG 圖片',()=>elToPNG($('#watch'),`NVIDIA_每週追蹤_${STAMP}`)],['列印／PDF',()=>printBlock($('#watch'))]],
 verify:[['Markdown',()=>download(`NVIDIA_資料校驗紀錄_${STAMP}.md`,'## 資料校驗紀錄\n\n'+[...document.querySelectorAll('#verify li')].map(li=>'- '+li.innerText).join('\n'),'text/markdown')],
         ['PNG 圖片',()=>elToPNG($('#verify'),`NVIDIA_資料校驗紀錄_${STAMP}`)],['列印／PDF',()=>printBlock($('#verify'))]]
};
document.querySelectorAll('.xslot').forEach(slot=>{
  const items=X[slot.dataset.x]; if(!items) return;
  const w=document.createElement('span'); w.className='xwrap';
  w.innerHTML=`<button class="xbtn">⬇ 輸出 ▾</button><div class="xmenu">${items.map((it,i)=>`<button data-i="${i}">${it[0]}</button>`).join('')}</div>`;
  const menu=w.querySelector('.xmenu');
  w.querySelector('.xbtn').onclick=e=>{e.stopPropagation();document.querySelectorAll('.xmenu.on').forEach(m=>m!==menu&&m.classList.remove('on'));menu.classList.toggle('on')};
  menu.querySelectorAll('button').forEach(b=>b.onclick=e=>{e.stopPropagation();menu.classList.remove('on');items[+b.dataset.i][1]()});
  slot.appendChild(w);
});
document.addEventListener('click',()=>document.querySelectorAll('.xmenu.on').forEach(m=>m.classList.remove('on')));
applyPrefs();
}
