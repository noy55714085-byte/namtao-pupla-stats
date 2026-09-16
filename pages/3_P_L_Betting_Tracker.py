"""ระบบบิลซื้อและคำนวณกำไร/ขาดทุน น้ำเต้าปูปลา."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analyze import SYMBOL_EMOJI, SYMBOLS, add_ticket, calculate_pnl, delete_ticket, load, load_betting, update_bet_results, update_ticket

st.set_page_config(page_title="P&L & Betting Tracker", page_icon="💰", layout="wide")
CHOICES = [f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}" for i in range(1, 7)]
NAME_TO_ID = {choice: i for i, choice in zip(range(1, 7), CHOICES)}


def money(value: float, currency: str = "LAK") -> str:
    return f"{value:,.0f} {currency}"


def reset_ticket_editor() -> None:
    st.session_state.ticket_rows = 1
    st.session_state.edit_ticket_id = None


def start_edit_ticket(ticket: dict) -> None:
    st.session_state.edit_ticket_id = ticket["id"]
    st.session_state.ticket_rows = len(ticket["rows"])
    st.session_state.ticket_draw_id = ticket["draw_id"]
    st.session_state.ticket_currency = ticket.get("currency", "LAK")
    for index, row in enumerate(ticket["rows"]):
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


def render_betting_form(db: dict, betting_data: dict) -> None:
    st.subheader("🧾 สร้างบิลการซื้อ")
    if not db["draws"]:
        st.warning("ยังไม่มีงวดในคลัง — เพิ่มงวดที่หน้า Data Management ก่อน")
        return
    st.caption("1 บิลเพิ่มได้หลายชุด: เดี่ยวจ่าย x3/x6/x9 ตามจำนวนที่ออก และคู่จ่าย x6 เมื่อออกครบทั้งคู่")
    st.session_state.setdefault("ticket_rows", 1)
    editing = next((item for item in betting_data["tickets"] if item["id"] == st.session_state.get("edit_ticket_id")), None)
    if st.session_state.get("edit_ticket_id") and not editing:
        reset_ticket_editor()
    if editing:
        st.info(f"กำลังแก้ไขบิล #{editing['id']}")

    draw_options = [item["id"] for item in sorted(db["draws"], key=lambda item: item["id"], reverse=True)]
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
            for key in (f"ticket_type_{index}", f"ticket_symbols_{index}", f"ticket_amount_{index}"):
                st.session_state.pop(key, None)
            st.session_state.ticket_rows -= 1
            st.rerun()
    current_rows = ticket_rows_from_state()
    total = sum(float(row["amount"] or 0) for row in current_rows)
    st.metric("ยอดเงินรวมทั้งบิล (Total Ticket Amount)", money(total, st.session_state.ticket_currency))
    a, b, c = st.columns([1, 1, 2])
    if a.button("+ เพิ่มชุดแทง", width="stretch"):
        st.session_state.ticket_rows += 1
        st.rerun()
    if b.button("ยกเลิกแก้ไข", width="stretch", disabled=not editing):
        reset_ticket_editor()
        st.rerun()
    if c.button("บันทึกการแก้ไขบิล" if editing else "บันทึกบิลการซื้อ", type="primary", width="stretch"):
        try:
            if editing:
                update_ticket(db, betting_data, editing["id"], st.session_state.ticket_draw_id, current_rows, st.session_state.ticket_currency)
            else:
                add_ticket(db, betting_data, st.session_state.ticket_draw_id, current_rows, st.session_state.ticket_currency)
            reset_ticket_editor()
            st.success("บันทึกบิลเรียบร้อย")
            st.rerun()
        except ValueError as error:
            st.error(str(error))


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
        start_edit_ticket(next(ticket for ticket in tickets if ticket["id"] == pick))
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
