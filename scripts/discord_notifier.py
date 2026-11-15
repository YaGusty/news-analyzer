"""
Discord Notifier for News Analyzer
Dispatches rich, beautiful Discord Embed notifications for Red Folder US Economic Events,
Forecasts, and Flash Post-News Analyses affecting NAS100, S&P 500, and Dow Jones.
"""

import sys
import os
import json
import argparse
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def load_webhook_url():
    """Load DISCORD_WEBHOOK_URL from .env or environment variable."""
    if os.environ.get("DISCORD_WEBHOOK_URL"):
        return os.environ.get("DISCORD_WEBHOOK_URL").strip()
        
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DISCORD_WEBHOOK_URL="):
                    url = line.split("=", 1)[1].strip()
                    if url and not url.startswith("#"):
                        return url
    return ""


# Discord Embed Color Constants
COLOR_RED = 0xE74C3C     # Hawkish / Hot inflation / Alert
COLOR_GREEN = 0x2ECC71   # Dovish / Soft landing / Cool data
COLOR_BLUE = 0x3498DB    # Weekly Radar / Calendar
COLOR_GOLD = 0xF1C40F    # Pre-News Forecast / In-line scenario
COLOR_PURPLE = 0x9B59B6  # FOMC / Powell Speech special


def send_discord_payload(payload: dict, webhook_url: str = None) -> tuple[bool, str]:
    """Send payload to Discord Webhook. Returns (success, message)."""
    url = webhook_url or load_webhook_url()
    
    if not url:
        return False, "DISCORD_WEBHOOK_URL is not set. Please set it in .env or pass --webhook."
        
    if not url.startswith("https://discord.com/api/webhooks/") and not url.startswith("https://discordapp.com/api/webhooks/"):
        return False, f"Invalid Discord webhook URL format: {url[:30]}..."
        
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 204):
            return True, "Notification successfully sent to Discord!"
        else:
            return False, f"Discord API returned status {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, f"Failed to send Discord webhook: {str(e)}"


def format_forecast_embed(analysis: dict) -> dict:
    """
    Format in-depth Pre-News Forecast into a high-signal Discord Embed.
    """
    event_name = analysis.get("event", "US Macro Event")
    bkk_time = analysis.get("time_bkk", "-")
    ny_time = analysis.get("time_ny", "-")
    consensus = analysis.get("consensus", "-")
    previous = analysis.get("previous", "-")
    period = analysis.get("period", "")
    
    embed = {
        "title": f"🔴 [FORECAST] {event_name} {f'({period})' if period else ''}",
        "description": (
            f"**Macro Economic Briefing & Index Sensitivity Forecast**\n"
            f"📅 **เวลาประกาศ:** {bkk_time}\n"
            f"🏛️ **NY Time:** {ny_time}\n"
            f"📊 **Consensus (คาดการณ์):** `{consensus}` | **Previous (ครั้งก่อน):** `{previous}`"
        ),
        "color": COLOR_GOLD,
        "fields": [],
        "footer": {
            "text": "News Analyzer • Macro Intelligence (NAS100 / SP500 / DOW)"
        }
    }
    
    # Core Index Impacts
    if analysis.get("nas100_impact"):
        embed["fields"].append({
            "name": "💻 NAS100 (NQ) Sensitivity",
            "value": analysis["nas100_impact"][:1024],
            "inline": False
        })
        
    if analysis.get("sp500_impact"):
        embed["fields"].append({
            "name": "📊 S&P 500 (ES) Sensitivity",
            "value": analysis["sp500_impact"][:1024],
            "inline": False
        })
        
    if analysis.get("dow_impact"):
        embed["fields"].append({
            "name": "🏭 Dow Jones (YM) Sensitivity",
            "value": analysis["dow_impact"][:1024],
            "inline": False
        })

    # Intermarket (DXY & US10Y)
    if analysis.get("intermarket"):
        embed["fields"].append({
            "name": "🌐 Intermarket Anchor (DXY & US10Y)",
            "value": analysis["intermarket"][:1024],
            "inline": False
        })
        
    # 3-Scenario Forecast Matrix
    scenarios = []
    if analysis.get("scenario_hot"):
        scenarios.append(f"🔴 **Hot / Hawkish:** {analysis['scenario_hot']}")
    if analysis.get("scenario_cool"):
        scenarios.append(f"🟢 **Cool / Dovish:** {analysis['scenario_cool']}")
    if analysis.get("scenario_inline"):
        scenarios.append(f"🟡 **In-line / Mixed:** {analysis['scenario_inline']}")
        
    if scenarios:
        embed["fields"].append({
            "name": "🎯 Scenario Matrix & Deviation Forecast",
            "value": "\n\n".join(scenarios)[:1024],
            "inline": False
        })
        
    return {
        "username": "News Analyzer",
        "avatar_url": "https://img.icons8.com/color/96/bullish.png",
        "embeds": [embed]
    }


