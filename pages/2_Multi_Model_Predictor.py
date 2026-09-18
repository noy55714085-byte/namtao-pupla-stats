"""หน้าวิเคราะห์และเปรียบเทียบโมเดล"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from analyze import (
    DEFAULT_SCHEDULE,
    SYMBOL_EMOJI,
    SYMBOLS,
    calculate_pair_ranking,
    detailed_backtest_matrix,
    detailed_model_breakdown,
    get_top_pairs,
    leaderboard_metrics,
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
            model_key = model_name.lower().replace("/", "").replace(" ", "").replace("-", "")
            if model_key == "hotcold":
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


def render_detailed_breakdown(db: dict, slot: str) -> None:
    """แสดงผลการทำนายแบบละเอียดยิบแยกตามโมเดล"""
    pred = multi_model_predict(db, None if slot == "อัตโนมัติ (งวดถัดไป)" else slot)
    
    if pred["next_id"] is None:
        st.warning("ยังไม่มีประวัติในคลัง — เพิ่มงวดแรกที่หน้า Data Management")
        return
    
    st.subheader("🎯 การทำนายงวดถัดไปแบบละเอียด (Next Draw Detailed Breakdown)")
    
    model_descriptions = {
        "Time-Slot": "เน้นช่วงเวลา 40%",
        "Markov": "เน้นการเปลี่ยนผ่านงวด 30%",
        "Hot/Cold": "เน้นแนวโน้มล่าสุด 10%",
        "Combo": "เน้นลูกเต๋าคู่/เบิ้ล/ตอง 20%",
        "Ensemble": "โมเดลรวมพลัง (ค่าเฉลี่ย)"
    }
    
    # ใช้ Tabs แยกตามโมเดล
    tabs = st.tabs([
        "⏰ Time-Slot Model",
        "🔗 Markov Chain Model", 
        "🔥 Hot/Cold Exponential",
        "🎲 Combination & Pair",
        "🌟 Ensemble Hybrid"
    ])
    
    model_names = ["Time-Slot", "Markov", "Hot/Cold", "Combo", "Ensemble"]
    
    for tab, model_name in zip(tabs, model_names):
        with tab:
            breakdown = detailed_model_breakdown(pred["models"], model_name, pred["next_time"])
            
            st.markdown(f"### {model_name} Model")
            st.caption(model_descriptions[model_name])
            
            # แสดง Top 1, Top 2, Top 3
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    f"🥇 Top 1: {breakdown['top1']['emoji']} {breakdown['top1']['name']}",
                    f"{breakdown['top1']['percentage']:.1f}%",
                    help=breakdown['top1']['reason']
                )
                st.caption(breakdown['top1']['reason'])
            
            with col2:
                st.metric(
                    f"🥈 Top 2: {breakdown['top2']['emoji']} {breakdown['top2']['name']}",
                    f"{breakdown['top2']['percentage']:.1f}%",
                    help=breakdown['top2']['reason']
                )
                st.caption(breakdown['top2']['reason'])
            
            with col3:
                st.metric(
                    f"🥉 Top 3: {breakdown['top3']['emoji']} {breakdown['top3']['name']}",
                    f"{breakdown['top3']['percentage']:.1f}%",
                    help=breakdown['top3']['reason']
                )
                st.caption(breakdown['top3']['reason'])
            
            # แสดง Confidence Level
            confidence_color = {"ต่ำ": "#C45C26", "ปานกลาง": "#C49A26", "สูง": "#1B7A4B"}[breakdown['confidence']]
            st.markdown(
                f"<div style='background:white;border:1px solid #d5e4da;border-radius:16px;padding:18px;'>"
                f"<div style='font-size:1.5rem;font-weight:700;color:{confidence_color}'>{breakdown['confidence']}</div>"
                f"<div class='hint'>ระดับความมั่นใจของโมเดลนี้</div></div>",
                unsafe_allow_html=True,
            )


def render_co_occurrence_analysis(db: dict, slot: str) -> None:
    """แสดงผล Co-occurrence Matrix Analysis สำหรับคู่แทง"""
    pred = multi_model_predict(db, None if slot == "อัตโนมัติ (งวดถัดไป)" else slot)
    
    if pred["next_id"] is None:
        st.warning("ยังไม่มีประวัติในคลัง — เพิ่มงวดแรกที่หน้า Data Management")
        return
    
    st.subheader("🎲 วิเคราะห์การจับคู่ด้วย Co-occurrence Matrix")
    st.caption("คำนวณสถิติว่าสัญลักษณ์ใดบ้างที่มักจะ 'ออกคู่กันในงวดเดียวกัน' บ่อยที่สุด")
    
    # ใช้คะแนนจาก Ensemble Model เป็นฐาน
    ensemble_prob = pred["models"]["ensemble"]
    
    # คำนวณ Top 3 คู่
    top_pairs = get_top_pairs(db, ensemble_prob, top_n=3)
    
    if not top_pairs:
        st.warning("ข้อมูลยังไม่เพียงพอสำหรับวิเคราะห์การจับคู่ (ต้องมีอย่างน้อย 10 งวด)")
        return
    
    # แสดง Top 3 คู่เด็ด
    st.markdown("### 🏆 Top 3 คู่เด็ดประจำงวด")
    
    for i, pair_data in enumerate(top_pairs, 1):
        col1, col2, col3, col4 = st.columns([1, 2, 2, 2])
        
        with col1:
            st.markdown(f"#### {i}")
        
        with col2:
            st.markdown(f"**{pair_data['emoji1']} {pair_data['name1']} + {pair_data['emoji2']} {pair_data['name2']}**")
        
        with col3:
            st.metric(
                "คะแนนรวม",
                f"{pair_data['combined_score']:.1f}%",
                help=f"Co-occurrence: {pair_data['co_occurrence_rate']:.1f}% + Individual: {pair_data['individual_avg_prob']:.1f}%"
            )
        
        with col4:
            st.metric(
                "ออกคู่กัน",
                f"{pair_data['co_occurrence_count']} ครั้ง",
                help=f"อัตราการออกคู่กัน: {pair_data['co_occurrence_rate']:.1f}%"
            )
        
        st.caption(f"Co-occurrence Rate: {pair_data['co_occurrence_rate']:.1f}% | Individual Avg Prob: {pair_data['individual_avg_prob']:.1f}%")
        st.divider()
    
    # แสดงตารางคู่ทั้งหมด
    st.markdown("### 📊 ตารางคะแนนคู่ทั้งหมด (All 15 Pairs)")
    
    all_pairs = calculate_pair_ranking(db, ensemble_prob)
    
    # สร้าง DataFrame สำหรับแสดง
    pair_data = []
    for pair in all_pairs:
        pair_data.append({
            "คู่": f"{pair['emoji1']} {pair['name1']} + {pair['emoji2']} {pair['name2']}",
            "คะแนนรวม (%)": f"{pair['combined_score']:.1f}%",
            "ออกคู่กัน (ครั้ง)": pair['co_occurrence_count'],
            "อัตรา Co-occurrence (%)": f"{pair['co_occurrence_rate']:.1f}%",
            "ค่าเฉลี่ยความน่าจะเป็น (%)": f"{pair['individual_avg_prob']:.1f}%"
        })
    
    pair_df = pd.DataFrame(pair_data)
    st.dataframe(pair_df, width="stretch", hide_index=True, use_container_width=True)


def render_backtest_results(db: dict) -> None:
    """แสดงผลการ Backtest"""
    st.subheader("🎯 วัดความแม่นยำย้อนหลัง (Backtest)")
    
    min_h = st.slider("ใช้ประวัติอย่างน้อยกี่งวดก่อนเริ่มวัด", 10, max(11, len(db["draws"]) - 1), min(20, len(db["draws"]) - 1))
    
    if len(db["draws"]) < min_h + 5:
        st.warning(f"ข้อมูลยังไม่พอสำหรับ backtest (ต้องมีอย่างน้อย {min_h + 5} งวด)")
        return
    
    # แสดงตารางย้อนหลังแบบละเอียด
    render_detailed_backtest_matrix(db, min_h)
    
    # แสดง Leaderboard
    render_leaderboard(db, min_h)
    
    # สรุปผลเดิม
    backtest_results = multi_model_backtest(db, min_history=min_h)
    
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


def render_detailed_backtest_matrix(db: dict, min_history: int) -> None:
    """แสดงตารางตรวจผลย้อนหลังรายงวดแบบละเอียด"""
    st.subheader("📊 ตารางตรวจผลย้อนหลังรายงวดแบบละเอียด (Detailed Historical Hit Matrix)")
    
    matrix = detailed_backtest_matrix(db, min_history)
    rows = matrix["rows"]
    model_names = matrix["model_names"]
    
    if not rows:
        st.warning("ยังไม่มีข้อมูลเพียงพอสำหรับตารางย้อนหลัง")
        return
    
    # สร้าง DataFrame สำหรับแสดง
    display_data = []
    for row in rows:
        display_row = {
            "งวด": row["งวด"],
            "รอบเวลา": row["รอบเวลา"],
            "ผลรางวัลจริง": row["ผลรางวัลจริง_emoji"],
            "แชมป์ประจำงวด": row["แชมป์ประจำงวด"]
        }
        
        # เพิ่มข้อมูลจากแต่ละโมเดล
        for model_name in model_names:
            display_row[f"{model_name.title()}_Top1"] = f"{row[f'{model_name}_top1']} ({row[f'{model_name}_top1_status']})"
            display_row[f"{model_name.title()}_Top2"] = f"{row[f'{model_name}_top2']} ({row[f'{model_name}_top2_status']})"
            display_row[f"{model_name.title()}_Top3"] = f"{row[f'{model_name}_top3']} ({row[f'{model_name}_top3_status']})"
        
        display_data.append(display_row)
    
    df = pd.DataFrame(display_data)
    
    # ใช้ st.dataframe แบบ interactive
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        height=400,
        use_container_width=True,
        column_config={
            "งวด": st.column_config.NumberColumn("งวด", width="small"),
            "รอบเวลา": st.column_config.TextColumn("รอบเวลา", width="small"),
            "ผลรางวัลจริง": st.column_config.TextColumn("ผลรางวัลจริง", width="medium"),
            "แชมป์ประจำงวด": st.column_config.TextColumn("แชมป์ประจำงวด", width="medium")
        }
    )


def render_leaderboard(db: dict, min_history: int) -> None:
    """แสดงสรุปเหรียญรางวัลความแม่นยำ (Leaderboard Metrics)"""
    st.subheader("🏆 สรุปเหรียญรางวัลความแม่นยำ (Leaderboard Metrics)")
    
    leaderboard = leaderboard_metrics(db, min_history)
    
    # สร้าง DataFrame สำหรับ Leaderboard
    leaderboard_data = []
    for model_name, metrics in leaderboard.items():
        leaderboard_data.append({
            "โมเดล": model_name.title(),
            "อัตราเข้าเป้า Top 1 ตรงๆ (%)": f"{metrics['top1_exact_hit_rate']:.1f}%",
            "อัตราเข้าเป้าอย่างน้อย 1 ตัวใน Top 3 (%)": f"{metrics['top3_any_hit_rate']:.1f}%",
            "อัตราเข้าเป้าพร้อมกัน 2 ตัวขึ้นใน Top 3 (%)": f"{metrics['top3_double_hit_rate']:.1f}%",
            "จำนวนงวดที่วัด": metrics['total_tests']
        })
    
    leaderboard_df = pd.DataFrame(leaderboard_data)
    
    # จัดเรียงตามอัตราเข้าเป้า Top 1
    leaderboard_df = leaderboard_df.sort_values(by="อัตราเข้าเป้า Top 1 ตรงๆ (%)", ascending=False)
    
    st.dataframe(
        leaderboard_df,
        width="stretch",
        hide_index=True,
        use_container_width=True,
        column_config={
            "โมเดล": st.column_config.TextColumn("โมเดล", width="medium"),
            "อัตราเข้าเป้า Top 1 ตรงๆ (%)": st.column_config.NumberColumn("Top 1 ตรงๆ (%)", format="%.1f%%"),
            "อัตราเข้าเป้าอย่างน้อย 1 ตัวใน Top 3 (%)": st.column_config.NumberColumn("Top 3 อย่างน้อย 1 (%)", format="%.1f%%"),
            "อัตราเข้าเป้าพร้อมกัน 2 ตัวขึ้นใน Top 3 (%)": st.column_config.NumberColumn("Top 3 พร้อมกัน 2 ตัว (%)", format="%.1f%%"),
            "จำนวนงวดที่วัด": st.column_config.NumberColumn("จำนวนงวดที่วัด", width="small")
        }
    )
    
    # แสดงชนะเลิศ
    if not leaderboard_df.empty:
        champion = leaderboard_df.iloc[0]
        st.success(f"🥇 แชมป์ปัจจุบัน: **{champion['โมเดล']}** ด้วยอัตราเข้าเป้า Top 1 ตรงๆ {champion['อัตราเข้าเป้า Top 1 ตรงๆ (%)']}")


def render_predictor_page(db: dict) -> None:
    st.title("🧠 Multi-Model Predictor & Backtest")
    
    # เลือกรอบเวลา
    slot_choice = ["อัตโนมัติ (งวดถัดไป)"] + list(db.get("schedule_times") or DEFAULT_SCHEDULE)
    slot = st.selectbox("รอบที่จะคำนวณ (Time-Slot)", slot_choice)
    
    # แสดงผลการทำนาย
    render_model_prediction(db, slot)
    
    st.divider()
    
    # แสดงผลการทำนายแบบละเอียด
    render_detailed_breakdown(db, slot)
    
    st.divider()
    
    # แสดงผล Co-occurrence Analysis
    render_co_occurrence_analysis(db, slot)
    
    st.divider()
    
    # แสดงผลการ Backtest
    render_backtest_results(db)


def main() -> None:
    db = load()
    render_predictor_page(db)


if __name__ == "__main__":
    main()
