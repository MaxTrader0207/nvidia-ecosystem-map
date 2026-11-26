#!/usr/bin/env python3
"""跨實體總網路圖建置器：彙整多份 data.json，合併同名交易對手，輸出單檔互動 HTML（含樞紐排行、「若出事」曝險、多實體比較）。
用法：python3 build_network.py network_template.html Ecosystem_Network_Map.html a/data.json b/data.json ...（可用萬用字元）
各實體 Dashboard 須與輸出檔放在同一資料夾，檔名為 <fileSlug>_Ecosystem_Capital_Map.html，連結才會通。
節點可設 "netSkip": true 排除（例如自身 IPO、回購、資本支出這類非交易對手節點）。"""
import json,re,glob,os,sys
ALIAS=[("NVIDIA",r"nvidia|輝達"),("AMD",r"^amd\b|^amd（|超微"),("Google／Alphabet",r"google|alphabet|谷歌"),("Meta",r"^meta\b|meta platforms"),
("Microsoft",r"microsoft|微軟"),("Amazon",r"amazon|aws"),("Oracle",r"oracle"),("TSMC 台積電",r"台積電|tsmc"),("Intel",r"^intel|英特爾"),
("Broadcom",r"broadcom|博通"),("Anthropic",r"anthropic"),("OpenAI",r"openai"),("SpaceX",r"spacex"),("xAI",r"^xai"),("DeepSeek",r"deepseek|深度求索"),
("騰訊 Tencent",r"騰訊|tencent"),("阿里巴巴 Alibaba",r"阿里巴巴|alibaba"),("Apple",r"^apple"),("Arm",r"^arm\b|^arm（|arm holdings"),("Blue Owl",r"blue owl"),
("BlackRock",r"blackrock"),("Apollo",r"apollo"),("Silver Lake",r"silver lake"),("SoftBank",r"softbank|軟銀"),("Samsung",r"samsung|三星"),("Qualcomm",r"qualcomm|高通"),
("Huawei",r"huawei|華為"),("CoreWeave",r"coreweave"),("Nebius",r"nebius"),("Ayar Labs",r"ayar"),("Cerebras",r"cerebras"),("Crusoe",r"crusoe"),("Fluidstack",r"fluidstack"),
("Mobileye",r"mobileye"),("Terafab",r"terafab"),("Tesla",r"^tesla"),("Stellantis",r"stellantis"),("Ford",r"^ford"),("Scale AI",r"scale ai"),("EssilorLuxottica",r"essilor"),
("字節跳動 ByteDance",r"字節|bytedance"),("寧德時代 CATL",r"寧德|catl"),("聯發科 MediaTek",r"聯發科|mediatek"),("宇樹 Unitree",r"宇樹|unitree"),("美團 Meituan",r"美團|meituan"),("紅杉 Sequoia",r"紅杉|sequoia"),("HUMAIN",r"humain"),("MGX",r"mgx"),("Valor",r"valor"),("Cursor",r"cursor"),("Vistra",r"vistra"),("SK hynix",r"hynix")]
def canon(name,tk=""):
    s=name.strip(); low=s.lower()
    for lab,rx in ALIAS:
        if re.search(rx,low) or (tk and re.search(rx,tk.lower())): return lab
    base=re.sub(r"[（(].*?[)）]","",s).strip()
    return base or s
