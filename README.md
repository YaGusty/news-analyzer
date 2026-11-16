# 🔴 News Analyzer

ระบบวิเคราะห์ คาดการณ์ และรายงานข่าวเศรษฐกิจสหรัฐฯ กล่องแดง (**Red Folder News**) ที่มีผลต่อดัชนี **NAS100 (NQ)**, **S&P 500 (ES)**, และ **Dow Jones (YM)** พร้อมระบบแจ้งเตือนเข้า **Discord Webhook** แบบ Rich Embeds อัตโนมัติ

---

## 🚀 ฟังก์ชันหลัก (Core Features)

1. **🔴 Red Folder Calendar Fetcher:** ดึงตารางข่าวเศรษฐกิจสำคัญของสหรัฐฯ อัตโนมัติ กรองเฉพาะระดับ High-Impact แปลงเวลาเป็นเวลาไทย (BKK UTC+7) และเวลานิวยอร์ก (ET) พร้อมคำนวณเวลานับถอยหลัง
2. **🔮 Macro Forecasting & 3-Scenario Matrix:** วิเคราะห์ความสำคัญของตัวเลข ชี้วัดผลกระทบเจาะจงต่อ Tech (NAS100), Broad Market (S&P 500), Cyclicals (Dow) และประเมินฉากทัศน์ล่วงหน้า 3 กรณี (Hot / Cool / In-line)
3. **⚡ Post-News Flash Report:** ประเมินตัวเลขจริงทันทีหลังประกาศ (Actual vs Consensus) สรุปทิศทางดอกเบี้ย Fed และปฏิกิริยาของตลาด
4. **💬 Discord Webhook Integration:** จัดรูปแบบข้อความแบบ Rich Embed สีสันชัดเจน (แดง = Hawkish / เขียว = Dovish / ฟ้า = Weekly / เหลือง = Forecast) ส่งตรงถึง Discord ของคุณ

---

## 🛠️ การตั้งค่าเริ่มต้น (Setup)

### 1. ตั้งค่า Discord Webhook
1. ใน Discord ไปที่ห้องที่ต้องการรับการแจ้งเตือน → กดรูปฟันเฟือง **Edit Channel**
2. ไปที่แถบ **Integrations** → เลือก **Webhooks** → กด **New Webhook**
3. ตั้งชื่อบอท (เช่น `News Analyzer`) แล้วกด **Copy Webhook URL**
4. เปิดไฟล์ `.env` แล้ววาง URL ลงไป:
   ```env
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456789/abcdef...
   ```

### 2. ทดสอบการเชื่อมต่อ
```bash
python scripts/main.py test-discord
```

---

## 📖 วิธีใช้งานผ่านคำสั่ง CLI (Usage)

### 1. ดูตารางข่าวกล่องแดง (Calendar)
```bash
# ดูข่าวกล่องแดงทั้งสัปดาห์
python scripts/main.py calendar

# ดูข่าวเฉพาะวันนี้
python scripts/main.py calendar --today

# ดูข่าวทั้งสัปดาห์พร้อมส่งสรุปเข้า Discord
python scripts/main.py calendar --discord
```

### 2. วิเคราะห์และคาดการณ์ก่อนข่าวออก (Pre-News Forecast)
```bash
# วิเคราะห์ข่าว Retail Sales ล่วงหน้า
python scripts/main.py forecast "Retail Sales"

# วิเคราะห์พร้อมส่งการ์ดเข้า Discord
python scripts/main.py forecast "Retail Sales" --discord

# วิเคราะห์ข่าว CPI โดยระบุตัวเลขคาดการณ์เอง
python scripts/main.py forecast "CPI" --consensus "2.6%" --previous "2.4%" --discord
```

### 3. วิเคราะห์ด่วนหลังตัวเลขออก (Post-News Flash)
```bash
# วิเคราะห์ตัวเลขจริงที่เพิ่งประกาศ พร้อมส่งเข้า Discord
python scripts/main.py flash "Retail Sales" "0.4%" --discord
```

### 4. ตรวจสอบ Market Pulse แบบเรียลไทม์ (DXY, US10Y, VIX, NQ, ES, YM)
```bash
# ดูบรรยากาศตลาดและตัวเลขอ้างอิงก่อนข่าวออก
python scripts/main.py pulse
```

### 5. เปิดระบบมอนิเตอร์และส่งแจ้งเตือนอัตโนมัติ (Automated Scheduler)
```bash
# เช็ครอบเดียว (Single Tick) เหมาะกับตั้ง Task Scheduler หรือ Cron
python scripts/main.py scheduler --check-once

# รัน Background มอนิเตอร์อัตโนมัติ (ตรวจจับ T-60 นาที และยิงเตือนก่อนข่าวออกทันที)
python scripts/main.py scheduler --daemon --interval 60
```

---

## 🤖 การใช้งานร่วมกับ AI (Antigravity Workspace Skills)

เมื่อใช้งานผ่าน Antigravity ระบบจะตรวจจับกฎของโปรเจกต์จาก `GEMINI.md` (หรือ `AGENTS.md`) และโหลด Skills จาก `.agents/skills/` โดยอัตโนมัติ:
- `news-calendar` — ดูตารางข่าวกล่องแดงสัปดาห์นี้หรือวันนี้
- `news-forecast` — วิเคราะห์เจาะลึกข่าวเศรษฐกิจล่วงหน้า
- `post-news` — วิเคราะห์ด่วนหลังตัวเลขจริงออก
- `weekly-radar` — ส่งสรุปตารางข่าวทั้งสัปดาห์เข้า Discord
- `discord-alert` — ทดสอบและจัดการการแจ้งเตือน Discord

---

## 📂 โครงสร้างโฟลเดอร์

```text
news-analyzer/
├── .env                  # ตั้งค่า Discord Webhook URL
├── config.json           # การตั้งค่า Timezone, ดัชนีเป้าหมาย และ Keywords
├── GEMINI.md             # กฎและขอบเขตของโปรเจกต์สำหรับ Antigravity
├── AGENTS.md             # กฎมาตรฐาน Multi-Agent Instructions
├── scripts/
│   ├── calendar_fetcher.py # ดึงตารางข่าวและแคชข้อมูล
│   ├── analyzer.py         # โมเดลวิเคราะห์มหภาคและ 3 ฉากทัศน์
│   ├── discord_notifier.py # ส่งการแจ้งเตือนเข้า Discord Webhook
│   ├── market_pulse.py     # ดึง Market Sentiment (DXY, US10Y, VIX)
│   ├── alert_scheduler.py  # ระบบตั้งเวลาแจ้งเตือนก่อนข่าวออก
│   └── main.py             # จุดรวมคำสั่ง Master CLI
├── data/
│   ├── calendar/           # แคชตารางข่าวเศรษฐกิจ
│   └── reports/            # บันทึกไฟล์บทวิเคราะห์ Markdown
└── .agents/skills/       # Antigravity Workspace Skills
```
