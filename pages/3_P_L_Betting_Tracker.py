"""หน้าระบบคำนวณกำไร/ขาดทุน"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

from analyze import (
    SYMBOL_EMOJI,
    SYMBOLS,
    add_bet,
    calculate_pnl,
    load,
    load_betting,
    save_betting,
    update_bet_results,
)

st.set_page_config(
    page_title="P&L & Betting Tracker",
    page_icon="💰",
    layout="wide",
)

CHOICES = [f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}" for i in range(1, 7)]
NAME_TO_ID = {f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}": i for i in range(1, 7)}


def render_betting_form(db: dict, betting_data: dict) -> None:
    """ฟอร์มบันทึกการแทง"""
    st.subheader("📝 บันทึกการแทง")
    
    with st.form("betting_form", clear_on_submit=False):
        a, b, c = st.columns([1, 1, 1])
        
        # เลือกงวด
        draw_options = [d["id"] for d in sorted(db["draws"], key=lambda x: x["id"], reverse=True)]
        if not draw_options:
            st.warning("ยังไม่มีงวดในคลัง — เพิ่มงวดที่หน้า Data Management ก่อน")
            return
        
        draw_id = a.selectbox("เลขงวด", draw_options, key="bet_draw_id")
        
        # เลือกสัญลักษณ์ที่จะแทง
        selected_symbols = b.multiselect(
            "เลือกสัญลักษณ์ที่จะแทง (เลือกได้หลายตัว)",
            CHOICES,
            key="bet_symbols"
        )
        
        # จำนวนเงิน
        amount = c.number_input("จำนวนเงินทุน", min_value=0.0, value=100.0, step=10.0, key="bet_amount")
        
        # เลือกสกุลเงิน
        currency = st.selectbox("สกุลเงิน", ["LAK", "THB"], key="bet_currency")
        
        submitted = st.form_submit_button("บันทึกการแทง", type="primary", width="stretch")
    
    if submitted:
        if not selected_symbols:
            st.error("กรุณาเลือกสัญลักษณ์ที่จะแทงอย่างน้อย 1 ตัว")
            return
        
        if amount <= 0:
            st.error("กรุณาระบุจำนวนเงินทุนมากกว่า 0")
            return
        
        # แปลงสัญลักษณ์เป็น ID
        symbol_ids = [NAME_TO_ID[s] for s in selected_symbols]
        
        try:
            add_bet(db, betting_data, draw_id, symbol_ids, amount, currency)
            st.success(f"บันทึกการแทงแล้ว: งวด {draw_id}, แทง {', '.join(selected_symbols)}, จำนวน {amount} {currency}")
            st.rerun()
        except ValueError as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")


def render_betting_history(betting_data: dict) -> None:
    """แสดงประวัติการแทง"""
    st.subheader("📋 ประวัติการแทง")
    
    if not betting_data["bets"]:
        st.caption("ยังไม่มีประวัติการแทง")
        return
    
    # แปลงข้อมูลเป็น DataFrame
    rows = []
    for bet in sorted(betting_data["bets"], key=lambda x: x["id"], reverse=True):
        symbols_str = ", ".join([f"{SYMBOL_EMOJI[s]} {SYMBOLS[s]}" for s in bet["symbols"]])
        status_emoji = {"pending": "⏳", "won": "✅", "lost": "❌"}[bet["status"]]
        
        rows.append({
            "ID": bet["id"],
            "งวด": bet["draw_id"],
            "เวลาแทง": bet["created_at"],
            "สัญลักษณ์ที่แทง": symbols_str,
            "จำนวนเงิน": f"{bet['amount']:.2f} {bet['currency']}",
            "สถานะ": f"{status_emoji} {bet['status'].title()}",
            "ผลลัพธ์": bet["result"] if bet["result"] is not None else "-",
            "อัตราจ่าย": f"{bet['payout']:.2f} {bet['currency']}" if bet["payout"] > 0 else "-",
            "กำไร/ขาดทุน": f"{bet['profit']:+.2f} {bet['currency']}" if bet["profit"] != 0 else "-"
        })
    
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True, height=300, use_container_width=True)


def render_pnl_dashboard(betting_data: dict) -> None:
    """แดชบอร์ดสรุปทางการเงิน"""
    st.subheader("💰 แดชบอร์ดสรุปทางการเงิน")
    
    if not betting_data["bets"]:
        st.caption("ยังไม่มีข้อมูลการแทง — บันทึกการแทงเพื่อดูสรุปทางการเงิน")
        return
    
    pnl = calculate_pnl(betting_data)
    
    # แสดง metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ยอดเงินลงทุนรวม", f"{pnl['total_invested']:.2f}", help="เงินทุนทั้งหมดที่ใช้แทง")
    c2.metric("ยอดเงินรางวัลรวม", f"{pnl['total_payout']:.2f}", help="เงินรางวัลทั้งหมดที่ได้รับ")
    c3.metric("กำไร/ขาดทุนสุทธิ", f"{pnl['net_pnl']:+.2f}", delta=f"{pnl['roi']:+.1f}%", delta_color="normal")
    c4.metric("อัตราชนะ", f"{pnl['win_rate']:.1f}%", help=f"ชนะ {pnl['won_bets']} จาก {pnl['total_bets']} ครั้ง")
    
    # กราฟเส้นแสดงแนวโน้มเงินทุน
    st.subheader("📈 แนวโน้มเงินทุนสะสม")
    
    # เตรียมข้อมูลสำหรับกราฟ
    cumulative_pnl = []
    running_total = 0
    bet_dates = []
    
    for bet in sorted(betting_data["bets"], key=lambda x: x["id"]):
        running_total += bet["profit"]
        cumulative_pnl.append(running_total)
        bet_dates.append(bet["created_at"])
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=bet_dates,
        y=cumulative_pnl,
        mode='lines+markers',
        name='กำไร/ขาดทุนสะสม',
        line=dict(color='#1B7A4B', width=2),
        marker=dict(size=6)
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    
    fig.update_layout(
        title="แนวโน้มกำไร/ขาดทุนสะสม",
        xaxis_title="เวลา",
        yaxis_title="กำไร/ขาดทุนสะสม",
        height=400,
        hovermode="x unified"
    )
    
    st.plotly_chart(fig, width="stretch")
    
    # กราฟวงกลมแสดงสัดส่วนผลการแทง
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎯 สัดส่วนผลการแทง")
        pie_data = {
            "ชนะ": pnl["won_bets"],
            "แพ้": pnl["lost_bets"],
            "รอผล": pnl["pending_bets"]
        }
        
        fig_pie = px.pie(
            values=list(pie_data.values()),
            names=list(pie_data.keys()),
            hole=0.4,
            color_discrete_sequence=["#1B7A4B", "#C45C26", "#C49A26"]
        )
        fig_pie.update_layout(height=300)
        st.plotly_chart(fig_pie, width="stretch")
    
    with col2:
        st.subheader("📊 สถิติการแทง")
        stats_data = [
            {"รายการ": "ทั้งหมด", "จำนวน": pnl["total_bets"]},
            {"รายการ": "ชนะ", "จำนวน": pnl["won_bets"]},
            {"รายการ": "แพ้", "จำนวน": pnl["lost_bets"]},
            {"รายการ": "รอผล", "จำนวน": pnl["pending_bets"]}
        ]
        stats_df = pd.DataFrame(stats_data)
        st.dataframe(stats_df, width="stretch", hide_index=True, use_container_width=True)


def render_tracker_page(db: dict, betting_data: dict) -> None:
    st.title("💰 P&L & Betting Tracker")
    
    # อัปเดตผลการแทงอัตโนมัติ
    betting_data = update_bet_results(db, betting_data)
    
    # แสดงแดชบอร์ดสรุปทางการเงิน
    render_pnl_dashboard(betting_data)
    
    st.divider()
    
    # ฟอร์มบันทึกการแทง
    render_betting_form(db, betting_data)
    
    st.divider()
    
    # ประวัติการแทง
    render_betting_history(betting_data)


def main() -> None:
    db = load()
    betting_data = load_betting()
    render_tracker_page(db, betting_data)


if __name__ == "__main__":
    main()