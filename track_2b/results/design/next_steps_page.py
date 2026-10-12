"""Render ``next_steps_analysis.json`` as one self-contained page with charts: ``docs/analysis/next_steps.html``.

    python results/design/next_steps_page.py

No dependencies and no network: inline SVG drawn by a small script, a table behind every chart.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = json.loads((ROOT / "results" / "design" / "next_steps_analysis.json").read_text(encoding="utf-8"))
THREE = ("Decider, fine-tuned", "Translator, fine-tuned", "Translator, 7 examples")
MISTAKES = ("\"Free slots\" read as \"slots needed\"", "Another preference added, dropped or changed",
            "Two preferences in the wrong order", "Link wrong or missing", "Refused a valid instruction (visible)")  # fmt: skip
OUTCOMES = ("same decision as without the instruction", "another route", "rejects the request")


def esc(value) -> str:
    return html.escape(str(value))


def table(header: list[str], rows: list[list]) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    return f'<details><summary>Table</summary><div class="tw"><table><tr>{head}</tr>{body}</table></div></details>'


def num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}"


# ---- data for the charts and their tables ----------------------------------------------------
probes = D["probes"]
sets = list(probes["sets"].items())
fig1 = {"rows": [{"label": label, "values": [probes["values"][p].get(key) for p in THREE]} for key, label in sets]}
t1 = table(["Test set", *probes["values"]], [[label] + [num(probes["values"][p][key]) if key in probes["values"][p] else "–"
                                                     for p in probes["values"]] for key, label in sets])  # fmt: skip

sent = D["sentences"]["policies"]
fig2 = {"rows": [{"label": p, "dots": [{"x": s["rate"], "t": s["sentence"], "n": s["requests"], "v": s["violations"],
                                        "u": s["unseen_wording"]} for s in sent[p]["sentences"]]} for p in THREE]}  # fmt: skip
t2 = table(["Policy", "Sentences", "With a violation", "Above 5 %", "Violations", "Share in the worst three, %"],
           [[p, len(sent[p]["sentences"]), sent[p]["with_violations"], sent[p]["above_5_percent"], sent[p]["violations"],
             num(sent[p]["share_of_violations_in_the_worst_three"], 0)] for p in THREE])  # fmt: skip

mist = D["mistakes"]
groups = list(next(iter(mist.values())))
fig3 = {"groups": [{"label": g, "bars": [{"label": tr, "n": mist[tr][g]["instructions"],
                                          "values": [mist[tr][g]["percent"].get(k, 0.0) for k in MISTAKES]}
                                         for tr in mist]} for g in groups]}  # fmt: skip
t3 = table(["Translator", "Instruction set", "Instructions", "Right, %", *MISTAKES, "Right if two-preference instructions were read right, %"],
           [[tr, g, mist[tr][g]["instructions"], num(mist[tr][g]["percent"].get("correct", 0))]
            + [num(mist[tr][g]["percent"].get(k, 0)) for k in MISTAKES]
            + [num(mist[tr][g]["correct_if_two_preference_instructions_were_right"])] for tr in mist for g in groups])  # fmt: skip

unseen = D["unseen_types"]
order = sorted(unseen, key=lambda k: -unseen[k].get("binding", 0))
fig4 = {"rows": [{"label": k, "k": unseen[k].get("binding and complies", 0), "n": unseen[k].get("binding", 0),
                  "lo": unseen[k]["binding_interval_95"][0], "hi": unseen[k]["binding_interval_95"][1]} for k in order]}  # fmt: skip
t4 = table(["Instruction type", "Requests", "Where it changes the right answer", "Decider complies there",
            "95 % interval, %", "Cannot be met", "Rejected when it cannot be met"],
           [[k, unseen[k]["requests"], unseen[k].get("binding", 0), unseen[k].get("binding and complies", 0),
             f"{unseen[k]['binding_interval_95'][0]:.0f}–{unseen[k]['binding_interval_95'][1]:.0f}",
             unseen[k].get("cannot be met", 0), unseen[k].get("cannot be met and rejects", 0)] for k in order])  # fmt: skip

ign = D["ignored"]


def outcome(counts: dict) -> list[float]:
    n = counts["requests"]
    other = counts.get("another route", 0) + counts.get("same route, another slot", 0)
    return [100 * counts.get(OUTCOMES[0], 0) / n, 100 * other / n, 100 * counts.get(OUTCOMES[2], 0) / n]


kinds = sorted(ign, key=lambda k: outcome(ign[k])[0])
fig5 = {"rows": [{"label": k, "n": ign[k]["requests"], "values": outcome(ign[k])} for k in kinds]}
t5 = table(["Kind of instruction", "Requests", "Same decision, %", "Another route or slot, %", "Rejects, %"],
           [[k, ign[k]["requests"], *(num(v, 0) for v in outcome(ign[k]))] for k in kinds])  # fmt: skip

cross = D["cross_check"]
t6_rows = [[tr, g, v["requests"], num(v["translator_wrong"]), num(v["decider_wrong"]), num(v["they_agree"]),
            num(v["wrong_when_they_agree"]), num(v["translator_errors_caught"], 0)] for tr in cross for g, v in cross[tr].items()]  # fmt: skip
head6 = ["Translator", "Instruction set", "Requests", "Translator wrong, %", "Decider wrong, %", "They agree, %",
         "Wrong when they agree, %", "Translator errors caught, %"]  # fmt: skip
t6 = ('<div class="tw"><table><tr>' + "".join(f"<th>{esc(h)}</th>" for h in head6) + "</tr>"
      + "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in t6_rows) + "</table></div>")  # fmt: skip

budget = D["budget"]
spent = sum(v for k, v in budget.items() if k != "credit")
ft, few = mist["Translator, fine-tuned"], mist["Translator, 7 examples"]
via = unseen["Pass through a named node"]
talk = ign["A question or small talk"]

DATA = json.dumps({"fig1": fig1, "fig2": fig2, "fig3": fig3, "fig4": fig4, "fig5": fig5, "three": THREE,
                   "mistakes": MISTAKES, "outcomes": ["Same decision as without the instruction", "Another route or slot",
                                                      "Rejects the request"]}, ensure_ascii=False)  # fmt: skip

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Next steps: what the data say</title>
<style>
:root{color-scheme:light dark}
.viz-root{color-scheme:light;--surface:#fcfcfb;--page:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
 --s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--m1:#eda100;--m2:#e87ba4;--m3:#008300;--m4:#4a3aa7;--m5:#e34948;--o1:#c3c2b7;--o2:#4a3aa7;--o3:#e34948;--border:rgba(11,11,11,.10)}
@media (prefers-color-scheme: dark){:root:where(:not([data-theme="light"])) .viz-root{color-scheme:dark;--surface:#1a1a19;--page:#0d0d0d;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;
 --s1:#3987e5;--s2:#d95926;--s3:#199e70;--m1:#c98500;--m2:#d55181;--m3:#008300;--m4:#9085e9;--m5:#e66767;--o1:#52514e;--o2:#9085e9;--o3:#e66767;--border:rgba(255,255,255,.10)}}
:root[data-theme="dark"] .viz-root{color-scheme:dark;--surface:#1a1a19;--page:#0d0d0d;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;
 --s1:#3987e5;--s2:#d95926;--s3:#199e70;--m1:#c98500;--m2:#d55181;--m3:#008300;--m4:#9085e9;--m5:#e66767;--o1:#52514e;--o2:#9085e9;--o3:#e66767;--border:rgba(255,255,255,.10)}
*{box-sizing:border-box}
body{margin:0}
.viz-root{background:var(--page);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;min-height:100vh}
main{max-width:920px;margin:0 auto;padding:32px 16px 72px}
h1{font-size:30px;line-height:1.2;margin:0 0 8px}
h2{font-size:21px;line-height:1.3;margin:0 0 4px}
h3{font-size:17px;margin:28px 0 6px}
p{margin:8px 0}p,li,h1,h2{overflow-wrap:anywhere}.lead{color:var(--ink2);font-size:17px}.sub{color:var(--ink2);font-size:14.5px;margin:2px 0 10px}
.src{color:var(--muted);font-size:12.5px;margin-top:8px}
section.fig{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px 20px 14px;margin:22px 0}
.chart{overflow-x:auto}.chart svg{display:block;width:100%;min-width:600px;height:auto}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13.5px;color:var(--ink2);margin:6px 0 8px}
.legend span{display:inline-flex;align-items:center;gap:6px}.legend i{width:11px;height:11px;border-radius:3px;display:inline-block}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:18px 0}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.tile b{display:block;font-size:30px;line-height:1.15;font-weight:650}.tile span{color:var(--ink2);font-size:13.5px}
.meter{height:10px;border-radius:5px;background:var(--grid);overflow:hidden;margin-top:10px}.meter i{display:block;height:100%;background:var(--s1);border-radius:5px}
details{margin-top:8px;font-size:13.5px}summary{cursor:pointer;color:var(--ink2)}
.tw{overflow-x:auto}table{border-collapse:collapse;margin-top:8px;font-size:13px;font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--grid);padding:5px 10px;text-align:left;vertical-align:top}th{color:var(--ink2);font-weight:600}
ol.plan li{margin:8px 0}
#tip{position:fixed;display:none;z-index:9;max-width:340px;background:var(--ink);color:var(--surface);font-size:12.5px;line-height:1.4;padding:7px 9px;border-radius:7px;pointer-events:none}
svg text{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
svg [tabindex]:focus{outline:2px solid var(--s1);outline-offset:2px}
</style></head>
<body><div class="viz-root"><main>
<h1>Next steps: what the data say</h1>
<p class="lead">Before choosing what to build next, I went back through the answers we already have. Nothing here needed a GPU. Every number comes from <code>results/design/next_steps_analysis.json</code>.</p>
<div class="tiles">
<div class="tile"><b>__FT_SENT__ of 70</b><span>instruction sentences on which the fine-tuned translator breaks an intent in closed loop</span></div>
<div class="tile"><b>__DEC_SENT__ of 70</b><span>sentences on which the decider breaks one at least once</span></div>
<div class="tile"><b>__VIA_K__ of __VIA_N__</b><span>times the decider obeyed "pass through this node", a type it never saw</span></div>
<div class="tile"><b>$__LEFT__</b><span>left of $__CREDIT__ <div class="meter"><i style="width:__PCT__%"></i></div></span></div>
</div>

<section class="fig"><h2>On every harder test, both translators stay above the decider</h2>
<p class="sub">Share of decisions that respect the instruction, on the same held-out requests with the instruction re-worded. All three were trained or prompted in English only.</p>
<div class="legend" id="lg1"></div><div class="chart"><svg id="c1"></svg></div>__T1__
<p class="src">Source: results/offline/*_probes.json. 1,863 requests per set; 600 for Swiss German and misspelt; 1,200 on the other topology.</p></section>

<section class="fig"><h2>The decider is slightly wrong on almost every sentence; a translator is very wrong on a few</h2>
<p class="sub">Each dot is one instruction sentence used by at least 100 requests in closed loop (load 390, three seeds). Its position is the share of those requests on which the intent was broken. The ring at zero stands for all sentences with no broken intent at all.</p>
<div class="chart"><svg id="c2"></svg></div>__T2__
<p class="src">Source: closed-loop replay from the answer caches. Conditions with one instruction per request; the unseen pairs are left out because each of their sentences is used by too few requests.</p></section>

<section class="fig"><h2>Most of the fine-tuned translator's mistakes are instructions with two preferences</h2>
<p class="sub">Share of distinct instructions translated wrongly, by kind of mistake. No translator was shown an instruction with two preferences, by design.</p>
<div class="legend" id="lg3"></div><div class="chart"><svg id="c3"></svg></div>__T3__
<p class="src">Source: results/cache/translate_*.jsonl against the labelled instruction sets in data/instructions/.</p></section>

<section class="fig"><h2>A first hint that the decider follows instructions nobody trained it on</h2>
<p class="sub">Requests where an unseen instruction type changes the right answer, and how often the fine-tuned decider complied. The bar is the 95 % interval; most samples are far too small to conclude from.</p>
<div class="chart"><svg id="c4"></svg></div>__T4__
<p class="src">Source: the out-of-scope probe set, scored afterwards with a rule per type. That set was not designed for this question.</p></section>

<section class="fig"><h2>Text that is not a routing instruction can make the decider reject a request</h2>
<p class="sub">What the decider does with an instruction it should ignore, by kind. Anything other than "same decision" is a silent side effect.</p>
<div class="legend" id="lg5"></div><div class="chart"><svg id="c5"></svg></div>__T5__
<p class="src">Source: 337 held-out requests without an instruction, each given one out-of-scope instruction.</p></section>

<section class="fig"><h2>Agreement between the two designs is a useful signal, not a fix</h2>
<p class="sub">Run both on the same request. Where they agree the decision is rarely wrong, but 8 to 20 % of decisions end up flagged, mostly through the decider's own errors.</p>__T6__
<p class="src">Source: results/cache, decisions of both designs on the same held-out and probe requests.</p></section>

<h3>What this changes in the plan</h3>
<ol class="plan">
<li><strong>Teach the translator two preferences first.</strong> If those instructions were read right, the fine-tuned translator would be at __FT_IND_FIX__ % on independent wording instead of __FT_IND__ %, and at __FT_OWN_FIX__ % on our wording. This is the largest single gain available, and it needs only training sentences we can generate.</li>
<li><strong>Add other languages to the training wording.</strong> In German, French and Italian the fine-tuned translator's main mistake is a wrong or missing link (__FT_LANG_LINK__ % of instructions).</li>
<li><strong>Test unseen instruction types properly before building on them.</strong> "Pass through a node" was obeyed __VIA_K__ of __VIA_N__ times (interval __VIA_LO__ to __VIA_HI__ %). The other types have one to five usable requests each.</li>
<li><strong>A hybrid needs a gate.</strong> Given a question or small talk, the decider rejected __TALK_REJ__ of __TALK_N__ requests. So the translator must separate "a routing instruction I have no rule for" from "not an instruction", and only the first may go to the decider.</li>
<li><strong>Keep the cross-check as a reported signal.</strong> It halves the error where both agree, at the price of many flags.</li>
</ol>
</main><div id="tip"></div></div>
<script>
const DATA=__DATA__;
const NS='http://www.w3.org/2000/svg',tip=document.getElementById('tip');
function el(tag,attrs,parent,text){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(text!=null)e.textContent=text;if(parent)parent.appendChild(e);return e}
function show(x,y,h){tip.innerHTML=h;tip.style.display='block';const r=tip.getBoundingClientRect();let px=x+14,py=y+14;if(px+r.width>innerWidth-8)px=x-r.width-14;if(py+r.height>innerHeight-8)py=y-r.height-14;tip.style.left=Math.max(8,px)+'px';tip.style.top=Math.max(8,py)+'px'}
function hover(n,h){n.setAttribute('tabindex','0');n.addEventListener('mousemove',e=>show(e.clientX,e.clientY,h));n.addEventListener('mouseleave',()=>tip.style.display='none');n.addEventListener('focus',()=>{const r=n.getBoundingClientRect();show(r.right,r.top,h)});n.addEventListener('blur',()=>tip.style.display='none')}
function legend(id,labels,vars){document.getElementById(id).innerHTML=labels.map((l,i)=>`<span><i style="background:var(${vars[i]})"></i>${l}</span>`).join('')}
function axis(svg,x,y0,y1,ticks,scale,unit,title,W){ticks.forEach(t=>{el('line',{x1:scale(t),x2:scale(t),y1:y0,y2:y1,style:'stroke:var(--grid)'},svg);el('text',{x:scale(t),y:y1+16,'text-anchor':'middle','font-size':12,style:'fill:var(--muted)'},svg,t+unit)});if(title)el('text',{x:W-16,y:y1+34,'text-anchor':'end','font-size':12,style:'fill:var(--muted)'},svg,title)}
const f1=v=>v.toFixed(1);
// 1. dot plot
(function(){const d=DATA.fig1,W=860,L=170,R=24,T=10,rh=32,H=T+rh*d.rows.length+44,svg=document.getElementById('c1');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
const s=v=>L+(v-84)/(100-84)*(W-L-R);axis(svg,0,T,T+rh*d.rows.length,[84,88,92,96,100],s,' %','decisions that respect the instruction',W);
legend('lg1',DATA.three,['--s1','--s2','--s3']);
d.rows.forEach((r,i)=>{const y=T+rh*i+rh/2,v=r.values.filter(x=>x!=null);el('text',{x:L-12,y:y+4,'text-anchor':'end','font-size':13,style:'fill:var(--ink)'},svg,r.label);
el('line',{x1:s(Math.min(...v)),x2:s(Math.max(...v)),y1:y,y2:y,style:'stroke:var(--axis);stroke-width:2'},svg);
r.values.forEach((x,j)=>{if(x!=null)el('circle',{cx:s(x),cy:y,r:6,style:`fill:var(--s${j+1});stroke:var(--surface);stroke-width:2`},svg)});
hover(el('rect',{x:0,y:y-rh/2,width:W,height:rh,fill:'transparent'},svg),`<b>${r.label}</b><br>`+r.values.map((x,j)=>`${DATA.three[j]}: ${x==null?'–':f1(x)+' %'}`).join('<br>'))})})();
// 2. strip plot
(function(){const d=DATA.fig2,W=860,L=170,R=24,T=8,rh=92,H=T+rh*d.rows.length+44,svg=document.getElementById('c2');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
const s=v=>L+v/42*(W-L-R);axis(svg,0,T,T+rh*d.rows.length,[0,10,20,30,40],s,' %','requests on which the intent was broken',W);
d.rows.forEach((r,i)=>{const cy=T+rh*i+rh/2;el('text',{x:L-12,y:cy+4,'text-anchor':'end','font-size':13,style:'fill:var(--ink)'},svg,r.label);
el('line',{x1:L,x2:W-R,y1:cy+rh/2-2,y2:cy+rh/2-2,style:'stroke:var(--grid)'},svg);
const none=r.dots.filter(p=>p.v===0);if(none.length)hover(el('circle',{cx:s(0),cy:cy,r:6.5,style:`fill:var(--surface);stroke:var(--s${i+1});stroke-width:2.5`},svg),`<b>${none.length} sentences</b> at exactly 0 %<br>no request with a broken intent`);
const placed=none.length?[{x:s(0),y:cy}]:[];r.dots.filter(p=>p.v>0).sort((a,b)=>a.x-b.x).forEach(p=>{const x=s(p.x);let k=0,y=cy;while(placed.some(q=>Math.hypot(q.x-x,q.y-y)<9.5)&&k<8){k++;y=cy+(k%2?1:-1)*Math.ceil(k/2)*9.5}placed.push({x,y});
hover(el('circle',{cx:x,cy:y,r:4,style:`fill:var(--s${i+1});stroke:var(--surface);stroke-width:1.5`},svg),`<b>${f1(p.x)} %</b> (${p.v} of ${p.n} requests)<br>${p.t.replace('{a}','A').replace('{b}','B')}${p.u?'<br><i>wording not seen in training</i>':''}`)});
const far=r.dots.filter(p=>p.x>20);if(far.length){const x=s(Math.min(...far.map(p=>p.x)));el('text',{x:x-10,y:cy-22,'text-anchor':'end','font-size':12.5,style:'fill:var(--ink2)'},svg,far.length+' sentences about "free slots", read as "fewest slots"')}
const zero=r.dots.filter(p=>p.v===0).length;el('text',{x:W-R,y:cy+rh/2-10,'text-anchor':'end','font-size':12.5,style:'fill:var(--ink2)'},svg,zero+' of '+r.dots.length+' sentences with no violation')})})();
// 3. stacked bars
(function(){const d=DATA.fig3,W=860,L=190,R=24,T=6,bh=18,gap=6,gh=26,svg=document.getElementById('c3');let y=T;const rows=[];d.groups.forEach(g=>{rows.push({head:g.label,y});y+=gh;g.bars.forEach(b=>{rows.push({bar:b,y});y+=bh+gap});y+=8});
const H=y+40;svg.setAttribute('viewBox',`0 0 ${W} ${H}`);const s=v=>L+v/26*(W-L-R);axis(svg,0,T,y,[0,5,10,15,20,25],s,' %','distinct instructions translated wrongly',W);
legend('lg3',DATA.mistakes,['--m1','--m2','--m3','--m4','--m5']);
rows.forEach(r=>{if(r.head){el('text',{x:L,y:r.y+17,'font-size':13,'font-weight':600,style:'fill:var(--ink)'},svg,r.head);return}
el('text',{x:L-12,y:r.y+bh/2+4,'text-anchor':'end','font-size':12.5,style:'fill:var(--ink2)'},svg,r.bar.label);let x=0;
r.bar.values.forEach((v,j)=>{if(v<=0)return;const x0=s(x),x1=s(x+v);hover(el('rect',{x:x0+1,y:r.y,width:Math.max(1,x1-x0-2),height:bh,rx:3,style:`fill:var(--m${j+1})`},svg),`<b>${DATA.mistakes[j]}</b><br>${r.bar.label}: ${f1(v)} % of ${r.bar.n} instructions`);x+=v});
el('text',{x:s(x)+8,y:r.y+bh/2+4,'font-size':12.5,style:'fill:var(--ink2)'},svg,f1(x)+' %')})})();
// 4. intervals
(function(){const d=DATA.fig4,W=860,L=260,R=120,T=10,rh=34,H=T+rh*d.rows.length+44,svg=document.getElementById('c4');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
const s=v=>L+v/100*(W-L-R);axis(svg,0,T,T+rh*d.rows.length,[0,25,50,75,100],s,' %','share of those requests on which the decider complied',W);
d.rows.forEach((r,i)=>{const y=T+rh*i+rh/2;el('text',{x:L-12,y:y+4,'text-anchor':'end','font-size':13,style:'fill:var(--ink)'},svg,r.label);
if(!r.n){el('text',{x:L+6,y:y+4,'font-size':12.5,style:'fill:var(--muted)'},svg,'no usable request');return}
el('line',{x1:s(r.lo),x2:s(r.hi),y1:y,y2:y,style:'stroke:var(--s1);stroke-width:2;opacity:.45'},svg);
hover(el('circle',{cx:s(100*r.k/r.n),cy:y,r:6,style:'fill:var(--s1);stroke:var(--surface);stroke-width:2'},svg),`<b>${r.label}</b><br>complied on ${r.k} of ${r.n} requests<br>95 % interval ${r.lo.toFixed(0)}–${r.hi.toFixed(0)} %`);
el('text',{x:W-R+12,y:y+4,'font-size':12.5,style:'fill:var(--ink2)'},svg,r.k+' of '+r.n)})})();
// 5. outcome bars
(function(){const d=DATA.fig5,W=860,L=250,R=70,T=6,bh=20,gap=9,H=T+(bh+gap)*d.rows.length+44,svg=document.getElementById('c5');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
const s=v=>L+v/100*(W-L-R);axis(svg,0,T,T+(bh+gap)*d.rows.length,[0,25,50,75,100],s,' %','requests that carried such an instruction',W);
legend('lg5',DATA.outcomes,['--o1','--o2','--o3']);
d.rows.forEach((r,i)=>{const y=T+(bh+gap)*i;el('text',{x:L-12,y:y+bh/2+4,'text-anchor':'end','font-size':13,style:'fill:var(--ink)'},svg,r.label);let x=0;
r.values.forEach((v,j)=>{if(v<=0)return;const x0=s(x),x1=s(x+v);hover(el('rect',{x:x0+1,y,width:Math.max(1,x1-x0-2),height:bh,rx:3,style:`fill:var(--o${j+1})`},svg),`<b>${r.label}</b><br>${DATA.outcomes[j]}: ${v.toFixed(0)} % of ${r.n} requests`);x+=v});
el('text',{x:W-R+10,y:y+bh/2+4,'font-size':12.5,style:'fill:var(--ink2)'},svg,'n = '+r.n)})})();
</script></body></html>
"""