def grade(t,u):
    t=str(t);u=str(u).lower()
    if re.search(r"洽談|傳出|據傳|傳聞|消息人士|知情人士|reportedly|in talks|rumou?r|weighs|considers|擬參與",t,re.I): return "D"
    if re.search(r"sec\.gov|hkexnews|\.gov\b|\.gov\.|newsroom|investor\.|//ir\.|about\.fb\.com|nvidianews|businesswire|prnewswire|globenewswire|mops\.twse|cninfo|szse\.cn|sse\.com|dfcfw\.com/pdf|intc\.com|media\.stellantis|pr\.tsmc|media-room",u): return "A"
    if re.search(r"caifuhao|hao\.cnyes|blog|medium\.com|substack|reddit|stocktwits|etoro|sacra\.com|dev\.to|towardsai|wikipedia|fourweekmba|fool\.com|247wallst|tradingview|uanalyze|stockfeel|statementdog|line\.me",u): return "C"
    if re.search(r"reuters|bloomberg|wsj\.com|ft\.com|cnbc|caixinglobal|nikkei|cna\.com\.tw|udn\.com|ctee\.com|technews|economist|theinformation|techcrunch|scmp\.com|aljazeera|fortune\.com|digitimes|trendforce|jiemian|cls\.cn|wallstreetcn|yicai|stheadline|apnews|anuenews|theregister|tomshardware|datacenterdynamics|36kr\.com|chinatimes|ltn\.com|barrons|axios|nytimes|washingtonpost|theverge|wired|businessinsider|insidermonkey|seekingalpha|thenextweb|siliconangle|finance\.yahoo|aol\.com|marketwatch|techrepublic|electrive|engadget|nownews|ifeng|sina\.c|eastmoney|mining\.com|world-nuclear-news|ans\.org|verdict\.co|energytrend|businesstoday|business-standard|livemint|heise\.de|calcalistech|timesofisrael|ynetnews",u) or re.search(r"Reuters|Bloomberg|路透|彭博|AP（|WSJ",t): return "B"
    if re.search(r"新聞稿|Newsroom|官方公告|重大訊息|10-Q|8-K|10-K|20-F|press release|Reports (First|Second|Third|Fourth)",t,re.I): return "A"
    return "C"
AMT={"equity":"股權成本","capex":"自建投資","commitment":"承諾上限","contract":"合約價值","project":"專案總額","inflow":"流入資金","disposal":"處分回收","return":"股東回饋","liability":"會計負債","none":"未揭露"}
ents=[];links=[];allpairs=set()
if len(sys.argv)<4: sys.exit(__doc__)
TPL,OUT=sys.argv[1],sys.argv[2]
FILES=sorted({p for a in sys.argv[3:] for p in glob.glob(a)})
SKIP_IDS={"dod","usreg","hungov","ndrc","fab28","escrow","govt","capex","buyback","ipo","bond","bonds","offer","hipo","hplace","classc","seriesg","seriesh","founder","founders","musk","zeng","capacity"}
for fp in FILES:
    D=json.load(open(fp,encoding="utf-8")); M=D["meta"]; S=D["sources"]
    cats={c["id"]:c for c in D["categories"]}
    f=f"{M.get('fileSlug') or M['entity']}_Ecosystem_Capital_Map.html"
    ek=canon(M["entity"],M.get("ticker",""))
    st={"tot":{},"grade":{"A":0,"B":0,"C":0,"D":0},"stale":0,"rumor":0,"risk":{},"cpNodes":0,"loops":len(D.get("loops",[])),
        "loopsQ":sum(1 for l in D.get("loops",[]) if l.get("back") is not None),"val":0,"events":len(D.get("events",[])),"top":[]}
    for n in D["nodes"]:
        c=cats.get(n["cat"],{})
        if c.get("counterparty"): st["cpNodes"]+=1; continue
        gs=[grade(S[s][0],S[s][1]) if len(S[s])<3 else S[s][2] for s in n["src"] if s in S]; g=sorted(gs)[0] if gs else "D"
        st["grade"][g]+=1
        if n.get("verified",M["asOf"]) is None: st["stale"]+=1
        if n.get("unconfirmed") or g=="D": st["rumor"]+=1
        for r in n.get("risks",[]): st["risk"][r["k"]]=st["risk"].get(r["k"],0)+1
        if n.get("val") is not None: st["val"]+=1
        if n.get("amt") is not None and not n.get("excludeFromSum") and not n.get("per"):
            t=n.get("amtType","equity"); st["tot"][t]=round(st["tot"].get(t,0)+n["amt"],3)
    st["top"]=[[n["name"],n.get("short",""),AMT.get(n.get("amtType","none"),"")] for n in sorted([n for n in D["nodes"] if n.get("amt") is not None and not cats.get(n["cat"],{}).get("counterparty") and not n.get("excludeFromSum")],key=lambda n:-n["amt"])[:3]]
    ents.append({"key":ek,"entity":M["entity"],"ticker":M.get("ticker",""),"accent":M.get("accent","#888"),"file":f,"asOf":M["asOf"],"nodes":len(D["nodes"]),"st":st})
    for n in D["nodes"]:
        if n["cat"] not in cats: continue
        c=cats[n["cat"]]
        k=canon(n["name"],n.get("tk",""))
        allpairs.add((ek,k))
        if n.get("netSkip") or n["id"] in SKIP_IDS: continue
        gs=[grade(S[s][0],S[s][1]) if len(S[s])<3 else S[s][2] for s in n["src"] if s in S]
        g=sorted(gs)[0] if gs else "D"
        links.append({"ent":ek,"cp":k,"name":n["name"],"cat":c["name"],"counterparty":bool(c.get("counterparty")),"type":n.get("type",""),
          "amtType":n.get("amtType","none"),"dir":n.get("direction","out"),"amt":n.get("amt"),"short":n.get("short",""),"date":n.get("date",""),
          "status":n.get("status",""),"grade":g,"rumor":bool(n.get("unconfirmed")) or g=="D","excl":bool(n.get("excludeFromSum") or n.get("per")),"risks":[r["k"] for r in n.get("risks",[])],
          "src":[[S[s][0],S[s][1]] for s in n["src"] if s in S][:3],
          "val":n.get("val"),"valDate":n.get("valDate",""),"xnote":n.get("xnote",""),"per":n.get("per","")})
