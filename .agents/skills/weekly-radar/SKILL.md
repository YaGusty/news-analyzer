---
name: weekly-radar
description: >-
  Use when generating and sending the weekly red folder economic news radar to Discord.
---

# weekly-radar Skill

ใช้เมื่อต้องการดูภาพรวมหรือส่งตารางข่าวกล่องแดงประจำสัปดาห์เข้า Discord

## ขั้นตอนการทำงาน:
1. รันคำสั่ง: `python scripts/main.py calendar --discord --refresh`
2. ระบบจะดึงตารางข่าว USD ทั้งสัปดาห์ กรองเฉพาะระดับ High Impact / Red Folder แปลงเวลาเป็นเวลาไทย (UTC+7) และยิงการแจ้งเตือนแบบ Rich Embed สีฟ้าเข้า Discord ทันที
3. สรุปความเสี่ยงรายวันให้ผู้ใช้ทราบว่าวันไหนมีข่าวที่มีน้ำหนักสูงสุดแห่งสัปดาห์
