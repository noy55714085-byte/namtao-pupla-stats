from __future__ import annotations

import json
from datetime import datetime, date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analyze import (
    DATA_PATH,
    HOT_WINDOW,
    SQLITE_PATH,
    SYMBOL_EMOJI,
    SYMBOLS,
    WEIGHTS,
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
    page_title="น้ำเต้าปูปลา · สถิติ",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded",
)

CHOICES = [f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}" for i in range(1, 7)]
NAME_TO_ID = {f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}": i for i in range(1, 7)}


def css() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.2rem; max-width: 1280px;}
        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid #d5e4da;
            border-radius: 14px;
            padding: 8px 12px;
        }
        .hint {color:#4d6657; font-size:0.92rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_db_cached(token: int) -> dict:
    _ = token
    return load()


def bump() -> None:
    st.session_state["data_token"] = st.session_state.get("data_token", 0) + 1
    load_db_cached.clear()


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


def bar_chart(pct: dict[int, float]) -> go.Figure:
    names = [f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}" for i in range(1, 7)]
    values = [round(pct[i], 2) for i in range(1, 7)]
    fig = px.bar(
        x=names,
        y=values,
        text=[f"{v:.1f}%" for v in values],
        color=values,
        color_continuous_scale="Greens",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        coloraxis_showscale=False,
        yaxis_title="โอกาส (%)",
        xaxis_title="",
        yaxis_range=[0, max(values) * 1.25 if values else 40],
        margin=dict(t=20, b=10, l=10, r=10),
        height=340,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render_dashboard(db: dict, slot: str) -> None:
    pred = predict(db, None if slot == "อัตโนมัติ (งวดถัดไป)" else slot)
    gaps = pred["gaps"]

    if pred["n"] == 0:
        st.warning("ยังไม่มีประวัติในคลัง — เพิ่มงวดแรกที่แถบข้างหรือแท็บจัดการข้อมูล")
        return

    last = pred["last"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("งวดถัดไป", str(pred["next_id"]))
    c2.metric("เวลาที่คำนวณ", pred["next_label"])
    c3.metric("รอบ (Time-Slot 40%)", pred["next_time"])
    c4.metric("จำนวนงวดในคลัง", pred["n"])

    st.caption(
        f"งวดล่าสุด `{last['id']}` · {last['datetime']} · {label_dice(last['dice'])}  ·  "
        f"ตัวอย่างรอบนี้ในคลัง {pred['slot_n']} งวด"
    )
    if not pred["auto_slot"]:
        st.info(
            f"กำลังใช้แพทเทิร์นรอบ **{pred['next_time']}** ตามตัวกรอง "
            f"(เลขงวดถัดไปจริงในตารางยังเป็นลำดับจากงวดล่าสุด)"
        )

    if gaps.get("missing_ids") or gaps.get("missing_slots_in_range"):
        st.warning(
            "พบช่องว่างในคลัง: "
            + (f"เลขงวด {gaps['missing_ids'][:12]}{'…' if len(gaps['missing_ids'])>12 else ''} " if gaps["missing_ids"] else "")
            + (f"ช่วงเวลา {len(gaps['missing_slots_in_range'])} ช่อง" if gaps["missing_slots_in_range"] else "")
        )

    st.subheader("เปอร์เซ็นต์ความน่าจะเป็นของงวดถัดไป")
    cols = st.columns(6)
    ranked_faces = {face for face, _ in pred["ranked"][:3]}
    for i, col in enumerate(cols, start=1):
        with col:
            st.metric(
                f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}",
                f"{pred['pct'][i]:.1f}%",
                help="น้ำหนัก: Time-Slot 40% + Markov 30% + Dice Combo 20% + Hot/Cold 10%",
            )
            if i in ranked_faces:
                st.caption("ตัวเต็ง")

    st.plotly_chart(bar_chart(pred["pct"]), width="stretch")

    left, right = st.columns([1.15, 0.85])
    with left:
        st.subheader("Top 3 ตัวเต็ง")
        for rank, name, p, why in reasons(pred):
            emoji = next(SYMBOL_EMOJI[i] for i in range(1, 7) if SYMBOLS[i] == name)
            st.markdown(f"**{rank}. {emoji} {name} — {p:.1f}%**")
            st.caption(why)
        st.markdown(
            f"**โอกาสเบิ้ล:** {pred['double_est']:.1f}%  ·  "
            f"**ตอง:** {pred['triple_est']:.1f}%  ·  "
            f"**อย่างน้อยคู่หรือตอง:** {pred['double_est'] + pred['triple_est']:.1f}%"
        )
        st.caption(
            f"ในคลัง เบิ้ล {pred['combo_stats']['double_pct']:.1f}% / ตอง {pred['combo_stats']['triple_pct']:.1f}% "
            f"· ทฤษฎีลูกเต๋า เบิ้ล {pred['combo_stats']['theory_double']:.1f}% / ตอง {pred['combo_stats']['theory_triple']:.1f}%"
        )
    with right:
        st.subheader("Confidence Score")
        color = {"ต่ำ": "#C45C26", "ปานกลาง": "#C49A26", "สูง": "#1B7A4B"}[pred["confidence"]]
        st.markdown(
            f"<div style='background:white;border:1px solid #d5e4da;border-radius:16px;padding:18px;'>"
            f"<div style='font-size:2rem;font-weight:700;color:{color}'>{pred['confidence']}</div>"
            f"<div class='hint'>คะแนนภายใน {pred['confidence_score']:.0f}/100 · "
            f"ยิ่งคลังยาวและคะแนนกระจุก ยิ่งสูง — ไม่ได้รับประกันผลรางวัล</div></div>",
            unsafe_allow_html=True,
        )
        st.write("")
        st.markdown("**ส่วนประกอบโมเดล**")
        for key, title in [
            ("timeslot", "Time-Slot 40%"),
            ("markov", "Markov 30%"),
            ("combo", "Dice Combo 20%"),
            ("hotcold", f"Hot/Cold 10% (หน้าต่าง {HOT_WINDOW} งวด)"),
        ]:
            st.caption(title)
            st.write(pred["components"][key])

    with st.expander("น้ำหนักอัลกอริทึม"):
        st.write(
            pd.DataFrame(
                {"ส่วน": ["Time-Slot", "Markov Chain", "Dice Combination", "Hot / Cold"],
                 "น้ำหนัก": [f"{int(WEIGHTS['timeslot']*100)}%", f"{int(WEIGHTS['markov']*100)}%",
                               f"{int(WEIGHTS['combo']*100)}%", f"{int(WEIGHTS['hotcold']*100)}%"]}
            )
        )
        st.caption(
            "โมเดลนี้เป็นสถิติจากประวัติ ไม่ใช่สูตรทำนายที่รับประกัน ลูกเต๋า 3 ลูกในระยะยาวแต่ละหน้าใกล้ 16.7% "
            f"โอกาสที่สัญลักษณ์หนึ่งออกอย่างน้อย 1 ลูก ≈ {pred['combo_stats']['theory_symbol_hit']:.1f}%"
        )


def render_manage(db: dict) -> None:
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
        bump()
        st.success(f"บันทึกงวด {int(draw_id)} แล้ว · {label_dice(dice)}")
        st.rerun()

    if edit_id:
        if st.button("ยกเลิกการแก้ไข"):
            st.session_state.pop("edit_id", None)
            st.rerun()

    st.divider()
    st.subheader("ประวัติย้อนหลัง")
    if not db["draws"]:
        st.caption("ยังไม่มีรายการ")
        return

    df = history_frame(db)
    st.dataframe(df, width="stretch", hide_index=True, height=420)

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
            bump()
            st.rerun()
        if k2.button("ไม่ลบ"):
            st.session_state.pop("confirm_delete", None)
            st.rerun()


def render_stats(db: dict) -> None:
    if len(db["draws"]) < 5:
        st.info("เพิ่มประวัติอย่างน้อย 5 งวดเพื่อดูสถิติรวม")
        return
    pred = predict(db)
    freq = pred["components"]["combo"]
    fig = px.pie(
        names=list(freq.keys()),
        values=list(freq.values()),
        hole=0.45,
        color_discrete_sequence=px.colors.sequential.Greens,
    )
    fig.update_layout(margin=dict(t=10, b=10), height=320)
    a, b = st.columns(2)
    with a:
        st.subheader("ความถี่รวมทั้งคลัง")
        st.plotly_chart(fig, width="stretch")
    with b:
        st.subheader("Hot / Cold")
        gaps = pred["hc_info"]["gaps"]
        hot = pred["hc_info"]["hot"]
        st.dataframe(
            pd.DataFrame(
                {
                    "สัญลักษณ์": list(SYMBOLS.values()),
                    f"คลื่น {HOT_WINDOW} งวด (%)": [hot.get(SYMBOLS[i], 0) for i in range(1, 7)],
                    "หายไปกี่งวด": [gaps.get(SYMBOLS[i], None) for i in range(1, 7)],
                }
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption("หายไป 0 = เพิ่งออกงวดล่าสุด")

    st.subheader("วัดความแม่นยำย้อนหลัง (Walk-forward)")
    st.caption(
        "ใช้ประวัติก่อนหน้างวดนั้นคำนวณ แล้วเช็กว่าตัวเต็งอันดับ 1 ออกใน 3 ลูกหรือไม่ "
        f"เส้นสุ่มของสัญลักษณ์เดียว ≈ {pred['combo_stats']['theory_symbol_hit']:.1f}%"
    )
    min_h = st.slider("ใช้ประวัติอย่างน้อยกี่งวดก่อนเริ่มวัด", 10, max(11, pred["n"] - 1), min(20, pred["n"] - 1))
    bt = backtest(db, min_history=min_h)
    if bt["n"] == 0:
        st.warning("ข้อมูลยังไม่พอสำหรับ backtest")
        return
    m1, m2, m3 = st.columns(3)
    m1.metric("งวดที่วัด", bt["n"])
    m2.metric("ทายอันดับ 1 แล้วออก", f"{bt['top1_pct']:.1f}%", delta=f"{bt['top1_pct'] - bt['baseline_top1']:.1f} จากสุ่ม")
    m3.metric("Top 3 ออกอย่างน้อย 1 ตัว", f"{bt['top3_pct']:.1f}%")
    st.dataframe(pd.DataFrame(bt["rows"]), width="stretch", hide_index=True, height=320)


def render_io(db: dict) -> None:
    st.subheader("สำรองและนำเข้า")
    st.caption("ข้อมูลหลักอยู่ที่ `data/history.json` และสำเนา `data/history.sqlite` บันทึกอัตโนมัติทุกครั้งที่เพิ่ม/แก้/ลบ")

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "ดาวน์โหลด history.json",
            data=DATA_PATH.read_text(encoding="utf-8") if DATA_PATH.exists() else "{}",
            file_name="history.json",
            mime="application/json",
            width="stretch",
        )
        if SQLITE_PATH.exists():
            st.download_button(
                "ดาวน์โหลด history.sqlite",
                data=SQLITE_PATH.read_bytes(),
                file_name="history.sqlite",
                mime="application/octet-stream",
                width="stretch",
            )
    with col2:
        up = st.file_uploader("นำเข้า JSON (แทนที่หรือผสาน)", type=["json"])
        mode = st.radio("โหมดนำเข้า", ["ผสานตามเลขงวด (แนะนำ)", "แทนที่ทั้งคลัง"], horizontal=True)
        if up and st.button("นำเข้าเลย", type="primary"):
            payload = json.loads(up.getvalue().decode("utf-8"))
            incoming = payload.get("draws", payload if isinstance(payload, list) else [])
            if mode.startswith("แทนที่"):
                db["draws"] = incoming
            else:
                by_id = {d["id"]: d for d in db["draws"]}
                for d in incoming:
                    by_id[d["id"]] = d
                db["draws"] = list(by_id.values())
            save(db)
            bump()
            st.success(f"นำเข้าแล้ว คลังมี {len(db['draws'])} งวด")
            st.rerun()

    st.divider()
    st.subheader("วางหลายงวดทีเดียว (อัปเดตรายเดือน)")
    st.caption("หนึ่งบรรทัดต่องวด: `เลขงวด,YYYY-MM-DD HH:MM,ลูก1,ลูก2,ลูก3` ใช้เลข 1–6 (ปู ปลา เต้า เสือ ไก่ กุ้ง)")
    st.code("36260204,2026-09-16 12:05,4,6,1\n36260205,2026-09-16 13:05,2,5,1", language="text")
    bulk = st.text_area("วางข้อมูล", height=140, placeholder="36260204,2026-09-16 12:05,4,6,1")
    if st.button("เพิ่มทั้งหมดจากกล่องข้อความ"):
        ok, err = 0, []
        for line in bulk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parts = [p.strip() for p in line.replace(";", ",").split(",")]
                did = int(parts[0])
                dt = parts[1]
                if len(parts[1].split()) == 1:
                    dt = f"{parts[1]} {parts[2]}"
                    dice = [int(parts[3]), int(parts[4]), int(parts[5])]
                else:
                    dice = [int(parts[2]), int(parts[3]), int(parts[4])]
                upsert_draw(db, did, dt, dice)
                ok += 1
            except Exception as exc:  # noqa: BLE001
                err.append(f"{line} → {exc}")
        bump()
        if ok:
            st.success(f"บันทึก {ok} งวด")
        if err:
            st.error("บางบรรทัดไม่ผ่าน:\n" + "\n".join(err[:8]))
        if ok:
            st.rerun()


def sidebar_form(db: dict, slot_choice: list[str]) -> str:
    st.sidebar.title("🎲 น้ำเต้าปูปลา")
    st.sidebar.caption("สถิติถ่วงน้ำหนัก · คลังบันทึกอัตโนมัติ")
    slot = st.sidebar.selectbox("รอบที่จะคำนวณ (Time-Slot)", slot_choice)
    st.sidebar.divider()
    st.sidebar.markdown("**เพิ่มงวดใหม่เร็ว**")
    nid, ndate, ntime = default_new_draw(db)
    with st.sidebar.form("quick_add"):
        qid = st.number_input("เลขงวด", min_value=1, value=int(nid), step=1)
        qday = st.date_input("วันที่", value=ndate, format="DD/MM/YYYY")
        qslot = st.selectbox("เวลา", db.get("schedule_times") or ["12:05"],
                             index=max(0, (db.get("schedule_times") or []).index(ntime) if ntime in (db.get("schedule_times") or []) else 0))
        qs1 = st.selectbox("ลูก 1", CHOICES, key="q1")
        qs2 = st.selectbox("ลูก 2", CHOICES, key="q2")
        qs3 = st.selectbox("ลูก 3", CHOICES, key="q3")
        go = st.form_submit_button("บันทึกงวด", width="stretch")
    if go:
        upsert_draw(db, int(qid), f"{qday.strftime('%Y-%m-%d')} {qslot}", [NAME_TO_ID[qs1], NAME_TO_ID[qs2], NAME_TO_ID[qs3]])
        bump()
        st.sidebar.success("บันทึกแล้ว")
        st.rerun()
    st.sidebar.caption("ไฟล์: `data/history.json` และ `data/history.sqlite`")
    return slot


def main() -> None:
    css()
    if "data_token" not in st.session_state:
        st.session_state["data_token"] = 0
    db = load_db_cached(st.session_state["data_token"])
    slot_choice = ["อัตโนมัติ (งวดถัดไป)"] + list(db.get("schedule_times") or [])
    slot = sidebar_form(db, slot_choice)

    st.title("แดชบอร์ดสถิติน้ำเต้าปูปลา")
    tabs = st.tabs(["แดชบอร์ด", "จัดการประวัติ", "สถิติและความแม่นยำ", "นำเข้า / สำรอง"])
    with tabs[0]:
        render_dashboard(db, slot)
    with tabs[1]:
        render_manage(db)
    with tabs[2]:
        render_stats(db)
    with tabs[3]:
        render_io(db)


if __name__ == "__main__":
    main()
