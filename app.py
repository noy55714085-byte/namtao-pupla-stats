"""หน้าหลัก (Landing Page) สำหรับ Multi-page Streamlit Application"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="น้ำเต้าปูปลา · Multi-Page App",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_landing_page() -> None:
    st.title("🎲 สถิติน้ำเต้าปูปลา · Multi-Page Application")
    
    st.markdown("""
    ## 📋 เมนูหลัก
    
    แอปพลิเคชันนี้มี 3 หน้าหลัก สามารถเลือกใช้งานได้จากเมนูด้านซ้าย:
    
    ### 📊 **Data Management** (ศูนย์จัดการประวัติผล)
    - เพิ่ม/แก้ไข/ลบงวด
    - ตารางสรุปประวัติย้อนหลังทั้งหมด
    - ระบบค้นหา/กรองตามช่วงเวลา
    
    ### 🧠 **Multi-Model Predictor & Backtest** (วิเคราะห์และเปรียบเทียบโมเดล)
    - คำนวณความน่าจะเป็นจาก 5 โมเดล:
      - Time-Slot Weighted Model
      - Markov Chain Model
      - Hot/Cold Exponential Decay Model
      - Combination & Pair Dice Model
      - Ensemble Hybrid Model
    - ตารางเปรียบเทียบ % โอกาสออกของทั้ง 6 สัญลักษณ์
    - ระบบ Backtesting วัดความแม่นยำย้อนหลัง
    
    ### 💰 **P&L & Betting Tracker** (ระบบคำนวณกำไร/ขาดทุน)
    - บันทึกการแทง (เลขงวด, สัญลักษณ์, จำนวนเงิน)
    - ตรวจผลรางวัลอัตโนมัติ
    - คำนวณอัตราจ่ายและกำไร/ขาดทุน
    - แดชบอร์ดสรุปทางการเงิน
    
    ---
    
    ## 🔧 ฟีเจอร์พิเศษ
    
    - **GitHub Storage** - ข้อมูลถูกบันทึกลง GitHub อัตโนมัติ (ป้องกันข้อมูลหายบน Streamlit Cloud)
    - **Hybrid Storage** - ใช้ Local Storage + GitHub Storage ร่วมกัน
    - **Auto Sync** - ทุกครั้งที่บันทึกข้อมูล จะ sync กับ GitHub อัตโนมัติ
    
    ---
    
    ## 🚀 เริ่มต้นใช้งาน
    
    เลือกหน้าที่ต้องการจากเมนูด้านซ้าย หรือคลิกที่ปุ่มด้านล่าง:
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 ไปหน้า Data Management", use_container_width=True):
            st.switch_page("pages/1_Data_Management.py")
    
    with col2:
        if st.button("🧠 ไปหน้า Multi-Model Predictor", use_container_width=True):
            st.switch_page("pages/2_Multi_Model_Predictor.py")
    
    with col3:
        if st.button("💰 ไปหน้า P&L Tracker", use_container_width=True):
            st.switch_page("pages/3_P_L_Betting_Tracker.py")
    
    st.divider()
    
    st.markdown("""
    ## 📝 ข้อมูลเพิ่มเติม
    
    - **เวอร์ชัน**: 2.0 (Multi-Page Edition)
    - **ฐานข้อมูล**: JSON + SQLite (Local) + GitHub (Cloud)
    - **เทคโนโลยี**: Python + Streamlit + Plotly + Pandas
    
    สำหรับข้อมูลเพิ่มเติม ดูไฟล์ README.md
    """)


def main() -> None:
    render_landing_page()


if __name__ == "__main__":
    main()