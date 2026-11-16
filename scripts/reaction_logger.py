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


def load_live_reactions() -> list:
    """Load existing verified live reactions log."""
    if REACTIONS_FILE.exists():
        try:
            with open(REACTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Warning: Unable to parse {REACTIONS_FILE}: {e}")
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


def compute_reaction_statistics() -> dict:
    """
    Calculate statistical distributions from verified live reactions:
    - Average Shock (NQ/ES points on Hot vs Cool)
    - Whipsaw rate
    - Macro Model Alignment rate
    """
    records = load_live_reactions()
    if not records:
        return {
            "total_events": 0,
            "message": "ยังไม่มีข้อมูลบันทึกราคาจริง Live Forward Reactions"
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


def print_reaction_report(stats: dict):
    """Print readable CLI statistical report for live reactions."""
    print("\n" + "=" * 80)
    print("📈 VERIFIED LIVE FORWARD REACTION REPORT (Out-of-Sample)")
    print("=" * 80)
    
    if stats.get("total_events", 0) == 0:
        print("ยังไม่มีประวัติการบันทึก Live Reaction (รัน scheduler หรือ flash เพื่อเริ่มบันทึก)")
        print("=" * 80)
        return

    print(f"จำนวนเหตุการณ์ที่บันทึกข้อมูลราคาจริง: {stats['total_events']} ครั้ง")
    print(f"• อัตราการวิ่งตรงตาม Macro Model: {stats['macro_alignment_rate']}%")
    print(f"• อัตราเกิด Whipsaw (กระชากสลับฝั่ง T+5 vs T+15): {stats['whipsaw_rate']}% ({stats['whipsaw_count']}/{stats['total_events']} ครั้ง)")
    print("-" * 80)
    
    print(f"🔴 กรณีตัวเลข HOT / HAWKISH ({stats['hot_count']} ครั้ง):")
    print(f"   • T+5m Initial Shock: NQ เฉลี่ย {stats['hot_avg_nq_t5_pts']:+} จุด ({stats['hot_avg_nq_t5_pct']:+}%)")
    print(f"   • T+60m Settled Move: NQ เฉลี่ย {stats['hot_avg_nq_t60_pts']:+} จุด")
    
    print(f"\n🟢 กรณีตัวเลข COOL / DOVISH ({stats['cool_count']} ครั้ง):")
    print(f"   • T+5m Initial Shock: NQ เฉลี่ย {stats['cool_avg_nq_t5_pts']:+} จุด ({stats['cool_avg_nq_t5_pct']:+}%)")
    print(f"   • T+60m Settled Move: NQ เฉลี่ย {stats['cool_avg_nq_t60_pts']:+} จุด")
    
    print("-" * 80)
    print("📋 บันทึกล่าสุด 3 รายการ:")
    for r in stats.get("records", [])[-3:]:
        nq_t5 = r.get("shock_t5", {}).get("nq_pts", "-")
        nq_t15 = r.get("absorption_t15", {}).get("nq_pts", "-")
        nq_t60 = r.get("settled_t60", {}).get("nq_pts", "-")
        whip = "⚡ Whipsaw" if r.get("whipsaw_detected") else "✅ Smooth"
        print(f"• [{r.get('verdict')}] {r.get('event')} | Actual: {r.get('actual')} vs Exp: {r.get('consensus')}")
        print(f"  NQ Moves: T+5m: {nq_t5} pts | T+15m: {nq_t15} pts | T+60m: {nq_t60} pts | {whip}")
    print("=" * 80)
