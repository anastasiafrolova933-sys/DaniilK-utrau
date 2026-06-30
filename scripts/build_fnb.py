# -*- coding: utf-8 -*-
"""
build_fnb.py — F&B Службы питания Утрау (ресторан КАЕФ).
Парсит помесячно: A1 (сводка, источник правды) + A2 (банкеты) + B1-B6 (продажи по блюдам)
→ data/fnb_data.js  (window.UTRAU_FNB)

Источники (Google Sheets, помесячно — добавлять gid'ы в MONTHS):
  Файл №1 (сводка): 10mv7goP8z1z0P8P9AAY2YkAO1UF5atOTSpSMrrIZ-MY  (A1 summary, A2 banquets)
  Файл №2 (iiko):   12IY6jtT4tBI1YHL_Bl6S_VyJoNxA6oWD9pVqdKGTbPg  (B1-B6 продажи, B7-B12 списания)

Запуск: python scripts/build_fnb.py   (скачает недостающее и пересоберёт)
"""
import os, re, csv, json, io, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW  = ROOT / "data" / "fnb_raw"
OUT  = ROOT / "data" / "fnb_data.js"

F1 = "10mv7goP8z1z0P8P9AAY2YkAO1UF5atOTSpSMrrIZ-MY"   # сводка
F2 = "12IY6jtT4tBI1YHL_Bl6S_VyJoNxA6oWD9pVqdKGTbPg"   # iiko

# Месяц -> файлы и gid'ы вкладок. Каждый новый месяц добавлять сюда.
MONTHS = {
    "2026-01": {
        "summary":  (F1, "1642884690"),
        "banquets": (F1, "2082985573"),
        "sales": {                       # тип -> gid
            "alacarte":  (F2, "783385239"),    # B1 а-ля карт (кухня)
            "bar_soft":  (F2, "1830234765"),   # B2 бар безалкоголь
            "bar_alco":  (F2, "2045101424"),   # B3 бар алкоголь
            "banquet":   (F2, "1150083890"),   # B4 банкеты
            "breakfast": (F2, "920499580"),    # B5 шведка/завтраки
            "free":      (F2, "1806741079"),   # B6 без оплаты
        },
    },
}

# ── загрузка ──────────────────────────────────────────────────────────────
def fetch(sheet_id, gid, dest):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read().decode("utf-8", errors="replace")
    dest.write_text(data, encoding="utf-8")
    return data

def ensure_month(month, cfg, force=False):
    mdir = RAW / month
    mdir.mkdir(parents=True, exist_ok=True)
    files = {}
    # summary + banquets
    for key in ("summary", "banquets"):
        sid, gid = cfg[key]
        p = mdir / f"{key}.csv"
        if force or not p.exists():
            try: fetch(sid, gid, p); print(f"  [{month}] {key} downloaded")
            except Exception as e: print(f"  [{month}] {key} FAILED: {e}")
        files[key] = p
    # sales
    files["sales"] = {}
    for t, (sid, gid) in cfg["sales"].items():
        p = mdir / f"sales_{t}.csv"
        if force or not p.exists():
            try: fetch(sid, gid, p); print(f"  [{month}] sales_{t} downloaded")
            except Exception as e: print(f"  [{month}] sales_{t} FAILED: {e}")
        files["sales"][t] = p
    return files

# ── утилиты парсинга ───────────────────────────────────────────────────────
def rows(path):
    if not path.exists(): return []
    txt = path.read_text(encoding="utf-8")
    return list(csv.reader(io.StringIO(txt)))

def num(s):
    """'1 346 000,00 ₽' / '28,28' / '24,32%' -> float|None"""
    if s is None: return None
    s = str(s).strip()
    if s == "" or s in ("-", "—"): return None
    s = s.replace("₽", "").replace("₽", "").replace("%", "")
    s = s.replace("\xa0", "").replace(" ", "").replace(" ", "")
    s = s.replace(",", ".")
    if s in ("", "-", "."): return None
    try: return round(float(s), 2)
    except ValueError: return None

def norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())

def find_row(rws, *needles, after=0, need_num=False):
    """Первая строка (с after), где есть ВСЕ needles. need_num=True — ещё и с числовым значением.
    Возвращает (index, row, value)."""
    needles = [n.lower() for n in needles]
    for i in range(after, len(rws)):
        joined = norm(" | ".join(rws[i]))
        if all(n in joined for n in needles):
            v = first_num_in(rws[i])
            if need_num and v is None:
                continue
            return i, rws[i], v
    return -1, None, None

def first_num_in(row, after_col=2):
    # колонка A = "№ п/п" (порядковый номер), B = метка; значения начинаются с C (индекс 2)
    for j in range(after_col, len(row)):
        v = num(row[j])
        if v is not None: return v
    return None

def label_value(rws, *needles, after=0):
    """Числовое значение строки-метки (берём строку, где есть метка И число)."""
    _, _, v = find_row(rws, *needles, after=after, need_num=True)
    return v

# ── A1: сводка ──────────────────────────────────────────────────────────────
def parse_summary(path):
    r = rows(path)
    S = {}
    # выручка
    S["rev_breakfast_packets"] = label_value(r, "завтраки пакетные")
    S["rev_breakfast_counter"] = label_value(r, "завтраки от стойки")
    S["rev_breakfast"]         = label_value(r, "завтрак")       # строка-итого "Завтрак" (1 346 000)
    S["rev_kitchen"]           = label_value(r, "кухня")         # первая 'кухня' с числом = приход кухни
    S["rev_bar_soft"]          = label_value(r, "бар напитки")
    S["rev_bar_alco"]          = label_value(r, "бар алкоголь")
    S["rev_alacarte_total"]    = label_value(r, "а-ля карт")
    S["rev_banquet_food"]      = label_value(r, "питание")
    S["rev_banquet_hall"]      = label_value(r, "аренда зала")
    S["rev_banquet_cork"]      = label_value(r, "пробковый сбор")
    S["rev_banquet_total"]     = label_value(r, "банкеты")
    S["rev_services_total"]    = label_value(r, "услуги")
    S["income_total"]          = label_value(r, "итого приход дс")
    # себестоимость
    S["cogs_breakfast"] = label_value(r, "с/с (завтраки)")
    S["cogs_alacarte"]  = label_value(r, "с/с (а-ля карт)")
    S["cogs_banquet"]   = label_value(r, "с/с (банкет)")
    # списания
    S["wo_comp"]       = label_value(r, "комплементы")
    S["wo_spoilage"]   = label_value(r, "порча")
    S["wo_represent"]  = label_value(r, "представительские")
    S["wo_deletions"]  = label_value(r, "удаления со списанием")
    S["wo_staff"]      = label_value(r, "питание сотрудников")
    S["wo_free"]       = label_value(r, "закрыто без оплаты")
    S["wo_dev"]        = label_value(r, "проработка блюд")
    S["cost_total"]    = label_value(r, "итого расход продуктов")
    # товарный остаток
    S["inv_kitchen_start"] = label_value(r, "кухня начало")
    S["inv_kitchen_buy"]   = label_value(r, "кухня закуп")
    S["inv_kitchen_end"]   = label_value(r, "кухня конец")
    S["inv_bar_start"]     = label_value(r, "бар начало")
    S["inv_bar_buy"]       = label_value(r, "бар закуп")
    S["inv_bar_end"]       = label_value(r, "бар конец")
    S["inv_total"]         = label_value(r, "итого товарный остаток")
    # KPI
    S["guests_alacarte"] = label_value(r, "количество гостей по меню а-ля карт")
    S["guests_banquet"]  = label_value(r, "количество гостей на банкеты")
    S["check_alacarte"]  = label_value(r, "средний чек по меню")
    S["check_banquet"]   = label_value(r, "средний чек на банкеты")
    S["fc_kitchen"]      = label_value(r, "средний fc за месяц меню кухня")
    S["fc_bar"]          = label_value(r, "средний fc за месяц бар")
    S["fc_alacarte"]     = label_value(r, "средний fc за месяц меню a-la carte")
    S["fc_breakfast"]    = label_value(r, "средний fc за месяц завтраки")
    S["fc_banquet"]      = label_value(r, "средний fc за месяц банкет")
    S["fc_total"]        = label_value(r, "общий fc службы")
    return S

