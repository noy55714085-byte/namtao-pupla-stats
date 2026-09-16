# สถิติน้ำเต้าปูปลา (Streamlit Multi-Page Application)

เว็บแอปวิเคราะห์ความน่าจะเป็นจากประวัติลูกเต๋า 3 ลูก พร้อมระบบ Multi-Page Application ที่มี 3 หน้าหลัก

## ✨ คุณสมบัติพิเศษ (เวอร์ชัน 2.0)

- **Multi-Page Application** - 3 หน้าหลักที่ใช้ฐานข้อมูลร่วมกัน
- **GitHub Storage** - ข้อมูลถูกบันทึกลง GitHub อัตโนมัติ (ป้องกันข้อมูลหายบน Streamlit Cloud)
- **Hybrid Storage** - ใช้ Local Storage + GitHub Storage ร่วมกัน
- **Auto Sync** - ทุกครั้งที่บันทึกข้อมูล จะ sync กับ GitHub อัตโนมัติ
- **Multi-Model Analysis** - วิเคราะห์จาก 5 โมเดลพร้อมระบบ Backtest
- **Betting Tracker** - ระบบบันทึกการแทงและคำนวณกำไร/ขาดทุน

## 📋 หน้าหลักทั้ง 3 หน้า

### 📊 หน้า 1: Data Management (ศูนย์จัดการประวัติผล)
- ฟอร์มเพิ่มงวดใหม่, แก้ไขข้อมูลย้อนหลัง, ลบงวด
- ตารางสรุปประวัติย้อนหลังทั้งหมด
- ระบบค้นหา/กรองตามช่วงเวลา

### 🧠 หน้า 2: Multi-Model Predictor & Backtest (วิเคราะห์และเปรียบเทียบโมเดล)
- คำนวณความน่าจะเป็นจาก 5 โมเดล:
  1. Time-Slot Weighted Model (เน้นช่วงเวลา 40%)
  2. Markov Chain Model (เน้นการเปลี่ยนผ่านงวดถัดไป)
  3. Hot/Cold Exponential Decay Model (เน้นงวดล่าสุด)
  4. Combination & Pair Dice Model (เน้นโอกาสเบิ้ล/ตอง)
  5. Ensemble Hybrid Model (ค่าเฉลี่ยรวมทุกโมเดล)
- ตารางเปรียบเทียบ % โอกาสออกของทั้ง 6 สัญลักษณ์
- ระบบ Backtesting: วัดความแม่นยำย้อนหลังของทั้ง 5 โมเดล

### 💰 หน้า 3: P&L & Betting Tracker (ระบบคำนวณกำไร/ขาดทุน)
- ฟอร์มบันทึกการแทง: เลขงวด, สัญลักษณ์ที่เลือกแทง, จำนวนเงินทุน
- ตรวจผลรางวัลให้อัตโนมัติเมื่อมีการเพิ่มผลรางวัล
- คำนวณอัตราจ่าย (Payout Ratio) ตามผลลูกเต๋า
- แดชบอร์ดสรุปทางการเงิน: ยอดเงินลงทุนรวม, ยอดเงินรางวัลรวม, กำไร/ขาดทุนสุทธิ, และ % ROI

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
3. ตั้งชื่อ: `namtao-pupla-stats`
4. เลือก scope: `repo` (หรือ `public_repo` ถ้า repository เป็น public)
5. กด **Generate token**
6. **คัดลอก token** (จะแสดงครั้งเดียวเท่านั้น!)

### 2. ตั้งค่าใน Streamlit Community Cloud
1. เข้า https://share.streamlit.io
2. เลือกแอปของคุณ
3. ไปที่ **Settings** → **Secrets**
4. เพิ่ม secret:
   ```
   GITHUB_TOKEN = "your_github_personal_access_token_here"
   ```
5. กด **Save**
6. **Redeploy** แอป

### 3. สำหรับ Local Development
คัดลอกไฟล์ `.streamlit/secrets.toml.example` เป็น `.streamlit/secrets.toml` และใส่ token ของคุณ:
```toml
GITHUB_TOKEN = "your_github_personal_access_token_here"
```

## โครงสร้างโปรเจกต์

```
Luncky/
├── app.py                          # หน้าหลัก (Landing Page)
├── analyze.py                      # เอนจินสถิติ + บันทึกคลัง + GitHub Storage
├── github_storage.py               # จัดการ GitHub API
├── requirements.txt                # ไลบรารี
├── pages/
│   ├── 1_Data_Management.py        # หน้าจัดการข้อมูล
│   ├── 2_Multi_Model_Predictor.py  # หน้าวิเคราะห์โมเดล
│   └── 3_P_L_Betting_Tracker.py    # หน้าระบบคำนวณกำไร/ขาดทุน
├── data/
│   ├── history.json                # ประวัติหลัก (local)
│   ├── history.sqlite              # สำเนา SQLite (local)
│   └── betting.json                # ข้อมูลการแทง (local)
├── .streamlit/
│   ├── config.toml                 # การตั้งค่า Streamlit
│   └── secrets.toml                # Secrets (GitHub Token)
└── README.md                       # คำอธิบายโปรเจกต์
```

## ระบบบันทึกข้อมูล

### Local Storage (ค่าเริ่มต้น)
- บันทึกลง `data/history.json` (JSON format)
- บันทึกสำเนาลง `data/history.sqlite` (SQLite format)
- บันทึกข้อมูลการแทงลง `data/betting.json`
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
4. หลังจากตั้งค่า secrets แล้ว แอปจะ redeploy อัตโนมัติเมื่อมีการ push ข้อมูลใหม่ขึ้น GitHub

## 📝 ข้อควรระวัง

- **Local Development**: ข้อมูลจะถูกบันทึกลงเครื่องเท่านั้น (ไม่ sync กับ GitHub ถ้าไม่มี token)
- **Streamlit Cloud**: ต้องมี `GITHUB_TOKEN` ใน Streamlit Secrets ถึงจะบันทึกลง GitHub ได้
- **GitHub API Rate Limit**: ถ้าไม่มี token จะโหลดได้แต่บันทึกไม่ได้
- **Data Sync**: ข้อมูลจะ sync กับ GitHub ทุกครั้งที่บันทึก/แก้ไข/ลบ
- **Multi-Page**: ทุกหน้าใช้ฐานข้อมูลร่วมกัน ข้อมูลจะอัปเดตตรงกันอัตโนมัติ

## อัตราจ่าย (Payout Ratio)

- ออก 1 ลูกตรง = ได้ 1 เท่า
- ออก 2 ลูกตรง = ได้ 2 เท่า
- ออก 3 ลูกตรง = ได้ 3 เท่า
- ออกไม่ตรงเลย = เสียทั้งหมด

## 🎯 สรุป

ตอนนี้แอปของคุณมี:
- ✅ **Multi-Page Application** - 3 หน้าหลักที่ใช้ฐานข้อมูลร่วมกัน
- ✅ **Hybrid Storage** - Local + GitHub ร่วมกัน
- ✅ **Auto Sync** - บันทึกลง GitHub อัตโนมัติ
- ✅ **Persistent Data** - ข้อมูลไม่หายแม้ redeploy
- ✅ **Multi-Model Analysis** - 5 โมเดลพร้อม Backtest
- ✅ **Betting Tracker** - ระบบบันทึกการแทงและคำนวณกำไร/ขาดทุน
- ✅ **Free Solution** - ใช้ GitHub ที่มีอยู่แล้ว ไม่ต้องจ่ายเพิ่ม

**โปรเจกต์พร้อม Deploy และข้อมูลจะไม่หายแล้วครับ!** 🎲✨