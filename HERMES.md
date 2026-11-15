# Project: News Analyzer

**What this is:** ระบบค้นหาข้อมูล คาดการณ์ วิเคราะห์ข่าวเศรษฐกิจสหรัฐฯ กล่องแดง (Red Folder News) ที่ส่งผลต่อ **NAS100**, **S&P 500**, และ **Dow Jones** พร้อมระบบส่งสรุปและแจ้งเตือนเข้า **Discord** โดยอัตโนมัติ

## กฎและขอบเขตของโปรเจกต์ (Scope & Principles)

1. **เน้นที่ข่าวอย่างเดียว (Pure News & Macro Intelligence):**
   - โฟกัสที่: การหาข้อมูล, การคาดการณ์ (Forecast), การวิเคราะห์ผลกระทบเชิงมหภาค (Macro Analysis) และการแจ้งเตือนเข้า Discord
   - **ไม่ต้องทำเรื่องการเทรด:** ไม่ยุ่งกับ Position, Lot Size, จุดเข้าซื้อ, Stop Loss หรือกลยุทธ์การกดออเดอร์
2. **ดัชนีและสินทรัพย์เป้าหมาย:**
   - **NAS100 (NQ / QQQ):** หุ้นเทคโนโลยีและการเติบโต ไวต่ออัตราผลตอบแทนพันธบัตร (Yield) และ P/E Valuation
   - **S&P 500 (ES / SPY):** ดัชนีภาพรวมตลาด บาลานซ์ระหว่าง Tech, การเงิน และอุตสาหกรรม
   - **Dow Jones (YM / DIA):** หุ้นคุณค่าและวัฏจักร (Cyclicals & Industrials) ไวต่อยอดค้าปลีกและ GDP
   - **Intermarket Anchors:** DXY (Dollar Index) และ US10Y (10-Year Treasury Yield)
3. **การแปลงเวลา:**
   - ต้องระบุทั้ง **New York Time (ET)** และ **เวลาไทย (UTC+7 / BKK Time)** เสมอ
4. **Python Environment:**
   - ใช้ `python` (Python 3.13) สำหรับรันสคริปต์ใน `scripts/` ห้ามใช้ `python3`

## Directory Structure

- `scripts/`:
  - `calendar_fetcher.py` — ดึงตารางข่าวกล่องแดง (Red Folder) USD อัตโนมัติ พร้อม Cache และแปลงเวลาไทย/NY
  - `analyzer.py` — วิเคราะห์เจาะลึก 3 Scenarios (Hot / Cool / In-line) และประเมิน NQ, ES, YM
  - `discord_notifier.py` — จัดรูปแบบ Discord Embeds สวยงาม พร้อมส่งผ่าน Discord Webhook
  - `main.py` — Master CLI จัดการทุกฟังก์ชัน
- `data/`:
  - `calendar/` — แคชตารางข่าวเศรษฐกิจ
  - `reports/` — รายงานวิเคราะห์คาดการณ์ (Forecast) และรายงานหลังข่าวออก (Flash Report) ในรูปแบบ Markdown
- `.hermes/skills/`:
  - `news-calendar` (`/calendar`) — ดูตารางข่าวกล่องแดงวันนี้ / สัปดาห์นี้
  - `news-forecast` (`/forecast <event>`) — หาข้อมูลและวิเคราะห์คาดการณ์ 3 ฉากทัศน์
  - `post-news` (`/post-news <event> <actual>`) — วิเคราะห์ผลตัวเลขจริงทันทีหลังประกาศ
  - `weekly-radar` (`/weekly-radar`) — ส่งสรุปภาพรวมข่าวสำคัญทั้งสัปดาห์เข้า Discord
  - `discord-alert` (`/discord`) — ทดสอบหรือส่งการแจ้งเตือนเข้า Discord
- `.env`:
  - ตั้งค่า `DISCORD_WEBHOOK_URL` สำหรับส่งการแจ้งเตือน

## Slash Commands & Workflows

1. **`/calendar`**: ตรวจสอบตารางข่าวกล่องแดงสัปดาห์นี้หรือวันนี้
2. **`/forecast <event>`**: วิเคราะห์เจาะลึกข่าว เช่น `/forecast CPI` หรือ `/forecast "Retail Sales"`
3. **`/post-news <event> <actual>`**: วิเคราะห์ด่วนหลังตัวเลขออก เช่น `/post-news "CPI" 2.6%`
4. **`/weekly-radar`**: ดึงตารางข่าวทั้งสัปดาห์และยิงสรุปเข้า Discord
5. **`/discord test`**: ทดสอบการเชื่อมต่อ Discord Webhook
