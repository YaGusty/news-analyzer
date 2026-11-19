"""
Quantitative Event Reaction Engine & Live Forward Tracker for News Analyzer
Tracks, logs, and analyzes verifiable market price movements following US Red Folder News:
- T-1m: Baseline Anchor Price
- T+5m: Initial Liquidity Shock (Spike / Move)
- T+15m: Absorption & Whipsaw Test (Reversal check)
- T+60m: Settled Macro Direction Alignment

Stores verifiable out-of-sample events in data/calendar/live_reactions.json.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REACTIONS_FILE = PROJECT_ROOT / "data" / "calendar" / "live_reactions.json"


def load_live_reactions(year: str = None) -> list:
    """Load existing verified reactions log for specified year or default live log."""
    year_str = str(year).strip() if year else None
    valid_years = [str(y) for y in range(2015, 2026)]
    if year_str in valid_years:
        target = PROJECT_ROOT / "data" / "calendar" / f"reactions_{year_str}.json"
    else:
        target = REACTIONS_FILE

    if target.exists():
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Warning: Unable to parse {target}: {e}")
            return []
    return []


def save_live_reactions(records: list):
    """Save records to live reactions log."""
    REACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REACTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def record_reaction_event(
    event_name: str,
    actual: str,
    consensus: str,
    previous: str,
    verdict: str,
    baseline: dict,
    shock_t5: dict = None,
    absorption_t15: dict = None,
    settled_t60: dict = None,
    notes: str = ""
) -> dict:
    """
    Record or update a verified live event reaction.
    """
    records = load_live_reactions()
    now_utc = datetime.now(timezone.utc).isoformat()
    
    # Calculate point and percent changes if t5 / t15 / t60 provided
    def calculate_deltas(target_snap: dict, base_snap: dict) -> dict:
        if not target_snap or not base_snap:
            return {}
        result = dict(target_snap)
        for ticker in ["NQ", "ES", "YM", "US10Y", "DXY"]:
            p_base = base_snap.get(ticker)
            p_tgt = target_snap.get(ticker)
            if p_base is not None and p_tgt is not None and p_base != 0:
                diff = round(p_tgt - p_base, 2)
                pct = round((diff / p_base) * 100, 2)
                result[f"{ticker.lower()}_pts"] = diff
                result[f"{ticker.lower()}_pct"] = pct
        return result

    t5_calc = calculate_deltas(shock_t5, baseline)
    t15_calc = calculate_deltas(absorption_t15, baseline)
    t60_calc = calculate_deltas(settled_t60, baseline)

    # Check for whipsaw (if T5 was positive but T15 reversed to negative, or vice versa)
    whipsaw_detected = False
    nq_t5 = t5_calc.get("nq_pts")
    nq_t15 = t15_calc.get("nq_pts")
    if nq_t5 is not None and nq_t15 is not None:
        if (nq_t5 > 30 and nq_t15 < -20) or (nq_t5 < -30 and nq_t15 > 20):
            whipsaw_detected = True

    # Check macro model alignment
    # Hawkish/Hot -> NQ should be negative; Dovish/Cool -> NQ should be positive
    macro_aligned = None
    nq_t60 = t60_calc.get("nq_pts") or nq_t15.get("nq_pts") or nq_t5.get("nq_pts")
    if nq_t60 is not None:
        if verdict in ("HAWKISH", "HOT") and nq_t60 < 0:
            macro_aligned = True
        elif verdict in ("DOVISH", "COOL") and nq_t60 > 0:
            macro_aligned = True
        elif verdict in ("IN-LINE", "NEUTRAL") and abs(nq_t60) < 60:
            macro_aligned = True
        else:
            macro_aligned = False

    record_id = f"REACT_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    
    entry = {
        "id": record_id,
        "event": event_name,
        "recorded_at": now_utc,
        "consensus": consensus,
        "actual": actual,
        "previous": previous,
        "verdict": verdict,
        "baseline": baseline,
        "shock_t5": t5_calc,
        "absorption_t15": t15_calc,
        "settled_t60": t60_calc,
        "whipsaw_detected": whipsaw_detected,
        "macro_model_aligned": macro_aligned,
        "notes": notes
    }
    
    records.append(entry)
    save_live_reactions(records)
    return entry


YEAR_THEMES = {
    "2015": "Liftoff / Zero-Lower-Bound Exit & Global Growth Fears",
    "2016": "Brexit Shock, Trump Election & The Reflation Trade",
    "2017": "Synchronized Global Growth & Low-Vol Goldilocks",
    "2018": "Trade War 1.0 & 'Long Way from Neutral' / Q4 Bear Market",
    "2019": "The Powell Pivot & 3 Mid-Cycle Insurance Rate Cuts",
    "2020": "COVID-19 Black Swan Shock, Emergency Zero Rates & Infinite QE",
    "2021": "Post-Vaccine Reopening Euphoria & The 'Transitory' Inflation Debate",
    "2022": "40-Year Inflation Peak (9.1%), Aggressive 75 bps Mega-Hikes & Tech Bear Market",
    "2023": "Regional Bank Crisis (SVB) & The AI Megatrend Kickoff (Nvidia Mania)",
    "2024": "The Great Rate Cut Debate (Sticky Q1 -> Disinflation -> 50bps Jumbo Cut)",
    "2025": "Pure Macro Fundamental Equilibrium & Rate Cutting Cycle"
}


def compute_reaction_statistics(year: str = None) -> dict:
    """
    Calculate statistical distributions from verified reactions:
    - Average Shock (NQ/ES points on Hot vs Cool)
    - Whipsaw rate
    - Macro Model Alignment rate
    """
    year_str = str(year).strip().lower() if year else "2024"
    if year_str in ("all", "2015-2019", "2020-2025"):
        if year_str == "2015-2019":
            years = ["2015", "2016", "2017", "2018", "2019"]
            title = "MACRO REGIME REACTION COMPARISON (2015 - 2019)"
        elif year_str == "2020-2025":
            years = ["2020", "2021", "2022", "2023", "2024", "2025"]
            title = "MACRO REGIME REACTION COMPARISON (2020 - 2025)"
        else:
            years = [str(y) for y in range(2015, 2026)]
            title = "FULL QUANTITATIVE MACRO REGIME REACTION COMPARISON (2015 - 2025)"
            
        results = {}
        for y in years:
            results[y] = compute_reaction_statistics(year=y)
        return {"mode": "comparison", "title": title, "years_list": years, "years": results}

    records = load_live_reactions(year_str)
    year_label = str(year).strip() if year else "Live Forward Tracker"
    if not records:
        return {
            "year": year_label,
            "total_events": 0,
            "message": f"ยังไม่มีข้อมูลบันทึกราคาจริงสำหรับปี/โหมด {year_label}"
        }

    total = len(records)
    hot_events = [r for r in records if r.get("verdict") in ("HAWKISH", "HOT")]
    cool_events = [r for r in records if r.get("verdict") in ("DOVISH", "COOL")]
    inline_events = [r for r in records if r.get("verdict") in ("IN-LINE", "NEUTRAL")]
    
    whipsaws = sum(1 for r in records if r.get("whipsaw_detected"))
    aligned = sum(1 for r in records if r.get("macro_model_aligned") is True)
    
    def avg_nq(events_list, key="shock_t5"):
        pts = [e.get(key, {}).get("nq_pts") for e in events_list if e.get(key, {}).get("nq_pts") is not None]
        return round(sum(pts) / len(pts), 1) if pts else 0.0

    def avg_pct(events_list, ticker="nq", key="shock_t5"):
        pcts = [e.get(key, {}).get(f"{ticker}_pct") for e in events_list if e.get(key, {}).get(f"{ticker}_pct") is not None]
        return round(sum(pcts) / len(pcts), 2) if pcts else 0.0

    stats = {
        "year": year_label,
        "total_events": total,
        "hot_count": len(hot_events),
        "cool_count": len(cool_events),
        "inline_count": len(inline_events),
        "whipsaw_count": whipsaws,
        "whipsaw_rate": round((whipsaws / total) * 100, 1),
        "macro_alignment_rate": round((aligned / total) * 100, 1),
        "hot_avg_nq_t5_pts": avg_nq(hot_events, "shock_t5"),
        "hot_avg_nq_t5_pct": avg_pct(hot_events, "nq", "shock_t5"),
        "hot_avg_nq_t60_pts": avg_nq(hot_events, "settled_t60"),
        "cool_avg_nq_t5_pts": avg_nq(cool_events, "shock_t5"),
        "cool_avg_nq_t5_pct": avg_pct(cool_events, "nq", "shock_t5"),
        "cool_avg_nq_t60_pts": avg_nq(cool_events, "settled_t60"),
        "records": records
    }
    return stats


def print_multi_year_reaction_comparison(all_results: dict):
    """Render comparison scorecard across specified years."""
    years = all_results.get("years_list", ["2020", "2021", "2022", "2023", "2024", "2025"])
    title = all_results.get("title", "QUANTITATIVE MACRO REGIME REACTION COMPARISON")
    
    col_width = 18
    header_line = f"{'มิติการประเมิน':<32}"
    for yr in years:
        short_theme = yr
        if yr == "2015": short_theme = "2015 (Liftoff)"
        elif yr == "2016": short_theme = "2016 (Brexit/DJT)"
        elif yr == "2017": short_theme = "2017 (Goldilocks)"
        elif yr == "2018": short_theme = "2018 (TradeWar)"
        elif yr == "2019": short_theme = "2019 (Pivot/Cuts)"
        elif yr == "2020": short_theme = "2020 (COVID)"
        elif yr == "2021": short_theme = "2021 (Transitory)"
        elif yr == "2022": short_theme = "2022 (75bps Hike)"
        elif yr == "2023": short_theme = "2023 (AI Boom)"
        elif yr == "2024": short_theme = "2024 (Rate Cuts)"
        elif yr == "2025": short_theme = "2025 (Soft Land)"
        header_line += f" | {short_theme:<{col_width}}"
        
    sep_len = len(header_line)
    print("\n" + "=" * sep_len)
    print(f"🌐 {title}")
    print("=" * sep_len)
    print(header_line)
    print("-" * sep_len)
    
    y = all_results["years"]
    
    # 1. Total events
    row_events = f"{'จำนวนเหตุการณ์ที่ทดสอบ':<32}"
    for yr in years:
        tot = y[yr]['total_events']
        row_events += f" | {f'{tot} รอบ':<{col_width}}"
    print(row_events)
    
    # 2. Alignment
    row_align = f"{'1️⃣ ทิศทางตรงโมเดล (T+60m)':<32}"
    for yr in years:
        rate = y[yr]['macro_alignment_rate']
        tot = y[yr]['total_events']
        count = int(round(rate * tot / 100))
        val_str = f"{rate}% ({count}/{tot})"
        row_align += f" | {val_str:<{col_width}}"
    print(row_align)
    
    # 3. Whipsaw
    row_whip = f"{'2️⃣ อัตราเกิด Whipsaw (T+5 vs T+15)':<32}"
    for yr in years:
        rate = y[yr]['whipsaw_rate']
        cnt = y[yr]['whipsaw_count']
        tot = y[yr]['total_events']
        val_str = f"{rate}% ({cnt}/{tot})"
        row_whip += f" | {val_str:<{col_width}}"
    print(row_whip)
    
    # 4. Shock Hot
    row_hot = f"{'3️⃣ แรงกระชาก Hot (NQ T+5m)':<32}"
    for yr in years:
        pts = y[yr]['hot_avg_nq_t5_pts']
        pct = y[yr]['hot_avg_nq_t5_pct']
        val_str = f"{pts:+}p ({pct:+}%)" if y[yr]['hot_count'] > 0 else "-"
        row_hot += f" | {val_str:<{col_width}}"
    print(row_hot)
    
    # 5. Shock Cool
    row_cool = f"{'4️⃣ แรงกระชาก Cool (NQ T+5m)':<32}"
    for yr in years:
        pts = y[yr]['cool_avg_nq_t5_pts']
        pct = y[yr]['cool_avg_nq_t5_pct']
        val_str = f"{pts:+}p ({pct:+}%)" if y[yr]['cool_count'] > 0 else "-"
        row_cool += f" | {val_str:<{col_width}}"
    print(row_cool)
    
    print("=" * sep_len)
    print("\n💡 วิวัฒนาการของสภาวะตลาด (Macro Paradigm Evolution):")
    for y_idx in years:
        print(f"• ปี {y_idx}: {YEAR_THEMES.get(y_idx)}")
    print("=" * sep_len)


def print_reaction_report(stats: dict):
    """Print readable CLI statistical report for reactions."""
    if stats.get("mode") == "comparison":
        print_multi_year_reaction_comparison(stats)
        return

    year_label = stats.get("year", "Live Forward Tracker")
    print("\n" + "=" * 90)
    print(f"📈 QUANTITATIVE MACRO EVENT REACTION BACKTEST: {year_label}")
    if year_label in YEAR_THEMES:
        print(f"ธีมเศรษฐกิจ: {YEAR_THEMES[year_label]}")
    print("=" * 90)
    
    if stats.get("total_events", 0) == 0:
        print(f"ยังไม่มีประวัติการบันทึก Reaction สำหรับ {year_label}")
        print("=" * 90)
        return

    print(f"จำนวนเหตุการณ์สำคัญที่ทดสอบ: {stats['total_events']} รอบ")
    print(f"• อัตราทิศทางวิ่งตรงตาม Macro Model (T+60m): {stats['macro_alignment_rate']}%")
    print(f"• อัตราเกิด Whipsaw (กระชากสลับฝั่ง T+5 vs T+15): {stats['whipsaw_rate']}% ({stats['whipsaw_count']}/{stats['total_events']} ครั้ง)")
    print("-" * 90)
    
    print(f"🔴 กรณีตัวเลข HOT / HAWKISH ({stats['hot_count']} ครั้ง):")
    print(f"   • T+5m Initial Shock: NQ เฉลี่ย {stats['hot_avg_nq_t5_pts']:+} จุด ({stats['hot_avg_nq_t5_pct']:+}%)")
    print(f"   • T+60m Settled Move: NQ เฉลี่ย {stats['hot_avg_nq_t60_pts']:+} จุด")
    
    print(f"\n🟢 กรณีตัวเลข COOL / DOVISH ({stats['cool_count']} ครั้ง):")
    print(f"   • T+5m Initial Shock: NQ เฉลี่ย {stats['cool_avg_nq_t5_pts']:+} จุด ({stats['cool_avg_nq_t5_pct']:+}%)")
    print(f"   • T+60m Settled Move: NQ เฉลี่ย {stats['cool_avg_nq_t60_pts']:+} จุด")
    
    print("-" * 90)
    print("📋 บันทึกรายละเอียดการเคลื่อนไหวราคาจริง (Real Price Reaction Logs):")
    print(f"{'วันที่ (ไทย)':<17} | {'ข่าว':<26} | {'จริง vs คาด':<13} | {'T+5m':<10} | {'T+15m':<10} | {'T+60m':<10} | {'Whip'}")
    print("-" * 90)
    for r in stats.get("records", []):
        nq_t5 = f"{r.get('shock_t5', {}).get('nq_pts', 0):+} pts" if r.get('shock_t5', {}).get('nq_pts') is not None else "-"
        nq_t15 = f"{r.get('absorption_t15', {}).get('nq_pts', 0):+} pts" if r.get('absorption_t15', {}).get('nq_pts') is not None else "-"
        nq_t60 = f"{r.get('settled_t60', {}).get('nq_pts', 0):+} pts" if r.get('settled_t60', {}).get('nq_pts') is not None else "-"
        whip = "⚡ Whip" if r.get("whipsaw_detected") else "✅ Smooth"
        bkk_date = r.get("date_bkk", r.get("recorded_at", "-"))[:16]
        act_exp = f"{r.get('actual')} / {r.get('consensus')}"[:13]
        evt_title = r.get('event', '-')[:26]
        print(f"{bkk_date:<17} | {evt_title:<26} | {act_exp:<13} | {nq_t5:<10} | {nq_t15:<10} | {nq_t60:<10} | {whip}")
    print("=" * 90)
