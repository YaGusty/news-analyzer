---
name: discord-alert
description: "Use when testing or managing Discord notifications for News Analyzer (/discord)."
metadata:
  hermes:
    tags: [discord, webhook, notification, test]
---

# discord-alert Skill

ใช้เมื่อต้องการทดสอบหรือตรวจสอบการเชื่อมต่อกับ Discord Webhook

## คำสั่ง:
- `/discord test` — ทดสอบยิงข้อความทดสอบเข้า Discord
- `/discord status` — ตรวจสอบสถานะ Webhook URL ใน `.env`

## ขั้นตอนการทำงาน:
1. หากต้องการทดสอบ: รัน `python scripts/main.py test-discord`
2. หากยังไม่ได้ใส่ Webhook:
   - แนะนำวิธีสร้าง Webhook ใน Discord:
     1. ไปที่ Discord Server -> Channel Settings (รูปฟันเฟืองห้องแชท)
     2. เมนู Integrations -> Webhooks -> New Webhook
     3. กด Copy Webhook URL
     4. นำ URL มาใส่ในไฟล์ `.env` ที่บรรทัด `DISCORD_WEBHOOK_URL=...`
