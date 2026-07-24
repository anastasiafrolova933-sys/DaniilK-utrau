# -*- coding: utf-8 -*-
"""
build_fnb.py — F&B Службы питания Утрау (ресторан КАЕФ).

НОВАЯ схема (2026-07): каждый месяц = отдельный Google-файл (выгрузка iiko OLAP),
ссылки собираются в РЕЕСТРЕ-таблице (месяц -> ссылка на файл).
Парсер обходит ВСЕ вкладки книги, классифицирует их по СТРУКТУРЕ
(продажи / акты списания), собирает сводку -> data/fnb_data.js (window.UTRAU_FNB).

Реестр: 1ueE5blgChEYljlVnGktWKedsrcxfXXcn-U64X80AOQA
  колонка A = месяц (напр. «Июль 2026»), B = ссылка на файл месяца.
  Необязательные колонки (по ЗАГОЛОВКУ, если добавлены строкой сверху):
    «аренда зала», «гости а-ля карт», «гости банкет», «товарный остаток»,
    «пробковый», «услуги» — то, чего нет в выгрузке iiko.

Новый месяц = вставить строку (месяц + ссылка) в реестр. Файл должен быть
открыт «Доступ по ссылке -> Просмотр». Ничего в коде править не нужно.

Запуск: python scripts/build_fnb.py
"""
import re, io, json, csv, sys, urllib.request, datetime
from pathlib import Path
import openpyxl

try: sys.stdout.reconfigure(encoding="utf-8")   # Windows-консоль иначе падает на эмодзи/кириллице
except Exception: pass

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "data" / "fnb_data.js"
RAW  = ROOT / "data" / "fnb_raw"
RAW.mkdir(parents=True, exist_ok=True)

REGISTRY_ID = "1ueE5blgChEYljlVnGktWKedsrcxfXXcn-U64X80AOQA"

MONTHS_RU = {"янв":1,"фев":2,"мар":3,"апр":4,"май":5,"мая":5,"июн":6,
             "июл":7,"авг":8,"сен":9,"окт":10,"ноя":11,"дек":12}

# ── утилиты ───────────────────────────────────────────────────────────────
def num(v):
    if v is None: return None
    if isinstance(v, (int, float)): return round(float(v), 2)
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(" ", "")
    s = s.replace("₽", "").replace("%", "").replace(",", ".")
    if s in ("", "-", "—", "."): return None
    try: return round(float(s), 2)
    except ValueError: return None

def norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())

def month_key(text):
    s = norm(text)
    mon = None
    for k, v in MONTHS_RU.items():
        if s.startswith(k):
            mon = v; break
    ym = re.search(r"(20\d{2})", s)
    if mon and ym:
        return f"{ym.group(1)}-{mon:02d}"
    return None

def file_id(url):
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_\-]+)", str(url or ""))
    if m: return m.group(1)
    m = re.search(r"[?&]id=([A-Za-z0-9_\-]+)", str(url or ""))
    return m.group(1) if m else None

def http_get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

# ── реестр ────────────────────────────────────────────────────────────────
# Необязательные показатели: ключ summary -> ключевые слова в заголовке колонки
EXTRA_COLS = {
    "rev_banquet_hall": ["аренда", "зал"],
    "rev_banquet_cork": ["пробков", "cork"],
    "rev_services_total": ["услуг"],
    "guests_alacarte": ["гост", "карт"],
    "guests_banquet": ["гост", "банкет"],
    "inv_total": ["остаток", "инвентар", "товарн"],
}

def match_extra(header_cell):
    h = norm(header_cell)
    if not h: return None
    for key, words in EXTRA_COLS.items():
        if all(w in h for w in words):
            return key
    return None

def fetch_registry():
    """-> список dict: {month, file_id, extras{}}"""
    url = f"https://docs.google.com/spreadsheets/d/{REGISTRY_ID}/export?format=csv"
    raw = http_get(url, 30).decode("utf-8", errors="replace")
    if raw.lstrip().startswith("<"):
        raise RuntimeError("реестр недоступен (нет доступа по ссылке?)")
    rows = list(csv.reader(io.StringIO(raw)))

    # заголовок? (первая непустая строка, где A не распознаётся как месяц)
    extra_map = {}   # индекс колонки -> ключ summary
    start = 0
    for i, r in enumerate(rows):
        if not any(str(c).strip() for c in r):
            continue
        if month_key(r[0]) is None:            # это строка-заголовок
            for j, c in enumerate(r):
                k = match_extra(c)
                if k: extra_map[j] = k
            start = i + 1
        break

    out = []
    for r in rows[start:]:
        if not r or not str(r[0]).strip():
            continue
        mk = month_key(r[0])
        fid = file_id(r[1]) if len(r) > 1 else None
        if not mk or not fid:
            continue
        extras = {}
        for j, key in extra_map.items():
            if j < len(r):
                v = num(r[j])
                if v is not None:
                    extras[key] = v
        out.append({"month": mk, "file_id": fid, "extras": extras})
    return out