def format_flash_embed(flash_data: dict) -> dict:
    """
    Format Post-News Flash analysis into a Discord Embed.
    """
    event_name = flash_data.get("event", "US Macro Event")
    actual = flash_data.get("actual", "-")
    consensus = flash_data.get("consensus", "-")
    previous = flash_data.get("previous", "-")
    verdict = flash_data.get("verdict", "NEUTRAL")  # HAWKISH / DOVISH / MIXED
    
    color = COLOR_RED if verdict == "HAWKISH" else (COLOR_GREEN if verdict == "DOVISH" else COLOR_GOLD)
    verdict_emoji = "🔴" if verdict == "HAWKISH" else ("🟢" if verdict == "DOVISH" else "🟡")
    
    embed = {
        "title": f"⚡ [FLASH REPORT] {event_name} ออกแล้ว!",
        "description": (
            f"**ผลการประกาศตัวเลขเศรษฐกิจจริงเทียบกับคาดการณ์**\n"
            f"• **Actual (ตัวเลขจริง):** **`{actual}`**\n"
            f"• **Consensus (คาดการณ์):** `{consensus}`\n"
            f"• **Previous (ครั้งก่อน):** `{previous}`\n"
            f"• **Macro Verdict:** {verdict_emoji} **{verdict}**"
        ),
        "color": color,
        "fields": [],
        "footer": {
            "text": "News Analyzer • Fast Flash Reaction"
        }
    }
    
    if flash_data.get("summary"):
        embed["fields"].append({
            "name": "📌 Key Takeaways & Economic Meaning",
            "value": flash_data["summary"][:1024],
            "inline": False
        })
        
    if flash_data.get("market_reaction"):
        embed["fields"].append({
            "name": "📊 Index Reaction Dynamics (NQ, ES, YM)",
            "value": flash_data["market_reaction"][:1024],
            "inline": False
        })
        
    if flash_data.get("fed_outlook"):
        embed["fields"].append({
            "name": "🏛️ Fed Interest Rate Expectation Shift",
            "value": flash_data["fed_outlook"][:1024],
            "inline": False
        })

    return {
        "username": "News Analyzer",
        "avatar_url": "https://img.icons8.com/color/96/bullish.png",
        "embeds": [embed]
    }