entkeys={e["key"] for e in ents}
from collections import defaultdict
by=defaultdict(list)
for l in links: by[l["cp"]].append(l)
hubs=[]
for k,ls in by.items():
    es=sorted(set(l["ent"] for l in ls)|({k} if k in entkeys else set()))
    tot=defaultdict(float)
    for l in ls:
        if l["amt"] is not None and not l["excl"]: tot[l["amtType"]]+=l["amt"]
    hubs.append({"key":k,"isEntity":k in entkeys,"ents":es,"deg":len(es),"links":len(ls),"tot":tot})
for e in ents: e["st"]["hubs"]=sum(1 for h in hubs if h["deg"]>=2 and e["key"] in h["ents"] and h["key"]!=e["key"])
# ---- 跨實體一致性檢查：同一筆關係在不同實體檔的金額是否對得上 ----
def near(a,b,tol=0.15): return a is not None and b is not None and abs(a-b)<=tol*max(abs(a),abs(b),1e-9)
def item(l): return {"ent":l["ent"],"name":l["name"],"short":l["short"],"amt":l["amt"],"amtType":l["amtType"],"dir":l["dir"],"date":l["date"],"val":l["val"],"valDate":l["valDate"],"xnote":l["xnote"],"rumor":l["rumor"]}
checks=[]
real=[l for l in links if l["amt"] is not None and not l["per"]]
# (a) 雙向：A 檔記「對 B」、B 檔記「對 A」
seen=set()
for a in real:
    if a["cp"] not in entkeys or a["cp"]==a["ent"]: continue
    for b in real:
        if b["ent"]!=a["cp"] or b["cp"]!=a["ent"] or a["dir"]==b["dir"]: continue
        ta,tb=a["amtType"],b["amtType"]
        inv=lambda x,y: x in ("equity","commitment") and y in ("inflow","commitment")      # 投資方 ↔ 被投資方
        buy=lambda x,y: x in ("commitment","contract") and y=="contract"                    # 買方 ↔ 賣方
        if not (inv(ta,tb) or inv(tb,ta) or buy(ta,tb) or buy(tb,ta)): continue
        key=tuple(sorted([a["ent"]+"|"+a["name"],b["ent"]+"|"+b["name"]]))
        if key in seen: continue
        seen.add(key)
        ok=near(a["amt"],b["amt"]) or near(a.get("val"),b["amt"]) or near(a["amt"],b.get("val"))
        for cap,act in ((a,b),(b,a)):   # 一方是承諾上限、另一方是已到位金額：不超過上限即一致
            if cap["amtType"]=="commitment" and act["amtType"] in ("inflow","equity") and act["amt"]<=cap["amt"]*1.15: ok=True
        flags=[]
        if a["rumor"]!=b["rumor"]: flags.append("一方標為傳聞／未定案，另一方沒有"); ok=False
        ya,yb=re.match(r"(\d{4})(?:-(\d{2}))?",a["date"] or ""),re.match(r"(\d{4})(?:-(\d{2}))?",b["date"] or "")
        if ya and yb and abs((int(ya[1])-int(yb[1]))*12+int(ya[2] or 6)-int(yb[2] or 6))>12: flags.append("兩邊記載的日期相差超過一年，請確認是否為同一事件")
        checks.append({"kind":"雙向","cp":a["ent"]+" ↔ "+b["ent"],"ok":ok,"items":[item(a),item(b)],"flags":flags})
