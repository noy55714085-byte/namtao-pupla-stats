#!/usr/bin/env python3
"""น้ำเต้าปูปลา — คลังข้อมูล + เอนจินถ่วงน้ำหนัก (ใช้ร่วมกับ Streamlit)"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# Import GitHub Storage module
try:
    from github_storage import load_from_github, save_to_github, github_storage_available
    GITHUB_STORAGE_AVAILABLE = github_storage_available()
except ImportError:
    GITHUB_STORAGE_AVAILABLE = False

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_PATH = DATA_DIR / "history.json"
SQLITE_PATH = DATA_DIR / "history.sqlite"
BETTING_PATH = DATA_DIR / "betting.json"
DRAFT_TICKET_PATH = DATA_DIR / "draft_ticket.json"

SYMBOLS = {1: "ปู", 2: "ปลา", 3: "น้ำเต้า", 4: "เสือ", 5: "ไก่", 6: "กุ้ง"}
SYMBOL_EMOJI = {1: "🦀", 2: "🐟", 3: "🎃", 4: "🐯", 5: "🐓", 6: "🦐"}
WEIGHTS = {"timeslot": 0.40, "markov": 0.30, "combo": 0.20, "hotcold": 0.10}
HOT_WINDOW = 12
DEFAULT_SCHEDULE = ["12:05", "13:05", "14:05", "16:05", "17:05", "18:05", "20:05"]

EMPTY_DB = {
    "game": "น้ำเต้าปูปลา",
    "symbols": {str(k): v for k, v in SYMBOLS.items()},
    "schedule_times": list(DEFAULT_SCHEDULE),
    "dataset_complete": True,
    "notes": [],
    "draws": [],
    "bets": [],  # เพิ่มข้อมูลการแทง
}


def empty_db() -> dict:
    return json.loads(json.dumps(EMPTY_DB))


def parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def combo_type(dice: list[int]) -> str:
    c = Counter(dice)
    if 3 in c.values():
        return "triple"
    if 2 in c.values():
        return "double"
    return "single"


def label_dice(dice: list[int]) -> str:
    return " · ".join(f"{SYMBOL_EMOJI[x]} {SYMBOLS[x]}" for x in dice)


def load() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # ลองโหลดจาก local ก่อน
    if DATA_PATH.exists():
        db = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    elif SQLITE_PATH.exists():
        db = load_sqlite()
    else:
        # ถ้าไม่มี local data ลองโหลดจาก GitHub
        if GITHUB_STORAGE_AVAILABLE:
            github_data = load_from_github()
            if github_data:
                db = github_data
                print(f"Loaded {len(db.get('draws', []))} draws from GitHub")
            else:
                db = empty_db()
        else:
            db = empty_db()
    
    db.setdefault("schedule_times", list(DEFAULT_SCHEDULE))
    db.setdefault("draws", [])
    db.setdefault("bets", [])  # เพิ่ม bets ใน db
    db.setdefault("dataset_complete", True)
    db["draws"] = sorted(db["draws"], key=lambda d: (d["id"], d["datetime"]))
    if db["draws"] and not SQLITE_PATH.exists():
        save_sqlite(db)
    return db


def save(db: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db["draws"] = sorted(db["draws"], key=lambda d: (d["id"], d["datetime"]))
    DATA_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save_sqlite(db)
    
    # บันทึกลง GitHub (ถ้ามี token)
    if GITHUB_STORAGE_AVAILABLE:
        save_to_github(db)


def save_sqlite(db: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS draws (
                id INTEGER PRIMARY KEY,
                datetime TEXT NOT NULL,
                d1 INTEGER NOT NULL,
                d2 INTEGER NOT NULL,
                d3 INTEGER NOT NULL
            )
            """
        )
        conn.execute("DELETE FROM draws")
        conn.executemany(
            "INSERT INTO draws (id, datetime, d1, d2, d3) VALUES (?, ?, ?, ?, ?)",
            [(d["id"], d["datetime"], d["dice"][0], d["dice"][1], d["dice"][2]) for d in db["draws"]],
        )
        conn.commit()
    finally:
        conn.close()


def load_sqlite() -> dict:
    db = empty_db()
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        rows = conn.execute("SELECT id, datetime, d1, d2, d3 FROM draws ORDER BY id").fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    db["draws"] = [{"id": r[0], "datetime": r[1], "dice": [r[2], r[3], r[4]]} for r in rows]
    return db


def upsert_draw(db: dict, draw_id: int, datetime_str: str, dice: list[int]) -> dict:
    if len(dice) != 3 or any(x not in SYMBOLS for x in dice):
        raise ValueError("ต้องเลือกสัญลักษณ์ 3 ลูก และเป็นเลข 1–6 เท่านั้น")
    parse_dt(datetime_str)
    found = False
    for d in db["draws"]:
        if d["id"] == draw_id:
            d["datetime"] = datetime_str
            d["dice"] = list(dice)
            found = True
            break
    if not found:
        db["draws"].append({"id": int(draw_id), "datetime": datetime_str, "dice": list(dice)})
    save(db)
    return db


def delete_draw(db: dict, draw_id: int) -> dict:
    db["draws"] = [d for d in db["draws"] if d["id"] != draw_id]
    save(db)
    return db