# ── классификация вкладок ───────────────────────────────────────────────────
SALE_CATS = [   # (ключевые слова в имени вкладки -> категория продаж)
    (["a-la carte", "a la carte", "а-ля карт", "меню a"], "kitchen"),
    (["бар напит", "напитки"], "bar_soft"),
    (["бар алког", "алкогол"], "bar_alco"),
    (["мероприят", "банкет"], "banquet"),
    (["завтрак"], "breakfast"),
    (["без оплат"], "free"),
]
WO_CATS = [     # (ключевые слова -> категория списаний)
    (["удален"], "wo_deletions"),
    (["комплемент", "комплимент"], "wo_comp"),
    (["представит"], "wo_represent"),
    (["стафф", "питание сотруд", "сотрудник"], "wo_staff"),
    (["порча"], "wo_spoilage"),
    (["проработ"], "wo_dev"),
]

def cat_by_name(name, table):
    n = norm(name)
    for words, cat in table:
        if any(w in n for w in words):
            return cat
    return None

def cat_by_content(rows, table):
    """Категория списания по колонке «Счёт списания» (когда имя вкладки — мусор, напр. «Лист1»)."""
    ci = -1
    for r in rows:
        for j, c in enumerate(r):
            if norm(c) in ("счёт списания", "счет списания"):
                ci = j; break
        if ci >= 0: break
    if ci < 0: return None
    txt = " ".join(norm(r[ci]) for r in rows if ci < len(r) and r[ci])
    for words, cat in table:
        if any(w in txt for w in words):
            return cat
    return None

DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}")

def find_header(rows, *needles):
    needles = [n.lower() for n in needles]
    for i, r in enumerate(rows):
        joined = norm(" | ".join("" if c is None else str(c) for c in r))
        if all(n in joined for n in needles):
            return i
    return -1

def classify(name, rows):
    """-> ('sale'|'writeoff'|'unknown', hint)"""
    if find_header(rows, "блюдо", "сумма со скидкой") >= 0:
        return "sale", cat_by_name(name, SALE_CATS)
    # акты списания: где-то «акты списания» или колонка «сумма, р.» + строки-даты
    has_acts = any("акты списания" in norm(" ".join("" if c is None else str(c) for c in r)) for r in rows[:3])
    has_sum  = find_header(rows, "сумма, р") >= 0
    has_dates = any(rows and DATE_RE.match(str(r[0]).strip()) for r in rows if r and r[0] is not None)
    if has_acts or (has_sum and has_dates):
        return "writeoff", cat_by_name(name, WO_CATS)
    return "unknown", None

def period_month(rows):
    """месяц из строки 'Период: с 01.07.2026 ...' внутри листа -> 'YYYY-MM' | None"""
    for r in rows[:6]:
        for c in r:
            m = re.search(r"с\s*\d{2}\.(\d{2})\.(\d{4})", str(c or ""))
            if m:
                return f"{m.group(2)}-{m.group(1)}"
    return None

# ── парсинг листов ──────────────────────────────────────────────────────────
def parse_sale(rows):
    """-> (rev_total, cost_total, items[])  берём строку «Итого» + позиции."""
    hi = find_header(rows, "блюдо")
    if hi < 0: return 0.0, 0.0, []
    hdr = [norm(c) for c in rows[hi]]
    def ci(*names):
        for nm in names:
            for j, c in enumerate(hdr):
                if nm in c: return j
        return -1
    c_name = ci("блюдо"); c_qty = ci("количество блюд")
    c_rev = ci("сумма со скидкой"); c_cost = ci("себестоимость, р")
    c_g1 = ci("группа блюда 1"); c_g2 = ci("группа блюда 2")
    items = []; rev_itogo = cost_itogo = None; rev_sum = cost_sum = 0.0
    for r in rows[hi+1:]:
        first = norm(r[c_name]) if 0 <= c_name < len(r) else ""
        if first == "":
            continue
        if first == "итого":
            rev_itogo  = num(r[c_rev])  if 0 <= c_rev  < len(r) else None
            cost_itogo = num(r[c_cost]) if 0 <= c_cost < len(r) else None
            continue
        rev = num(r[c_rev]) if 0 <= c_rev < len(r) else None
        qty = num(r[c_qty]) if 0 <= c_qty < len(r) else None
        cost = num(r[c_cost]) if 0 <= c_cost < len(r) else None
        if rev is None and qty is None and cost is None:
            continue
        items.append({"name": str(r[c_name]).strip(),
                      "g1": (str(r[c_g1]).strip() if 0 <= c_g1 < len(r) and r[c_g1] else ""),
                      "g2": (str(r[c_g2]).strip() if 0 <= c_g2 < len(r) and r[c_g2] else ""),
                      "qty": qty, "rev": rev or 0, "cost": cost or 0})
        rev_sum += rev or 0; cost_sum += cost or 0
    # «Итого» приоритетнее (точные значения iiko); иначе — сумма позиций
    rev_total  = rev_itogo  if rev_itogo  is not None else round(rev_sum, 2)
    cost_total = cost_itogo if cost_itogo is not None else round(cost_sum, 2)
    return rev_total, cost_total, items