# (a2) 單邊記載：A 檔有記對 B 的金額關係，但 B 檔完全沒有 A 這個節點
MONEY=("equity","commitment","contract","inflow","project")
one=set()
for a in real:
    if a["cp"] in entkeys and a["cp"]!=a["ent"] and a["amtType"] in MONEY and (a["cp"],a["ent"]) not in allpairs and not a["counterparty"]:
        key=(a["ent"],a["cp"])
        if key in one: continue
        one.add(key)
        checks.append({"kind":"單邊記載","cp":a["ent"]+" → "+a["cp"],"ok":False,"single":True,"items":[item(a),{"ent":a["cp"],"name":"（沒有對應節點）","short":"—","amt":None,"amtType":"none","dir":"","date":"","val":None,"valDate":"","xnote":"","rumor":False}]})
# (b) 同向同口徑：兩家以上都記同一個第三方、口徑相同（專案／合資／收購對象）
for k,ls in by.items():
    if k in entkeys: continue
    g=defaultdict(list)
    for l in ls:
        if l["amt"] is not None and not l["per"] and l["amtType"] in ("project","capex"): g[l["amtType"]].append(l)
    for tp,xs in g.items():
        if len({x["ent"] for x in xs})<2: continue
        am=[x["amt"] for x in xs]
        checks.append({"kind":"同一專案","cp":k,"ok":near(min(am),max(am)),"items":[item(x) for x in xs]})
    # (c) 買賣雙方：一方記股權／收購、另一方記處分
    eq=[l for l in ls if l["amt"] is not None and l["amtType"]=="equity"]; ds=[l for l in ls if l["amt"] is not None and l["amtType"]=="disposal"]
    for e in eq:
        for d_ in ds:
            if e["ent"]!=d_["ent"] and "收購" in (e["type"]+e["name"]): checks.append({"kind":"買賣雙方","cp":k,"ok":d_["amt"]<=e["amt"]*1.15,"items":[item(e),item(d_)]})
for c in checks:
    c["explained"]=any(i["xnote"] for i in c["items"]); c.setdefault("flags",[])
    c["status"]="一致" if c["ok"] else ("已說明" if c["explained"] else ("單邊" if c.get("single") else "待確認"))
checks.sort(key=lambda c:{"待確認":0,"單邊":1,"已說明":2,"一致":3}[c["status"]])
# ---- 跨實體資金閉環偵測：把所有有金額的關係接成有向圖，找出 2–4 個環節的閉環 ----
G=defaultdict(dict)
for l in links:
    und=l["amt"] is None      # 金額未揭露的供應／採購關係也納入，但每條閉環最多一段
    if und and (l["cp"] not in entkeys or re.search(r"訴訟|無金流|競爭|終止|取消",l["type"]+l["short"]+l["status"])): continue
    if not und and l["amtType"] not in MONEY+("capex",): continue
    u,v=(l["cp"],l["ent"]) if l["dir"]=="in" else (l["ent"],l["cp"])
    if u==v: continue
    e=G[u].get(v)
    if e is None or (e["amt"] is None and not und) or (not und and e["amt"] is not None and ((e["rumor"] and not l["rumor"]) or (e["rumor"]==l["rumor"] and l["amt"]>e["amt"]))):
        G[u][v]={"amt":l["amt"],"type":l["type"],"short":l["short"],"amtType":l["amtType"],"rumor":l["rumor"],"per":l["per"],"by":l["ent"],"name":l["name"]}
