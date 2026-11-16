---
name: news-forecast
description: >-
  Use when analyzing and forecasting the macro impact of upcoming Red Folder news on NAS100, S&P 500, and Dow Jones.
---

# news-forecast Skill

ใช้เมื่อต้องการวิเคราะห์เจาะลึกและคาดการณ์ผลกระทบของข่าวเศรษฐกิจก่อนประกาศจริง

## คำสั่ง:
`forecast <EVENT>` เช่น `CPI`, `NFP`, `"Retail Sales"`, `FOMC`

## ขั้นตอนการทำงาน:
1. หากผู้ใช้ไม่ได้ระบุ event ให้ตรวจสอบตารางข่าวที่กำลังจะมาถึงจาก `python scripts/main.py calendar`
2. รันสคริปต์วิเคราะห์:
   - วิเคราะห์ทั่วไป: `python scripts/main.py forecast "<EVENT>"`
   - พร้อมส่งเข้า Discord: `python scripts/main.py forecast "<EVENT>" --discord`
   - สามารถระบุตัวเลขคาดการณ์เองได้: `python scripts/main.py forecast "<EVENT>" --consensus "2.6%" --previous "2.4%" --discord`
3. สรุปผล 4 องค์ประกอบสำคัญ:
   - **ความสำคัญเชิงมหภาค (Macro Significance):** ชี้วัดอะไร ทำไมตลาดถึงกลัวหรือรอคอย
   - **Index Sensitivity:** ผลกระทบเจาะจงต่อ NAS100 (Tech), S&P 500 (Broad Market), และ Dow Jones (Cyclicals)
   - **Intermarket Dynamics:** ทิศทางของ DXY (ดอลลาร์) และ US10Y (Bond Yield)
   - **3-Scenario Matrix:** คาดการณ์ทิศทางหากตัวเลขออกมาร้อนแรง (Hot), เย็นลง (Cool), หรือเป็นไปตามคาด (In-line)