def format_weekly_radar_embed(events: list) -> dict:
    """Format upcoming weekly events into a clean Discord calendar radar."""
    embed = {
        "title": "📡 [WEEKLY RADAR] Red Folder US Economic Calendar",
        "description": (
            f"สรุปตารางข่าวกล่องแดงสำคัญที่มีผลต่อ **NAS100, S&P 500, Dow Jones** ในรอบสัปดาห์นี้\n"
            f"*(แปลงเวลาเป็นเวลาไทย UTC+7 เรียบร้อยแล้ว)*"
        ),
        "color": COLOR_BLUE,
        "fields": [],
        "footer": {
            "text": "News Analyzer • Weekly Radar"
        }
    }
    
    if not events:
        embed["fields"].append({
            "name": "🗓️ สถานะข่าวสัปดาห์นี้",
            "value": "ไม่มีข่าว Tier-1 / Red Folder ในสัปดาห์นี้ หรือตัวเลขยังไม่อัปเดต",
            "inline": False
        })
    else:
        # Group or list top events
        lines = []
        for i, e in enumerate(events[:12], 1):
            forecast_str = f"Exp: `{e['forecast']}`" if e.get("forecast") is not None else "Exp: `N/A`"
            prev_str = f"Prev: `{e['previous']}`" if e.get("previous") is not None else ""
            status_tag = f"({e['time_relative']})"
            
            lines.append(
                f"**{i}. {e['title']}**\n"
                f"⏰ `{e['date_bkk']}` | `{e['date_ny']}` {status_tag}\n"
                f"📊 {forecast_str} {('• ' + prev_str) if prev_str else ''}\n"
            )
            
        embed["fields"].append({
            "name": "🗓️ รายการข่าวกล่องแดง (USD High-Impact)",
            "value": "\n".join(lines)[:1024],
            "inline": False
        })
        
    embed["fields"].append({
        "name": "💡 Focus Indices",
        "value": (
            "• **NAS100:** จับตาดอกเบี้ย/Bond Yield กระทบ Tech Valuation\n"
            "• **S&P 500:** ชี้วัดภาพรวมเศรษฐกิจและ Earnings Guidance\n"
            "• **Dow Jones:** ไวต่อยอดค้าปลีก, PMI ภาคการผลิต และ GDP"
        ),
        "inline": False
    })
    
    return {
        "username": "News Analyzer",
        "avatar_url": "https://img.icons8.com/color/96/bullish.png",
        "embeds": [embed]
    }


def test_webhook(webhook_url: str = None) -> bool:
    """Send a test message to confirm webhook functionality."""
    url = webhook_url or load_webhook_url()
    if not url:
        print("[!] DISCORD_WEBHOOK_URL is not set.")
        print("To configure:")
        print("1. In Discord: Open Channel Settings -> Integrations -> Webhooks -> New Webhook")
        print("2. Copy Webhook URL")
        print(f"3. Paste into '{ENV_PATH}' as DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...")
        return False
        
    test_payload = {
        "username": "News Analyzer",
        "avatar_url": "https://img.icons8.com/color/96/bullish.png",
        "embeds": [{
            "title": "✅ News Analyzer Connection Test",
            "description": "Discord Webhook เชื่อมต่อกับระบบ **News Analyzer** สำเร็จเรียบร้อย!\nพร้อมส่งข้อมูล คาดการณ์ และวิเคราะห์ข่าวกล่องแดง (NAS100, S&P 500, Dow) แล้วครับ",
            "color": COLOR_GREEN,
            "fields": [
                {"name": "Status", "value": "🟢 Active & Online", "inline": True},
                {"name": "Focus Targets", "value": "NAS100, S&P 500, Dow Jones, DXY", "inline": True}
            ],
            "footer": {"text": "News Analyzer • Discord Gateway"}
        }]
    }
    
    print(f"Sending test alert to Discord webhook ({url[:35]}...)...")
    success, msg = send_discord_payload(test_payload, url)
    print(msg)
    return success


def main():
    parser = argparse.ArgumentParser(description="Discord Notifier for News Analyzer")
    parser.add_argument("--test", action="store_true", help="Send test webhook message")
    parser.add_argument("--webhook", type=str, help="Specify webhook URL directly")
    args = parser.parse_args()
    
    if args.test:
        test_webhook(args.webhook)
    else:
        url = args.webhook or load_webhook_url()
        if url:
            print(f"[OK] Webhook configured: {url[:35]}...")
        else:
            print("[!] Webhook not configured in .env")


if __name__ == "__main__":
    main()