def parse_writeoff(rows):
    """сумма колонки «Сумма, р.» по строкам-датам."""
    c_sum = 4
    for r in rows:
        for j, c in enumerate(r):
            if norm(c) == "сумма, р.":
                c_sum = j; break
    total = 0.0
    for r in rows:
        first = str(r[0]).strip() if r and r[0] is not None else ""
        if DATE_RE.match(first) and c_sum < len(r):
            v = num(r[c_sum])
            if v: total += v
    return round(total, 2)

# ── сборка одного месяца ────────────────────────────────────────────────────
def build_month(entry, log):
    mk, fid, extras = entry["month"], entry["file_id"], entry["extras"]
    # скачать xlsx
    data = None
    for u in (f"https://docs.google.com/spreadsheets/d/{fid}/export?format=xlsx",
              f"https://drive.google.com/uc?export=download&id={fid}"):
        try:
            raw = http_get(u)
            if raw[:2] == b"PK":
                data = raw; break
        except Exception as e:
            log.append(f"  [{mk}] download err: {e}")
    if data is None:
        log.append(f"  [{mk}] ❌ не удалось скачать файл {fid}")
        return None
    xpath = RAW / f"{mk}.xlsx"; xpath.write_bytes(data)
    wb = openpyxl.load_workbook(xpath, read_only=True, data_only=True)

    cat_rev, cat_cost, sales = {}, {}, {}
    other_rev = other_cost = other_wo = 0.0
    wo = {"wo_deletions":0.0,"wo_comp":0.0,"wo_represent":0.0,"wo_staff":0.0,"wo_spoilage":0.0,"wo_dev":0.0}
    seen_period = None

    for sheet in wb.sheetnames:
        rows = [list(r) for r in wb[sheet].iter_rows(values_only=True)]
        rows = [r for r in rows if any(c is not None and str(c).strip() for c in r)]
        if not rows:
            continue
        seen_period = seen_period or period_month(rows)
        kind, cat = classify(sheet, rows)
        if kind == "sale":
            rev, cost, items = parse_sale(rows)
            if cat:
                cat_rev[cat] = cat_rev.get(cat, 0) + rev
                cat_cost[cat] = cat_cost.get(cat, 0) + cost
                sales.setdefault(cat, []).extend(items)
            else:
                other_rev += rev; other_cost += cost
                log.append(f"  [{mk}] ⚠️ незнакомая ВКЛАДКА-ПРОДАЖИ «{sheet}» ({rev:,.0f} ₽) — учтена в прочее")
        elif kind == "writeoff":
            total = parse_writeoff(rows)
            if cat is None:
                cat = cat_by_content(rows, WO_CATS)   # по «Счёт списания», если имя вкладки не помогло
            if cat:
                wo[cat] = wo.get(cat, 0) + total
            else:
                other_wo += total
                log.append(f"  [{mk}] ⚠️ незнакомая ВКЛАДКА-СПИСАНИЯ «{sheet}» ({total:,.0f} ₽) — учтена в прочее")
        else:
            log.append(f"  [{mk}] ⚠️ вкладка «{sheet}» не распознана ({len(rows)} строк) — пропущена")

    if seen_period and seen_period != mk:
        log.append(f"  [{mk}] ⚠️ период в файле = {seen_period} (реестр говорит {mk}) — проверьте ссылку")

    # ── сводка ──
    g = lambda k: cat_rev.get(k, 0)
    c = lambda k: cat_cost.get(k, 0)
    rev_kitchen = g("kitchen"); rev_bs = g("bar_soft"); rev_ba = g("bar_alco")
    rev_bfast = g("breakfast"); rev_banq = g("banquet")
    cogs_kitchen = c("kitchen"); cogs_bs = c("bar_soft"); cogs_ba = c("bar_alco")
    cogs_bfast = c("breakfast"); cogs_banq = c("banquet")
    rev_alacarte_total = rev_kitchen + rev_bs + rev_ba
    cogs_alacarte = cogs_kitchen + cogs_bs + cogs_ba
    # завтраки: пакетные (ЮЛ) vs от стойки — по позициям
    bp = bc = 0.0
    for it in sales.get("breakfast", []):
        if "юл" in norm(it["g1"]) or (it.get("qty") or 0) >= 100: bp += it["rev"]
        else: bc += it["rev"]
    wo_sum = sum(wo.values()) + other_wo
    income_total = rev_kitchen + rev_bs + rev_ba + rev_bfast + rev_banq + other_rev
    income_total += extras.get("rev_banquet_hall", 0) + extras.get("rev_banquet_cork", 0) + extras.get("rev_services_total", 0)
    cost_total = cogs_bfast + cogs_alacarte + cogs_banq + wo_sum + other_cost
    pct = lambda a, b: round(a / b * 100, 2) if b else None
    ga = extras.get("guests_alacarte"); gb = extras.get("guests_banquet")

    summary = {
        "rev_breakfast_packets": round(bp, 2), "rev_breakfast_counter": round(bc, 2),
        "rev_breakfast": round(rev_bfast, 2), "rev_kitchen": round(rev_kitchen, 2),
        "rev_bar_soft": round(rev_bs, 2), "rev_bar_alco": round(rev_ba, 2),
        "rev_alacarte_total": round(rev_alacarte_total, 2),
        "rev_banquet_food": round(rev_banq, 2),
        "rev_banquet_hall": extras.get("rev_banquet_hall"),
        "rev_banquet_cork": extras.get("rev_banquet_cork"),
        "rev_banquet_total": (round(rev_banq + extras.get("rev_banquet_hall", 0) + extras.get("rev_banquet_cork", 0), 2)
                              if ("rev_banquet_hall" in extras or "rev_banquet_cork" in extras) else None),
        "rev_services_total": extras.get("rev_services_total"),
        "income_total": round(income_total, 2),
        "cogs_breakfast": round(cogs_bfast, 2), "cogs_alacarte": round(cogs_alacarte, 2),
        "cogs_banquet": round(cogs_banq, 2),
        "wo_comp": wo["wo_comp"], "wo_spoilage": wo["wo_spoilage"], "wo_represent": wo["wo_represent"],
        "wo_deletions": wo["wo_deletions"], "wo_staff": wo["wo_staff"], "wo_free": 0.0,
        "wo_dev": wo["wo_dev"], "cost_total": round(cost_total, 2),
        "inv_kitchen_start": None, "inv_kitchen_buy": None, "inv_kitchen_end": None,
        "inv_bar_start": None, "inv_bar_buy": None, "inv_bar_end": None,
        "inv_total": extras.get("inv_total"),
        "guests_alacarte": ga, "guests_banquet": gb,
        "check_alacarte": round(rev_alacarte_total / ga, 2) if ga else None,
        "check_banquet": round(rev_banq / gb, 2) if gb else None,
        "fc_kitchen": pct(cogs_kitchen, rev_kitchen), "fc_bar": pct(cogs_bs + cogs_ba, rev_bs + rev_ba),
        "fc_alacarte": pct(cogs_alacarte, rev_alacarte_total), "fc_breakfast": pct(cogs_bfast, rev_bfast),
        "fc_banquet": pct(cogs_banq, rev_banq),
        "fc_total": pct(cogs_bfast + cogs_alacarte + cogs_banq, income_total),
    }
    # «Без оплаты» — приход 0, интересна себестоимость -> кладём в wo_free
    if "free" in cat_cost:
        summary["wo_free"] = round(cat_cost["free"], 2)
        summary["cost_total"] = round(summary["cost_total"] + cat_cost["free"], 2)

    log.append(f"  [{mk}] ✓ выручка {income_total:,.0f} ₽ | списания {wo_sum:,.0f} | "
               f"вкладок-продаж {len(cat_rev)} | FC {summary['fc_total']}%")
    return {"summary": summary, "sales": sales, "banquets": []}

# ── main ────────────────────────────────────────────────────────────────────
def build():
    log = []
    reg = fetch_registry()
    log.append(f"Реестр: {len(reg)} месяц(ев) со ссылками: " + ", ".join(e["month"] for e in reg))
    months = {}
    for entry in reg:
        m = build_month(entry, log)
        if m: months[entry["month"]] = m
    data = {"generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "months": months}
    js = "// fnb_data.js — auto-generated (registry+all-tabs), do not edit\nwindow.UTRAU_FNB=" + \
         json.dumps(data, ensure_ascii=False) + ";"
    OUT.write_text(js, encoding="utf-8")
    print("\n".join(log))
    print(f"\nGenerated {OUT} ({len(months)} month(s))")

if __name__ == "__main__":
    build()
