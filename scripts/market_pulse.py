"""
Market Pulse Fetcher for News Analyzer
Fetches real-time market snapshot for:
- DXY (US Dollar Index)
- US10Y (10-Year Treasury Yield)
- VIX (Volatility Index)
- NQ=F (Nasdaq 100 Futures)
- ES=F (S&P 500 Futures)
- YM=F (Dow Jones Futures)
"""

import sys
import os
import json
import argparse
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Tickers to track
PULSE_TICKERS = {
    "DXY": {"symbol": "DX-Y.NYB", "name": "US Dollar Index", "category": "currency"},
    "US10Y": {"symbol": "^TNX", "name": "10-Yr US Treasury Yield", "category": "yield"},
    "VIX": {"symbol": "^VIX", "name": "CBOE Volatility Index", "category": "volatility"},
    "NQ": {"symbol": "NQ=F", "name": "Nasdaq 100 Futures", "category": "index"},
    "ES": {"symbol": "ES=F", "name": "S&P 500 Futures", "category": "index"},
    "YM": {"symbol": "YM=F", "name": "Dow Jones Futures", "category": "index"}
}


def fetch_single_quote(symbol: str) -> dict:
    """Fetch quote metadata from Yahoo v8 chart endpoint (no crumb required)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
    
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            result = resp.json().get("chart", {}).get("result", [])
            if result:
                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice")
                prev_close = meta.get("chartPreviousClose")
                
                if price is not None and prev_close is not None and prev_close != 0:
                    change = price - prev_close
                    change_pct = (change / prev_close) * 100
                else:
                    change = 0.0
                    change_pct = 0.0
                    
                return {
                    "symbol": symbol,
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "success": True
                }
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "success": False}
        
    return {"symbol": symbol, "error": "Not found", "success": False}


def get_market_pulse() -> dict:
    """Fetch current market pulse for all key intermarket assets."""
    pulse = {}
    
    for key, info in PULSE_TICKERS.items():
        data = fetch_single_quote(info["symbol"])
        if data.get("success"):
            pulse[key] = {
                "name": info["name"],
                "symbol": info["symbol"],
                "price": data["price"],
                "change": data["change"],
                "change_pct": data["change_pct"]
            }
        else:
            pulse[key] = {
                "name": info["name"],
                "symbol": info["symbol"],
                "price": None,
                "change": None,
                "change_pct": None
            }
            
    # Macro Intermarket Sentiment Synthesis
    sentiment_notes = []
    
    # 1. Yield & Dollar Assessment
    us10y = pulse.get("US10Y", {})
    dxy = pulse.get("DXY", {})
    if us10y.get("change_pct") is not None and us10y["change_pct"] > 0.8:
        sentiment_notes.append("⚠️ US 10Y Yield พุ่งขึ้น (+ กดดัน Valuation หุ้นเทค)")
    elif us10y.get("change_pct") is not None and us10y["change_pct"] < -0.8:
        sentiment_notes.append("🟢 US 10Y Yield ปรับตัวลดลง (เปิดทางหนุน Tech)")
        
    if dxy.get("change_pct") is not None and dxy["change_pct"] > 0.25:
        sentiment_notes.append("💵 ดอลลาร์ (DXY) แข็งค่า (ตึงตัวต่อสภาพคล่องโลก)")
        
    # 2. VIX Assessment
    vix = pulse.get("VIX", {})
    if vix.get("price") is not None:
        if vix["price"] > 22:
            sentiment_notes.append("🔥 VIX สูงเกิน 22 (ตลาดระแวงและป้องกันความเสี่ยงสูง)")
        elif vix["price"] < 15:
            sentiment_notes.append("😌 VIX ต่ำกว่า 15 (ตลาดนิ่ง ไร้ความตระหนก)")
            
    # 3. Equities Assessment & Pre-News Drift Skew
    nq = pulse.get("NQ", {})
    es = pulse.get("ES", {})
    positioning_risk = "⚖️ Neutral Positioning (ตลาดทรงตัวสมดุลก่อนข่าวออก ไม่เอนเอียงฝั่งใดชัดเจน)"
    macro_regime = "Goldilocks / Macro Normalcy"
    
    if nq.get("change_pct") is not None:
        if nq["change_pct"] >= 0.8:
            sentiment_notes.append("📈 NQ ปรับตัวขึ้นแรงนำตลาดล่วงหน้า")
            positioning_risk = "⚠️ Asymmetric Downside Risk (Priced for Perfection): ตลาดแรลลี่ดักหน้าไปแล้ว หากตัวเลขออกมาเพียง In-line หรือ Hot เล็กน้อย อาจเผชิญแรง Sell-on-fact ทันที"
        elif nq["change_pct"] <= -0.8:
            sentiment_notes.append("📉 NQ ถูกเทขายซึมซับความกลัวนำตลาด")
            positioning_risk = "🛡️ Asymmetric Upside Risk (Priced for Fear): ตลาดซึมซับความกลัวไปล่วงหน้า หากตัวเลขไม่ออกมาแย่กว่าคาด มีโอกาสเกิด Short Squeeze / Relief Rally รวดเร็ว"

    # Macro Regime Context Identification
    if us10y.get("price") is not None and us10y["price"] > 4.5:
        macro_regime = "Yield Dominance (ดอกเบี้ยและบอนด์ยีลด์ระดับสูงเป็นตัวบงการ Valuation ของหุ้น Growth)"
    elif vix.get("price") is not None and vix["price"] > 24:
        macro_regime = "High Volatility / Growth Recession Fear (ตลาดกังวลความเสี่ยงเศรษฐกิจถดถอยและสภาพคล่อง)"
    else:
        macro_regime = "Equilibrium / Disinflation Watch (ตลาดตอบสนองตามตรรกะดอกเบี้ยแท้จริง)"

    pulse["sentiment_summary"] = " | ".join(sentiment_notes) if sentiment_notes else "สภาวะตลาดอยู่ในเกณฑ์ปกติก่อนการประกาศตัวเลข"
    pulse["positioning_risk"] = positioning_risk
    pulse["macro_regime"] = macro_regime
    return pulse


def format_pulse_text(pulse: dict) -> str:
    """Format market pulse into a clean text block."""
    lines = []
    lines.append("🌐 [PRE-NEWS MARKET PULSE & POSITIONING]")
    
    dxy = pulse.get("DXY", {})
    us10y = pulse.get("US10Y", {})
    vix = pulse.get("VIX", {})
    nq = pulse.get("NQ", {})
    es = pulse.get("ES", {})
    ym = pulse.get("YM", {})
    
    def fmt(item, unit=""):
        if item.get("price") is None:
            return "N/A"
        sign = "+" if item.get("change", 0) >= 0 else ""
        pct_sign = "+" if item.get("change_pct", 0) >= 0 else ""
        return f"{item['price']:.2f}{unit} ({pct_sign}{item.get('change_pct', 0):.2f}%)"

    lines.append(f"• DXY: {fmt(dxy)} | US10Y: {fmt(us10y, '%')} | VIX: {fmt(vix)}")
    lines.append(f"• NQ (Tech): {fmt(nq)} | ES (S&P): {fmt(es)} | YM (Dow): {fmt(ym)}")
    lines.append(f"• สรุปบรรยากาศ: {pulse.get('sentiment_summary')}")
    lines.append(f"• Pre-News Drift: {pulse.get('positioning_risk')}")
    lines.append(f"• Macro Regime: {pulse.get('macro_regime')}")
    return "\n".join(lines)


def format_pulse_for_discord(pulse: dict) -> str:
    """Format market pulse for a Discord Embed field value."""
    dxy = pulse.get("DXY", {})
    us10y = pulse.get("US10Y", {})
    vix = pulse.get("VIX", {})
    nq = pulse.get("NQ", {})
    es = pulse.get("ES", {})
    ym = pulse.get("YM", {})
    
    def fmt(item, unit=""):
        if item.get("price") is None:
            return "`N/A`"
        pct_sign = "+" if item.get("change_pct", 0) >= 0 else ""
        return f"`{item['price']:.2f}{unit}` ({pct_sign}{item.get('change_pct', 0):.2f}%)"

    lines = [
        f"💵 **DXY:** {fmt(dxy)} • 🏛️ **US10Y:** {fmt(us10y, '%')} • ⚡ **VIX:** {fmt(vix)}",
        f"💻 **NQ:** {fmt(nq)} • 📊 **ES:** {fmt(es)} • 🏭 **YM:** {fmt(ym)}",
        f"📌 **บรรยากาศ:** *{pulse.get('sentiment_summary')}*",
        f"⚖️ **Pre-News Drift:** {pulse.get('positioning_risk')}"
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Real-time Pre-News Market Pulse")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()
    
    pulse = get_market_pulse()
    if args.json:
        print(json.dumps(pulse, ensure_ascii=False, indent=2))
    else:
        print(format_pulse_text(pulse))


if __name__ == "__main__":
    main()
