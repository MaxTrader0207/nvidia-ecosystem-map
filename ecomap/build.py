#!/usr/bin/env python3
"""投資生態族譜 Dashboard 建置器：驗證 data.json 並注入 template.html，輸出單檔互動 HTML。
用法：python3 build.py data.json template.html output.html [--prev 舊版data.json或舊版output.html]
未給 --prev 時，若 output.html 已存在，會自動與它比對並產生「與上一版差異」。
同資料夾若有 pending.json（自動更新腳本產生），會顯示在「待人工確認」。
"""
import json, os, re, sys

RISK_TYPES = ["reg", "geo", "conc", "acct", "exec", "fin"]
DIFF_FIELDS = {"amt": "金額(US$十億)", "short": "金額", "status": "最新狀態", "amtType": "金額口徑", "type": "交易型態", "val": "現值"}

def load_prev(path):
    """從舊版 data.json 或舊版輸出 HTML 取出資料。"""
    try: t = open(path, encoding="utf-8").read()
    except OSError: return None
    if path.endswith(".json"): return json.loads(t)
    m = re.search(r"const DATA = (\{.*?\});\nconst M = DATA\.meta;", t, re.S)
    return json.loads(m.group(1)) if m else None

def make_diff(prev, d):
    P = {n["id"]: n for n in prev.get("nodes", [])}; C = {n["id"]: n for n in d["nodes"]}
    added = [{"id": k, "name": C[k]["name"], "short": C[k].get("short", "")} for k in C if k not in P]
    removed = [{"id": k, "name": P[k]["name"], "short": P[k].get("short", "")} for k in P if k not in C]
    changed = []
    for k in C:
        if k not in P: continue
        for f, lab in DIFF_FIELDS.items():
            a, b = P[k].get(f), C[k].get(f)
            if (a or None) != (b or None): changed.append({"id": k, "name": C[k]["name"], "field": lab, "old": "—" if a in (None, "") else a, "new": "—" if b in (None, "") else b})
    return {"prevAsOf": prev.get("meta", {}).get("asOf"), "added": added, "removed": removed, "changed": changed}