# ── A2: банкеты ──────────────────────────────────────────────────────────────
def parse_banquets(path):
    r = rows(path)
    out = []
    # ищем строку заголовка с 'заказчик'
    hi, _, _ = find_row(r, "заказчик")
    if hi < 0: return out
    for row in r[hi+1:]:
        joined = norm(" | ".join(row))
        if joined.startswith("итого") or "итого" in (norm(row[0]) if row else ""):
            continue
        # дата во 2-й колонке, заказчик в 3-й
        date = (row[1] if len(row) > 1 else "").strip()
        cust = (row[2] if len(row) > 2 else "").strip()
        if not cust: continue
        out.append({
            "date": date, "customer": cust,
            "format": (row[3] if len(row) > 3 else "").strip(),
            "guests": num(row[4]) if len(row) > 4 else None,
            "menu":   num(row[5]) if len(row) > 5 else None,
            "cogs":   num(row[6]) if len(row) > 6 else None,
            "fc":     num(row[7]) if len(row) > 7 else None,
            "check":  num(row[8]) if len(row) > 8 else None,
            "total":  num(row[16]) if len(row) > 16 else None,
            "profit": num(row[17]) if len(row) > 17 else None,
        })
    return out

# ── B1-B6: продажи по блюдам ──────────────────────────────────────────────────
def parse_sales(path):
    r = rows(path)
    # найти строку заголовка (содержит 'Блюдо')
    hi, hdr, _ = find_row(r, "блюдо")
    if hi < 0: return []
    cols = [norm(c) for c in hdr]
    def ci(*names):
        for n in names:
            for j, c in enumerate(cols):
                if n in c: return j
        return -1
    c_name = ci("блюдо")
    c_qty  = ci("количество блюд")
    c_rev  = ci("сумма со скидкой")
    c_cost = ci("себестоимость, р")
    c_g1   = ci("группа блюда 1")
    c_g2   = ci("группа блюда 2")
    items = []
    for row in r[hi+1:]:
        if not row: continue
        name = (row[c_name] if c_name >= 0 and c_name < len(row) else "").strip()
        if not name or norm(name) == "итого": continue
        rev = num(row[c_rev]) if 0 <= c_rev < len(row) else None
        qty = num(row[c_qty]) if 0 <= c_qty < len(row) else None
        cost = num(row[c_cost]) if 0 <= c_cost < len(row) else None
        if rev is None and qty is None and cost is None: continue
        items.append({
            "name": name,
            "g1": (row[c_g1].strip() if 0 <= c_g1 < len(row) else ""),
            "g2": (row[c_g2].strip() if 0 <= c_g2 < len(row) else ""),
            "qty": qty, "rev": rev or 0, "cost": cost or 0,
        })
    return items

# ── сборка ──────────────────────────────────────────────────────────────────
def build():
    months = {}
    for month, cfg in MONTHS.items():
        print(f"[{month}] ...")
        files = ensure_month(month, cfg)
        summary  = parse_summary(files["summary"])
        banquets = parse_banquets(files["banquets"])
        sales = {t: parse_sales(p) for t, p in files["sales"].items()}
        months[month] = {"summary": summary, "banquets": banquets, "sales": sales}
    data = {"generated": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
            "months": months}
    js = "// fnb_data.js — auto-generated, do not edit\nwindow.UTRAU_FNB=" + \
         json.dumps(data, ensure_ascii=False) + ";"
    OUT.write_text(js, encoding="utf-8")
    print(f"\nGenerated {OUT} ({len(months)} month(s))")
    return data

if __name__ == "__main__":
    build()