cycles=[]; seenc=set()
def walk(start,path):
    u=path[-1]
    for v in G.get(u,{}):
        if v==start and len(path)>=2:
            if tuple(sorted(path)) in seenc and len(path)==2: continue
            r=min(range(len(path)),key=lambda i:path[i]); canonp=tuple(path[r:]+path[:r])
            if canonp in seenc: continue
            seenc.add(canonp); seenc.add(tuple(sorted(path))) if len(path)==2 else None
            es=[dict(G[path[i]][path[(i+1)%len(path)]],**{"from":path[i],"to":path[(i+1)%len(path)]}) for i in range(len(path))]
            if sum(e["amt"] is None for e in es)>1 or sum(e["amt"] is not None for e in es)<2: continue
            mi=min((i for i in range(len(es)) if es[i]["amt"] is not None),key=lambda i:es[i]["amt"])
            cycles.append({"path":list(path),"edges":es,"min":es[mi]["amt"],"minIdx":mi,"len":len(path),"ents":sum(1 for x in path if x in entkeys),"rumor":any(e["rumor"] for e in es),"und":any(e["amt"] is None for e in es)})
        elif v not in path and len(path)<4 and v>start: walk(start,path+[v])
for s in sorted(G): walk(s,[s])
cycles.sort(key=lambda c:(c["und"],-c["min"],c["len"])); cycles=cycles[:40]
data={"asOf":max(e["asOf"] for e in ents),"ents":ents,"links":links,"hubs":hubs,"amt":AMT,"checks":checks,"cycles":cycles}
tpl=open(TPL,encoding="utf-8").read()
if "/*__DATA__*/null" not in tpl: sys.exit("network template 缺少 /*__DATA__*/null 佔位符")
open(OUT,"w",encoding="utf-8").write(tpl.replace("/*__DATA__*/null",json.dumps(data,ensure_ascii=False).replace("</","<\\/")))
multi=sorted([h for h in hubs if h["deg"]>=2],key=lambda h:-h["deg"])
print(f"✅ 已輸出 {OUT}｜實體 {len(ents)}、關係 {len(links)}、交易對手 {len(hubs)}、跨 ≥2 實體樞紐 {len(multi)}")
for h in multi[:10]: print("  ",h["deg"],h["key"],"、".join(h["ents"]))
print(f"🔁 跨實體資金閉環：{len(cycles)} 條（列出金額最小一段最大的前 5 條）")
for c in cycles[:5]: print("   "," → ".join(f"{e['from']}［{e['short'] if e['amt'] is not None else '金額未揭露'}］" for e in c["edges"]),"→",c["path"][0])
nc=[c for c in checks if c["status"]=="待確認"]
print(f"🔎 跨實體一致性檢查：{len(checks)} 組，其中一致 {sum(c['status']=='一致' for c in checks)}、已說明 {sum(c['status']=='已說明' for c in checks)}、待確認 {len(nc)}、單邊記載 {sum(c['status']=='單邊' for c in checks)}")
for c in checks:
    if c["status"]=="單邊": print("   ➖ 單邊",c["cp"],"｜",c["items"][0]["name"],c["items"][0]["short"])
for c in nc: print("   ⚠️",c["kind"],c["cp"],"；".join(c["flags"]),"｜"," vs ".join(f"{i['ent']}：{i['short']}（{AMT.get(i['amtType'],'')}，{i['date']}）" for i in c["items"]))