fills = {
    "__FT_SENT__": sent["Translator, fine-tuned"]["with_violations"],
    "__DEC_SENT__": sent["Decider, fine-tuned"]["with_violations"],
    "__VIA_K__": via["binding and complies"], "__VIA_N__": via["binding"],
    "__VIA_LO__": f"{via['binding_interval_95'][0]:.0f}", "__VIA_HI__": f"{via['binding_interval_95'][1]:.0f}",
    "__LEFT__": f"{budget['credit'] - spent:.2f}", "__CREDIT__": f"{budget['credit']:.0f}",
    "__PCT__": f"{100 * spent / budget['credit']:.0f}",
    "__FT_IND__": num(ft["Independent wording"]["percent"]["correct"]),
    "__FT_IND_FIX__": num(ft["Independent wording"]["correct_if_two_preference_instructions_were_right"]),
    "__FT_OWN_FIX__": num(ft["Our wording"]["correct_if_two_preference_instructions_were_right"], 0),
    "__FT_LANG_LINK__": num(ft["German, French, Italian"]["percent"].get("Link wrong or missing", 0)),
    "__TALK_REJ__": talk.get("rejects the request", 0), "__TALK_N__": talk["requests"],
    "__T1__": t1, "__T2__": t2, "__T3__": t3, "__T4__": t4, "__T5__": t5, "__T6__": t6, "__DATA__": DATA,
}  # fmt: skip
page = PAGE
for key, value in fills.items():
    assert key in page, key
    page = page.replace(key, str(value))
out = ROOT / "docs" / "analysis" / "next_steps.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8", newline="\n")
print(f"wrote {out} ({len(page) // 1024} KB)")