AMT_TYPES = ["equity","capex","commitment","contract","project","inflow","disposal","return","liability","none"]
def validate(d):
    err, warn = [], []
    for k in ("meta", "sources", "categories", "nodes"):
        if k not in d: err.append(f"缺少頂層欄位：{k}")
    if err: return err, warn
    m = d["meta"]
    for k in ("entity", "asOf", "accent"):
        if not m.get(k): err.append(f"meta.{k} 未填")
    S = d["sources"]
    for k, v in S.items():
        if not (isinstance(v, list) and len(v) in (2, 3)): err.append(f"sources.{k} 必須是 [標題, URL] 或 [標題, URL, 可信度]")
        elif not str(v[1]).startswith("https://"): warn.append(f"sources.{k} 非 https 連結：{v[1]}")
    cats = {c["id"]: c for c in d["categories"]}
    if len(cats) != len(d["categories"]): err.append("categories.id 重複")
    used = set()
    def chk_src(where, keys, need=True):
        if need and not keys: err.append(f"{where} 沒有任何來源")
        for k in keys or []:
            if k not in S: err.append(f"{where} 引用不存在的來源 key：{k}")
            used.add(k)
    ids = set()
    for n in d["nodes"]:
        w = f"node[{n.get('id')}]"
        for k in ("id", "name", "cat", "type", "date", "src"):
            if k not in n: err.append(f"{w} 缺少 {k}")
        if n.get("id") in ids: err.append(f"{w} id 重複")
        ids.add(n.get("id"))
        if n.get("cat") not in cats: err.append(f"{w} 類別不存在：{n.get('cat')}")
        a = n.get("amt")
        if a is not None and not isinstance(a, (int, float)): err.append(f"{w} amt 必須是數字（US$ 十億）或 null")
        if not re.match(r"^\d{4}(-\d{2}){0,2}$", str(n.get("date", ""))): err.append(f"{w} date 格式須為 YYYY、YYYY-MM 或 YYYY-MM-DD")
        chk_src(w, n.get("src"))
        if n.get("amtType") and n["amtType"] not in AMT_TYPES: err.append(f"{w} amtType 不合法：{n['amtType']}（可用：{', '.join(AMT_TYPES)}）")
        if n.get("per") not in (None,"","year"): err.append(f"{w} per 只能是 \"year\"（年度金額）")
        if n.get("amt") is None and n.get("amtType") not in (None,"none"): warn.append(f"{w} amt 為空但 amtType={n['amtType']}，應填 none")
        if not n.get("amtType"): warn.append(f"{w} 未標 amtType（金額口徑），將以 equity／none 推定")
        if n.get("direction") not in (None, "in", "out"): err.append(f"{w} direction 須為 in 或 out")
        v = n.get("verified", "")
        if v is not None and v != "" and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(v)): err.append(f"{w} verified 須為 YYYY-MM-DD 或 null")
        for r in n.get("risks", []):
            if r.get("k") not in RISK_TYPES: err.append(f"{w} risks.k 不合法：{r.get('k')}（可用：{', '.join(RISK_TYPES)}）")
            chk_src(w + " risks", r.get("src"), need=False)
        if n.get("pos") not in (None, "", "held", "same", "coinv", "watch"): err.append(f"{w} pos 須為 held/same/coinv/watch")
        if n.get("val") is not None and not isinstance(n["val"], (int, float)): err.append(f"{w} val 必須是數字（US$ 十億）")
        if n.get("val") is not None and not (n.get("valSrc") or n.get("valNote")): warn.append(f"{w} 有 val 但沒有 valSrc／valNote")
        chk_src(w + " valSrc", n.get("valSrc"), need=False)
        if n.get("shares") is not None and not isinstance(n["shares"], (int, float)): err.append(f"{w} shares 必須是數字（股數）")
        if n.get("soldPct") is not None and not (isinstance(n["soldPct"], (int, float)) and 0 < n["soldPct"] < 100): err.append(f"{w} soldPct 必須是 0–100 之間的數字（已減持百分比）")
        if n.get("realized") is not None and not isinstance(n["realized"], (int, float)): err.append(f"{w} realized 必須是數字（已回收金額，US$ 十億）")
        if bool(n.get("shares")) != bool(n.get("pxTk")): warn.append(f"{w} shares 與 pxTk 要一起填，現值才會自動更新")
        if n.get("pxMult") is not None and not isinstance(n["pxMult"], (int, float)): err.append(f"{w} pxMult 必須是數字")
    for i, f in enumerate(d.get("flows", [])):
        if len(f) != 3 or f[0] not in ids or f[1] not in ids: err.append(f"flows[{i}] 端點不存在或格式錯誤：{f}")
    for i, k in enumerate(d.get("kpis", [])): chk_src(f"kpis[{i}]", k.get("src"))
    for i, e in enumerate(d.get("events", [])):
        if e.get("cat") != "gov" and e.get("cat") not in cats: err.append(f"events[{i}] 類別不存在：{e.get('cat')}")
        chk_src(f"events[{i}]", e.get("src"))
    for i, e in enumerate((d.get("notice") or {}).get("items", [])):
        if e.get("cat") != "gov" and e.get("cat") not in cats: err.append(f"notice.items[{i}] 類別不存在：{e.get('cat')}")
        if not re.match(r"^\d{4}-\d{2}(-\d{2})?$", str(e.get("d", ""))): err.append(f"notice.items[{i}] d 須為 YYYY-MM 或 YYYY-MM-DD")
        chk_src(f"notice.items[{i}]", e.get("src"))
    for k, s in S.items():
        if len(s) > 2 and s[2] not in ("A", "B", "C", "D"): err.append(f"sources.{k} 第三欄可信度須為 A/B/C/D")
    for i, l in enumerate(d.get("loops", [])):
        n = len(l.get("nodes", []))
        if not 3 <= n <= 6: warn.append(f"loops[{i}] 節點數 {n}（建議 3–6）")
        for e in l.get("edges", []):
            if not (0 <= e[0] < n and 0 <= e[1] < n): err.append(f"loops[{i}] edge 索引超出範圍：{e}")
        chk_src(f"loops[{i}]", l.get("src"))
        if l.get("dep") not in (None, "high", "mid", "low"): err.append(f"loops[{i}] dep 須為 high/mid/low")
        if l.get("back") is not None and not l.get("backSrc"): warn.append(f"loops[{i}] 有 back 但沒有 backSrc")
        chk_src(f"loops[{i}] backSrc", l.get("backSrc"), need=False)
    ic = d.get("ic") or {}
    chk_src("ic", ic.get("src"), need=False)
    for part in ("opps", "risks", "triggers"):
        for j, x in enumerate(ic.get(part, [])):
            if isinstance(x, dict): chk_src(f"ic.{part}[{j}]", x.get("src"), need=False)
    for i, c in enumerate(d.get("center", [])): chk_src(f"center[{i}]", c.get("src"), need=False)
    if d.get("loopNote"): chk_src("loopNote", d["loopNote"].get("src"), need=False)
    for c in cats.values():
        if not any(n.get("cat") == c["id"] for n in d["nodes"]): warn.append(f"類別 {c['id']} 沒有任何節點")
    unused = set(S) - used
    html_blob = json.dumps([d.get("notice"), d.get("verify"), d.get("method")], ensure_ascii=False)
    unused = [k for k in unused if S[k][1] not in html_blob]
    if unused: warn.append(f"未被引用的來源：{', '.join(sorted(unused))}")
    return err, warn

