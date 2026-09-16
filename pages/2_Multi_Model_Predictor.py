"""หน้าวิเคราะห์และเปรียบเทียบโมเดล"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from analyze import (
    DEFAULT_SCHEDULE,
    SYMBOL_EMOJI,
    SYMBOLS,
    load,
    multi_model_backtest,
    multi_model_predict,
)

st.set_page_config(
    page_title="Multi-Model Predictor",
    page_icon="🧠",
    layout="wide",
)


def render_model_comparison_table(comparison_df: pd.DataFrame) -> None:
    """แสดงตารางเปรียบเทียบโมเดล"""
    st.subheader("📊 เปรียบเทียบ % โอกาสออกของทั้ง 6 สัญลักษณ์")
    st.dataframe(comparison_df, width="stretch", hide_index=True, use_container_width=True)


def render_model_prediction(db: dict, slot: str) -> None:
    """แสดงผลการทำนายจากทุกโมเดล"""
    pred = multi_model_predict(db, None if slot == "อัตโนมัติ (งวดถัดไป)" else slot)
    
    if pred["next_id"] is None:
        st.warning("ยังไม่มีประวัติในคลัง — เพิ่มงวดแรกที่หน้า Data Management")
        return
    
    c1, c2, c3 = st.columns(3)
    c1.metric("งวดถัดไป", str(pred["next_id"]))
    c2.metric("รอบที่คำนวณ", pred["next_time"])
    c3.metric("จำนวนงวดในคลัง", len(db["draws"]))
    
    # แสดงตารางเปรียบเทียบ
    render_model_comparison_table(pred["comparison"])
    
    # แสดงกราฟเปรียบเทียบ
    st.subheader("📈 กราฟเปรียบเทียบโมเดล")
    
    # เตรียมข้อมูลสำหรับกราฟ
    models = pred["models"]
    model_names = ["Time-Slot", "Markov", "Hot/Cold", "Combo", "Ensemble"]
    
    fig_data = []
    for i in range(1, 7):
        for model_name in model_names:
            model_key = model_name.lower().replace("/", "").replace(" ", "")
            if model_key == "hot/cold":
                model_key = "hotcold"
            fig_data.append({
                "สัญลักษณ์": f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}",
                "โมเดล": model_name,
                "เปอร์เซ็นต์": models[model_key][i]
            })
    
    fig_df = pd.DataFrame(fig_data)
    fig = px.bar(
        fig_df,
        x="สัญลักษณ์",
        y="เปอร์เซ็นต์",
        color="โมเดล",
        barmode="group",
        title="เปรียบเทียบความน่าจะเป็นของแต่ละโมเดล",
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig.update_layout(
        xaxis_title="",
        yaxis_title="เปอร์เซ็นต์ (%)",
        height=500,
        hovermode="x unified"
    )
    st.plotly_chart(fig, width="stretch")


def render_backtest_results(db: dict) -> None:
    """แสดงผลการ Backtest"""
    st.subheader("🎯 วัดความแม่นยำย้อนหลัง (Backtest)")
    
    min_h = st.slider("ใช้ประวัติอย่างน้อยกี่งวดก่อนเริ่มวัด", 10, max(11, len(db["draws"]) - 1), min(20, len(db["draws"]) - 1))
    
    if len(db["draws"]) < min_h + 5:
        st.warning(f"ข้อมูลยังไม่พอสำหรับ backtest (ต้องมีอย่างน้อย {min_h + 5} งวด)")
        return
    
    backtest_results = multi_model_backtest(db, min_history=min_h)
    
    # สรุปผล
    st.caption("วัดความแม่นยำโดยใช้ประวัติก่อนหน้างวดนั้นคำนวณ แล้วเช็กว่าตัวเต็งอันดับ 1 ออกใน 3 ลูกหรือไม่")
    
    # แสดงตารางสรุป
    summary_data = []
    for model_name, results in backtest_results.items():
        summary_data.append({
            "โมเดล": model_name.title(),
            "ทายอันดับ 1 ถูก (%)": f"{results['top1_pct']:.1f}%",
            "Top 3 ออกอย่างน้อย 1 (%)": f"{results['top3_pct']:.1f}%",
            "จำนวนงวดที่วัด": results['total_tests']
        })
    
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, width="stretch", hide_index=True, use_container_width=True)
    
    # หาโมเดลที่แม่นยำที่สุด
    best_model = max(backtest_results.items(), key=lambda x: x[1]["top1_pct"])
    best_model_name = best_model[0].title()
    best_accuracy = best_model[1]["top1_pct"]
    
    st.success(f"🏆 โมเดลที่แม่นยำที่สุดในปัจจุบัน: **{best_model_name}** ด้วยความแม่นยำ {best_accuracy:.1f}%")
    
    # กราฟเปรียบเทียบความแม่นยำ
    chart_data = []
    for model_name, results in backtest_results.items():
        chart_data.append({
            "โมเดล": model_name.title(),
            "ความแม่นยำ (%)": results["top1_pct"]
        })
    
    chart_df = pd.DataFrame(chart_data)
    fig = px.bar(
        chart_df,
        x="โมเดล",
        y="ความแม่นยำ (%)",
        title="เปรียบเทียบความแม่นยำของแต่ละโมเดล",
        color="ความแม่นยำ (%)",
        color_continuous_scale="RdYlGn"
    )
    fig.update_layout(
        xaxis_title="",
        yaxis_title="ความแม่นยำ (%)",
        height=400
    )
    st.plotly_chart(fig, width="stretch")


def render_predictor_page(db: dict) -> None:
    st.title("🧠 Multi-Model Predictor & Backtest")
    
    # เลือกรอบเวลา
    slot_choice = ["อัตโนมัติ (งวดถัดไป)"] + list(db.get("schedule_times") or DEFAULT_SCHEDULE)
    slot = st.selectbox("รอบที่จะคำนวณ (Time-Slot)", slot_choice)
    
    # แสดงผลการทำนาย
    render_model_prediction(db, slot)
    
    st.divider()
    
    # แสดงผลการ Backtest
    render_backtest_results(db)


def main() -> None:
    db = load()
    render_predictor_page(db)


if __name__ == "__main__":
    main()