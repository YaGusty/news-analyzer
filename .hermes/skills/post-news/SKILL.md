---
name: post-news
description: "Use when analyzing the actual released numbers post-news and reporting market impacts to Discord (/post-news)."
metadata:
  hermes:
    tags: [macro, flash, post-news, actual, reaction]
---

# post-news Skill

ใช้เมื่อตัวเลขเศรษฐกิจประกาศออกมาแล้ว และต้องการวิเคราะห์ด่วนทันที (Flash Analysis)

## คำสั่ง:
`/post-news <EVENT> <ACTUAL>` เช่น `/post-news "CPI" 2.6%`, `/post-news "NFP" 150k`

## ขั้นตอนการทำงาน:
1. รันสคริปต์ Flash Analysis:
   - รันในเทอร์มินัล: `python scripts/main.py flash "<EVENT>" "<ACTUAL>"`
   - พร้อมส่งเข้า Discord: `python scripts/main.py flash "<EVENT>" "<ACTUAL>" --discord`
2. ระบบจะทำการ:
   - เปรียบเทียบ Actual vs Consensus vs Previous
   - จัดหมวดหมู่ผลลัพธ์เป็น **HAWKISH** (เงินเฟ้อ/แรงงานร้อนกว่าคาด), **DOVISH** (เงินเฟ้อ/แรงงานชะลอตัว), หรือ **IN-LINE**
   - ประเมินผลกระทบต่อ NQ, ES, YM และแนวโน้มดอกเบี้ยของ Fed
   - บันทึกรายงานฉบับเต็มลงใน `data/reports/flash_<EVENT>_<DATE>.md`