def main():
    args = sys.argv[1:]; prev_p = None
    if "--prev" in args:
        i = args.index("--prev"); prev_p = args[i + 1]; del args[i:i + 2]
    if len(args) != 3: sys.exit(__doc__)
    data_p, tpl_p, out_p = args
    d = json.load(open(data_p, encoding="utf-8"))
    d.pop("diff", None)
    pend_p = os.path.join(os.path.dirname(os.path.abspath(data_p)), "pending.json")
    if os.path.exists(pend_p): d["pending"] = json.load(open(pend_p, encoding="utf-8"))
    prev = load_prev(prev_p or out_p)
    if prev:
        d["diff"] = make_diff(prev, d)
        # 查證日把關：內容沒變的節點不該只因為重建就把 verified 改成新的 asOf
        pa = prev.get("meta", {}).get("asOf"); P = {n["id"]: n for n in prev.get("nodes", [])}
        AUTO = ("verified", "val", "valDate", "valNote", "valSrc")
        strip = lambda n: {k: v for k, v in n.items() if k not in AUTO}
        bumped = [n["name"] for n in d["nodes"] if n["id"] in P and pa and d["meta"]["asOf"] > pa
                  and n.get("verified") == d["meta"]["asOf"] and P[n["id"]].get("verified", pa) != n.get("verified") and strip(n) == strip(P[n["id"]])]
        if bumped: print(f"⚠️  {len(bumped)} 個節點內容與上一版相同，查證日卻改成 {d['meta']['asOf']}：{'、'.join(bumped[:8])}{'…' if len(bumped) > 8 else ''}。沒有重新查證就請保留原本的 verified。")
        print(f"🔄 與上一版（{d['diff']['prevAsOf']}）差異：新增 {len(d['diff']['added'])}、移除 {len(d['diff']['removed'])}、變動 {len(d['diff']['changed'])}")
    err, warn = validate(d)
    for w in warn: print("⚠️ ", w)
    if err:
        for e in err: print("❌", e)
        sys.exit(f"驗證失敗：{len(err)} 項錯誤")
    tpl = open(tpl_p, encoding="utf-8").read()
    if "/*__DATA_JSON__*/null" not in tpl: sys.exit("template 缺少 /*__DATA_JSON__*/null 佔位符")
    js = json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    open(out_p, "w", encoding="utf-8").write(tpl.replace("/*__DATA_JSON__*/null", js))
    n = d["nodes"]
    print(f"✅ 已輸出 {out_p}｜節點 {len(n)}、類別 {len(d['categories'])}、循環 {len(d.get('loops', []))}、"
          f"事件 {len(d.get('events', []))}、來源 {len(d['sources'])}")

if __name__ == "__main__":
    main()