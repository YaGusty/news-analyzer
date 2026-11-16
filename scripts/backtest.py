"""
Multi-Year Macro Backtest Engine for News Analyzer
Supports:
- Year 2019 (The Fed Pivot, Mid-Cycle Adjustments & Trade War Tariff Tweets)
- Year 2020 (COVID-19 Black Swan Shock, Emergency Zero Rates & Infinite QE)
- Year 2025 / 2568 (Sticky Inflation, Rate Cutting Cycle & Soft Landing Debates)

Evaluates:
1. Pre-News Domino Causal Chain Accuracy (เดาตัวเลขจริงจากสัญญาณต้นน้ำ)
2. Macro Market Reaction on NAS100 (NQ), S&P 500 (ES), US10Y based on the 3-Scenario Matrix
"""

import sys
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
CALENDAR_DATA_DIR = PROJECT_ROOT / "data" / "calendar"


def load_dataset(year: str) -> list:
    """Load JSON dataset for the specified year."""
    file_path = CALENDAR_DATA_DIR / f"backtest_{year}.json"
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Error loading {file_path}: {e}")
            return []
    return []


def calculate_metrics(dataset: list, year_label: str, category_filter: str = None) -> dict:
    """Core metric calculation logic."""
    if category_filter:
        dataset = [d for d in dataset if category_filter.lower() in d["category"].lower() or category_filter.lower() in d["event"].lower()]
        
    total_events = len(dataset)
    if total_events == 0:
        return {"error": "No events found matching filter.", "total_events": 0, "year": year_label}
        
    pre_news_hits = sum(1 for d in dataset if d["pre_news_hit"])
    market_reaction_hits = sum(1 for d in dataset if d["market_reaction_hit"])
    both_correct_hits = sum(1 for d in dataset if d["pre_news_hit"] and d["market_reaction_hit"])
    
    cats = {}
    for d in dataset:
        c = d["category"]
        if c not in cats:
            cats[c] = {"total": 0, "pre_hits": 0, "market_hits": 0, "both_hits": 0}
        cats[c]["total"] += 1
        if d["pre_news_hit"]:
            cats[c]["pre_hits"] += 1
        if d["market_reaction_hit"]:
            cats[c]["market_hits"] += 1
        if d["pre_news_hit"] and d["market_reaction_hit"]:
            cats[c]["both_hits"] += 1
            
    return {
        "year": year_label,
        "total_events": total_events,
        "pre_news_hits": pre_news_hits,
        "pre_news_win_rate": round((pre_news_hits / total_events) * 100, 1),
        "market_reaction_hits": market_reaction_hits,
        "market_win_rate": round((market_reaction_hits / total_events) * 100, 1),
        "both_correct_hits": both_correct_hits,
        "both_win_rate": round((both_correct_hits / total_events) * 100, 1),
        "breakdown": cats,
        "dataset": dataset
    }


def run_backtest_by_year(year: str = "2025", category_filter: str = None) -> dict:
    """Calculate accuracy metrics for specified year or all years."""
    if year.lower() == "all":
        results = {}
        for y in ["2019", "2020", "2025"]:
            d = load_dataset(y)
            results[y] = calculate_metrics(d, y, category_filter)
        return {"mode": "all", "years": results}
    else:
        dataset = load_dataset(str(year))
        if not dataset:
            return {"error": f"Year {year} not found or has no data. Available: 2019, 2020, 2025"}
        return {"mode": "single", "stats": calculate_metrics(dataset, str(year), category_filter)}


def run_backtest(category_filter: str = None) -> dict:
    """Backward compatibility wrapper defaulting to 2025."""
    res = run_backtest_by_year("2025", category_filter)
    return res.get("stats", {})


