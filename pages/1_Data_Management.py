"""หน้าจัดการข้อมูลประวัติผลรางวัล"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import datetime, date

from analyze import (
    DATA_PATH,
    HOT_WINDOW,
    SQLITE_PATH,
    SYMBOL_EMOJI,
    SYMBOLS,
    backtest,
    combo_type,
    delete_draw,
    label_dice,
    load,
    predict,
    reasons,
    save,
    upsert_draw,
)

st.set_page_config(
    page_title="Data Management",
    page_icon="📊",
    layout="wide",
)

CHOICES = [f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}" for i in range(1, 7)]
NAME_TO_ID = {f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}": i for i in range(1, 7)}


def default_new_draw(db: dict) -> tuple[int, date, str]:
    times = db.get("schedule_times") or []
    if not db["draws"]:
        return 1, date.today(), times[0] if times else "12:05"
    last = max(db["draws"], key=lambda d: d["id"])
    pred = predict(db)
    dt = datetime.strptime(pred["next_label"], "%d/%m/%Y %H:%M") if pred["next_id"] else datetime.now()
    return last["id"] + 1, dt.date(), pred["next_time"]


def history_frame(db: dict) -> pd.DataFrame:
    rows = []
    for d in sorted(db["draws"], key=lambda x: x["id"], reverse=True):
        kind = {"single": "เดี่ยว", "double": "เบิ้ล", "triple": "ตอง"}[combo_type(d["dice"])]
        rows.append(
            {
                "งวด": d["id"],
                "วันเวลา": d["datetime"],
                "รอบ": d["datetime"][-5:],
                "ลูก 1": f"{SYMBOL_EMOJI[d['dice'][0]]} {SYMBOLS[d['dice'][0]]}",
                "ลูก 2": f"{SYMBOL_EMOJI[d['dice'][1]]} {SYMBOLS[d['dice'][1]]}",
                "ลูก 3": f"{SYMBOL_EMOJI[d['dice'][2]]} {SYMBOLS[d['dice'][2]]}",
                "รูปแบบ": kind,
            }
        )
    return pd.DataFrame(rows)


def render_management_page(db: dict) -> None:
    st.title("📊 ศูนย์จัดการประวัติผล")
    
    # เพิ่มงวดใหม่
    st.subheader("เพิ่ม / แก้ไขงวด")
    nid, ndate, ntime = default_new_draw(db)
    edit_id = st.session_state.get("edit_id")
    if edit_id:
        src = next((d for d in db["draws"] if d["id"] == edit_id), None)
        if src:
            nid = src["id"]
            dt = datetime.strptime(src["datetime"], "%Y-%m-%d %H:%M")
            ndate, ntime = dt.date(), dt.strftime("%H:%M")
            st.info(f"กำลังแก้ไขงวด `{edit_id}` — กดบันทึกเมื่อแก้เสร็จ หรือยกเลิกด้านล่าง")

    with st.form("draw_form", clear_on_submit=False):
        a, b, c = st.columns([1, 1, 1])
        draw_id = a.number_input("เลขงวด", min_value=1, value=int(nid), step=1, key="m_id")
        day = b.date_input("วันที่", value=ndate, format="DD/MM/YYYY", key="m_day")
        slot = c.selectbox(
            "เวลา / รอบ",
            db.get("schedule_times") or ["12:05"],
            index=max(0, (db.get("schedule_times") or ["12:05"]).index(ntime) if ntime in (db.get("schedule_times") or []) else 0),
            key="m_slot",
        )
        d1, d2, d3 = st.columns(3)
        defaults = [CHOICES[0]] * 3
        if edit_id:
            src = next((d for d in db["draws"] if d["id"] == edit_id), None)
            if src:
                defaults = [f"{SYMBOL_EMOJI[x]} {SYMBOLS[x]}" for x in src["dice"]]
        s1 = d1.selectbox("ลูกที่ 1", CHOICES, index=CHOICES.index(defaults[0]))
        s2 = d2.selectbox("ลูกที่ 2", CHOICES, index=CHOICES.index(defaults[1]))
        s3 = d3.selectbox("ลูกที่ 3", CHOICES, index=CHOICES.index(defaults[2]))
        submitted = st.form_submit_button("บันทึกลงคลัง (JSON + SQLite)", type="primary", width="stretch")

    if submitted:
        dt_str = f"{day.strftime('%Y-%m-%d')} {slot}"
        dice = [NAME_TO_ID[s1], NAME_TO_ID[s2], NAME_TO_ID[s3]]
        upsert_draw(db, int(draw_id), dt_str, dice)
        st.session_state.pop("edit_id", None)
        st.success(f"บันทึกงวด {int(draw_id)} แล้ว · {label_dice(dice)}")
        st.rerun()

    if edit_id:
        if st.button("ยกเลิกการแก้ไข"):
            st.session_state.pop("edit_id", None)
            st.rerun()

    st.divider()
    
    # ตารางประวัติย้อนหลัง
    st.subheader("ประวัติย้อนหลัง")
    if not db["draws"]:
        st.caption("ยังไม่มีรายการ")
        return

    # ระบบค้นหา/กรอง
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        start_date = st.date_input("ตั้งแต่วันที่", value=None, key="filter_start")
    with col2:
        end_date = st.date_input("ถึงวันที่", value=None, key="filter_end")
    with col3:
        search_id = st.text_input("ค้นหางวด", placeholder="เช่น 36260204")

    df = history_frame(db)
    
    # กรองข้อมูล
    if start_date:
        df = df[pd.to_datetime(df["วันเวลา"]).dt.date >= start_date]
    if end_date:
        df = df[pd.to_datetime(df["วันเวลา"]).dt.date <= end_date]
    if search_id:
        df = df[df["งวด"].astype(str).str.contains(search_id)]

    st.dataframe(df, width="stretch", hide_index=True, height=420)

    # ปุ่มแก้ไข/ลบ
    e1, e2, e3 = st.columns([1.2, 1, 1])
    options = [d["id"] for d in sorted(db["draws"], key=lambda x: x["id"], reverse=True)]
    pick = e1.selectbox("เลือกงวดเพื่อแก้หรือลบ", options)
    if e2.button("แก้ไขงวดนี้", width="stretch"):
        st.session_state["edit_id"] = pick
        st.rerun()
    if e3.button("ลบงวดนี้", type="secondary", width="stretch"):
        st.session_state["confirm_delete"] = pick

    if st.session_state.get("confirm_delete"):
        cid = st.session_state["confirm_delete"]
        st.error(f"ยืนยันลบงวด {cid} ? การลบจะบันทึกลงไฟล์ทันที")
        k1, k2 = st.columns(2)
        if k1.button("ยืนยันลบ", type="primary"):
            delete_draw(db, cid)
            st.session_state.pop("confirm_delete", None)
            st.rerun()
        if k2.button("ไม่ลบ"):
            st.session_state.pop("confirm_delete", None)
            st.rerun()


def main() -> None:
    db = load()
    render_management_page(db)


if __name__ == "__main__":
    main()