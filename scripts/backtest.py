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
    available_years = ["2019", "2020", "2021", "2022", "2025"]
    if year.lower() == "all":
        results = {}
        for y in available_years:
            d = load_dataset(y)
            results[y] = calculate_metrics(d, y, category_filter)
        return {"mode": "all", "years": results}
    else:
        dataset = load_dataset(str(year))
        if not dataset:
            return {"error": f"Year {year} not found or has no data. Available: {', '.join(available_years)}"}
        return {"mode": "single", "stats": calculate_metrics(dataset, str(year), category_filter)}


def run_backtest(category_filter: str = None) -> dict:
    """Backward compatibility wrapper defaulting to 2025."""
    res = run_backtest_by_year("2025", category_filter)
    return res.get("stats", {})


def print_comparative_table(all_results: dict):
    """Render comparison scorecard across 2019, 2020, 2021, 2022, and 2025."""
    years = ["2019", "2020", "2021", "2022", "2025"]
    print("\n" + "=" * 110)
    print("🌐 FULL MACRO CYCLE REGIME COMPARISON (2019 - 2025)")
    print("=" * 110)
    print(f"{'มิติการประเมิน':<28} | {'2019 (Trade War)':<14} | {'2020 (COVID QE)':<14} | {'2021 (Transitory)':<15} | {'2022 (75bps Hikes)':<15} | {'2025 (Inflation)':<14}")
    print("-" * 110)
    
    y = all_results["years"]
    
    print(f"{'จำนวนเหตุการณ์ที่ทดสอบ':<28} | {y['2019']['total_events']} รอบ{'':<8} | {y['2020']['total_events']} รอบ{'':<8} | {y['2021']['total_events']} รอบ{'':<9} | {y['2022']['total_events']} รอบ{'':<9} | {y['2025']['total_events']} รอบ")
    print(f"{'1️⃣ เดาตัวเลขจริงถูก (Pre-News)':<28} | {y['2019']['pre_news_win_rate']}% ({y['2019']['pre_news_hits']}/{y['2019']['total_events']}){'':<2} | {y['2020']['pre_news_win_rate']}% ({y['2020']['pre_news_hits']}/{y['2020']['total_events']}){'':<2} | {y['2021']['pre_news_win_rate']}% ({y['2021']['pre_news_hits']}/{y['2021']['total_events']}){'':<3} | {y['2022']['pre_news_win_rate']}% ({y['2022']['pre_news_hits']}/{y['2022']['total_events']}){'':<3} | {y['2025']['pre_news_win_rate']}% ({y['2025']['pre_news_hits']}/{y['2025']['total_events']})")
    print(f"{'2️⃣ ตลาดวิ่งตรงโมเดล (Market Hit)':<28} | {y['2019']['market_win_rate']}% ({y['2019']['market_reaction_hits']}/{y['2019']['total_events']}){'':<2} | {y['2020']['market_win_rate']}% ({y['2020']['market_reaction_hits']}/{y['2020']['total_events']}){'':<2} | {y['2021']['market_win_rate']}% ({y['2021']['market_reaction_hits']}/{y['2021']['total_events']}){'':<3} | {y['2022']['market_win_rate']}% ({y['2022']['market_reaction_hits']}/{y['2022']['total_events']}){'':<3} | {y['2025']['market_win_rate']}% ({y['2025']['market_reaction_hits']}/{y['2025']['total_events']})")
    print(f"{'3️⃣ แม่นยำสมบูรณ์ (Both Correct)':<28} | {y['2019']['both_win_rate']}% ({y['2019']['both_correct_hits']}/{y['2019']['total_events']}){'':<2} | {y['2020']['both_win_rate']}% ({y['2020']['both_correct_hits']}/{y['2020']['total_events']}){'':<2} | {y['2021']['both_win_rate']}% ({y['2021']['both_correct_hits']}/{y['2021']['total_events']}){'':<3} | {y['2022']['both_win_rate']}% ({y['2022']['both_correct_hits']}/{y['2022']['total_events']}){'':<3} | {y['2025']['both_win_rate']}% ({y['2025']['both_correct_hits']}/{y['2025']['total_events']})")
    print("=" * 110)
    
    print("\n💡 วิวัฒนาการ 5 ยุคสมัยของเศรษฐกิจมหภาค (The Macro Paradigm Evolution):")
    print("1. ปี 2019: 'Geopolitics Overrides Economics' (สงครามการค้า & ทวีตภาษีกลบตัวเลขเศรษฐกิจ)")
    print("2. ปี 2020: 'Infinite Liquidity Trumps Fundamentals' (พิมพ์เงิน QE ไม่อั้น หุ้นขึ้นแม้คนตกงาน 20M)")
    print("3. ปี 2021: 'The Transitory Delusion' (ตลาดเพลิดเพลินกับเงินเฟ้อชั่วคราว ดันหุ้นเทคทำ All-Time High)")
    print("4. ปี 2022: 'The Great Tightening Shock' (เงินเฟ้อทะลุ 9.1% + ขึ้นดอกเบี้ย 75 bps ติด 4 ครั้ง หุ้นพังทลาย)")
    print("5. ปี 2025: 'Pure Macro Fundamental Equilibrium' (ตลาดกลับสู่ระเบียบวินัยตามกลไกดอกเบี้ยแท้จริง)")
    print("=" * 110)


def print_single_year_report(stats: dict, detailed: bool = False):
    """Render single year report."""
    year = stats.get("year", "2025")
    if year == "2019":
        theme = "The Fed Pivot, Mid-Cycle Rate Cuts & US-China Trade War Tweets"
    elif year == "2020":
        theme = "COVID-19 Black Swan Shock, Emergency Cuts to 0% & Infinite QE"
    elif year == "2021":
        theme = "Post-Vaccine Reopening Euphoria & The 'Transitory Inflation' Trap"
    elif year == "2022":
        theme = "40-Year Inflation Peak (9.1%), Aggressive 75 bps Mega-Hikes & Tech Bear Market"
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
