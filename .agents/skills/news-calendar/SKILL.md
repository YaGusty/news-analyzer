---
name: news-calendar
description: >-
  Use when checking upcoming US Red Folder economic news calendar or when the user asks to view or refresh the economic schedule.
---

# news-calendar Skill

ใช้เมื่อผู้ใช้ต้องการดูตารางข่าวเศรษฐกิจสหรัฐฯ กล่องแดง (Red Folder News)

## ขั้นตอนการทำงาน:
1. รันคำสั่งผ่าน terminal:
   - ดูข่าวทั้งสัปดาห์: `python scripts/main.py calendar`
   - ดูข่าวเฉพาะวันนี้: `python scripts/main.py calendar --today`
   - รีเฟรชข้อมูลล่าสุด: `python scripts/main.py calendar --refresh`
   - ส่งเข้า Discord ด้วย: `python scripts/main.py calendar --discord`
2. สรุปผลให้ผู้ใช้ทราบ:
   - วันและเวลา (ระบุเวลาไทย UTC+7 และเวลา NY เสมอ)
   - ตัวเลขคาดการณ์ (Consensus) เทียบกับครั้งก่อน (Previous)
   - ระดับความสำคัญและดัชนีที่คาดว่าจะได้รับผลกระทบสูงสุด
