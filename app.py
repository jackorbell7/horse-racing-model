import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
import json
import os
import re
import math

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
div[data-testid="metric-container"]{background:#f8f9fa;border-radius:8px;padding:12px;border:1px solid #e9ecef}
.bet-box{padding:16px;border-radius:10px;margin:8px 0;font-size:15px;font-weight:500}
.win-bet{background:#d4edda;border:1px solid #28a745;color:#155724}
.ew-bet{background:#cce5ff;border:1px solid #004085;color:#004085}
.no-bet{background:#f8d7da;border:1px solid #721c24;color:#721c24}
.dutch-bet{background:#fff3cd;border:1px solid #856404;color:#856404}
.horse-rank-1{background:#fff9e6;border-left:4px solid #f4c430}
.horse-rank-2{background:#f0f8ff;border-left:4px solid #4a90d9}
.horse-rank-3{background:#f0fff0;border-left:4px solid #28a745}
</style>
""", unsafe_allow_html=True)

LOG_FILE = "results_log.json"
GOING_MAP = {
    "Firm": 1, "Hard": 1, "Fast": 2, "Good": 3,
    "Good to Firm": 4, "Good to Soft": 5, "Good to Yielding": 5,
    "Soft": 6, "Yielding": 6, "Soft to Heavy": 7,
    "Very Soft": 7, "Heavy": 8, "Standard": 9,
    "Standard to Slow": 10, "Slow": 11
}

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    return []

def save_log(log):
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, default=str)

def parse_rp_string(rp_str):
    """Parse Racing Post form string like: 18Oct25 Cat 7 Gd 4Hc 6K"""
    result = {"date": None, "surface": None, "ground": None,
              "distance": None, "class_val": None}
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
        mo = months.index(mo_str) + 1
        yr = 2000 + int(yr_str)
        result["date"] = date(yr, mo, dy)
    except:
        pass

    # Surface (from course code - token 1)
    if len(tokens) > 1:
        course = tokens[1]
        aw_courses = {"Lin": "Polytrack", "Kem": "Polytrack", "Dun": "Polytrack",
                      "Wol": "Tapeta", "Ncs": "Tapeta", "Sou": "Tapeta"}
        result["surface"] = aw_courses.get(course, "Turf")

    # Distance (token 2)
    if len(tokens) > 2:
        x = tokens[2]
        x = x.replace("½", " 1/2").replace("¼", " 1/4")
        m = 0
        f = 0
        try:
            if "m" in x:
                m_part = x[:x.index("m")]
                m = float(m_part) if m_part else 0
                after = x[x.index("m")+1:].strip()
            else:
                after = x
            if "f" in after:
                f_part = after[:after.index("f")].strip()
                if "1/2" in f_part:
                    f = float(f_part.replace("1/2","").strip() or "0") + 0.5
                elif "1/4" in f_part:
                    f = float(f_part.replace("1/4","").strip() or "0") + 0.25
                else:
                    f = float(f_part) if f_part else 0
            result["distance"] = m + (f / 8) if m > 0 else f / 8
        except:
            pass

    # Ground (token 3)
    if len(tokens) > 3:
        g = tokens[3]
        gmap = {
            "St": "Standard", "Std": "Standard",
            "St/Slw": "Standard to Slow", "Std/Slw": "Standard to Slow",
            "Slw": "Slow", "Slow": "Slow",
            "Fm": "Firm", "Hrd": "Hard",
            "Gd": "Good", "Gd/Fm": "Good to Firm", "GF": "Good to Firm",
            "Gd/Sft": "Good to Soft", "GS": "Good to Soft", "Y": "Good to Soft",
            "Sft": "Soft", "Sft/Hy": "Soft to Heavy", "Hy": "Heavy",
            "Yld": "Yielding", "Gd/Yld": "Good to Yielding", "VS": "Very Soft"
        }
        result["ground"] = gmap.get(g, g)

    # Class (from full string)
    full = rp_str
    last_tok = tokens[-1]
    prize = 0
    try:
        prize = float(last_tok.replace("K", ""))
    except:
        pass

    if "G1" in full: result["class_val"] = 1
    elif "G2" in full: result["class_val"] = 1
    elif "G3" in full: result["class_val"] = 1
    elif "1L" in full: result["class_val"] = 1
    elif "2L" in full: result["class_val"] = 2
    elif "3L" in full: result["class_val"] = 3
    elif "4L" in full: result["class_val"] = 4
    elif prize >= 50: result["class_val"] = 1
    elif prize >= 15: result["class_val"] = 2
    elif prize >= 10: result["class_val"] = 3
    elif prize >= 6: result["class_val"] = 4
    elif prize >= 3: result["class_val"] = 5
    else: result["class_val"] = 6

    return result

def parse_position_string(pos_str):
    """Parse position string like: 5/10  (3½L Mudamer 9-11) 11/2"""
    result = {"position": None, "runners": None, "beaten": None, "race_odds": None}
    if not pos_str or not pos_str.strip():
        return result
    pos_str = pos_str.strip()

    # Non-finishers
    for nf in ["PU", "UR", "BD", "RO"]:
        if nf in pos_str.upper():
            result["position"] = 99
            return result

    # Position and runners from X/Y
    slash_match = re.search(r'(\d+)/(\d+)', pos_str)
    if slash_match:
        result["position"] = int(slash_match.group(1))
        result["runners"] = int(slash_match.group(2))

    # Wait — runners is before the bracket: "5/10  (..."
    # So find / then find ( to get runners
    try:
        slash_idx = pos_str.index("/")
        bracket_idx = pos_str.index("(")
        runners_str = pos_str[slash_idx+1:bracket_idx].strip()
        result["runners"] = int(runners_str)
    except:
        pass

    # Beaten distance from inside brackets
    try:
        open_b = pos_str.index("(")
        # Find "L" after bracket
        sub = pos_str[open_b+1:]
        l_idx = sub.index("L")
        raw = sub[:l_idx].strip()
        raw = raw.replace("½", ".5").replace("¼", ".25")
        beat_map = {"sh hd": 0.1, "sh": 0.1, "hd": 0.2, "nk": 0.3}
        if raw.lower() in beat_map:
            result["beaten"] = beat_map[raw.lower()]
        else:
            # Try to extract leading number
            num_match = re.match(r'(\d+\.?\d*)', raw)
            if num_match:
                result["beaten"] = float(num_match.group(1))
            else:
                result["beaten"] = 0.0
    except:
        pass

    # Race odds — last token after closing bracket
    try:
        close_b = pos_str.rindex(")")
        after = pos_str[close_b+1:].strip()
        if after:
            result["race_odds"] = after
    except:
        pass

    return result

def weight_to_lbs(weight_str):
    """Convert 9-2 to lbs"""
    if not weight_str or "-" not in str(weight_str):
        return None
    try:
        parts = str(weight_str).split("-")
        return int(parts[0]) * 14 + int(parts[1])
    except:
        return None

def odds_to_decimal(odds_str):
    """Convert odds string to decimal"""
    if not odds_str:
        return None
    x = str(odds_str).upper().strip().replace(" ", "")
    if x in ["EVS", "EVENS"]:
        return 2.0
    if "/" in x:
        try:
            parts = x.split("/")
            return 1 + float(parts[0]) / float(parts[1])
        except:
            return None
    try:
        v = float(x)
        return v if v > 1 else None
    except:
        return None

def calc_ability(or_val, all_ors):
    """AS - Relative OR scaling"""
    valid = [o for o in all_ors if o is not None and o != 0]
    if not valid or or_val is None or or_val == 0:
        return 1.0
    mn, mx = min(valid), max(valid)
    if mx == mn:
        return 3.0
    return min(5, max(1, 1 + 4 * ((or_val - mn) / (mx - mn + 0.001))))

def calc_form_run(pos, runners, ts, rpr):
    """Form score for a single run"""
    if pos is None or runners is None:
        pos_score = 1.0
    elif runners <= 1:
        pos_score = 5.0
    else:
        pos_score = round(1 + 4 * (1 - ((pos - 1) / (runners - 1))), 1)
        pos_score = min(5, max(1, pos_score))

    ts_score = 1.0 if (ts is None or ts == 0) else round(min(5, ts / 20), 1)
    rpr_score = 1.0 if (rpr is None or rpr == 0) else round(min(5, rpr / 20), 1)
    return (pos_score * 0.4) + (ts_score * 0.2) + (rpr_score * 0.4)

def calc_form(runs):
    """AT - Form across 3 runs, recency weighted 50/30/20"""
    weights = [0.5, 0.3, 0.2]
    total = 0
    for i, run in enumerate(runs[:3]):
        score = calc_form_run(
            run.get("position"), run.get("runners"),
            run.get("ts"), run.get("rpr")
        )
        total += score * weights[i]
    return total

def calc_suitability_run(surface, distance, ground, today_surface, today_distance, today_ground):
    """AU - Suitability for a single run"""
    if surface is None or distance is None or ground is None:
        return 1.0
    g_today = GOING_MAP.get(today_ground, 5)
    g_run = GOING_MAP.get(ground, 5)
    dist_diff = abs(distance - today_distance)
    going_diff = abs(g_run - g_today)

    # Perfect match
    if surface == today_surface and dist_diff <= 0.125 and going_diff <= 1:
        return 5.0
    # Surface switch penalty
    turf_switch = (today_surface == "Turf" and surface != "Turf") or \
                  (today_surface != "Turf" and surface == "Turf")
    if turf_switch:
        return max(1, 2 - dist_diff * 4)
    # Same surface family
    aw_compat = (today_surface in ["Tapeta","Polytrack"] and surface in ["Tapeta","Polytrack"])
    surf_score = 5 if surface == today_surface else (3 if aw_compat else 1)
    dist_score = max(1, 5 - dist_diff * 8)
    going_score = max(1, 5 - going_diff)
    return 0.5 * dist_score + 0.3 * surf_score + 0.2 * going_score

def calc_suitability(runs, today_surface, today_distance, today_ground):
    """AU - Weighted suitability"""
    weights = [0.5, 0.3, 0.2]
    total = 0
    for i, run in enumerate(runs[:3]):
        s = calc_suitability_run(
            run.get("surface"), run.get("distance"), run.get("ground"),
            today_surface, today_distance, today_ground
        )
        total += s * weights[i]
    return total

def calc_fitness(last_run_date):
    """AV - Days since last run"""
    if last_run_date is None:
        return 1
    if isinstance(last_run_date, str):
        try:
            last_run_date = datetime.strptime(last_run_date, "%Y-%m-%d").date()
        except:
            return 1
    days = (date.today() - last_run_date).days
    if days <= 30: return 5
    if days <= 60: return 4
    if days <= 120: return 3
    if days <= 180: return 2
    return 1

def calc_class(runs, today_class):
    """AW - Class comparison"""
    scores = []
    for run in runs[:3]:
        rc = run.get("class_val")
        if rc is None:
            scores.append(2)
        elif rc < today_class:
            scores.append(5)
        elif rc == today_class:
            scores.append(4)
        elif rc == today_class + 1:
            scores.append(3)
        else:
            scores.append(2)
    return sum(scores) / len(scores) if scores else 2

def calc_weight_adj(weight_lbs, run_weights):
    """AX - Weight adjustment"""
    valid = [w for w in run_weights if w is not None]
    if not valid or weight_lbs is None:
        return 3.0
    avg = sum(valid) / len(valid)
    return max(1, min(5, 5 - abs(weight_lbs - avg) / 5))

def calc_score(ability, form, suit, fitness, weight_adj, class_sc, dist_band):
    """AL - Weighted score"""
    if dist_band == "SPRINT":
        return (ability*0.32 + form*0.25 + suit*0.32 + fitness*0.08 +
                class_sc*0.03 + weight_adj*0)
    elif dist_band == "MIDDLE":
        return (ability*0.34 + form*0.22 + suit*0.30 + fitness*0.08 +
                class_sc*0.03 + weight_adj*0.03)
    else:  # STAYING
        return (ability*0.30 + form*0.20 + suit*0.36 + fitness*0.06 +
                class_sc*0.03 + weight_adj*0.05)

def dist_to_band(dist):
    if dist is None: return "MIDDLE"
    if dist <= 0.75: return "SPRINT"
    if dist <= 1.3: return "MIDDLE"
    return "STAYING"

def run_model(horses, race):
    """Run the full model across all horses"""
    today_surface = race["surface"]
    today_distance = race["distance"]
    today_ground = race["ground"]
    today_class = race["class_val"]
    dist_band = dist_to_band(today_distance)

    all_ors = [h.get("or_rating") for h in horses]
    results = []

    for h in horses:
        runs = h.get("runs", [{}, {}, {}])
        while len(runs) < 3:
            runs.append({})

        ability = calc_ability(h.get("or_rating"), all_ors)
        form = calc_form(runs)
        suit = calc_suitability(runs, today_surface, today_distance, today_ground)
        fitness = calc_fitness(runs[0].get("date") if runs else None)
        class_sc = calc_class(runs, today_class)
        wt_lbs = weight_to_lbs(h.get("weight"))
        run_wts = [weight_to_lbs(r.get("weight")) for r in runs]
        weight_adj = calc_weight_adj(wt_lbs, run_wts)
        score = calc_score(ability, form, suit, fitness, weight_adj, class_sc, dist_band)

        odds_dec = odds_to_decimal(h.get("odds"))
        impl_prob = (1 / odds_dec) if odds_dec and odds_dec > 0 else None

        results.append({
            "name": h["name"],
            "ability": round(ability, 2),
            "form": round(form, 2),
            "suit": round(suit, 2),
            "fitness": fitness,
            "class_sc": round(class_sc, 2),
            "weight_adj": round(weight_adj, 2),
            "score": round(score, 3),
            "odds_dec": odds_dec,
            "impl_prob": impl_prob,
        })

    # Probability — simple linear normalisation (not cubic, matching user's current model)
    total_score = sum(r["score"] for r in results)
    for r in results:
        r["prob"] = r["score"] / total_score if total_score > 0 else 0
        r["edge"] = (r["prob"] - r["impl_prob"]) if r["impl_prob"] else None

    # Rank
    sorted_probs = sorted([r["prob"] for r in results], reverse=True)
    for r in results:
        r["rank"] = sorted_probs.index(r["prob"]) + 1

    results.sort(key=lambda x: x["rank"])
    return results, dist_band

def get_bet_strategy(results, dist_band, race):
    """Replicate the full bet strategy logic"""
    if not results:
        return "NO BET", None

    runners = len(results)
    top_prob = results[0]["prob"] if results else 0
    second_prob = results[1]["prob"] if len(results) > 1 else 0
    third_prob = results[2]["prob"] if len(results) > 2 else 0
    gap = top_prob - second_prob
    top2_pct = top_prob + second_prob
    top2_thresh = 0.30 if runners <= 7 else (0.25 if runners <= 10 else 0.22)
    gap_thresh = 0.005
    max_edge = max((r["edge"] for r in results if r["edge"] is not None), default=0)

    # Force bet check
    force_bet = max_edge >= 0.12 and top2_pct >= 0.38 and top_prob >= 0.22

    # Find best edge selection (rank 1 vs rank 2 edge comparison)
    r1 = results[0]
    r2 = results[1] if len(results) > 1 else None
    r1_edge = r1.get("edge") or 0
    r2_edge = r2.get("edge") or 0 if r2 else 0
    selection = r2 if (r2 and r2_edge - r1_edge >= 0.03) else r1
    sel_edge = selection.get("edge") or 0

    if force_bet:
        return "WIN BET", selection
    if sel_edge < 0:
        return "NO BET", None
    if top_prob < 0.10:
        return "NO BET", None
    if gap < 0.03 and top_prob < 0.22:
        return "NO BET", None
    if max_edge < 0.07:
        return "NO BET", None
    if dist_band == "SPRINT" and gap < gap_thresh:
        return "NO BET", None
    if top_prob < 0.12 or top2_pct < top2_thresh:
        return "NO BET", None
    if gap < gap_thresh / 2 and top2_pct >= 0.30 and (top_prob - third_prob) > gap_thresh:
        return "DUTCH TOP 2", None
    if gap < gap_thresh and top2_pct >= top2_thresh:
        odds_sel = selection.get("odds_dec") or 0
        return ("E/W BET" if odds_sel >= 5 else "WIN BET"), selection
    if gap >= gap_thresh * 2 and top_prob >= 0.16 and top2_pct >= top2_thresh:
        return "WIN BET", selection
    return "NO BET", None

# ─── MAIN APP ─────────────────────────────────────────────────────────────────
st.markdown("## 🏇 Horse Racing Model")

tab1, tab2, tab3 = st.tabs(["Race Entry", "Results Log", "Analysis"])

# ═══════════════════════════════════════════════════════
# TAB 1 — RACE ENTRY
# ═══════════════════════════════════════════════════════
with tab1:
    # Race setup
    with st.expander("Race Setup", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            race_date = st.date_input("Date", value=date.today())
            course = st.text_input("Course", placeholder="e.g. Newmarket")
        with c2:
            race_time = st.text_input("Race Time", placeholder="e.g. 14:30")
            distance_input = st.text_input("Distance", placeholder="e.g. 6f or 1m2f")
        with c3:
            surface = st.selectbox("Surface", ["Turf", "Polytrack", "Tapeta"])
            ground = st.selectbox("Ground", list(GOING_MAP.keys()))
        with c4:
            race_class = st.number_input("Class (1-6)", min_value=1, max_value=6, value=4)
            ew_places = st.number_input("E/W Places", min_value=2, max_value=4, value=3)

    # Parse distance
    def parse_distance_input(d):
        if not d: return None
        d = d.strip().replace("½","1/2").replace("¼","1/4")
        m = 0; f = 0
        try:
            if "m" in d:
                m_part = d[:d.index("m")]
                m = float(m_part) if m_part else 0
                after = d[d.index("m")+1:].strip()
            else:
                after = d
            if "f" in after:
                f_part = after[:after.index("f")].strip()
                if "1/2" in f_part:
                    f = float(f_part.replace("1/2","").strip() or "0") + 0.5
                elif "1/4" in f_part:
                    f = float(f_part.replace("1/4","").strip() or "0") + 0.25
                else:
                    f = float(f_part) if f_part else 0
        except:
            pass
        return m + (f / 8) if m > 0 else (f / 8 if f > 0 else None)

    distance_val = parse_distance_input(distance_input)
    dist_band = dist_to_band(distance_val)

    race = {
        "date": str(race_date),
        "course": course,
        "time": race_time,
        "distance": distance_val,
        "surface": surface,
        "ground": ground,
        "class_val": race_class,
        "ew_places": ew_places,
    }

    st.markdown("---")
    st.markdown("### Horse Entry")
    st.caption("Paste the Racing Post data string and position string for each horse. OR, Odds, Stall, TS, RPR are manual.")

    # Number of horses
    num_horses = st.number_input("Number of horses", min_value=2, max_value=30, value=8)

    # Session state for horses
    if "horses" not in st.session_state:
        st.session_state.horses = []

    horses_data = []

    for i in range(int(num_horses)):
        with st.expander(f"Horse {i+1}", expanded=(i < 3)):
            hc1, hc2, hc3, hc4 = st.columns([2, 1, 1, 1])
            with hc1:
                name = st.text_input("Name", key=f"name_{i}", placeholder="Horse name")
            with hc2:
                or_rating = st.number_input("OR", key=f"or_{i}", min_value=0, max_value=150, value=0)
            with hc3:
                odds = st.text_input("Odds", key=f"odds_{i}", placeholder="e.g. 5/1 or 6.0")
            with hc4:
                stall = st.number_input("Stall", key=f"stall_{i}", min_value=0, max_value=30, value=0)

            weight = st.text_input("Weight", key=f"wt_{i}", placeholder="e.g. 9-2")

            runs = []
            for rn in range(1, 4):
                st.markdown(f"**Race {rn}**")
                rc1, rc2 = st.columns([2, 2])
                with rc1:
                    rp_str = st.text_input(f"RP String", key=f"rp_{i}_{rn}",
                                           placeholder="e.g. 18Oct25 Cat 7 Gd 4Hc 6K")
                with rc2:
                    pos_str = st.text_input(f"Position String", key=f"pos_{i}_{rn}",
                                            placeholder="e.g. 5/10  (3½L Mudamer 9-11) 11/2")

                rc3, rc4 = st.columns(2)
                with rc3:
                    ts = st.text_input(f"TS", key=f"ts_{i}_{rn}", placeholder="-")
                with rc4:
                    rpr = st.text_input(f"RPR", key=f"rpr_{i}_{rn}", placeholder="-")

                parsed_rp = parse_rp_string(rp_str) if rp_str else {}
                parsed_pos = parse_position_string(pos_str) if pos_str else {}

                def safe_int(v):
                    try: return int(v) if v and v != "-" else None
                    except: return None

                run_data = {
                    "date": parsed_rp.get("date"),
                    "surface": parsed_rp.get("surface"),
                    "ground": parsed_rp.get("ground"),
                    "distance": parsed_rp.get("distance"),
                    "class_val": parsed_rp.get("class_val"),
                    "weight": weight,
                    "position": parsed_pos.get("position"),
                    "runners": parsed_pos.get("runners"),
                    "beaten": parsed_pos.get("beaten"),
                    "ts": safe_int(ts),
                    "rpr": safe_int(rpr),
                }
                runs.append(run_data)

                # Show parsed preview
                if rp_str or pos_str:
                    prev = []
                    if parsed_rp.get("date"): prev.append(f"📅 {parsed_rp['date']}")
                    if parsed_rp.get("surface"): prev.append(f"🏟 {parsed_rp['surface']}")
                    if parsed_rp.get("ground"): prev.append(f"🌱 {parsed_rp['ground']}")
                    if parsed_rp.get("distance"): prev.append(f"📏 {parsed_rp['distance']:.3f}m")
                    if parsed_rp.get("class_val"): prev.append(f"🏆 Cls {parsed_rp['class_val']}")
                    if parsed_pos.get("position") and parsed_pos.get("runners"):
                        prev.append(f"🏁 {parsed_pos['position']}/{parsed_pos['runners']}")
                    if prev:
                        st.caption("  |  ".join(prev))

            horse = {
                "name": name,
                "or_rating": or_rating if or_rating > 0 else None,
                "odds": odds,
                "stall": stall,
                "weight": weight,
                "runs": runs,
            }
            horses_data.append(horse)

    st.markdown("---")

    # RUN MODEL
    valid_horses = [h for h in horses_data if h["name"].strip()]

    if st.button("🏇 Run Model", type="primary", use_container_width=True):
        if len(valid_horses) < 2:
            st.error("Enter at least 2 horses to run the model.")
        elif distance_val is None:
            st.error("Enter a valid distance (e.g. 6f, 1m2f)")
        else:
            results, dist_band_calc = run_model(valid_horses, race)
            bet_strategy, selection = get_bet_strategy(results, dist_band_calc, race)

            runners = len(results)
            top_prob = results[0]["prob"]
            second_prob = results[1]["prob"] if len(results) > 1 else 0
            gap = top_prob - second_prob
            top2 = top_prob + second_prob
            max_edge = max((r["edge"] for r in results if r["edge"] is not None), default=0)

            # Output panel
            st.markdown("## Model Output")
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            mc1.metric("Distance Band", dist_band_calc)
            mc2.metric("Runners", runners)
            mc3.metric("Top Probability", f"{top_prob:.1%}")
            mc4.metric("Gap 1-2", f"{gap:.2%}")
            mc5.metric("Max Edge", f"{max_edge:.1%}")

            mc6, mc7, mc8, mc9 = st.columns(4)
            mc6.metric("Top 2 %", f"{top2:.1%}")
            race_type = "STRONG FAV" if top_prob >= 0.28 else ("SOLID FAV" if top_prob >= 0.22 else "OPEN RACE")
            mc7.metric("Race Type", race_type)
            mc8.metric("Value OK?", "YES" if max_edge >= 0.07 else "NO")
            mc9.metric("Bet?", "YES" if bet_strategy != "NO BET" else "NO")

            # Bet recommendation
            if bet_strategy == "WIN BET":
                st.markdown(f'<div class="bet-box win-bet">🎯 WIN BET — {selection["name"] if selection else ""} &nbsp; | &nbsp; Stake: 1pt WIN</div>', unsafe_allow_html=True)
            elif bet_strategy == "E/W BET":
                st.markdown(f'<div class="bet-box ew-bet">🆗 E/W BET — {selection["name"] if selection else ""} &nbsp; | &nbsp; Stake: 0.5pt E/W</div>', unsafe_allow_html=True)
            elif bet_strategy == "DUTCH TOP 2":
                st.markdown(f'<div class="bet-box dutch-bet">⚖️ DUTCH TOP 2 — {results[0]["name"]} / {results[1]["name"]} &nbsp; | &nbsp; Stake: 0.5pt each</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="bet-box no-bet">❌ NO BET — Race too open or insufficient edge</div>', unsafe_allow_html=True)

            # Horse rankings table
            st.markdown("### Field Rankings")
            for r in results:
                rank_class = "horse-rank-1" if r["rank"]==1 else ("horse-rank-2" if r["rank"]==2 else ("horse-rank-3" if r["rank"]==3 else ""))
                edge_str = f"{r['edge']:.1%}" if r['edge'] is not None else "—"
                edge_col = "green" if (r['edge'] or 0) > 0 else "red"
                odds_str = r.get("odds_dec")
                odds_disp = f"{odds_str:.2f}" if odds_str else "—"
                st.markdown(f"""
                <div class="{rank_class}" style="padding:10px 14px;margin:4px 0;border-radius:6px;display:flex;justify-content:space-between;font-size:14px">
                    <span><strong>#{r['rank']}</strong> &nbsp; {r['name']}</span>
                    <span style="color:#666">Prob: <strong>{r['prob']:.1%}</strong> &nbsp;|&nbsp; Edge: <strong style="color:{edge_col}">{edge_str}</strong> &nbsp;|&nbsp; Odds: {odds_disp} &nbsp;|&nbsp; Ability: {r['ability']} &nbsp;|&nbsp; Form: {r['form']} &nbsp;|&nbsp; Suit: {r['suit']}</span>
                </div>
                """, unsafe_allow_html=True)

            # Save to log
            st.session_state["last_result"] = {
                "race": race,
                "results": results,
                "bet_strategy": bet_strategy,
                "selection": selection["name"] if selection else None,
                "dist_band": dist_band_calc,
                "race_type": race_type,
                "top_prob": top_prob,
                "second_prob": second_prob,
                "gap": gap,
                "top2": top2,
                "max_edge": max_edge,
            }

    # Post-race result entry
    if "last_result" in st.session_state:
        st.markdown("---")
        st.markdown("### Post-Race Result")
        pr1, pr2, pr3, pr4 = st.columns(4)
        with pr1:
            winner = st.text_input("Winner")
            second = st.text_input("2nd Place")
        with pr2:
            third = st.text_input("3rd Place")
            sp = st.text_input("SP of Selection", placeholder="e.g. 5/1")
        with pr3:
            outcome = st.selectbox("Outcome", ["—", "Won", "Placed", "Lost", "No Bet"])
        with pr4:
            notes = st.text_input("Notes", placeholder="Optional")

        if st.button("💾 Save to Results Log", type="secondary"):
            lr = st.session_state["last_result"]
            results = lr["results"]
            top1 = results[0] if results else {}
            top2_horse = results[1] if len(results) > 1 else {}
            top3_horse = results[2] if len(results) > 2 else {}

            winner_rank = next((r["rank"] for r in results if r["name"].lower() == winner.lower()), None)
            in_top2 = winner_rank is not None and winner_rank <= 2
            in_top3 = winner_rank is not None and winner_rank <= 3

            log_entry = {
                "date": lr["race"]["date"],
                "course": lr["race"]["course"],
                "time": lr["race"]["time"],
                "dist_band": lr["dist_band"],
                "runners": len(results),
                "top_prob": round(lr["top_prob"], 4),
                "second_prob": round(lr["second_prob"], 4),
                "third_prob": round(top3_horse.get("prob", 0), 4) if top3_horse else 0,
                "gap": round(lr["gap"], 4),
                "top2_pct": round(lr["top2"], 4),
                "race_type": lr["race_type"],
                "bet_strategy": lr["bet_strategy"],
                "bet_yn": "Y" if lr["bet_strategy"] != "NO BET" else "N",
                "selection": lr["selection"],
                "sel_odds": sp,
                "model_prob": round(next((r["prob"] for r in results if r["name"] == lr["selection"]), 0), 4),
                "impl_prob": round(next((r.get("impl_prob") or 0 for r in results if r["name"] == lr["selection"]), 0), 4),
                "true_edge": round(next((r.get("edge") or 0 for r in results if r["name"] == lr["selection"]), 0), 4),
                "max_edge": round(lr["max_edge"], 4),
                "winner": winner,
                "winner_rank": winner_rank,
                "in_top2": "Y" if in_top2 else "N",
                "in_top3": "Y" if in_top3 else "N",
                "bet_type": lr["bet_strategy"],
                "result": outcome,
                "pl": 0,
                "notes": notes,
            }

            log = load_log()
            log.append(log_entry)
            save_log(log)
            del st.session_state["last_result"]
            st.success("Saved to results log!")
            st.rerun()

# ═══════════════════════════════════════════════════════
# TAB 2 — RESULTS LOG
# ═══════════════════════════════════════════════════════
with tab2:
    log = load_log()
    if not log:
        st.info("No results logged yet. Run the model and save your first race.")
    else:
        df = pd.DataFrame(log)
        st.markdown(f"### Results Log — {len(df)} races")

        # Summary stats
        bets = df[df["bet_yn"] == "Y"]
        wins = df[df["result"] == "Won"]
        sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
        sc1.metric("Total Races", len(df))
        sc2.metric("Bets Placed", len(bets))
        sc3.metric("Winners", len(wins))
        sc4.metric("Strike Rate", f"{len(wins)/len(bets):.0%}" if len(bets) > 0 else "—")
        avg_rank = df["winner_rank"].dropna().mean()
        sc5.metric("Avg Winner Rank", f"{avg_rank:.1f}" if not pd.isna(avg_rank) else "—")
        top3_rate = (df["in_top3"] == "Y").mean()
        sc6.metric("Top 3 Rate", f"{top3_rate:.0%}")

        # Display table
        display_cols = ["date","course","time","dist_band","runners","bet_yn",
                        "selection","bet_strategy","winner","winner_rank",
                        "in_top2","in_top3","result","top_prob","max_edge"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], use_container_width=True, height=400)

        # Export
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Download Full Log (CSV)",
            data=csv,
            file_name=f"horse_racing_log_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True
        )

# ═══════════════════════════════════════════════════════
# TAB 3 — ANALYSIS
# ═══════════════════════════════════════════════════════
with tab3:
    log = load_log()
    if not log:
        st.info("No data yet. Log some races first.")
    else:
        df = pd.DataFrame(log)
        st.markdown("### Model Performance Analysis")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Hit rates by distance band**")
            if "dist_band" in df.columns and "in_top3" in df.columns:
                by_band = df.groupby("dist_band").agg(
                    races=("date","count"),
                    top3_rate=("in_top3", lambda x: (x=="Y").mean()),
                    top2_rate=("in_top2", lambda x: (x=="Y").mean()),
                ).round(3)
                st.dataframe(by_band, use_container_width=True)

        with col2:
            st.markdown("**Bet races vs no-bet races**")
            if "bet_yn" in df.columns:
                by_bet = df.groupby("bet_yn").agg(
                    races=("date","count"),
                    top3_rate=("in_top3", lambda x: (x=="Y").mean()),
                    top2_rate=("in_top2", lambda x: (x=="Y").mean()),
                    avg_winner_rank=("winner_rank","mean"),
                ).round(3)
                st.dataframe(by_bet, use_container_width=True)

        st.markdown("**Winner rank distribution**")
        if "winner_rank" in df.columns:
            rank_counts = df["winner_rank"].value_counts().sort_index()
            rank_df = pd.DataFrame({"rank": rank_counts.index, "count": rank_counts.values})
            rank_df["pct"] = (rank_df["count"] / len(df) * 100).round(1)
            st.dataframe(rank_df, use_container_width=True)
