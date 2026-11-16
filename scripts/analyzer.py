"""
Macro Economic Analyzer & Scenario Forecasting Engine
Analyzes US Red Folder economic news and models their impact on:
- NAS100 (NQ): Tech growth, valuation multiples, yield sensitivity
- S&P 500 (ES): Broad market, corporate earnings, balance of sectors
- Dow Jones (YM): Cyclicals, industrials, consumer and GDP health
- Intermarket: DXY (US Dollar) and US10Y (10-Year Treasury Yield)
"""

import sys
import os
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"
CONFIG_PATH = PROJECT_ROOT / "config.json"

try:
    from scripts.calendar_fetcher import get_calendar_events, BKK_TZ, get_ny_timezone, calculate_deviation
    from scripts.market_pulse import get_market_pulse, format_pulse_text
    from scripts.discord_notifier import (
        format_forecast_embed,
        format_flash_embed,
        send_discord_payload,
        load_webhook_url
    )
except ImportError:
    from calendar_fetcher import get_calendar_events, BKK_TZ, get_ny_timezone, calculate_deviation
    from market_pulse import get_market_pulse, format_pulse_text
    from discord_notifier import (
        format_forecast_embed,
        format_flash_embed,
        send_discord_payload,
        load_webhook_url
    )


# Comprehensive Macro Knowledge Base for US Red Folder Events
EVENT_KNOWLEDGE = {
    "cpi": {
        "full_name": "Consumer Price Index (CPI)",
        "category": "Inflation",
        "description": "ดัชนีราคาผู้บริโภค ชี้วัดอัตราเงินเฟ้อหลักของสหรัฐฯ มีผลกระทบต่อการตัดสินใจเรื่องดอกเบี้ยของ Fed สูงสุด",
        "nas100": "Tech Index มีความอ่อนไหวสูงสุดต่อเงินเฟ้อและอัตราผลตอบแทนพันธบัตร (US10Y) หากเงินเฟ้อร้อนแรง Yield พุ่ง จะเกิด Valuation Multiple Contraction กดดันหุ้น Tech ขนาดใหญ่",
        "sp500": "ดัชนีตลาดภาพรวม รับแรงกดดันจากต้นทุนทางการเงินที่ตึงตัวขึ้นและ P/E ที่อาจถูกปรับลดลง แต่มีกลุ่มพลังงานและการเงินช่วยพยุงบางส่วน",
        "dow": "ดัชนีหุ้นคุณค่าและอุตสาหกรรม (Value & Cyclicals) ได้รับผลกระทบน้อยกว่า Tech เล็กน้อย แต่หากเงินเฟ้อทำให้กำลังซื้อผู้บริโภคลดลง หุ้นค้าปลีกและอุตสาหกรรมจะเผชิญแรงกดดัน",
        "intermarket": "ตัวเลขเงินเฟ้อสูง → หนุน DXY แข็งค่าทันที + US10Y Yield พุ่งขึ้น / เงินเฟ้อชะลอ → DXY ร่วงแรง + Yield ปรับลดลง",
        "hot_direction": "DXY แข็งค่า, Yields พุ่ง, NQ ทุบหนัก, ES ร่วง, YM ย่อตัว",
        "cool_direction": "DXY ร่วง, Yields ปรับลดลง, NQ พุ่งแรง (Tech Rally), ES ดีดตัว, YM ปรับขึ้น",
        "inline_direction": "ราคาจะ Whipsaw สองฝั่งช่วง 5-15 นาทีแรก จากนั้นตลาดจะเจาะดูรายละเอียด Core CPI ไส้ใน (เช่น Shelter, SuperCore Services)"
    },
    "pce": {
        "full_name": "Core PCE Price Index",
        "category": "Inflation",
        "description": "มาตรวัดเงินเฟ้อที่ธนาคารกลางสหรัฐฯ (Fed) ให้ความสำคัญและใช้อ้างอิงเป็นเป้าหมาย 2% อย่างเป็นทางการ",
        "nas100": "มีความอ่อนไหวสูงมากต่อ Core PCE MoM หากออกมาสูงกว่า 0.3% MoM จะบีบให้ Fed คงดอกเบี้ยสูงนานขึ้น (Higher-for-Longer) ฉุดหุ้นกลุ่ม Semiconductor และ Cloud",
        "sp500": "ส่งผลต่อการคาดการณ์ Discount Rate ของกระแสเงินสดในอนาคต หาก PCE สอดคล้องกับเป้าหมาย Fed ตลาดหุ้นภาพรวมจะตอบรับเชิงบวก",
        "dow": "สะท้อนแรงกดดันด้านค่าครองชีพและราคาสินค้าอุปโภคบริโภค มีผลต่อหุ้นกลุ่ม Defensive และ Consumer Staples",
        "intermarket": "Core PCE สูงกว่าคาด → DXY แข็งค่า, US10Y พุ่ง / Core PCE เย็นลง → DXY ปรับฐานลง, US10Y ย่อ",
        "hot_direction": "บั่นทอนโอกาสลดดอกเบี้ยของ Fed, NQ และ ES เผชิญแรงขายทำกำไรอย่างหนัก",
        "cool_direction": "เปิดทาง Fed ผ่อนคลายนโยบายการเงิน, Equities ปรับตัวขึ้นทั่วทั้งกระดาน",
        "inline_direction": "ตลาดเคลื่อนไหวตามแนวโน้มเดิม (Trend Continuation) ก่อนหน้าการประกาศ"
    },
    "nonfarm": {
        "full_name": "Non-Farm Payrolls (NFP) & Unemployment Rate",
        "category": "Employment",
        "description": "ตัวเลขการจ้างงานนอกภาคเกษตรและอัตราการว่างงาน ชี้วัดความแข็งแกร่งของตลาดแรงงานสหรัฐฯ",
        "nas100": "ตลาด Tech ตอบสนองต่อ NFP สองมิติ: ถ้าการจ้างงานแข็งแกร่งเกินไป ตลาดจะกลัวเงินเฟ้อค่าจ้าง (Average Hourly Earnings) และดอกเบี้ย แต่ถ้าการจ้างงานพังเกินไป ตลาดจะเริ่มกังวลภาวะเศรษฐกิจถดถอย (Hard Landing)",
        "sp500": "S&P 500 ชอบตัวเลขแบบ 'Goldilocks' (จ้างงานเติบโตปานกลาง 140k-180k อัตราว่างงานคงที่ ค่าจ้างไม่เร่งตัว) ซึ่งสะท้อนว่าเศรษฐกิจยังเติบโตโดยไม่สร้างเงินเฟ้อ",
        "dow": "Dow Jones ตอบรับเชิงบวกต่อการจ้างงานที่มั่นคง เพราะสะท้อนสุขภาพของภาคธุรกิจ อุตสาหกรรม และการจ้างงานจริง",
        "intermarket": "NFP สูงกว่าคาด + ว่างงานต่ำ → DXY พุ่งทะลุแนวต้าน, US10Y ดีดตัว / NFP ต่ำกว่าคาดมาก → DXY ร่วงแรง",
        "hot_direction": "ตลาดมองว่า Fed ไม่มีเหตุผลต้องรีบลดดอกเบี้ย ดอลลาร์แข็ง หุ้นเทคโนโลยีพักฐาน",
        "cool_direction": "หากไม่ต่ำจนน่ากลัว จะเป็นปัจจัยบวกหนุนตลาดหุ้น แต่ถ้าต่ำกว่า 80k ตลาดจะตกใจเรื่องเศรษฐกิจถดถอย",
        "inline_direction": "สายตาทุกคู่จะพุ่งไปที่ 'Unemployment Rate' และ 'Average Hourly Earnings MoM' เป็นตัวตัดสินทิศทาง"
    },
    "fomc": {
        "full_name": "FOMC Rate Decision & Press Conference",
        "category": "Central Bank",
        "description": "การตัดสินใจอัตราดอกเบี้ยนโยบายของ Fed ถ้อยแถลง และการแถลงข่าวของประธาน Jerome Powell",
        "nas100": "อีเวนต์ที่มีน้ำหนักสูงสุดแห่งไตรมาส ทัศนะของ Powell ต่ออัตราดอกเบี้ยและ Dot Plot จะกำหนดทิศทางของดัชนี Tech ทั้งเดือน",
        "sp500": "สะท้อนต้นทุนทางการเงินรวมของบริษัทจดทะเบียนในดัชนี และสภาพคล่องส่วนเกินในระบบการเงิน",
        "dow": "หุ้นสถาบันการเงิน (JPM, GS) และกลุ่มอุตสาหกรรมใน Dow ไวต่อการส่งสัญญาณเรื่อง Balance Sheet (QT) และ Neutral Rate",
        "intermarket": "มักเกิด Whipsaw รุนแรงตอน 14:00 NY และเกิดทิศทางแท้จริงตอน Powell ตอบคำถามสื่อช่วง 14:30 NY",
        "hot_direction": "Hawkish (ส่งสัญญาณคงดอกเบี้ยนาน/ไม่รีบลด/กังวลเงินเฟ้อ) → NQ, ES, YM ร่วงลงทั้งกระดาน",
        "cool_direction": "Dovish (ส่งสัญญาณพร้อมผ่อนคลาย/กังวลตลาดแรงงานชะลอ) → ตลาดหุ้นระเบิดขึ้นทำจุดสูงสุดใหม่",
        "inline_direction": "คำศัพท์และน้ำเสียง (Tone) ในช่วงถาม-ตอบ (Q&A) ของ Powell จะเป็นตัวขับเคลื่อนตลาดอย่างแท้จริง"
    },
    "retail sales": {
        "full_name": "US Retail Sales (MoM)",
        "category": "Consumption",
        "description": "ยอดค้าปลีก ชี้วัดการใช้จ่ายของผู้บริโภค ซึ่งคิดเป็นเกือบ 70% ของ GDP สหรัฐฯ",
        "nas100": "สะท้อนกำลังซื้อด้านฮาร์ดแวร์ สินค้าอิเล็กทรอนิกส์ และ E-commerce (เช่น AMZN, AAPL)",
        "sp500": "มีผลโดยตรงต่อกลุ่ม Consumer Discretionary และ Consumer Staples สะท้อนว่าผู้บริโภคยังแบกรับเศรษฐกิจได้หรือไม่",
        "dow": "Dow Jones มีความไวสูงมากต่อ Retail Sales ผ่านหุ้นค้าปลีกยักษ์ใหญ่อย่าง Home Depot (HD), Walmart (WMT), Nike (NKE)",
        "intermarket": "ยอดค้าปลีกแกร่ง → ตอกย้ำเศรษฐกิจไม่ถดถอย หนุน DXY แข็งค่าเล็กน้อย",
        "hot_direction": "ผู้บริโภคยังแข็งแกร่ง หนุนความเชื่อมั่นด้านกำไรบริษัทจดทะเบียน แต่อาจชะลอการลดดอกเบี้ย",
        "cool_direction": "ผู้บริโภคเริ่มรัดเข็มขัด หุ้นค้าปลีกและอุตสาหกรรมเผชิญแรงขาย",
        "inline_direction": "ตลาดจะโฟกัสไปที่ Control Group (Core Retail Sales) ซึ่งใช้คำนวณตัวเลข GDP โดยตรง"
    },
    "gdp": {
        "full_name": "Advance GDP (QoQ Annualized)",
        "category": "Growth",
        "description": "อัตราการเติบโตทางเศรษฐกิจของสหรัฐฯ แบบรายไตรมาส",
        "nas100": "ชอบการเติบโตที่สมดุล หาก GDP สูงเกิน 3% อาจจุดชนวนความกังวลเรื่องเงินเฟ้อ แต่ถ้าชะลอตัวแบบมีเสถียรภาพจะส่งผลดีต่อหุ้น Tech",
        "sp500": "ตัวขับเคลื่อนหลักของการเติบโตของรายได้ (Top-line Revenue Growth) ของบริษัทขนาดใหญ่",
        "dow": "สะท้อนความต้องการเครื่องจักร การขนส่ง และสินค้าอุตสาหกรรมหนักโดยตรง",
        "intermarket": "GDP เหนือคาดหมาย → ดอลลาร์แข็งค่าจากความโดดเด่นของเศรษฐกิจสหรัฐฯ (US Exceptionalism)",
        "hot_direction": "สะท้อนเศรษฐกิจแข็งแกร่ง ปิดประตูความเสี่ยง Recession ตลาดหุ้นตอบรับบวกในภาพกลาง-ยาว",
        "cool_direction": "หาก GDP ต่ำกว่า 1% จะจุดกระแสความกลัวเศรษฐกิจถดถอยและกำไรบริษัทตกต่ำ",
        "inline_direction": "ตลาดจะแยกดูไส้ในระหว่าง Personal Consumption กับ Business Investment"
    },
    "ism": {
        "full_name": "ISM Manufacturing / Services PMI",
        "category": "Business Activity",
        "description": "ดัชนีผู้จัดการฝ่ายจัดซื้อภาคการผลิตและบริการ ระดับ 50 คือเส้นแบ่งระหว่างการขยายตัวและการหดตัว",
        "nas100": "ภาคบริการ (Services PMI) มีความสำคัญสูงเพราะคิดเป็นสัดส่วนใหญ่ของเศรษฐกิจ และไส้ใน 'Prices Paid' เป็นมาตรวัดเงินเฟ้อล่วงหน้า",
        "sp500": "สะท้อนความเชื่อมั่นและการส่งคำสั่งซื้อใหม่ (New Orders) ของผู้บริหารบริษัทชั้นนำ",
        "dow": "ภาคการผลิต (Manufacturing PMI) มีผลกระทบต่อหุ้น Dow Jones โดยตรงอย่างมีนัยสำคัญ",
        "intermarket": "ISM Services > 53 + Prices Paid พุ่ง → DXY แข็งค่า, Yield ปรับตัวขึ้น",
        "hot_direction": "กิจกรรมทางเศรษฐกิจขยายตัวดี หนุนหุ้นกลุ่ม Cyclicals และ Industrials",
        "cool_direction": "หากดัชนีหลุดต่ำกว่า 48 ตลาดจะกังวลเรื่องการชะลอตัวของเศรษฐกิจ",
        "inline_direction": "พิจารณาองค์ประกอบย่อย: New Orders (แนวโน้มข้างหน้า) vs Employment (การจ้างงาน)"
    },
    "jobless claims": {
        "full_name": "Initial Jobless Claims",
        "category": "Labor Flow",
        "description": "จำนวนผู้ขอรับสวัสดิการว่างงานรายสัปดาห์ เป็น High-Frequency Data ที่รายงานทุกวันพฤหัสบดี",
        "nas100": "ช่วยบอกทิศทางตลาดแรงงานแบบ Real-time ก่อนตัวเลข NFP รายเดือน",
        "sp500": "ใช้ประเมินเสถียรภาพรายได้ของผู้บริโภค",
        "dow": "ตอบสนองต่อแนวโน้มการปลดพนักงานในภาคอุตสาหกรรม",
        "intermarket": "ตัวเลขต่ำกว่า 215k → ตลาดแรงงานตึงตัว หนุน DXY / ตัวเลขสูงเกิน 240k → ตลาดแรงงานเริ่มคลายตัว",
        "hot_direction": "ตัวเลขต่ำมาก = คนตกงานน้อยมาก = ตลาดแรงงานยังตึงตัว ไม่เอื้อให้รีบลดดอกเบี้ย",
        "cool_direction": "ตัวเลขพุ่งขึ้น = ตลาดแรงงานเริ่มชะลอตัว หนุนความหวังลดดอกเบี้ย",
        "inline_direction": "หากตัวเลขแกว่งในกรอบ 215k - 230k ตลาดจะถือว่าไม่มีนัยสำคัญใหม่"
    }
}


