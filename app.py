import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
import json
import os
import re

st.set_page_config(
    page_title="Horse Racing Model",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.block-container{padding-top:1rem;padding-bottom:1rem}
.stTabs [data-baseweb="tab"]{font-size:15px;font-weight:500}
.bet-box{padding:16px;border-radius:10px;margin:10px 0;font-size:16px;font-weight:600;text-align:center}
.win-bet{background:#d4edda;border:2px solid #28a745;color:#155724}
.ew-bet{background:#cce5ff;border:2px solid #0056b3;color:#004085}
.no-bet{background:#f8d7da;border:2px solid #721c24;color:#721c24}
.dutch-bet{background:#fff3cd;border:2px solid #856404;color:#856404}
.rank-row{padding:10px 14px;margin:4px 0;border-radius:6px;display:flex;justify-content:space-between;align-items:center;font-size:14px}
.r1{background:#fff9e6;border-left:4px solid #f4c430}
.r2{background:#f0f8ff;border-left:4px solid #4a90d9}
.r3{background:#f0fff0;border-left:4px solid #28a745}
.rn{background:#f8f9fa;border-left:4px solid #dee2e6}
.parsed-preview{background:#f0f8ff;border-radius:6px;padding:8px 12px;font-size:12px;margin:4px 0;color:#333}
</style>
""", unsafe_allow_html=True)

LOG_FILE = "results_log.json"

GOING_MAP = {
    "Firm":1,"Hard":1,"Fast":2,"Good":3,"Good to Firm":4,
    "Good to Soft":5,"Good to Yielding":5,"Soft":6,"Yielding":6,
    "Soft to Heavy":7,"Very Soft":7,"Heavy":8,
    "Standard":9,"Standard to Slow":10,"Slow":11
}

GOING_CODES = {
    "St":"Standard","Std":"Standard","St/Slw":"Standard to Slow",
    "Std/Slw":"Standard to Slow","Slw":"Slow","Slow":"Slow",
    "Fm":"Firm","Hrd":"Hard","Gd":"Good","Gd/Fm":"Good to Firm",
    "GF":"Good to Firm","Gd/Sft":"Good to Soft","GS":"Good to Soft",
    "Y":"Good to Soft","Sft":"Soft","Sft/Hy":"Soft to Heavy",
    "Hy":"Heavy","Yld":"Yielding","Gd/Yld":"Good to Yielding","VS":"Very Soft"
}

AW_COURSES = {"Lin","Kem","Dun","Wol","Ncs","Sou"}

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE,"r") as f:
            return json.load(f)
    return []

def save_log(log):
    with open(LOG_FILE,"w") as f:
        json.dump(log, f, indent=2, default=str)

def parse_rp_string(rp_str):
    result = {"date":None,"surface":None,"ground":None,"distance":None,"class_val":None}
    if not rp_str or not rp_str.strip():
        return result
    rp_str = rp_str.strip()
    tokens = rp_str.split()
    if not tokens:
        return result
    # Date
    try:
        raw = tokens[0]
        has2 = raw[:2].isdigit()
        dy = int(raw[:2]) if has2 else int(raw[:1])
        mo_str = raw[2:5] if has2 else raw[1:4]
        yr_str = raw[5:7] if has2 else raw[4:6]
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        mo = months.index(mo_str)+1
        result["date"] = date(2000+int(yr_str), mo, dy)
    except:
        pass
    # Surface
    if len(tokens) > 1:
        course = tokens[1]
        result["surface"] = "Polytrack" if course in {"Lin","Kem","Dun"} else \
                            "Tapeta" if course in {"Wol","Ncs","Sou"} else "Turf"
    # Distance — handle "8", "8½", "1m2f", "5f" etc
    if len(tokens) > 2:
        raw_dist = tokens[2]
        # Replace unicode fractions
        raw_dist = raw_dist.replace("½", ".5").replace("¼", ".25")
        m=0; f=0
        try:
            if "m" in raw_dist:
                m_part = raw_dist[:raw_dist.index("m")]
                m = float(m_part) if m_part else 0
                after = raw_dist[raw_dist.index("m")+1:].strip()
                if "f" in after:
                    fp = after[:after.index("f")].strip()
                    f = float(fp) if fp else 0
                result["distance"] = m + (f/8)
            elif "f" in raw_dist:
                fp = raw_dist[:raw_dist.index("f")].strip()
                f = float(fp) if fp else 0
                result["distance"] = f/8
            else:
                # Just a number — treat as furlongs
                f = float(raw_dist)
                result["distance"] = f/8
        except:
            pass
    # Ground
    if len(tokens) > 3:
        result["ground"] = GOING_CODES.get(tokens[3], tokens[3])
    # Class
    full = rp_str
    last = tokens[-1]
    prize = 0
    try: prize = float(last.replace("K",""))
    except: pass
    if "G1" in full: result["class_val"]=1
    elif "G2" in full: result["class_val"]=1
    elif "G3" in full: result["class_val"]=1
    elif "1L" in full: result["class_val"]=1
    elif "2L" in full: result["class_val"]=2
    elif "3L" in full: result["class_val"]=3
    elif "4L" in full: result["class_val"]=4
    elif prize>=50: result["class_val"]=1
    elif prize>=15: result["class_val"]=2
    elif prize>=10: result["class_val"]=3
    elif prize>=6: result["class_val"]=4
    elif prize>=3: result["class_val"]=5
    else: result["class_val"]=6
    return result

def parse_position_string(pos_str):
    result = {"position":None,"runners":None,"beaten":None}
    if not pos_str or not pos_str.strip():
        return result
    pos_str = pos_str.strip()
    for nf in ["PU","UR","BD","RO"]:
        if nf in pos_str.upper():
            result["position"]=99
            return result
    # position/runners (runners = between / and ()
    try:
        slash = pos_str.index("/")
        result["position"] = int(pos_str[:slash])
        bracket = pos_str.index("(")
        result["runners"] = int(pos_str[slash+1:bracket].strip())
    except:
        pass
    # beaten distance
    try:
        open_b = pos_str.index("(")
        sub = pos_str[open_b+1:]
        l_idx = sub.index("L")
        raw = sub[:l_idx].strip()
        raw = raw.replace("½",".5").replace("¼",".25")
        beat_map = {"sh hd":0.1,"sh":0.1,"hd":0.2,"nk":0.3}
        if raw.lower() in beat_map:
            result["beaten"] = beat_map[raw.lower()]
        else:
            nm = re.match(r'(\d+\.?\d*)', raw)
            result["beaten"] = float(nm.group(1)) if nm else 0.0
    except:
        pass
    return result

def parse_bulk_paste(text):
    """
    Parse Google Sheets paste in format:
    Horse Name  |  RP String  |  RP String (dup)  |  WGT  |  Position String  |  SP  |  Jockey  |  MR  |  OR  |  TS  |  RPR
    Horse name only appears on first of the 3 rows. Blank on rows 2 and 3.
    """
    horses = []
    if not text or not text.strip():
        return horses

    lines = [l for l in text.strip().split("\n") if l.strip()]
    current_horse = None
    current_runs = []
    horse_number = 0

    def safe_int(v):
        try:
            v = str(v).strip()
            return int(v) if v and v != "-" else None
        except:
            return None

    for line in lines:
        cols = line.split("\t")
        while len(cols) < 11:
            cols.append("")
        cols = [c.strip() for c in cols]

        first_col = cols[0]

        # Detect if this is a new horse row — first col has text that isn't a date
        # Dates start with digits (e.g. 11Apr26), horse names start with letters
        # and don't look like RP strings
        def is_horse_name(val):
            if not val: return False
            # RP strings start with date like "11Apr26" — digits first
            if re.match(r'^\d{1,2}[A-Z][a-z]{2}\d{2}', val): return False
            # If it contains letters and doesn't look like a date, it's a name
            return bool(re.match(r'^[A-Za-z]', val))

        if is_horse_name(first_col):
            # Save previous horse
            if current_horse is not None:
                current_horse["runs"] = current_runs[:3]
                horses.append(current_horse)

            horse_number += 1
            # Columns: Name | RP String | RP String dup | WGT | Position | SP | Jockey | MR | OR | TS | RPR
            rp_str  = cols[1] if len(cols) > 1 else ""
            wgt     = cols[3] if len(cols) > 3 else ""
            pos_str = cols[4] if len(cols) > 4 else ""
            ts_raw  = cols[9]  if len(cols) > 9  else ""
            rpr_raw = cols[10] if len(cols) > 10 else ""

            parsed_rp  = parse_rp_string(rp_str)
            parsed_pos = parse_position_string(pos_str)

            run = {
                "date": parsed_rp.get("date"),
                "surface": parsed_rp.get("surface"),
                "ground": parsed_rp.get("ground"),
                "distance": parsed_rp.get("distance"),
                "class_val": parsed_rp.get("class_val"),
                "weight": wgt,
                "position": parsed_pos.get("position"),
                "runners": parsed_pos.get("runners"),
                "beaten": parsed_pos.get("beaten"),
                "ts": safe_int(ts_raw),
                "rpr": safe_int(rpr_raw),
            }

            current_horse = {
                "number": horse_number,
                "name": first_col,
                "or_rating": None,
                "odds": "",
                "stall": None,
                "weight": wgt,
            }
            current_runs = [run]

        else:
            # Continuation row (race 2 or 3) — first col is blank
            if current_horse is None:
                continue

            # Columns: blank | RP String | RP String dup | WGT | Position | SP | Jockey | MR | OR | TS | RPR
            rp_str  = cols[1] if len(cols) > 1 else ""
            wgt     = cols[3] if len(cols) > 3 else ""
            pos_str = cols[4] if len(cols) > 4 else ""
            ts_raw  = cols[9]  if len(cols) > 9  else ""
            rpr_raw = cols[10] if len(cols) > 10 else ""

            parsed_rp  = parse_rp_string(rp_str)
            parsed_pos = parse_position_string(pos_str)

            run = {
                "date": parsed_rp.get("date"),
                "surface": parsed_rp.get("surface"),
                "ground": parsed_rp.get("ground"),
                "distance": parsed_rp.get("distance"),
                "class_val": parsed_rp.get("class_val"),
                "weight": wgt,
                "position": parsed_pos.get("position"),
                "runners": parsed_pos.get("runners"),
                "beaten": parsed_pos.get("beaten"),
                "ts": safe_int(ts_raw),
                "rpr": safe_int(rpr_raw),
            }
            current_runs.append(run)

    # Add last horse
    if current_horse is not None:
        current_horse["runs"] = current_runs[:3]
        horses.append(current_horse)

    return horses

def weight_to_lbs(weight_str):
    if not weight_str or "-" not in str(weight_str):
        return None
    try:
        parts = str(weight_str).split("-")
        return int(parts[0])*14+int(parts[1])
    except:
        return None

def odds_to_decimal(odds_str):
    if not odds_str: return None
    x = str(odds_str).upper().strip().replace(" ","")
    # Remove F suffix (favourite marker)
    x = x.rstrip("F")
    if x in ["EVS","EVENS"]: return 2.0
    if "/" in x:
        try:
            p = x.split("/")
            return 1+float(p[0])/float(p[1])
        except: return None
    try:
        v = float(x)
        return v if v>1 else None
    except: return None

def calc_ability(or_val, all_ors):
    valid = [o for o in all_ors if o and o>0]
    if not valid or not or_val or or_val==0: return 1.0
    mn,mx = min(valid),max(valid)
    if mx==mn: return 3.0
    return min(5,max(1,1+4*((or_val-mn)/(mx-mn+0.001))))

def calc_form_run(pos, runners, ts, rpr):
    if pos is None or runners is None: pos_score=1.0
    elif runners<=1: pos_score=5.0
    else: pos_score=min(5,max(1,round(1+4*(1-((pos-1)/(runners-1))),1)))
    ts_score = 1.0 if not ts else round(min(5,ts/20),1)
    rpr_score = 1.0 if not rpr else round(min(5,rpr/20),1)
    return (pos_score*0.4)+(ts_score*0.2)+(rpr_score*0.4)

def calc_form(runs):
    weights=[0.5,0.3,0.2]
    total=0
    for i,run in enumerate(runs[:3]):
        score=calc_form_run(run.get("position"),run.get("runners"),run.get("ts"),run.get("rpr"))
        total+=score*weights[i]
    return total

def calc_suit_run(surface,distance,ground,ts,td,tg):
    if not surface or distance is None or not ground: return 1.0
    g_today=GOING_MAP.get(tg,5)
    g_run=GOING_MAP.get(ground,5)
    dist_diff=abs(distance-td)
    going_diff=abs(g_run-g_today)
    if surface==ts and dist_diff<=0.125 and going_diff<=1: return 5.0
    turf_sw=(ts=="Turf" and surface!="Turf") or (ts!="Turf" and surface=="Turf")
    if turf_sw: return max(1,2-dist_diff*4)
    aw_compat=ts in ["Tapeta","Polytrack"] and surface in ["Tapeta","Polytrack"]
    surf_score=5 if surface==ts else (3 if aw_compat else 1)
    return 0.5*max(1,5-dist_diff*8)+0.3*surf_score+0.2*max(1,5-going_diff)

def calc_suitability(runs,today_surface,today_distance,today_ground):
    weights=[0.5,0.3,0.2]
    total=0
    for i,run in enumerate(runs[:3]):
        s=calc_suit_run(run.get("surface"),run.get("distance"),run.get("ground"),
                        today_surface,today_distance,today_ground)
        total+=s*weights[i]
    return total

def calc_fitness(last_date):
    if not last_date: return 1
    if isinstance(last_date,str):
        try: last_date=datetime.strptime(last_date,"%Y-%m-%d").date()
        except: return 1
    days=(date.today()-last_date).days
    if days<=30: return 5
    if days<=60: return 4
    if days<=120: return 3
    if days<=180: return 2
    return 1

def calc_class(runs,today_class):
    scores=[]
    for run in runs[:3]:
        rc=run.get("class_val")
        if rc is None: scores.append(2)
        elif rc<today_class: scores.append(5)
        elif rc==today_class: scores.append(4)
        elif rc==today_class+1: scores.append(3)
        else: scores.append(2)
    return sum(scores)/len(scores) if scores else 2

def calc_weight_adj(wt_lbs,run_weights):
    valid=[w for w in run_weights if w]
    if not valid or not wt_lbs: return 3.0
    avg=sum(valid)/len(valid)
    return max(1,min(5,5-abs(wt_lbs-avg)/5))

def calc_score(ability,form,suit,fitness,class_sc,weight_adj,dist_band):
    if dist_band=="SPRINT":
        return ability*0.32+form*0.25+suit*0.32+fitness*0.08+class_sc*0.03+weight_adj*0
    elif dist_band=="MIDDLE":
        return ability*0.34+form*0.22+suit*0.30+fitness*0.08+class_sc*0.03+weight_adj*0.03
    else:
        return ability*0.30+form*0.20+suit*0.36+fitness*0.06+class_sc*0.03+weight_adj*0.05

def dist_to_band(d):
    if d is None: return "MIDDLE"
    if d<=0.75: return "SPRINT"
    if d<=1.3: return "MIDDLE"
    return "STAYING"

def parse_distance_input(d):
    if not d: return None
    d=d.strip().replace("½","1/2").replace("¼","1/4")
    m=0; f=0
    try:
        if "m" in d:
            m=float(d[:d.index("m")]) if d[:d.index("m")] else 0
            after=d[d.index("m")+1:].strip()
        else: after=d
        if "f" in after:
            fp=after[:after.index("f")].strip()
            if "1/2" in fp: f=float(fp.replace("1/2","").strip() or "0")+0.5
            elif "1/4" in fp: f=float(fp.replace("1/4","").strip() or "0")+0.25
            else: f=float(fp) if fp else 0
    except: pass
    return m+(f/8) if m>0 else (f/8 if f>0 else None)

def run_model(horses,race):
    td=race["distance"]
    ts_today=race["surface"]
    tg=race["ground"]
    tc=race["class_val"]
    dist_band=dist_to_band(td)
    all_ors=[h.get("or_rating") for h in horses]
    results=[]
    for h in horses:
        runs=h.get("runs",[{},{},{}])
        while len(runs)<3: runs.append({})
        ability=calc_ability(h.get("or_rating"),all_ors)
        form=calc_form(runs)
        suit=calc_suitability(runs,ts_today,td,tg)
        fitness=calc_fitness(runs[0].get("date") if runs else None)
        class_sc=calc_class(runs,tc)
        wt=weight_to_lbs(h.get("weight"))
        rw=[weight_to_lbs(r.get("weight")) for r in runs]
        wadj=calc_weight_adj(wt,rw)
        score=calc_score(ability,form,suit,fitness,class_sc,wadj,dist_band)
        odds_dec=odds_to_decimal(h.get("odds"))
        impl_prob=(1/odds_dec) if odds_dec and odds_dec>0 else None
        results.append({
            "name":h["name"] or f"Horse {h.get('number','')}",
            "ability":round(ability,2),"form":round(form,2),
            "suit":round(suit,2),"fitness":fitness,
            "class_sc":round(class_sc,2),"score":round(score,3),
            "odds_dec":odds_dec,"impl_prob":impl_prob,
        })
    total=sum(r["score"] for r in results)
    for r in results:
        r["prob"]=r["score"]/total if total>0 else 0
        r["edge"]=(r["prob"]-r["impl_prob"]) if r["impl_prob"] else None
    sorted_probs=sorted([r["prob"] for r in results],reverse=True)
    for r in results:
        r["rank"]=sorted_probs.index(r["prob"])+1
    results.sort(key=lambda x:x["rank"])
    return results,dist_band

def get_bet_strategy(results,dist_band):
    if not results: return "NO BET",None
    runners=len(results)
    top_prob=results[0]["prob"]
    second_prob=results[1]["prob"] if len(results)>1 else 0
    third_prob=results[2]["prob"] if len(results)>2 else 0
    gap=top_prob-second_prob
    top2=top_prob+second_prob
    top2_thresh=0.30 if runners<=7 else (0.25 if runners<=10 else 0.22)
    gap_thresh=0.005
    max_edge=max((r["edge"] for r in results if r["edge"] is not None),default=0)
    r1=results[0]; r2=results[1] if len(results)>1 else None
    r1_edge=r1.get("edge") or 0
    r2_edge=r2.get("edge") or 0 if r2 else 0
    selection=r2 if (r2 and r2_edge-r1_edge>=0.03) else r1
    sel_edge=selection.get("edge") or 0
    force_bet=max_edge>=0.12 and top2>=0.38 and top_prob>=0.22
    if force_bet: return "WIN BET",selection
    if sel_edge<0: return "NO BET",None
    if top_prob<0.10: return "NO BET",None
    if gap<0.03 and top_prob<0.22: return "NO BET",None
    if max_edge<0.07: return "NO BET",None
    if dist_band=="SPRINT" and gap<gap_thresh: return "NO BET",None
    if top_prob<0.12 or top2<top2_thresh: return "NO BET",None
    if gap<gap_thresh/2 and top2>=0.30 and (top_prob-third_prob)>gap_thresh:
        return "DUTCH TOP 2",None
    if gap<gap_thresh and top2>=top2_thresh:
        odds_sel=selection.get("odds_dec") or 0
        return ("E/W BET" if odds_sel>=5 else "WIN BET"),selection
    if gap>=gap_thresh*2 and top_prob>=0.16 and top2>=top2_thresh:
        return "WIN BET",selection
    return "NO BET",None

# ═══════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════
st.markdown("## 🏇 Horse Racing Model")
tab1,tab2,tab3=st.tabs(["Race Entry","Results Log","Analysis"])

with tab1:
    # ── RACE SETUP ──────────────────────────────────────
    with st.expander("Race Setup", expanded=True):
        c1,c2,c3,c4=st.columns(4)
        with c1:
            race_date=st.date_input("Date",value=date.today())
            course=st.text_input("Course",placeholder="e.g. Newmarket")
        with c2:
            race_time=st.text_input("Race Time",placeholder="e.g. 14:30")
            distance_input=st.text_input("Distance",placeholder="e.g. 6f or 1m2f")
        with c3:
            surface=st.selectbox("Surface",["Turf","Polytrack","Tapeta"])
            ground=st.selectbox("Ground",list(GOING_MAP.keys()))
        with c4:
            race_class=st.number_input("Class (1-6)",min_value=1,max_value=6,value=4)
            ew_places=st.number_input("E/W Places",min_value=2,max_value=4,value=3)

    distance_val=parse_distance_input(distance_input)
    dist_band=dist_to_band(distance_val)
    race={
        "date":str(race_date),"course":course,"time":race_time,
        "distance":distance_val,"surface":surface,"ground":ground,
        "class_val":race_class,"ew_places":ew_places,
    }

    # ── BULK PASTE ───────────────────────────────────────
    st.markdown("---")
    st.markdown("### Paste Race Data")
    st.caption("Copy the full table from Google Sheets and paste it below. The app will extract all horses and their form automatically.")

    paste_text=st.text_area(
        "Paste here",
        height=200,
        placeholder="Paste your Google Sheets data here (all horses at once)...",
        label_visibility="collapsed"
    )

    parsed_horses=[]
    if paste_text.strip():
        parsed_horses=parse_bulk_paste(paste_text)
        if parsed_horses:
            st.success(f"Detected {len(parsed_horses)} horses — now add names, OR, odds and stall below")
        else:
            st.warning("Could not parse the pasted data. Make sure it's copied directly from Google Sheets.")

    # ── MANUAL FIELDS PER HORSE ──────────────────────────
    if parsed_horses:
        st.markdown("### Horse Details")
        st.caption("Name, OR, today's odds and stall for each horse")

        horse_inputs=[]
        for idx,h in enumerate(parsed_horses):
            with st.container():
                col1,col2,col3,col4=st.columns([3,1,2,1])
                with col1:
                    name=st.text_input(f"Name",key=f"name_{idx}",
                                       placeholder=f"Horse {h['number']}",
                                       label_visibility="visible" if idx==0 else "collapsed")
                with col2:
                    or_rating=st.number_input(f"OR",key=f"or_{idx}",
                                              min_value=0,max_value=150,value=0,
                                              label_visibility="visible" if idx==0 else "collapsed")
                with col3:
                    odds=st.text_input(f"Today's Odds",key=f"odds_{idx}",
                                       placeholder="e.g. 5/1",
                                       label_visibility="visible" if idx==0 else "collapsed")
                with col4:
                    stall=st.number_input(f"Stall",key=f"stall_{idx}",
                                          min_value=0,max_value=30,value=0,
                                          label_visibility="visible" if idx==0 else "collapsed")

                # Show parsed form preview
                runs=h.get("runs",[])
                preview_parts=[]
                for i,run in enumerate(runs[:3]):
                    bits=[]
                    if run.get("date"): bits.append(str(run["date"]))
                    if run.get("surface"): bits.append(run["surface"])
                    if run.get("ground"): bits.append(run["ground"])
                    if run.get("distance"): bits.append(f"{run['distance']:.2f}m")
                    if run.get("position") and run.get("runners"):
                        bits.append(f"{run['position']}/{run['runners']}")
                    if run.get("ts"): bits.append(f"TS:{run['ts']}")
                    if run.get("rpr"): bits.append(f"RPR:{run['rpr']}")
                    if bits:
                        preview_parts.append(f"R{i+1}: "+" | ".join(bits))

                if preview_parts:
                    st.markdown(
                        f'<div class="parsed-preview">{"&nbsp;&nbsp;&nbsp;".join(preview_parts)}</div>',
                        unsafe_allow_html=True
                    )

                horse_inputs.append({
                    "number":h["number"],"name":name,"or_rating":or_rating if or_rating>0 else None,
                    "odds":odds,"stall":stall,"weight":h.get("weight",""),
                    "runs":h.get("runs",[]),
                })

        st.markdown("---")

        if st.button("🏇 Run Model",type="primary",use_container_width=True):
            valid=[h for h in horse_inputs if h["name"].strip()]
            if len(valid)<2:
                st.error("Add at least 2 horse names to run the model.")
            elif not distance_val:
                st.error("Enter a valid distance in Race Setup (e.g. 6f, 1m2f)")
            else:
                results,db=run_model(valid,race)
                bet_strategy,selection=get_bet_strategy(results,db)

                runners=len(results)
                top_prob=results[0]["prob"]
                second_prob=results[1]["prob"] if len(results)>1 else 0
                third_prob=results[2]["prob"] if len(results)>2 else 0
                gap=top_prob-second_prob
                top2=top_prob+second_prob
                max_edge=max((r["edge"] for r in results if r["edge"] is not None),default=0)
                race_type="STRONG FAV" if top_prob>=0.28 else ("SOLID FAV" if top_prob>=0.22 else "OPEN RACE")

                # Metrics
                st.markdown("## Model Output")
                m1,m2,m3,m4,m5,m6=st.columns(6)
                m1.metric("Band",db)
                m2.metric("Runners",runners)
                m3.metric("Top Prob",f"{top_prob:.1%}")
                m4.metric("Gap 1-2",f"{gap:.2%}")
                m5.metric("Top 2 %",f"{top2:.1%}")
                m6.metric("Max Edge",f"{max_edge:.1%}")

                m7,m8,m9=st.columns(3)
                m7.metric("Race Type",race_type)
                m8.metric("Value OK?","YES" if max_edge>=0.07 else "NO")
                m9.metric("Bet?","YES" if bet_strategy!="NO BET" else "NO")

                # Bet box
                if bet_strategy=="WIN BET":
                    sel_name=selection["name"] if selection else ""
                    st.markdown(f'<div class="bet-box win-bet">🎯 WIN BET &nbsp;—&nbsp; {sel_name} &nbsp;|&nbsp; Stake: 1pt WIN</div>',unsafe_allow_html=True)
                elif bet_strategy=="E/W BET":
                    sel_name=selection["name"] if selection else ""
                    st.markdown(f'<div class="bet-box ew-bet">🆗 E/W BET &nbsp;—&nbsp; {sel_name} &nbsp;|&nbsp; Stake: 0.5pt E/W</div>',unsafe_allow_html=True)
                elif bet_strategy=="DUTCH TOP 2":
                    st.markdown(f'<div class="bet-box dutch-bet">⚖️ DUTCH TOP 2 &nbsp;—&nbsp; {results[0]["name"]} / {results[1]["name"]} &nbsp;|&nbsp; Stake: 0.5pt each</div>',unsafe_allow_html=True)
                else:
                    st.markdown('<div class="bet-box no-bet">❌ NO BET — Race too open or insufficient edge</div>',unsafe_allow_html=True)

                # Rankings
                st.markdown("### Field Rankings")
                for r in results:
                    rc="r1" if r["rank"]==1 else ("r2" if r["rank"]==2 else ("r3" if r["rank"]==3 else "rn"))
                    edge_str=f"{r['edge']:.1%}" if r["edge"] is not None else "—"
                    edge_col="#28a745" if (r["edge"] or 0)>0 else "#dc3545"
                    odds_str=f"{r['odds_dec']:.2f}" if r["odds_dec"] else "—"
                    st.markdown(f"""
                    <div class="rank-row {rc}">
                        <span><strong>#{r['rank']}</strong>&nbsp;&nbsp;{r['name']}</span>
                        <span style="color:#555;font-size:13px">
                            Prob: <strong>{r['prob']:.1%}</strong>&nbsp;|&nbsp;
                            Edge: <strong style="color:{edge_col}">{edge_str}</strong>&nbsp;|&nbsp;
                            Odds: {odds_str}&nbsp;|&nbsp;
                            Ability: {r['ability']}&nbsp;|&nbsp;
                            Form: {r['form']}&nbsp;|&nbsp;
                            Suit: {r['suit']}
                        </span>
                    </div>
                    """,unsafe_allow_html=True)

                # Store for result entry
                st.session_state["last_result"]={
                    "race":race,"results":results,"bet_strategy":bet_strategy,
                    "selection":selection["name"] if selection else None,
                    "dist_band":db,"race_type":race_type,
                    "top_prob":top_prob,"second_prob":second_prob,
                    "third_prob":third_prob,"gap":gap,"top2":top2,"max_edge":max_edge,
                }

    # ── POST RACE RESULT ─────────────────────────────────
    if "last_result" in st.session_state:
        st.markdown("---")
        st.markdown("### Post-Race Result")
        pr1,pr2,pr3=st.columns(3)
        with pr1:
            winner=st.text_input("Winner")
            second=st.text_input("2nd Place")
        with pr2:
            third=st.text_input("3rd Place")
            sp=st.text_input("SP of Selection",placeholder="e.g. 5/1")
        with pr3:
            outcome=st.selectbox("Outcome",["—","Won","Placed","Lost","No Bet"])
            notes=st.text_input("Notes",placeholder="Optional")

        if st.button("💾 Save to Results Log",type="secondary",use_container_width=True):
            lr=st.session_state["last_result"]
            results=lr["results"]
            t3=results[2] if len(results)>2 else {}
            winner_rank=next((r["rank"] for r in results if r["name"].lower()==winner.lower()),None)
            log_entry={
                "date":lr["race"]["date"],"course":lr["race"]["course"],
                "time":lr["race"]["time"],"dist_band":lr["dist_band"],
                "runners":len(results),"top_prob":round(lr["top_prob"],4),
                "second_prob":round(lr["second_prob"],4),
                "third_prob":round(t3.get("prob",0),4),
                "gap":round(lr["gap"],4),"top2_pct":round(lr["top2"],4),
                "race_type":lr["race_type"],"bet_strategy":lr["bet_strategy"],
                "bet_yn":"Y" if lr["bet_strategy"]!="NO BET" else "N",
                "selection":lr["selection"],"sel_odds":sp,
                "model_prob":round(next((r["prob"] for r in results if r["name"]==lr["selection"]),0),4),
                "impl_prob":round(next((r.get("impl_prob") or 0 for r in results if r["name"]==lr["selection"]),0),4),
                "true_edge":round(next((r.get("edge") or 0 for r in results if r["name"]==lr["selection"]),0),4),
                "max_edge":round(lr["max_edge"],4),
                "winner":winner,"winner_rank":winner_rank,
                "in_top2":"Y" if winner_rank and winner_rank<=2 else "N",
                "in_top3":"Y" if winner_rank and winner_rank<=3 else "N",
                "bet_type":lr["bet_strategy"],"result":outcome,"pl":0,"notes":notes,
            }
            log=load_log()
            log.append(log_entry)
            save_log(log)
            del st.session_state["last_result"]
            st.success("Saved to results log!")
            st.rerun()

# ═══════════════════════════════════════════════════════
# TAB 2 — RESULTS LOG
# ═══════════════════════════════════════════════════════
with tab2:
    log=load_log()
    if not log:
        st.info("No results logged yet.")
    else:
        df=pd.DataFrame(log)
        st.markdown(f"### Results Log — {len(df)} races")
        bets=df[df["bet_yn"]=="Y"]
        wins=df[df["result"]=="Won"]
        s1,s2,s3,s4,s5,s6=st.columns(6)
        s1.metric("Total Races",len(df))
        s2.metric("Bets Placed",len(bets))
        s3.metric("Winners",len(wins))
        s4.metric("Strike Rate",f"{len(wins)/len(bets):.0%}" if len(bets)>0 else "—")
        avg_rank=df["winner_rank"].dropna().mean()
        s5.metric("Avg Winner Rank",f"{avg_rank:.1f}" if not pd.isna(avg_rank) else "—")
        top3=(df["in_top3"]=="Y").mean()
        s6.metric("Top 3 Rate",f"{top3:.0%}")
        display_cols=["date","course","time","dist_band","runners","bet_yn",
                      "selection","bet_strategy","winner","winner_rank",
                      "in_top2","in_top3","result","top_prob","max_edge"]
        available=[c for c in display_cols if c in df.columns]
        st.dataframe(df[available],use_container_width=True,height=400)
        csv=df.to_csv(index=False)
        st.download_button("📥 Download Full Log (CSV)",data=csv,
                           file_name=f"racing_log_{date.today()}.csv",
                           mime="text/csv",use_container_width=True)

# ═══════════════════════════════════════════════════════
# TAB 3 — ANALYSIS
# ═══════════════════════════════════════════════════════
with tab3:
    log=load_log()
    if not log:
        st.info("No data yet.")
    else:
        df=pd.DataFrame(log)
        st.markdown("### Model Performance")
        c1,c2=st.columns(2)
        with c1:
            st.markdown("**By distance band**")
            if "dist_band" in df.columns:
                by_band=df.groupby("dist_band").agg(
                    races=("date","count"),
                    top2=("in_top2",lambda x:(x=="Y").mean()),
                    top3=("in_top3",lambda x:(x=="Y").mean()),
                    avg_rank=("winner_rank","mean")
                ).round(3)
                st.dataframe(by_band,use_container_width=True)
        with c2:
            st.markdown("**Bet vs No Bet**")
            if "bet_yn" in df.columns:
                by_bet=df.groupby("bet_yn").agg(
                    races=("date","count"),
                    top2=("in_top2",lambda x:(x=="Y").mean()),
                    top3=("in_top3",lambda x:(x=="Y").mean()),
                    avg_rank=("winner_rank","mean")
                ).round(3)
                st.dataframe(by_bet,use_container_width=True)
        st.markdown("**Winner rank distribution**")
        if "winner_rank" in df.columns:
            rc=df["winner_rank"].value_counts().sort_index()
            rd=pd.DataFrame({"rank":rc.index,"count":rc.values})
            rd["pct"]=(rd["count"]/len(df)*100).round(1)
            st.dataframe(rd,use_container_width=True)