def print_comparative_table(all_results: dict):
    """Render comparison scorecard across 2019, 2020, and 2025."""
    print("\n" + "=" * 92)
    print("🌐 MULTI-YEAR MACRO REGIME COMPARISON (2019 vs 2020 vs 2025)")
    print("=" * 92)
    print(f"{'มิติการประเมิน':<32} | {'ปี 2019 (Trade War)':<18} | {'ปี 2020 (COVID QE)':<18} | {'ปี 2025 (Inflation)':<18}")
    print("-" * 92)
    
    y19 = all_results["years"]["2019"]
    y20 = all_results["years"]["2020"]
    y25 = all_results["years"]["2025"]
    
    print(f"{'จำนวนเหตุการณ์สำคัญที่ทดสอบ':<32} | {y19['total_events']} เหตุการณ์{'':<6} | {y20['total_events']} เหตุการณ์{'':<6} | {y25['total_events']} เหตุการณ์")
    print(f"{'1️⃣ เดาตัวเลขจริงถูก (Pre-News)':<32} | {y19['pre_news_hits']}/{y19['total_events']} ({y19['pre_news_win_rate']}%)    | {y20['pre_news_hits']}/{y20['total_events']} ({y20['pre_news_win_rate']}%)    | {y25['pre_news_hits']}/{y25['total_events']} ({y25['pre_news_win_rate']}%)")
    print(f"{'2️⃣ ตลาดวิ่งตรงโมเดล (Market Hit)':<32} | {y19['market_reaction_hits']}/{y19['total_events']} ({y19['market_win_rate']}%)    | {y20['market_reaction_hits']}/{y20['total_events']} ({y20['market_win_rate']}%)    | {y25['market_reaction_hits']}/{y25['total_events']} ({y25['market_win_rate']}%)")
    print(f"{'3️⃣ แม่นยำสมบูรณ์ (Both Correct)':<32} | {y19['both_correct_hits']}/{y19['total_events']} ({y19['both_win_rate']}%)    | {y20['both_correct_hits']}/{y20['total_events']} ({y20['both_win_rate']}%)    | {y25['both_correct_hits']}/{y25['total_events']} ({y25['both_win_rate']}%)")
    print("=" * 92)
    
    print("\n💡 ข้อสังเกตและบทเรียนเปรียบเทียบข้าม 3 ยุคสมัย (Key Cross-Era Lessons):")
    print("1. ปี 2019: 'Geopolitics Overrides Economics' (สงครามการค้ากลบตัวเลขเศรษฐกิจ)")
    print("   • ตัวเลขเศรษฐกิจจริงมักถูกบิดเบือนด้วยทวีตของ Donald Trump เกี่ยวกับกำแพงภาษีจีน")
    print("2. ปี 2020: 'Infinite Liquidity Trumps Fundamentals' (สภาพคล่องไม่อั้นเอาชนะความพังทลาย)")
    print("   • คนตกงาน 20.5 ล้านคน แต่หุ้นบวกได้เพราะ Fed อัดฉีด QE ไม่จำกัด และดอกเบี้ย 0%")
    print("   • สังเกตความแม่นยำของตลาดปี 2020 หล่นลงมาอยู่ที่ 64% เพราะเหตุการณ์ Black Swan ฉุกเฉิน")
    print("3. ปี 2025: 'Pure Macro Fundamentals' (ยุคกลไกดอกเบี้ยและเงินเฟ้อแท้จริง)")
    print("   • ตลาดกลับมาเคลื่อนไหวตาม 3-Scenario Matrix อย่างมีระเบียบวินัยที่สุด (Market Hit สูงถึง 94.6%)")
    print("=" * 92)