def match_knowledge_entry(event_title: str) -> dict:
    """Find matching knowledge entry by keywords."""
    title_lower = event_title.lower()
    for key, data in EVENT_KNOWLEDGE.items():
        if key in title_lower:
            return data
            
    # Default fallback template
    return {
        "full_name": event_title,
        "category": "Economic Indicator",
        "description": f"รายงานตัวเลขเศรษฐกิจสหรัฐฯ: {event_title}",
        "nas100": "ติดตามผลกระทบต่ออัตราดอกเบี้ยและต้นทุนเงินทุนของบริษัทเทคโนโลยี",
        "sp500": "สะท้อนภาพรวมสภาวะเศรษฐกิจมหภาคและความเชื่อมั่นของนักลงทุน",
        "dow": "สะท้อนสุขภาพของภาคธุรกิจและการใช้จ่ายในระบบเศรษฐกิจจริง",
        "intermarket": "จับตาความเคลื่อนไหวของ DXY และ US 10-Year Treasury Yield เป็นเข็มทิศชี้นำ",
        "hot_direction": "หากตัวเลขสูงกว่าคาดมาก อาจหนุนดอลลาร์และสร้างแรงกดดันต่อดัชนีหุ้น",
        "cool_direction": "หากตัวเลขต่ำกว่าคาด อาจลดแรงกดดันด้านดอกเบี้ยและเปิดโอกาสให้ตลาดหุ้นฟื้นตัว",
        "inline_direction": "หากตัวเลขเป็นไปตามคาดการณ์ ตลาดจะเคลื่อนไหวตามเทรนด์และปัจจัยพื้นฐานเดิม"
    }


