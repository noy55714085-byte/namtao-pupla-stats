"""ระบบบิลซื้อและคำนวณกำไร/ขาดทุน น้ำเต้าปูปลา."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analyze import (
    SYMBOL_EMOJI, SYMBOLS, add_ticket, calculate_pnl, clear_ticket_draft,
    delete_ticket, get_top_pairs, load, load_betting, load_ticket_draft,
    multi_model_predict, save_ticket_draft, update_bet_results, update_ticket,
)

st.set_page_config(page_title="P&L & Betting Tracker", page_icon="💰", layout="wide")
CHOICES = [f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}" for i in range(1, 7)]
NAME_TO_ID = {choice: i for i, choice in zip(range(1, 7), CHOICES)}


def money(value: float, currency: str = "LAK") -> str:
    return f"{value:,.0f} {currency}"


def reset_ticket_editor() -> None:
    st.session_state.ticket_rows = 1
    st.session_state.edit_ticket_id = None
    for key in list(st.session_state):
        if key.startswith(("ticket_type_", "ticket_symbols_", "ticket_amount_")):
            st.session_state.pop(key, None)


def start_edit_ticket(ticket: dict) -> None:
    """เลื่อนการกำหนดค่าไปก่อนสร้าง widget ในรอบถัดไป."""
    st.session_state.pending_ticket_edit = ticket


def set_ticket_rows(rows: list[dict]) -> None:
    st.session_state.ticket_rows = len(rows)
    for index, row in enumerate(rows):
        st.session_state[f"ticket_type_{index}"] = "แทงเดี่ยว (1 สัญลักษณ์)" if row["type"] == "single" else "แทงคู่ (2 สัญลักษณ์)"
        st.session_state[f"ticket_amount_{index}"] = float(row["amount"])
        st.session_state[f"ticket_symbols_{index}"] = [CHOICES[symbol - 1] for symbol in row["symbols"]]


def ticket_rows_from_state() -> list[dict]:
    rows = []
    for index in range(st.session_state.get("ticket_rows", 1)):
        rows.append({
            "type": "single" if st.session_state.get(f"ticket_type_{index}") == "แทงเดี่ยว (1 สัญลักษณ์)" else "pair",
            "symbols": [NAME_TO_ID[item] for item in st.session_state.get(f"ticket_symbols_{index}", [])],
            "amount": st.session_state.get(f"ticket_amount_{index}", 0.0),
        })
    return rows


def load_draft_into_state(draw_options: list[int]) -> None:
    """เติม session state จาก JSON เพียงครั้งแรกของ session นี้."""
    if st.session_state.pop("ticket_editor_reset_pending", False):
        reset_ticket_editor()
    pending_edit = st.session_state.pop("pending_ticket_edit", None)
    if pending_edit:
        st.session_state.edit_ticket_id = pending_edit["id"]
        st.session_state.ticket_draw_id = pending_edit["draw_id"]
        st.session_state.ticket_currency = pending_edit.get("currency", "LAK")
        set_ticket_rows(pending_edit["rows"])
        st.session_state.ticket_draft_loaded = True
        return
    pending_rows = st.session_state.pop("pending_ticket_rows", None)
    if pending_rows is not None:
        set_ticket_rows(pending_rows)
        st.session_state.ticket_draft_loaded = True
        return
    if st.session_state.get("ticket_draft_loaded"):
        return
    draft = load_ticket_draft() or {}
    rows = draft.get("rows") or [{"type": "single", "symbols": [], "amount": 10000.0}]
    st.session_state.edit_ticket_id = draft.get("edit_ticket_id")
    st.session_state.ticket_draw_id = draft.get("draw_id") if draft.get("draw_id") in draw_options else draw_options[0]
    st.session_state.ticket_currency = draft.get("currency", "LAK")
    set_ticket_rows(rows)
    st.session_state.ticket_draft_loaded = True


def persist_ticket_draft(rows: list[dict] | None = None) -> None:
    """เก็บทุกค่าปัจจุบันของฟอร์ม เพื่อให้กลับมาแก้ต่อหลัง reboot ได้."""
    save_ticket_draft({
        "draw_id": st.session_state.get("ticket_draw_id"),
        "currency": st.session_state.get("ticket_currency", "LAK"),
        "rows": ticket_rows_from_state() if rows is None else rows,
        "edit_ticket_id": st.session_state.get("edit_ticket_id"),
    })


def render_pair_recommendations(db: dict) -> None:
    """แสดงคำแนะนำคู่แทงจาก Co-occurrence Matrix"""
    if len(db["draws"]) < 10:
        st.caption("ข้อมูลยังไม่เพียงพอสำหรับวิเคราะห์คู่แทง (ต้องมีอย่างน้อย 10 งวด)")
        return
    
    st.markdown("### 🎲 คำแนะนำคู่แทงจาก Co-occurrence Matrix")
    st.caption("คำนวณสถิติว่าสัญลักษณ์ใดบ้างที่มักจะ 'ออกคู่กันในงวดเดียวกัน' บ่อยที่สุด")
    
    # คำนวณคะแนนจาก Ensemble Model
    pred = multi_model_predict(db)
    ensemble_prob = pred["models"]["ensemble"]
    
    # คำนวณ Top 3 คู่
    top_pairs = get_top_pairs(db, ensemble_prob, top_n=3)
    
    if not top_pairs:
        st.warning("ไม่สามารถคำนวณคู่แทงได้")
        return
    
    # แสดง Top 3 คู่เด็ด
    st.markdown("#### 🏆 Top 3 คู่เด็ดประจำงวด")
    
    for i, pair_data in enumerate(top_pairs, 1):
        col1, col2, col3, col4 = st.columns([1, 2, 2, 2])
        
        with col1:
            st.markdown(f"**{i}.**")
        
        with col2:
            st.markdown(f"{pair_data['emoji1']} {pair_data['name1']} + {pair_data['emoji2']} {pair_data['name2']}")
        
        with col3:
            st.metric(
                "คะแนนรวม",
                f"{pair_data['combined_score']:.1f}%",
                help=f"Co-occurrence: {pair_data['co_occurrence_rate']:.1f}% + Individual: {pair_data['individual_avg_prob']:.1f}%"
            )
        
        with col4:
            # ปุ่มดึงคู่เข้าฟอร์มบิล
            if st.button(f"ดึงคู่นี้", key=f"import_pair_{i}", use_container_width=True):
                # เพิ่มชุดแทงคู่ใหม่
                new_index = st.session_state.ticket_rows
                st.session_state.ticket_rows += 1
                st.session_state[f"ticket_type_{new_index}"] = "แทงคู่ (2 สัญลักษณ์)"
                st.session_state[f"ticket_symbols_{new_index}"] = [
                    f"{pair_data['emoji1']} {pair_data['name1']}",
                    f"{pair_data['emoji2']} {pair_data['name2']}"
                ]
                st.session_state[f"ticket_amount_{new_index}"] = 10000.0
                persist_ticket_draft()
                st.success(f"ดึงคู่ {pair_data['name1']} + {pair_data['name2']} เข้าฟอร์มบิลแล้ว")
                st.rerun()
        
        st.caption(f"ออกคู่กัน: {pair_data['co_occurrence_count']} ครั้ง ({pair_data['co_occurrence_rate']:.1f}%)")
        st.divider()


def render_betting_form(db: dict, betting_data: dict) -> None:
    st.subheader("🧾 สร้างบิลการซื้อ")
    if not db["draws"]:
        st.warning("ยังไม่มีงวดในคลัง — เพิ่มงวดที่หน้า Data Management ก่อน")
        return
    st.caption("1 บิลเพิ่มได้หลายชุด: เดี่ยวจ่าย x3/x6/x9 ตามจำนวนที่ออก และคู่จ่าย x6 เมื่อออกครบทั้งคู่")
    
    # เพิ่มส่วน Co-occurrence Analysis
    render_pair_recommendations(db)
    
    st.divider()
    
    draw_options = [item["id"] for item in sorted(db["draws"], key=lambda item: item["id"], reverse=True)]
    load_draft_into_state(draw_options)
    editing = next((item for item in betting_data["tickets"] if item["id"] == st.session_state.get("edit_ticket_id")), None)
    if st.session_state.get("edit_ticket_id") and not editing:
        reset_ticket_editor()
    if editing:
        st.info(f"กำลังแก้ไขบิล #{editing['id']}")

    header1, header2 = st.columns(2)
    header1.selectbox("เลขงวด", draw_options, key="ticket_draw_id")
    header2.selectbox("สกุลเงิน", ["LAK", "THB"], key="ticket_currency")
    for index in range(st.session_state.ticket_rows):
        left, middle, right, remove = st.columns([1.2, 3, 1.2, .55])
        bet_type = left.selectbox("ประเภท", ["แทงเดี่ยว (1 สัญลักษณ์)", "แทงคู่ (2 สัญลักษณ์)"], key=f"ticket_type_{index}")
        required = 1 if bet_type == "แทงเดี่ยว (1 สัญลักษณ์)" else 2
        current = st.session_state.get(f"ticket_symbols_{index}", [])
        if len(current) != required:
            st.session_state[f"ticket_symbols_{index}"] = current[:required]
        middle.multiselect("สัญลักษณ์", CHOICES, max_selections=required, key=f"ticket_symbols_{index}", placeholder=f"เลือกให้ครบ {required} สัญลักษณ์")
        right.number_input("เงิน (LAK)", min_value=0.0, value=10000.0, step=1000.0, key=f"ticket_amount_{index}")
        if remove.button("✕", key=f"remove_ticket_row_{index}", disabled=st.session_state.ticket_rows == 1, help="ลบชุดนี้"):
            remaining_rows = [row for row_number, row in enumerate(ticket_rows_from_state()) if row_number != index]
            st.session_state.pending_ticket_rows = remaining_rows
            persist_ticket_draft(remaining_rows)
            st.rerun()
    current_rows = ticket_rows_from_state()
    total = sum(float(row["amount"] or 0) for row in current_rows)
    st.metric("ยอดเงินรวมทั้งบิล (Total Ticket Amount)", money(total, st.session_state.ticket_currency))
    a, b, c = st.columns([1, 1, 2])
    if a.button("+ เพิ่มชุดแทง", width="stretch"):
        new_index = st.session_state.ticket_rows
        st.session_state.ticket_rows += 1
        st.session_state[f"ticket_type_{new_index}"] = "แทงเดี่ยว (1 สัญลักษณ์)"
        st.session_state[f"ticket_symbols_{new_index}"] = []
        st.session_state[f"ticket_amount_{new_index}"] = 10000.0
        persist_ticket_draft()
        st.rerun()
    if b.button("ยกเลิก", width="stretch"):
        clear_ticket_draft()
        st.session_state.ticket_editor_reset_pending = True
        st.rerun()
    if c.button("บันทึกการแก้ไขบิล" if editing else "บันทึกบิลการซื้อ", type="primary", width="stretch"):
        try:
            if editing:
                update_ticket(db, betting_data, editing["id"], st.session_state.ticket_draw_id, current_rows, st.session_state.ticket_currency)
            else:
                add_ticket(db, betting_data, st.session_state.ticket_draw_id, current_rows, st.session_state.ticket_currency)
            clear_ticket_draft()
            st.session_state.ticket_editor_reset_pending = True
            st.success("บันทึกบิลเรียบร้อย")
            st.rerun()
        except ValueError as error:
            st.error(str(error))
    # Streamlit reruns afterทุกการเลือก/พิมพ์ จึงเขียนร่างล่าสุดทันทีทุกครั้ง.
    persist_ticket_draft()


def row_summary(ticket: dict) -> str:
    return " | ".join(
        f"{'เดี่ยว' if row['type'] == 'single' else 'คู่'}: {'+'.join(f'{SYMBOL_EMOJI[s]} {SYMBOLS[s]}' for s in row['symbols'])} ({money(row['amount'], ticket['currency'])})"
        for row in ticket["rows"]
    )


def render_betting_history(betting_data: dict) -> None:
    st.subheader("📋 ประวัติบิลการซื้อ")
    tickets = betting_data.get("tickets", [])
    if not tickets:
        st.caption("ยังไม่มีบิล")
        return
    rows = []
    for ticket in sorted(tickets, key=lambda item: item["id"], reverse=True):
        status = {"pending": "⏳ รอผล", "won": "✅ ถูกรางวัล", "lost": "❌ ไม่ถูก"}[ticket["status"]]
        rows.append({"บิล": f"#{ticket['id']}", "งวด": ticket["draw_id"], "เวลา": ticket["created_at"], "รายการในบิล": row_summary(ticket), "ทุนรวม": money(ticket["total_amount"], ticket["currency"]), "เงินรางวัล": money(ticket["payout"], ticket["currency"]), "สุทธิ": f"{ticket['profit']:+,.0f} {ticket['currency']}", "สถานะ": status})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, use_container_width=True)
    pick = st.selectbox("เลือกบิลเพื่อแก้ไขหรือลบ", [ticket["id"] for ticket in sorted(tickets, key=lambda item: item["id"], reverse=True)])
    edit_col, delete_col = st.columns(2)
    if edit_col.button("✏️ แก้ไขบิล", width="stretch"):
        ticket = next(ticket for ticket in tickets if ticket["id"] == pick)
        start_edit_ticket(ticket)
        save_ticket_draft({"draw_id": ticket["draw_id"], "currency": ticket.get("currency", "LAK"),
                           "rows": ticket["rows"], "edit_ticket_id": ticket["id"]})
        st.rerun()
    if delete_col.button("🗑️ ลบบิล", type="secondary", width="stretch"):
        st.session_state.confirm_delete_ticket = pick
    if st.session_state.get("confirm_delete_ticket"):
        ticket_id = st.session_state.confirm_delete_ticket
        st.warning(f"ยืนยันการลบบิล #{ticket_id} ?")
        yes, no = st.columns(2)
        if yes.button("ยืนยันลบ", type="primary", key="confirm_delete_ticket_yes"):
            delete_ticket(betting_data, ticket_id)
            st.session_state.pop("confirm_delete_ticket", None)
            st.success(f"ลบบิล #{ticket_id} แล้ว")
            st.rerun()
        if no.button("ไม่ลบ", key="confirm_delete_ticket_no"):
            st.session_state.pop("confirm_delete_ticket", None)
            st.rerun()


def render_pnl_dashboard(betting_data: dict) -> None:
    st.subheader("💰 สรุปกำไร/ขาดทุนรายบิล")
    tickets = betting_data.get("tickets", [])
    if not tickets:
        st.caption("ยังไม่มีข้อมูลบิล")
        return
    pnl = calculate_pnl(betting_data)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ยอดทุนรวม", f"{pnl['total_invested']:,.0f}")
    c2.metric("เงินรางวัลรวม", f"{pnl['total_payout']:,.0f}")
    c3.metric("กำไร/ขาดทุนสุทธิ", f"{pnl['net_pnl']:+,.0f}", delta=f"{pnl['roi']:+.1f}%")
    c4.metric("บิลที่ถูกรางวัล", f"{pnl['won_bets']} / {pnl['total_bets']}")
    running, values, dates = 0.0, [], []
    for ticket in sorted(tickets, key=lambda item: item["id"]):
        running += ticket["profit"]
        values.append(running)
        dates.append(ticket["created_at"])
    fig = go.Figure(go.Scatter(x=dates, y=values, mode="lines+markers", name="P&L สะสม"))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(height=330, yaxis_title="กำไร/ขาดทุนสะสม")
    st.plotly_chart(fig, width="stretch")
    pie = px.pie(values=[pnl["won_bets"], pnl["lost_bets"], pnl["pending_bets"]], names=["ชนะ", "แพ้", "รอผล"], hole=.4)
    st.plotly_chart(pie, width="stretch")


def main() -> None:
    db = load()
    betting_data = update_bet_results(db, load_betting())
    st.title("💰 P&L & Betting Tracker")
    render_pnl_dashboard(betting_data)
    st.divider()
    render_betting_form(db, betting_data)
    st.divider()
    render_betting_history(betting_data)


if __name__ == "__main__":
    main()
