# สถิติน้ำเต้าปูปลา (Streamlit)

เว็บแอปวิเคราะห์ความน่าจะเป็นจากประวัติลูกเต๋า 3 ลูก น้ำหนักโมเดล: Time-Slot 40% + Markov 30% + Dice Combination 20% + Hot/Cold 10%

ข้อมูลถูกบันทึกอัตโนมัติที่ `data/history.json` และสำเนา `data/history.sqlite` — ปิดเว็บแล้วเปิดใหม่ข้อมูลไม่หาย

## ✨ คุณสมบัติพิเศษ

- **GitHub Storage** - ข้อมูลถูกบันทึกลง GitHub อัตโนมัติ (ป้องกันข้อมูลหายบน Streamlit Cloud)
- **Hybrid Storage** - ใช้ Local Storage + GitHub Storage ร่วมกัน
- **Auto Sync** - ทุกครั้งที่บันทึกข้อมูล จะ sync กับ GitHub อัตโนมัติ

## ติดตั้งและรัน

วิธีที่เร็วที่สุดบนเครื่องนี้ (มี Python พกไปกับโปรเจกต์แล้ว):

```powershell
cd F:\Luncky
.\run.bat
```

หรือ:

```powershell
cd F:\Luncky
.\.tools\python\python.exe -m streamlit run app.py
```

ถ้าติดตั้ง Python เองในระบบ:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## ตั้งค่า GitHub Storage (สำหรับ Streamlit Cloud)

### 1. สร้าง GitHub Personal Access Token
1. เข้า https://github.com/settings/tokens
2. กด **Generate new token** → **Generate new token (classic)**
3. ตั้งชื่อ (เช่น `namtao-pupla-stats`)
4. เลือก scope: `repo` (หรือ `public_repo` ถ้า repository เป็น public)
5. กด **Generate token**
6. **คัดลอก token** (จะแสดงครั้งเดียวเท่านั้น)

### 2. ตั้งค่าใน Streamlit Community Cloud
1. เข้า https://share.streamlit.io
2. เลือกแอปของคุณ
3. ไปที่ **Settings** → **Secrets**
4. เพิ่ม secret:
   ```
   GITHUB_TOKEN = "your_github_personal_access_token_here"
   ```
5. กด **Save**

### 3. สำหรับ Local Development
คัดลอกไฟล์ `.streamlit/secrets.toml.example` เป็น `.streamlit/secrets.toml` และใส่ token ของคุณ:

```toml
GITHUB_TOKEN = "your_github_personal_access_token_here"
```

## วิธีใช้อย่างย่อ

1. แท็บ **แดชบอร์ด** — ดู % ทั้ง 6 ตัว, Top 3, กราฟ, Confidence และเลือก **รอบเวลา** ที่แถบข้าง
2. แท็บ **จัดการประวัติ** หรือฟอร์มข้างจอ — เพิ่ม / แก้ไข / ลบงวด แล้วโมเดลคำนวณใหม่ทันที
3. แท็บ **สถิติและความแม่นยำ** — ความถี่รวม, Hot/Cold, วัดทายย้อนหลังเทียบเส้นสุ่ม (~42% สำหรับตัวเต็งอันดับ 1)
4. แท็บ **นำเข้า / สำรอง** — ดาวน์โหลด JSON/SQLite หรือวางหลายงวดทีเดียวเมื่ออัปเดตรายเดือน

รูปแบบวางหลายงวด:

```
36260204,2026-09-16 12:05,4,6,1
```

เลขสัญลักษณ์: 1 ปู, 2 ปลา, 3 น้ำเต้า, 4 เสือ, 5 ไก่, 6 กุ้ง

ส่งรูปรายเดือนมาเพิ่มในคลังได้ — ยิ่งงวดมาก backtest จะบอกได้ชัดขึ้นว่าโมเดลดีกว่าสุ่มหรือไม่

## ไฟล์หลัก

- `app.py` — UI Streamlit
- `analyze.py` — เอนจินสถิติ + บันทึกคลัง + GitHub Storage
- `github_storage.py` — จัดการ GitHub API สำหรับ persistent storage
- `data/history.json` — ประวัติหลัก (local)
- `data/history.sqlite` — สำเนา SQLite (local)
- `requirements.txt` — ไลบรารี

## ระบบบันทึกข้อมูล

### Local Storage (ค่าเริ่มต้น)
- บันทึกลง `data/history.json` (JSON format)
- บันทึกสำเนาลง `data/history.sqlite` (SQLite format)
- ข้อมูลคงอยู่ถาวรบนเครื่อง

### GitHub Storage (สำหรับ Streamlit Cloud)
- บันทึกลง GitHub repository อัตโนมัติ
- ต้องมี `GITHUB_TOKEN` ใน secrets
- ข้อมูลคงอยู่ถาวรแม้ redeploy แอป
- Hybrid Storage: ใช้ Local + GitHub ร่วมกัน

### การทำงาน
1. **โหลดข้อมูล**: ลอง Local → ถ้าไม่มี ลอง GitHub → ถ้าไม่มี สร้างใหม่
2. **บันทึกข้อมูล**: บันทึก Local → บันทึก GitHub (ถ้ามี token)
3. **การ Sync**: ทุกครั้งที่บันทึก จะ sync กับ GitHub อัตโนมัติ

## Deploy บน Streamlit Community Cloud

1. ดูคำแนะนำที่ [GitHub Repository](https://github.com/noy55714085-byte/namtao-pupla-stats)
2. ตั้งค่า `GITHUB_TOKEN` ใน Streamlit Secrets
3. Deploy ปกติตามขั้นตอน Streamlit Community Cloud

## 📝 ข้อควรระวัง

- **Local Development**: ข้อมูลจะถูกบันทึกลงเครื่องเท่านั้น (ไม่ sync กับ GitHub ถ้าไม่มี token)
- **Streamlit Cloud**: ต้องมี `GITHUB_TOKEN` ถึงจะบันทึกลง GitHub ได้
- **GitHub API Rate Limit**: ถ้าไม่มี token จะโหลดได้แต่บันทึกไม่ได้
- **Data Sync**: ข้อมูลจะ sync กับ GitHub ทุกครั้งที่บันทึก/แก้ไข/ลบ