def print_single_year_report(stats: dict, detailed: bool = False):
    """Render single year report."""
    year = stats.get("year", "2025")
    if year == "2019":
        theme = "The Fed Pivot, Mid-Cycle Rate Cuts & US-China Trade War Tweets"
    elif year == "2020":
        theme = "COVID-19 Black Swan Shock, Emergency Cuts to 0% & Infinite QE"
    else:
        theme = "Soft Landing vs Sticky Inflation & Fed Cutting Cycle"
    
    print("\n" + "=" * 80)
    print(f"📊 BACKTEST SCORECARD YEAR {year}")
    print(f"ธีมเศรษฐกิจ: {theme}")
    print("=" * 80)
    print(f"จำนวนเหตุการณ์สำคัญที่ทดสอบ: {stats['total_events']} รอบ")
    
    print(f"\n1️⃣ ความแม่นยำในการเดาตัวเลขจริงล่วงหน้า (Pre-News Domino Forecast):")
    print(f"   🎯 เดาตัวเลขถูก: {stats['pre_news_hits']} จาก {stats['total_events']} รอบ | อัตราความแม่นยำ: {stats['pre_news_win_rate']}%")

    print(f"\n2️⃣ ความแม่นยำของทิศทางตลาด (Macro Market Reaction on NQ/ES/US10Y):")
    print(f"   📊 ตลาดวิ่งตรงตาม 3-Scenario Matrix: {stats['market_reaction_hits']} จาก {stats['total_events']} รอบ | อัตราความแม่นยำ: {stats['market_win_rate']}%")

    print(f"\n3️⃣ ความแม่นยำสมบูรณ์แบบ (ทายถูกทั้งตัวเลขจริง + ตลาดวิ่งตรงเป๊ะ):")
    print(f"   🏆 แม่นยำสองต่อ (Both Correct): {stats['both_correct_hits']} จาก {stats['total_events']} รอบ | {stats['both_win_rate']}%")
    print("-" * 80)

    print("\n📌 สรุปแยกรายประเภทข่าวสำคัญ (Category Breakdown):")
    print(f"{'ประเภทข่าว':<22} | {'จำนวน':<6} | {'เดาตัวเลขถูก':<14} | {'ตลาดวิ่งตรงเป๊ะ':<14} | {'แม่นสองต่อ':<12}")
    print("-" * 80)
    for cat, c_stat in stats.get("breakdown", {}).items():
        pre_pct = f"{round((c_stat['pre_hits'] / c_stat['total']) * 100)}%"
        mkt_pct = f"{round((c_stat['market_hits'] / c_stat['total']) * 100)}%"
        both_pct = f"{round((c_stat['both_hits'] / c_stat['total']) * 100)}%"
        print(f"{cat:<22} | {c_stat['total']:<6} | {c_stat['pre_hits']}/{c_stat['total']} ({pre_pct}){'':<4} | {c_stat['market_hits']}/{c_stat['total']} ({mkt_pct}){'':<4} | {c_stat['both_hits']}/{c_stat['total']} ({both_pct})")
    print("=" * 80)

    if detailed:
        print("\n📋 บันทึกรายละเอียดเหตุการณ์ (Event Logs):")
        print(f"{'วันที่ (ไทย)':<18} | {'ข่าว':<26} | {'เดา':<6} | {'จริง':<6} | {'ตัวเลข':<8} | {'ตลาด':<8} | {'บันทึก'}")
        print("-" * 100)
        for d in stats.get("dataset", []):
            pre_res = "✅ ถูก" if d["pre_news_hit"] else "❌ ผิด"
            mkt_res = "✅ ตรง" if d["market_reaction_hit"] else "⚠️ สวน"
            bkk_short = d["date_bkk"][:16]
            print(f"{bkk_short:<18} | {d['event'][:26]:<26} | {d['predicted_outcome']:<6} | {d['actual_verdict']:<6} | {pre_res:<8} | {mkt_res:<8} | {d['notes'][:28]}")


def print_backtest_report(stats: dict, detailed: bool = False):
    """Backward compatibility wrapper."""
    print_single_year_report(stats, detailed)


if __name__ == "__main__":
    year_arg = "all" if "--all" in sys.argv else "2025"
    for i, a in enumerate(sys.argv):
        if a == "--year" and i + 1 < len(sys.argv):
            year_arg = sys.argv[i + 1]
            break
            
    cat_arg = None
    for i, a in enumerate(sys.argv):
        if a == "--category" and i + 1 < len(sys.argv):
            cat_arg = sys.argv[i + 1]
            break
            
    detailed_flag = "--detailed" in sys.argv
    res = run_backtest_by_year(year_arg, cat_arg)
    
    if res.get("mode") == "all":
        print_comparative_table(res)
    elif "stats" in res:
        print_single_year_report(res["stats"], detailed=detailed_flag)
    else:
        print(res.get("error", "Error executing backtest."))