def analyze_forecast(event_name: str, consensus: str = None, previous: str = None, period: str = None) -> dict:
    """
    Generate comprehensive pre-news forecast & scenario matrix.
    """
    kb = match_knowledge_entry(event_name)
    
    # Check if we can find exact match in upcoming calendar
    time_bkk = "รอกำหนดการ"
    time_ny = "Pending"
    try:
        events = get_calendar_events(high_only=False)
        for e in events:
            if event_name.lower() in e["title"].lower() or e["title"].lower() in event_name.lower():
                if not consensus and e.get("forecast") is not None:
                    consensus = str(e["forecast"])
                if not previous and e.get("previous") is not None:
                    previous = str(e["previous"])
                time_bkk = e.get("date_bkk", time_bkk)
                time_ny = e.get("date_ny", time_ny)
                if not period and e.get("period"):
                    period = str(e["period"])
                break
    except Exception:
        pass
        
    consensus_val = consensus if consensus else "N/A"
    previous_val = previous if previous else "N/A"
    
    # Live Pre-News Market Pulse
    pulse_data = get_market_pulse()
    pulse_display = format_pulse_text(pulse_data)
    
    # Dynamic high-signal TL;DR
    if kb["category"] == "Inflation":
        tldr = f"🔥 สรุปจุดโฟกัส: ตลาดจับตาเงินเฟ้อเทียบคาด `{consensus_val}` — หากร้อนแรง Yields พุ่งกดดัน Tech (NQ) หนักสุด / หากเย็นลงเปิดทาง Relief Rally ทั่วกระดาน"
    elif kb["category"] == "Employment":
        tldr = f"💼 สรุปจุดโฟกัส: ตลาดต้องการตัวเลข Goldilocks เทียบคาด `{consensus_val}` — ร้อนเกินไปกลัวดอกเบี้ย / แย่เกินไปกลัว Recession"
    elif kb["category"] == "Central Bank":
        tldr = f"🏛️ สรุปจุดโฟกัส: นโยบายดอกเบี้ย Fed และถ้อยแถลง Powell — ทัศนะต่อ Dot Plot จะชี้ชะตาทิศทางของ NQ, ES, YM ทั้งสัปดาห์"
    elif kb["category"] == "Consumption":
        tldr = f"🛒 สรุปจุดโฟกัส: กำลังซื้อผู้บริโภค 70% ของ GDP เทียบคาด `{consensus_val}` — มีผลตรงต่อ Dow Jones และหุ้นค้าปลีกขนาดใหญ่"
    else:
        tldr = f"📊 สรุปจุดโฟกัส: ติดตามตัวเลขจริงเทียบคาดการณ์ `{consensus_val}` เพื่อจับทิศทาง Dollar Index (DXY) และพันธบัตรสหรัฐฯ (US10Y)"
    
    analysis = {
        "event": kb["full_name"],
        "category": kb["category"],
        "period": period or "",
        "time_bkk": time_bkk,
        "time_ny": time_ny,
        "consensus": consensus_val,
        "previous": previous_val,
        "tldr": tldr,
        "description": kb["description"],
        "nas100_impact": kb["nas100"],
        "sp500_impact": kb["sp500"],
        "dow_impact": kb["dow"],
        "intermarket": kb["intermarket"],
        "market_pulse": pulse_data,
        "pulse_text": pulse_display,
        "scenario_hot": kb["hot_direction"],
        "scenario_cool": kb["cool_direction"],
        "scenario_inline": kb["inline_direction"],
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Save markdown report (resilient to filesystem permissions)
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        slug = event_name.lower().replace(" ", "_").replace("/", "_")[:20]
        date_str = datetime.now().strftime("%Y%m%d")
        report_file = REPORTS_DIR / f"forecast_{slug}_{date_str}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        analysis["report_path"] = str(report_file)
    except Exception:
        analysis["report_path"] = "Generated in-memory (File write skipped)"
        
    return analysis


def analyze_flash(event_name: str, actual: str, consensus: str = None, previous: str = None) -> dict:
    """
    Generate instant post-news flash breakdown with deviation delta and high visual clarity.
    """
    kb = match_knowledge_entry(event_name)
    
    # Auto fill consensus/previous if not given
    if not consensus or not previous:
        try:
            events = get_calendar_events(high_only=False)
            for e in events:
                if event_name.lower() in e["title"].lower():
                    if not consensus and e.get("forecast") is not None:
                        consensus = str(e["forecast"])
                    if not previous and e.get("previous") is not None:
                        previous = str(e["previous"])
                    break
        except Exception:
            pass
            
    consensus_val = consensus or "N/A"
    previous_val = previous or "N/A"
    
    # Calculate exact deviation
    dev_info = calculate_deviation(actual, consensus_val)
    delta_str = dev_info.get("delta_str", "-")
    direction = dev_info.get("direction", "UNKNOWN")
    
    # Invert logic for Unemployment / Jobless Claims (where higher is dovish for rates)
    is_labor_claim = "unemployment" in event_name.lower() or "claims" in event_name.lower()
    
    if direction == "BEAT":
        verdict = "DOVISH" if is_labor_claim else "HAWKISH"
        deviation_badge = f"🔴 HOT ({delta_str})" if not is_labor_claim else f"🟢 DOVISH ({delta_str})"
    elif direction == "MISS":
        verdict = "HAWKISH" if is_labor_claim else "DOVISH"
        deviation_badge = f"🟢 COOL ({delta_str})" if not is_labor_claim else f"🔴 HOT ({delta_str})"
    else:
        verdict = "IN-LINE"
        deviation_badge = f"🟡 IN-LINE ({delta_str})"

    if verdict == "HAWKISH":
        tldr = f"⚡ ฟันธง: ตัวเลขร้อนแรงกว่าคาด ({delta_str}) → หนุน DXY แข็งค่า + US10Y พุ่ง → กดดัน Valuation หุ้นเทค (NQ ย่อตัวแรงสุด)"
        nq_impact = "⬇️ **NQ (Tech):** เสี่ยงย่อตัวแรงสุดจาก Bond Yield ดีดตัวกดดัน P/E Multiples หุ้นเติบโตและ AI"
        es_impact = "⬇️ **ES (S&P 500):** เผชิญแรงขายทำกำไรตามสภาพคล่องที่ตึงตัวขึ้น แต่มีกลุ่ม Defensive ช่วยพยุง"
        ym_impact = "↘️ **YM (Dow):** ปรับฐานปานกลาง หุ้น Cyclicals กังวลต้นทุนกู้ยืมที่อาจสูงนานขึ้น"
        intermarket_impact = "⬆️ **DXY / US10Y:** ดอลลาร์แข็งค่าทดสอบแนวต้าน / Yield พันธบัตรพุ่งขึ้น"
        fed_outlook = "🏛️ ลดโอกาสที่ Fed จะผ่อนคลายนโยบายการเงินเร็ว หนุนธีม Higher-for-Longer"
    elif verdict == "DOVISH":
        tldr = f"⚡ ฟันธง: ตัวเลขชะลอตัวลง ({delta_str}) → DXY อ่อนค่า + US10Y ปรับลง → หนุน Relief Rally หุ้นเทคและภาพรวม (NQ/ES ดีดตัว)"
        nq_impact = "⬆️ **NQ (Tech):** ผู้ชนะหลัก (Top Outperformer) Yields ลดลงหนุนแรงซื้อกลุ่ม Semiconductor และ Cloud"
        es_impact = "⬆️ **ES (S&P 500):** ดัชนีภาพรวมเปิดรับความเสี่ยง (Risk-On) หนุนความเชื่อมั่นกำไรบริษัทจดทะเบียน"
        ym_impact = "↗️ **YM (Dow):** ฟื้นตัวตามความหวัง Soft Landing และแรงกดดันเงินเฟ้อที่เบาลง"
        intermarket_impact = "⬇️ **DXY / US10Y:** ดอลลาร์ร่วงหลุดแนวรับ / Yield ปรับฐานลงเปิดทางหุ้นขึ้น"
        fed_outlook = "🏛️ สนับสนุนสมมติฐานว่า Fed สามารถลดดอกเบี้ยได้ตามเป้า เพิ่มโอกาสผ่อนคลายนโยบายการเงิน"
    else:
        tldr = f"⚡ ฟันธง: ตัวเลขใกล้เคียงคาด ({delta_str}) → ตลาดซึมซับไว้แล้ว (Priced-in) ระวังราคาผันผวนสะบัดสองฝั่ง (Whipsaw)"
        nq_impact = "↔️ **NQ (Tech):** ผันผวนตาม Technical และกระแสเงินเฉพาะกลุ่ม เคลื่อนไหวในกรอบ"
        es_impact = "↔️ **ES (S&P 500):** แกว่งตัวรอปัจจัยใหม่ สลับกลุ่มหมุนเวียน (Sector Rotation)"
        ym_impact = "↔️ **YM (Dow):** เคลื่อนไหวตามผลประกอบการและข้อมูลรายอุตสาหกรรม"
        intermarket_impact = "↔️ **DXY / US10Y:** แกว่งตัวในกรอบเดิม ไม่เกิด Breakout รุนแรง"
        fed_outlook = "🏛️ ไม่เปลี่ยนแนวโน้ม Dot Plot ของ Fed ตลาดรอคอยชุดข้อมูลถัดไป"

    summary = f"ตัวเลข {kb['full_name']} รายงานออกมาที่ `{actual}` เทียบกับคาดการณ์ `{consensus_val}` (ส่วนต่าง: `{delta_str}` | ครั้งก่อน `{previous_val}`)"
    
    market_reaction = f"{nq_impact}\n{es_impact}\n{ym_impact}\n{intermarket_impact}"

    flash_data = {
        "event": kb["full_name"],
        "actual": actual,
        "consensus": consensus_val,
        "previous": previous_val,
        "deviation_str": delta_str,
        "deviation_badge": deviation_badge,
        "verdict": verdict,
        "tldr": tldr,
        "summary": summary,
        "market_reaction": market_reaction,
        "nq_impact": nq_impact,
        "es_impact": es_impact,
        "ym_impact": ym_impact,
        "intermarket_impact": intermarket_impact,
        "fed_outlook": fed_outlook,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Save markdown report (resilient to filesystem permissions)
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        slug = event_name.lower().replace(" ", "_").replace("/", "_")[:20]
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        report_file = REPORTS_DIR / f"flash_{slug}_{date_str}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        flash_data["report_path"] = str(report_file)
    except Exception:
        flash_data["report_path"] = "Generated in-memory (File write skipped)"
        
    return flash_data


def main():
    parser = argparse.ArgumentParser(description="Macro Analyzer for News Analyzer")
    subparsers = parser.add_subparsers(dest="command", help="Command: forecast or flash")
    
    # Forecast parser
    p_fc = subparsers.add_parser("forecast", help="Generate pre-news forecast & scenario matrix")
    p_fc.add_argument("event", type=str, help="Event name (e.g. CPI, NFP, Retail Sales, FOMC)")
    p_fc.add_argument("--consensus", type=str, default=None, help="Market consensus value")
    p_fc.add_argument("--previous", type=str, default=None, help="Previous release value")
    p_fc.add_argument("--period", type=str, default=None, help="Reference period")
    p_fc.add_argument("--discord", action="store_true", help="Send analysis directly to Discord")
    p_fc.add_argument("--webhook", type=str, default=None, help="Explicit webhook URL")
    
    # Flash parser
    p_fl = subparsers.add_parser("flash", help="Generate post-news flash analysis")
    p_fl.add_argument("event", type=str, help="Event name (e.g. CPI, NFP, Retail Sales)")
    p_fl.add_argument("actual", type=str, help="Actual released number")
    p_fl.add_argument("--consensus", type=str, default=None, help="Market consensus value")
    p_fl.add_argument("--previous", type=str, default=None, help="Previous release value")
    p_fl.add_argument("--discord", action="store_true", help="Send flash report to Discord")
    p_fl.add_argument("--webhook", type=str, default=None, help="Explicit webhook URL")
    
    args = parser.parse_args()
    
    if args.command == "forecast":
        analysis = analyze_forecast(args.event, args.consensus, args.previous, args.period)
        print(f"\n[OK] Forecast generated for: {analysis['event']}")
        print(f"Time (BKK): {analysis['time_bkk']} | NY: {analysis['time_ny']}")
        print(f"Consensus: {analysis['consensus']} | Previous: {analysis['previous']}")
        print(f"Report saved: {analysis['report_path']}")
        print("\n--- NAS100 Sensitivity ---")
        print(analysis['nas100_impact'])
        print("\n--- 3-Scenario Matrix ---")
        print(f"Hot: {analysis['scenario_hot']}")
        print(f"Cool: {analysis['scenario_cool']}")
        print(f"In-line: {analysis['scenario_inline']}")
        
        if args.discord:
            payload = format_forecast_embed(analysis)
            ok, msg = send_discord_payload(payload, args.webhook)
            print(f"\nDiscord Dispatch: {msg}")
            
    elif args.command == "flash":
        flash_data = analyze_flash(args.event, args.actual, args.consensus, args.previous)
        print(f"\n[OK] Flash Report generated for: {flash_data['event']}")
        print(f"Actual: {flash_data['actual']} vs Exp: {flash_data['consensus']} (Verdict: {flash_data['verdict']})")
        print(f"Report saved: {flash_data['report_path']}")
        print("\n--- Market Reaction ---")
        print(flash_data['market_reaction'])
        
        if args.discord:
            payload = format_flash_embed(flash_data)
            ok, msg = send_discord_payload(payload, args.webhook)
            print(f"\nDiscord Dispatch: {msg}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