# Betting Management Functions
def load_betting() -> dict:
    """โหลดและย้ายข้อมูลการแทงแบบเดิมไปเป็นระบบบิล (ticket) เมื่อจำเป็น."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if BETTING_PATH.exists():
        betting_data = json.loads(BETTING_PATH.read_text(encoding="utf-8"))
        if "tickets" not in betting_data:
            # รองรับข้อมูลรุ่นเดิม: หนึ่งรายการเดิมกลายเป็นหนึ่งบิลที่มีหนึ่งชุด
            tickets = []
            for bet in betting_data.get("bets", []):
                tickets.append({
                    "id": bet.get("id", len(tickets) + 1),
                    "draw_id": bet["draw_id"],
                    "draw_datetime": bet.get("draw_datetime", ""),
                    "currency": bet.get("currency", "LAK"),
                    "created_at": bet.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    "rows": [{"type": "single" if len(bet.get("symbols", [])) == 1 else "pair",
                              "symbols": bet.get("symbols", []), "amount": float(bet.get("amount", 0))}],
                    "status": bet.get("status", "pending"), "result": bet.get("result"),
                    "payout": float(bet.get("payout", 0)), "profit": float(bet.get("profit", 0)),
                })
            betting_data = {"tickets": tickets}
        betting_data.setdefault("tickets", [])
        return betting_data
    return {"tickets": []}


def save_betting(betting_data: dict) -> None:
    """บันทึกข้อมูลการแทงลงไฟล์ betting.json"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BETTING_PATH.write_text(json.dumps(betting_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_ticket_draft() -> dict | None:
    """โหลดร่างบิลที่เก็บไว้ เพื่อคืนฟอร์มเดิมหลัง Streamlit รีบูต."""
    if not DRAFT_TICKET_PATH.exists():
        return None
    try:
        draft = json.loads(DRAFT_TICKET_PATH.read_text(encoding="utf-8"))
        return draft if isinstance(draft, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def save_ticket_draft(draft: dict) -> None:
    """บันทึกร่างบิลล่าสุดลง JSON โดยไม่กระทบประวัติบิลจริง."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DRAFT_TICKET_PATH.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clear_ticket_draft() -> None:
    """ลบร่างบิลหลังบันทึกสำเร็จหรือผู้ใช้ยกเลิก."""
    if DRAFT_TICKET_PATH.exists():
        DRAFT_TICKET_PATH.unlink()


def add_ticket(db: dict, betting_data: dict, draw_id: int, rows: list[dict], currency: str = "LAK", persist: bool = True) -> dict:
    """เพิ่มบิลที่ประกอบด้วยชุดแทงเดี่ยวหรือแทงคู่หลายชุด."""
    draw = next((d for d in db["draws"] if d["id"] == draw_id), None)
    if not draw:
        raise ValueError(f"ไม่พบงวด {draw_id} ในคลังข้อมูล")
    if not rows:
        raise ValueError("บิลต้องมีอย่างน้อย 1 ชุด")
    cleaned_rows = []
    for row in rows:
        symbols = list(row.get("symbols", []))
        bet_type = row.get("type")
        amount = float(row.get("amount", 0))
        required = 1 if bet_type == "single" else 2
        if bet_type not in ("single", "pair") or len(symbols) != required or len(set(symbols)) != required:
            raise ValueError("แต่ละชุดต้องเป็นแทงเดี่ยว 1 สัญลักษณ์ หรือแทงคู่ 2 สัญลักษณ์ที่ไม่ซ้ำกัน")
        if any(symbol not in SYMBOLS for symbol in symbols) or amount <= 0:
            raise ValueError("กรุณาระบุสัญลักษณ์และจำนวนเงินที่มากกว่า 0 ให้ครบทุกชุด")
        cleaned_rows.append({"type": bet_type, "symbols": symbols, "amount": amount})

    ticket = {
        "id": max((ticket.get("id", 0) for ticket in betting_data["tickets"]), default=0) + 1,
        "draw_id": draw_id,
        "draw_datetime": draw["datetime"],
        "currency": currency,
        "rows": cleaned_rows,
        "total_amount": sum(row["amount"] for row in cleaned_rows),
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "result": None,
        "payout": 0.0,
        "profit": 0.0
    }
    betting_data["tickets"].append(ticket)
    if persist:
        save_betting(betting_data)
    return betting_data


def calculate_ticket_result(ticket: dict, draw: dict) -> dict:
    """ใช้กติกา CL Racing: เดี่ยวจ่าย 3/6/9, คู่จ่าย 6 เมื่อออกครบทั้งคู่."""
    counts = Counter(draw["dice"])
    row_results = []
    for row in ticket["rows"]:
        symbols, amount = row["symbols"], float(row["amount"])
        if row["type"] == "single":
            occurrences = counts[symbols[0]]
            multiplier = occurrences * 3  # 1, 2, 3 ลูก = x3, x6, x9
            detail = f"ออก {occurrences} ลูก" if occurrences else "ไม่ออก"
        else:
            complete_pair = all(counts[symbol] > 0 for symbol in symbols)
            multiplier = 6 if complete_pair else 0
            detail = "ออกครบทั้งคู่" if complete_pair else "ออกไม่ครบคู่"
        row_results.append({"multiplier": multiplier, "payout": amount * multiplier, "detail": detail})
    payout = sum(item["payout"] for item in row_results)
    total_amount = sum(float(row["amount"]) for row in ticket["rows"])
    return {"status": "won" if payout > 0 else "lost", "result": row_results,
            "payout": payout, "profit": payout - total_amount, "total_amount": total_amount}


def update_bet_results(db: dict, betting_data: dict) -> dict:
    """คำนวณบิลใหม่ทุกครั้ง เพื่อสะท้อนการแก้ไขผลรางวัลใน Data Management."""
    changed = False
    for ticket in betting_data.get("tickets", []):
        draw = next((d for d in db["draws"] if d["id"] == ticket["draw_id"]), None)
        if draw:
            result = calculate_ticket_result(ticket, draw)
            for key, value in result.items():
                if ticket.get(key) != value:
                    ticket[key] = value
                    changed = True
            if ticket.get("draw_datetime") != draw["datetime"]:
                ticket["draw_datetime"] = draw["datetime"]
                changed = True
    if changed:
        save_betting(betting_data)
    return betting_data


def update_ticket(db: dict, betting_data: dict, ticket_id: int, draw_id: int, rows: list[dict], currency: str = "LAK") -> dict:
    """แก้ไขบิล โดยใช้การตรวจสอบเดียวกับการสร้างบิล."""
    ticket = next((item for item in betting_data.get("tickets", []) if item["id"] == ticket_id), None)
    if not ticket:
        raise ValueError("ไม่พบบิลที่ต้องการแก้ไข")
    staged = {"tickets": []}
    add_ticket(db, staged, draw_id, rows, currency, persist=False)
    replacement = staged["tickets"][0]
    replacement["id"] = ticket_id
    replacement["created_at"] = ticket.get("created_at", replacement["created_at"])
    betting_data["tickets"][betting_data["tickets"].index(ticket)] = replacement
    update_bet_results(db, betting_data)
    save_betting(betting_data)
    return betting_data


def delete_ticket(betting_data: dict, ticket_id: int) -> dict:
    """ลบบิลที่ระบุออกจากประวัติ."""
    before = len(betting_data.get("tickets", []))
    betting_data["tickets"] = [ticket for ticket in betting_data.get("tickets", []) if ticket["id"] != ticket_id]
    if len(betting_data["tickets"]) == before:
        raise ValueError("ไม่พบบิลที่ต้องการลบ")
    save_betting(betting_data)
    return betting_data


def calculate_pnl(betting_data: dict) -> dict:
    """คำนวณสรุปผลการเงิน"""
    bets = betting_data.get("tickets", [])
    
    total_invested = sum(b.get("total_amount", sum(row["amount"] for row in b["rows"])) for b in bets)
    total_payout = sum(b["payout"] for b in bets)
    net_pnl = total_payout - total_invested
    
    # คำนวณ ROI
    roi = (net_pnl / total_invested * 100) if total_invested > 0 else 0
    
    # แยกตามสถานะ
    total_bets = len(bets)
    won_bets = len([b for b in bets if b["status"] == "won"])
    lost_bets = len([b for b in bets if b["status"] == "lost"])
    pending_bets = len([b for b in bets if b["status"] == "pending"])
    
    win_rate = (won_bets / total_bets * 100) if total_bets > 0 else 0
    
    return {
        "total_invested": total_invested,
        "total_payout": total_payout,
        "net_pnl": net_pnl,
        "roi": roi,
        "total_bets": total_bets,
        "won_bets": won_bets,
        "lost_bets": lost_bets,
        "pending_bets": pending_bets,
        "win_rate": win_rate
    }


def expected_schedule(start: datetime, end: datetime, times: list[str]) -> list[datetime]:
    slots = []
    day = start.date()
    last = end.date()
    while day <= last:
        for t in times:
            hh, mm = map(int, t.split(":"))
            dt = datetime(day.year, day.month, day.day, hh, mm)
            if start <= dt <= end:
                slots.append(dt)
        day += timedelta(days=1)
    return slots


def find_gaps(db: dict) -> dict:
    draws = sorted(db["draws"], key=lambda d: d["id"])
    times = db["schedule_times"]
    gaps = {
        "missing_ids": [],
        "missing_slots_in_range": [],
        "truncated_before": None,
        "notes": list(db.get("notes", [])),
        "complete": False,
    }
    if not draws:
        gaps["notes"].append("ยังไม่มีข้อมูลประวัติ")
        return gaps

    ids = [d["id"] for d in draws]
    for prev, cur in zip(ids, ids[1:]):
        if cur != prev + 1:
            gaps["missing_ids"].extend(range(prev + 1, cur))

    first_dt = parse_dt(draws[0]["datetime"])
    last_dt = parse_dt(draws[-1]["datetime"])
    present = {parse_dt(d["datetime"]) for d in draws}
    for slot in expected_schedule(first_dt, last_dt, times):
        if slot not in present:
            gaps["missing_slots_in_range"].append(slot.strftime("%Y-%m-%d %H:%M"))

    if not db.get("dataset_complete"):
        first_time = first_dt.strftime("%H:%M")
        if times and first_time != times[0]:
            missing_open = []
            for t in times:
                if t == first_time:
                    break
                missing_open.append(f"{first_dt.strftime('%Y-%m-%d')} {t}")
            gaps["truncated_before"] = {
                "first_known": draws[0]["id"],
                "likely_missing_same_day": missing_open,
            }
    gaps["complete"] = bool(db.get("dataset_complete")) and not gaps["missing_ids"] and not gaps["missing_slots_in_range"]
    return gaps


def normalize(scores: dict[int, float]) -> dict[int, float]:
    total = sum(max(v, 0.0) for v in scores.values())
    if total <= 0:
        return {i: 100 / 6 for i in range(1, 7)}
    return {i: 100.0 * max(scores[i], 0.0) / total for i in range(1, 7)}


# Multi-Model Functions
def timeslot_model_only(draws: list[dict], next_time: str) -> dict[int, float]:
    """Model 1: Time-Slot Weighted Model (เน้นช่วงเวลา 100%)"""
    same = [d["dice"] for d in draws if d["datetime"].endswith(next_time)]
    return face_share(same)


def markov_model_only(draws: list[dict]) -> dict[int, float]:
    """Model 2: Markov Chain Model (เน้นการเปลี่ยนผ่านงวดถัดไป 100%)"""
    trans = defaultdict(Counter)
    for a, b in zip(draws, draws[1:]):
        nxt = Counter(b["dice"])
        for face in a["dice"]:
            trans[face].update(nxt)
    last = draws[-1]["dice"]
    scores = {i: 0.0 for i in range(1, 7)}
    used = 0
    for face in last:
        cnt = trans[face]
        tot = sum(cnt.values())
        if tot == 0:
            continue
        used += 1
        for i in range(1, 7):
            scores[i] += cnt[i] / tot
    if used == 0:
        return {i: 1 / 6 for i in range(1, 7)}
    return {i: scores[i] / used for i in range(1, 7)}


def hotcold_exponential_model(draws: list[dict]) -> dict[int, float]:
    """Model 3: Hot/Cold Exponential Decay Model (เน้นงวดล่าสุด 100%)"""
    weights = []
    for i in range(len(draws)):
        # Exponential decay: 0.9^i (งวดล่าสุดมีน้ำหนักสูงสุด)
        weights.append(0.9 ** i)
    weights.reverse()  # งวดล่าสุดมีน้ำหนัก 1.0
    
    face_counts = Counter()
    total_weight = 0
    for draw, weight in zip(draws, weights):
        for face in draw["dice"]:
            face_counts[face] += weight
        total_weight += weight * 3
    
    if total_weight == 0:
        return {i: 1 / 6 for i in range(1, 7)}
    
    return {i: face_counts[i] / total_weight for i in range(1, 7)}


def combo_model_only(draws: list[dict]) -> dict[int, float]:
    """Model 4: Combination & Pair Dice Model (เน้นโอกาสเบิ้ล/ตอง 100%)"""
    return face_share([d["dice"] for d in draws])


def ensemble_model(draws: list[dict], next_time: str) -> dict[int, float]:
    """Model 5: Ensemble Hybrid Model (ค่าเฉลี่ยรวมทุกโมเดล)"""
    ts = timeslot_model_only(draws, next_time)
    mk = markov_model_only(draws)
    hc = hotcold_exponential_model(draws)
    cm = combo_model_only(draws)
    
    # ค่าเฉลี่ยจากทุกโมเดล
    ensemble = {i: (ts[i] + mk[i] + hc[i] + cm[i]) / 4 for i in range(1, 7)}
    return normalize(ensemble)


def multi_model_predict(db: dict, timeslot: str | None = None) -> dict:
    """คำนวณความน่าจะเป็นจากทุกโมเดล"""
    draws = sorted(db["draws"], key=lambda d: (d["id"], d["datetime"]))
    if not draws:
        uniform = {i: 100 / 6 for i in range(1, 7)}
        return {
            "next_id": None,
            "next_time": timeslot or "12:05",
            "models": {
                "timeslot": uniform,
                "markov": uniform,
                "hotcold": uniform,
                "combo": uniform,
                "ensemble": uniform
            },
            "comparison": pd.DataFrame()
        }
    
    nxt_id, nxt_label, nxt_time, auto_slot = next_period(db, timeslot)
    
    # คำนวณจากทุกโมเดล
    models = {
        "timeslot": normalize(timeslot_model_only(draws, nxt_time)),
        "markov": normalize(markov_model_only(draws)),
        "hotcold": normalize(hotcold_exponential_model(draws)),
        "combo": normalize(combo_model_only(draws)),
        "ensemble": normalize(ensemble_model(draws, nxt_time))
    }
    
    # สร้างตารางเปรียบเทียบ
    comparison_data = []
    for i in range(1, 7):
        row = {
            "สัญลักษณ์": f"{SYMBOL_EMOJI[i]} {SYMBOLS[i]}",
            "Time-Slot": f"{models['timeslot'][i]:.1f}%",
            "Markov": f"{models['markov'][i]:.1f}%",
            "Hot/Cold": f"{models['hotcold'][i]:.1f}%",
            "Combo": f"{models['combo'][i]:.1f}%",
            "Ensemble": f"{models['ensemble'][i]:.1f}%"
        }
        comparison_data.append(row)
    
    return {
        "next_id": nxt_id,
        "next_time": nxt_time,
        "models": models,
        "comparison": pd.DataFrame(comparison_data)
    }


def multi_model_backtest(db: dict, min_history: int = 20) -> dict:
    """Backtest ทุกโมเดลและเปรียบเทียบความแม่นยำ"""
    draws = sorted(db["draws"], key=lambda d: (d["id"], d["datetime"]))
    
    model_results = {
        "timeslot": {"top1": 0, "top3": 0, "total": 0},
        "markov": {"top1": 0, "top3": 0, "total": 0},
        "hotcold": {"top1": 0, "top3": 0, "total": 0},
        "combo": {"top1": 0, "top3": 0, "total": 0},
        "ensemble": {"top1": 0, "top3": 0, "total": 0}
    }
    
    for i in range(min_history, len(draws)):
        subset = {"schedule_times": db.get("schedule_times", DEFAULT_SCHEDULE), "draws": draws[:i], "dataset_complete": True}
        actual = set(draws[i]["dice"])
        
        # คำนวณจากทุกโมเดล
        pred = multi_model_predict(subset)
        
        for model_name, scores in pred["models"].items():
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            top1 = ranked[0][0]
            top3 = set([x[0] for x in ranked[:3]])
            
            model_results[model_name]["total"] += 1
            if top1 in actual:
                model_results[model_name]["top1"] += 1
            if top3 & actual:
                model_results[model_name]["top3"] += 1
    
    # คำนวณเปอร์เซ็นต์
    summary = {}
    for model_name, results in model_results.items():
        total = results["total"]
        if total > 0:
            summary[model_name] = {
                "top1_pct": (results["top1"] / total * 100),
                "top3_pct": (results["top3"] / total * 100),
                "total_tests": total
            }
        else:
            summary[model_name] = {
                "top1_pct": 0,
                "top3_pct": 0,
                "total_tests": 0
            }
    
    return summary


def detailed_model_breakdown(models: dict, model_name: str, next_time: str) -> dict:
    """สร้างรายละเอียดการทำนายของแต่ละโมเดล"""
    model_key = model_name.lower().replace("/", "").replace(" ", "").replace("-", "")
    if model_key == "hotcold":
        model_key = "hotcold"
    
    scores = models[model_key]
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    
    return {
        "model_name": model_name,
        "top1": {
            "symbol": ranked[0][0],
            "emoji": SYMBOL_EMOJI[ranked[0][0]],
            "name": SYMBOLS[ranked[0][0]],
            "percentage": ranked[0][1],
            "reason": f"คะแนนรวม {ranked[0][1]:.1f}%"
        },
        "top2": {
            "symbol": ranked[1][0],
            "emoji": SYMBOL_EMOJI[ranked[1][0]],
            "name": SYMBOLS[ranked[1][0]],
            "percentage": ranked[1][1],
            "reason": f"คะแนนรวม {ranked[1][1]:.1f}%"
        },
        "top3": {
            "symbol": ranked[2][0],
            "emoji": SYMBOL_EMOJI[ranked[2][0]],
            "name": SYMBOLS[ranked[2][0]],
            "percentage": ranked[2][1],
            "reason": f"คะแนนรวม {ranked[2][1]:.1f}%"
        },
        "confidence": "สูง" if ranked[0][1] > 20 else "ปานกลาง" if ranked[0][1] > 17 else "ต่ำ"
    }


def detailed_backtest_matrix(db: dict, min_history: int = 20) -> dict:
    """สร้างตารางย้อนหลังแบบละเอียดรายงวด"""
    draws = sorted(db["draws"], key=lambda d: (d["id"], d["datetime"]))
    
    matrix_rows = []
    model_names = ["timeslot", "markov", "hotcold", "combo", "ensemble"]
    
    for i in range(min_history, len(draws)):
        actual_draw = draws[i]
        actual_symbols = set(actual_draw["dice"])
        
        # คำนวณการทำนายจากทุกโมเดล
        subset = {"schedule_times": db.get("schedule_times", DEFAULT_SCHEDULE), "draws": draws[:i], "dataset_complete": True}
        pred = multi_model_predict(subset)
        
        row = {
            "งวด": actual_draw["id"],
            "รอบเวลา": actual_draw["datetime"][-5:],
            "ผลรางวัลจริง": label_dice(actual_draw["dice"]),
            "ผลรางวัลจริง_emoji": " ".join([SYMBOL_EMOJI[x] for x in actual_draw["dice"]])
        }
        
        best_model_score = 0
        best_model_name = ""
        
        for model_name in model_names:
            scores = pred["models"][model_name]
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            top3 = [x[0] for x in ranked[:3]]
            
            # ตรวจสอบการเข้าเป้า
            top1_symbol = ranked[0][0]
            top1_hit = top1_symbol in actual_symbols
            top1_matches = len([x for x in top3 if x in actual_symbols])
            
            row[f"{model_name}_top1"] = f"{SYMBOL_EMOJI[top1_symbol]} {SYMBOLS[top1_symbol]}"
            row[f"{model_name}_top1_status"] = "✅ เข้า" if top1_hit else "❌ ไม่เข้า"
            row[f"{model_name}_top1_matches"] = top1_matches
            
            row[f"{model_name}_top2"] = f"{SYMBOL_EMOJI[ranked[1][0]]} {SYMBOLS[ranked[1][0]]}"
            row[f"{model_name}_top2_status"] = "✅ เข้า" if ranked[1][0] in actual_symbols else "❌ ไม่เข้า"
            
            row[f"{model_name}_top3"] = f"{SYMBOL_EMOJI[ranked[2][0]]} {SYMBOLS[ranked[2][0]]}"
            row[f"{model_name}_top3_status"] = "✅ เข้า" if ranked[2][0] in actual_symbols else "❌ ไม่เข้า"
            
            # คำนวณคะแนนสำหรับการเลือกแชมป์
            model_score = top1_matches * 2 + len([x for x in top3 if x in actual_symbols])
            if model_score > best_model_score:
                best_model_score = model_score
                best_model_name = model_name
        
        row["แชมป์ประจำงวด"] = best_model_name.title()
        
        matrix_rows.append(row)
    
    return {"rows": matrix_rows, "model_names": model_names}


def leaderboard_metrics(db: dict, min_history: int = 20) -> dict:
    """คำนวณสถิติตลอดกาลของ Top 1, Top 2, Top 3"""
    matrix = detailed_backtest_matrix(db, min_history)
    rows = matrix["rows"]
    model_names = matrix["model_names"]
    
    leaderboard = {}
    
    for model_name in model_names:
        total = len(rows)
        if total == 0:
            leaderboard[model_name] = {
                "top1_exact_hit_rate": 0,
                "top3_any_hit_rate": 0,
                "top3_double_hit_rate": 0,
                "total_tests": 0
            }
            continue
        
        top1_exact_hits = sum(1 for row in rows if row[f"{model_name}_top1_status"] == "✅ เข้า")
        top3_any_hits = sum(1 for row in rows if row[f"{model_name}_top1_matches"] > 0)
        top3_double_hits = sum(1 for row in rows if row[f"{model_name}_top1_matches"] >= 2)
        
        leaderboard[model_name] = {
            "top1_exact_hit_rate": (top1_exact_hits / total * 100),
            "top3_any_hit_rate": (top3_any_hits / total * 100),
            "top3_double_hit_rate": (top3_double_hits / total * 100),
            "total_tests": total
        }
    
    return leaderboard


def face_share(dice_lists: list[list[int]]) -> dict[int, float]:
    c = Counter()
    n = 0
    for d in dice_lists:
        c.update(d)
        n += len(d)
    if n == 0:
        return {i: 1 / 6 for i in range(1, 7)}
    return {i: c[i] / n for i in range(1, 7)}


def timeslot_scores(draws: list[dict], next_time: str) -> dict[int, float]:
    same = [d["dice"] for d in draws if d["datetime"].endswith(next_time)]
    return face_share(same)


def markov_scores(draws: list[dict]) -> dict[int, float]:
    trans = defaultdict(Counter)
    for a, b in zip(draws, draws[1:]):
        nxt = Counter(b["dice"])
        for face in a["dice"]:
            trans[face].update(nxt)
    last = draws[-1]["dice"]
    scores = {i: 0.0 for i in range(1, 7)}
    used = 0
    for face in last:
        cnt = trans[face]
        tot = sum(cnt.values())
        if tot == 0:
            continue
        used += 1
        for i in range(1, 7):
            scores[i] += cnt[i] / tot
    if used == 0:
        return {i: 1 / 6 for i in range(1, 7)}
    return {i: scores[i] / used for i in range(1, 7)}


def combo_scores(draws: list[dict]) -> tuple[dict[int, float], dict]:
    faces = face_share([d["dice"] for d in draws])
    types = Counter(combo_type(d["dice"]) for d in draws)
    n = max(len(draws), 1)
    stats = {
        "double_pct": 100.0 * types["double"] / n,
        "triple_pct": 100.0 * types["triple"] / n,
        "single_pct": 100.0 * types["single"] / n,
        "n": len(draws),
        "theory_double": 100.0 * 90 / 216,
        "theory_triple": 100.0 * 6 / 216,
        "theory_pair_or_triple": 100.0 * 96 / 216,
        "theory_symbol_hit": 100.0 * (1 - (5 / 6) ** 3),
    }
    pair_face = Counter()
    for d in draws:
        c = Counter(d["dice"])
        for face, k in c.items():
            if k >= 2:
                pair_face[face] += 1
    stats["pair_faces"] = {SYMBOLS[k]: v for k, v in pair_face.most_common()}
    stats["pair_faces_ids"] = dict(pair_face)
    return faces, stats


def hotcold_scores(draws: list[dict]) -> tuple[dict[int, float], dict]:
    hot = face_share([d["dice"] for d in draws[-HOT_WINDOW:]])
    last_seen = {i: None for i in range(1, 7)}
    for ago, d in enumerate(reversed(draws)):
        for face in set(d["dice"]):
            if last_seen[face] is None:
                last_seen[face] = ago
    max_gap = max((v if v is not None else len(draws)) for v in last_seen.values()) or 1
    cold = {}
    for i in range(1, 7):
        gap = last_seen[i] if last_seen[i] is not None else len(draws)
        cold[i] = gap / max_gap
    blended = {i: 0.65 * hot[i] + 0.35 * cold[i] for i in range(1, 7)}
    s = sum(blended.values()) or 1.0
    blended = {i: blended[i] / s for i in range(1, 7)}
    info = {
        "hot_window": HOT_WINDOW,
        "gaps": {SYMBOLS[i]: last_seen[i] for i in range(1, 7)},
        "gaps_ids": last_seen,
        "hot": {SYMBOLS[i]: round(100 * hot[i], 2) for i in range(1, 7)},
    }
    return blended, info


def next_period(db: dict, timeslot: str | None = None) -> tuple[int, str, str, bool]:
    """คืนค่า (งวดถัดไป, ป้ายเวลา, รอบที่ใช้คำนวณ, เป็นรอบอัตโนมัติหรือไม่)"""
    last = max(db["draws"], key=lambda d: (d["id"], d["datetime"]))
    last_dt = parse_dt(last["datetime"])
    times = db.get("schedule_times") or DEFAULT_SCHEDULE
    last_time = last_dt.strftime("%H:%M")
    auto = True
    if timeslot and timeslot != "auto":
        auto = False
        nxt_time = timeslot
        hh, mm = map(int, nxt_time.split(":"))
        candidate = last_dt.replace(hour=hh, minute=mm)
        if candidate <= last_dt:
            candidate = candidate + timedelta(days=1)
        nxt_dt = candidate
    else:
        if last_time in times:
            idx = times.index(last_time)
            if idx + 1 < len(times):
                nxt_time = times[idx + 1]
                nxt_dt = last_dt.replace(hour=int(nxt_time[:2]), minute=int(nxt_time[3:]))
            else:
                nxt_time = times[0]
                nxt_day = last_dt.date() + timedelta(days=1)
                nxt_dt = datetime(nxt_day.year, nxt_day.month, nxt_day.day, int(nxt_time[:2]), int(nxt_time[3:]))
        else:
            nxt_time = times[0]
            nxt_day = last_dt.date() + timedelta(days=1)
            nxt_dt = datetime(nxt_day.year, nxt_day.month, nxt_day.day, int(nxt_time[:2]), int(nxt_time[3:]))
    return last["id"] + 1, nxt_dt.strftime("%d/%m/%Y %H:%M"), nxt_time, auto


def blend(parts: dict[str, dict[int, float]]) -> dict[int, float]:
    scores = {i: 0.0 for i in range(1, 7)}
    for name, w in WEIGHTS.items():
        dist = parts[name]
        for i in range(1, 7):
            scores[i] += w * dist[i]
    return normalize(scores)


def entropy_confidence(pct: dict[int, float], n: int, gaps: dict) -> tuple[str, float]:
    p = [v / 100 for v in pct.values()]
    h = -sum(x * math.log(x + 1e-12) for x in p)
    h_max = math.log(6)
    spread = 1 - h / h_max
    score = min(100.0, max(0.0, 35 + n * 0.35 + spread * 250))
    if gaps.get("missing_ids") or gaps.get("missing_slots_in_range"):
        score *= 0.75
    if n < 40:
        label = "ต่ำ"
    elif spread >= 0.08 and n >= 80:
        label = "สูง"
    elif spread >= 0.03 and n >= 50:
        label = "ปานกลาง"
    else:
        label = "ต่ำ"
    return label, round(score, 1)


def predict(db: dict, timeslot: str | None = None) -> dict:
    draws = sorted(db["draws"], key=lambda d: (d["id"], d["datetime"]))
    if not draws:
        uniform = {i: 100 / 6 for i in range(1, 7)}
        return {
            "next_id": None,
            "next_label": "-",
            "next_time": timeslot or "12:05",
            "auto_slot": True,
            "last": None,
            "pct": uniform,
            "components": {},
            "ranked": sorted(uniform.items(), key=lambda x: -x[1]),
            "combo_stats": {"double_pct": 0, "triple_pct": 0, "single_pct": 0, "n": 0,
                            "theory_double": 100 * 90 / 216, "theory_triple": 100 * 6 / 216,
                            "theory_symbol_hit": 100 * (1 - (5 / 6) ** 3), "pair_faces": {}},
            "double_est": 100 * 90 / 216,
            "triple_est": 100 * 6 / 216,
            "hc_info": {"hot_window": HOT_WINDOW, "gaps": {}, "hot": {}},
            "gaps": find_gaps(db),
            "n": 0,
            "slot_n": 0,
            "confidence": "ต่ำ",
            "confidence_score": 0.0,
        }

    nxt_id, nxt_label, nxt_time, auto_slot = next_period(db, timeslot)
    ts = timeslot_scores(draws, nxt_time)
    mk = markov_scores(draws)
    combo, combo_stats = combo_scores(draws)
    hc, hc_info = hotcold_scores(draws)
    pct = blend({"timeslot": ts, "markov": mk, "combo": combo, "hotcold": hc})
    gaps = find_gaps(db)
    top = sorted(pct.values(), reverse=True)
    concentration = (top[0] + top[1]) / 200.0
    double_est = (0.55 * combo_stats["double_pct"] + 0.45 * combo_stats["theory_double"]) * (0.85 + 0.30 * concentration)
    triple_est = (0.40 * combo_stats["triple_pct"] + 0.60 * combo_stats["theory_triple"]) * (0.80 + 0.40 * concentration)
    ranked = sorted(pct.items(), key=lambda x: -x[1])
    label, cscore = entropy_confidence(pct, len(draws), gaps)
    slot_n = sum(1 for d in draws if d["datetime"].endswith(nxt_time))
    return {
        "next_id": nxt_id,
        "next_label": nxt_label,
        "next_time": nxt_time,
        "auto_slot": auto_slot,
        "last": draws[-1],
        "pct": pct,
        "components": {
            "timeslot": {SYMBOLS[i]: round(100 * ts[i], 2) for i in range(1, 7)},
            "markov": {SYMBOLS[i]: round(100 * mk[i], 2) for i in range(1, 7)},
            "combo": {SYMBOLS[i]: round(100 * combo[i], 2) for i in range(1, 7)},
            "hotcold": {SYMBOLS[i]: round(100 * hc[i], 2) for i in range(1, 7)},
        },
        "ranked": ranked,
        "combo_stats": combo_stats,
        "double_est": double_est,
        "triple_est": triple_est,
        "hc_info": hc_info,
        "gaps": gaps,
        "n": len(draws),
        "slot_n": slot_n,
        "confidence": label,
        "confidence_score": cscore,
    }


def reasons(pred: dict) -> list[tuple[int, str, float, str]]:
    if not pred.get("last"):
        return []
    last = pred["last"]["dice"]
    last_s = ", ".join(SYMBOLS[x] for x in last)
    ts = pred["components"]["timeslot"]
    gaps = pred["hc_info"]["gaps"]
    hot = pred["hc_info"]["hot"]
    pair = pred["combo_stats"]["pair_faces"]
    out = []
    for i, (face, p) in enumerate(pred["ranked"][:3], 1):
        name = SYMBOLS[face]
        bits = [f"คะแนนรวม {p:.1f}%"]
        bits.append(f"รอบ {pred['next_time']} ออก{name} {ts[name]:.1f}% ของหน้าในช่วงนี้ (n={pred['slot_n']})")
        bits.append(f"Markov จากงวดล่าสุด ({last_s})")
        g = gaps.get(name)
        if g == 0:
            bits.append("เพิ่งออกงวดล่าสุด")
        elif g and g >= 4:
            bits.append(f"Cold หายไป {g} งวด")
        bits.append(f"คลื่น {HOT_WINDOW} งวดล่าสุด {hot.get(name, 0):.1f}%")
        if name in pair:
            bits.append(f"เคยเบิ้ล/ตอง {pair[name]} ครั้ง")
        out.append((i, name, p, " · ".join(bits)))
    return out


def backtest(db: dict, min_history: int = 20) -> dict:
    draws = sorted(db["draws"], key=lambda d: (d["id"], d["datetime"]))
    hits_top1 = 0
    hits_top3_any = 0
    n = 0
    rows = []
    for i in range(min_history, len(draws)):
        subset = {"schedule_times": db.get("schedule_times", DEFAULT_SCHEDULE), "draws": draws[:i], "dataset_complete": True}
        pred = predict(subset)
        actual = set(draws[i]["dice"])
        ranked = [face for face, _ in pred["ranked"]]
        top1 = ranked[0]
        top3 = set(ranked[:3])
        n += 1
        t1 = top1 in actual
        t3 = bool(top3 & actual)
        hits_top1 += int(t1)
        hits_top3_any += int(t3)
        rows.append({
            "งวด": draws[i]["id"],
            "เวลา": draws[i]["datetime"],
            "ผลจริง": label_dice(draws[i]["dice"]),
            "ทายอันดับ 1": f"{SYMBOL_EMOJI[top1]} {SYMBOLS[top1]}",
            "ทายถูกอันดับ 1": t1,
            "Top3 ออกอย่างน้อย 1": t3,
        })
    baseline = 100.0 * (1 - (5 / 6) ** 3)
    return {
        "n": n,
        "top1_pct": 100.0 * hits_top1 / n if n else 0.0,
        "top3_pct": 100.0 * hits_top3_any / n if n else 0.0,
        "baseline_top1": baseline,
        "rows": rows,
    }


def print_report(pred: dict) -> None:
    print(f"งวดถัดไป: {pred['next_id']} / {pred['next_label']} รอบ {pred['next_time']}")
    print(" ".join(f"{SYMBOLS[i]} {pred['pct'][i]:.1f}%" for i in range(1, 7)))
    print("Top 3:", reasons(pred))
    print("Confidence:", pred["confidence"], pred.get("confidence_score"))


if __name__ == "__main__":
    print_report(predict(load()))
