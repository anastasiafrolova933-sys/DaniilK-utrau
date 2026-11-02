# -*- coding: utf-8 -*-
"""
build_finance.py — «Доходность и загрузка» Утрау (выгрузка Shelter, по дням).
Google Sheets -> data/dashboard_data.js (window.UTRAU_DATA)

Чем лучше прежнего build.ps1 (02.11.2026):
  * ВКЛАДКИ находятся сами (страница htmlview отдаёт имя+gid) — новая вкладка «2027»
    подхватится без правки кода; запасной список gid ниже — если Google не ответил.
  * КОЛОНКИ берутся по ЗАГОЛОВКАМ строки «Дата | Доход за проживание | …», а не по номерам:
    вставка/перестановка колонки в таблице больше не сдвигает цифры молча.
    Нет обязательной колонки -> вкладка пропущена с ошибкой в статусе (а не мусор на дашборде).
  * CSV читается настоящим CSV-парсером (кавычки, переносы строк внутри ячеек).
  * В файл пишется status: последняя дата с данными, заготовки дат без цифр, нечитаемые
    ячейки, неизвестные вкладки — по нему check_health.py поднимает тревогу.

Запуск: python scripts/build_finance.py            (скачать + собрать)
        python scripts/build_finance.py --offline  (собрать из уже скачанных data/raw_*.csv)
"""
import re, io, sys, csv, json, datetime, urllib.request
from pathlib import Path

try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT  = DATA / "dashboard_data.js"
SHEET_ID = "1N9YFy76rV3KcZnN5EwSt8Y-Ji0Y7WpHkwkBrgndChuw"
KNOWN_TABS = {"2024": "1688657215", "2025": "881244924", "2026": "253518640"}   # запасной вариант

# поле дашборда -> признаки заголовка (все слова должны быть в тексте заголовка)
COLUMNS = [
    ("revenue",       ["доход", "проживан"]),
    ("roomNights",    ["продано", "номероноч"]),
    ("guestArrivals", ["заезд", "гост"]),
    ("roomArrivals",  ["заезд", "номер"]),
    ("adr",           ["adr"]),
    ("revpar",        ["revpar"]),
    ("als",           ["als"]),
    ("totalRooms",    ["всего", "номеров"]),
    ("underRepair",   ["ремонт"]),
    ("availRooms",    ["доступно"]),
    ("occupancy",     ["загрузк"]),
]
REQUIRED = {"revenue", "roomNights", "occupancy"}
FIELDS = [c for c, _ in COLUMNS]
DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")

def http_get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())

def num(s):
    """'1 234,56' / '85,11 %' / '' -> float | None; нечитаемое -> 'BAD'"""
    t = str(s or "").strip()
    if t == "": return None
    t = re.sub(r"\s", "", t).replace(" ", "").replace("%", "").replace(",", ".").replace('"', "")
    if t in ("", "-", "—"): return None
    try: return round(float(t), 2)
    except ValueError: return "BAD"

def discover_tabs(status):
    """[(name, gid)] из htmlview; при ошибке — KNOWN_TABS"""
    try:
        html = http_get(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/htmlview", 60).decode("utf-8", "replace")
        pairs = re.findall(r'\{name: "((?:[^"\\]|\\.)*)", pageUrl: "[^"]*?gid=(\d+)', html)
        if pairs:
            def unjs(s):                                  # имя может прийти с \uXXXX-экранированием
                try: return json.loads(f'"{s}"')
                except ValueError: return s
            return [(unjs(n), g) for n, g in pairs]
        status["warnings"].append("список вкладок не найден на странице htmlview — взят запасной список gid")
    except Exception as e:
        status["warnings"].append(f"список вкладок недоступен ({type(e).__name__}) — взят запасной список gid")
    return list(KNOWN_TABS.items())

def safe_name(tab):
    return re.sub(r"[^0-9A-Za-zА-Яа-яЁё_-]+", "_", tab.strip()) or "tab"

def find_header(rows):
    """-> (index, {field: col}) по строке, где есть «дата» и «доход за проживание»"""
    for i, r in enumerate(rows[:60]):
        cells = [norm(c) for c in r]
        if not any(c == "дата" for c in cells): continue
        cmap = {}
        for field, words in COLUMNS:
            for j, c in enumerate(cells):
                if j in cmap.values(): continue
                if all(w in c for w in words):
                    # «Всего номеров» не путать с «Всего доступно номеров», «заезд номеров» — с «номероночей»
                    if field == "totalRooms" and "доступ" in c: continue
                    if field == "roomArrivals" and "номероноч" in c: continue
                    cmap[field] = j; break
        if "revenue" in cmap:
            return i, cmap
    return -1, {}

def parse_tab(name, text, tstat):
    rows = list(csv.reader(io.StringIO(text)))
    hi, cmap = find_header(rows)
    if hi < 0:
        tstat["state"] = "no_header"; return []
    missing = [f for f in FIELDS if f not in cmap]
    if missing: tstat["missing_columns"] = missing
    if REQUIRED - set(cmap):
        tstat["state"] = "missing_required"; return []
    date_col = next(j for j, c in enumerate(rows[hi]) if norm(c) == "дата")
    recs, placeholders, bad = [], [], []
    for r in rows[hi + 1:]:
        r = r + [""] * 30
        # дата обычно в колонке «Дата»; в части строк (вставка вручную) она съезжает на 1 вправо
        d = None
        for j in (date_col, date_col + 1):
            m = DATE_RE.match(str(r[j]).strip())
            if m: d = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))); break
        if d is None: continue
        vals = {f: num(r[cmap[f]]) if f in cmap else None for f in FIELDS}
        if vals["revenue"] is None:                    # заготовка будущей даты — цифр ещё нет
            placeholders.append(d.isoformat()); continue
        for f, v in vals.items():
            if v == "BAD":
                bad.append(f"{d.strftime('%d.%m.%Y')} {f}={r[cmap[f]]!r}"); vals[f] = None
        rec = {"date": d.isoformat(), "year": d.year}
        rec.update({f: (vals[f] if vals[f] is not None else 0) for f in FIELDS})
        recs.append(rec)
    tstat.update(state="ok", records=len(recs))
    if recs:
        tstat["first"] = recs[0]["date"]; tstat["last"] = max(x["date"] for x in recs)
    if placeholders:
        tstat["placeholders"] = len(placeholders)
        tstat["placeholder_range"] = [min(placeholders), max(placeholders)]
    if bad: tstat["bad_cells"] = bad[:20]
    return recs

def js_num(v):
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return json.dumps(v)

def build(offline=False):
    status = {"tabs": [], "warnings": []}
    tabs = list(KNOWN_TABS.items()) if offline else discover_tabs(status)
    byday = {}
    for name, gid in tabs:
        fname = f"raw_{name}.csv" if re.fullmatch(r"20\d{2}", name.strip()) else f"raw_tab_{safe_name(name)}.csv"
        path = DATA / fname
        tstat = {"tab": name.strip(), "gid": gid, "file": fname}
        status["tabs"].append(tstat)
        if not offline:
            try:
                raw = http_get(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}")
                if raw.lstrip()[:1] == b"<": raise RuntimeError("вместо CSV пришла HTML-страница (нет доступа?)")
                path.write_bytes(raw)
            except Exception as e:
                tstat["download_error"] = f"{type(e).__name__}: {e}"
                if not path.exists():
                    tstat["state"] = "download_error"; continue
                status["warnings"].append(f"вкладка «{name}» не скачалась — взята прошлая копия {fname}")
        if not path.exists():
            tstat["state"] = "no_file"; continue
        recs = parse_tab(name, path.read_text(encoding="utf-8-sig", errors="replace"), tstat)
        for rec in recs:
            if rec["date"] in byday:
                status["warnings"].append(f"дата {rec['date']} есть в двух вкладках — взята вкладка «{name.strip()}»")
            byday[rec["date"]] = rec
        print(f"[{name.strip()}] {tstat.get('state')} | дней: {tstat.get('records', 0)}"
              + (f" | по {tstat['last']}" if tstat.get("last") else "")
              + (f" | заготовок без цифр: {tstat['placeholders']}" if tstat.get("placeholders") else "")
              + (f" | нет колонок: {', '.join(tstat['missing_columns'])}" if tstat.get("missing_columns") else "")
              + (f" | нечитаемых ячеек: {len(tstat['bad_cells'])}" if tstat.get("bad_cells") else ""))

    daily = [byday[d] for d in sorted(byday)]
    if not daily:
        print("❌ нет ни одной строки с данными — dashboard_data.js НЕ перезаписан"); return 2
    status["lastDate"] = daily[-1]["date"]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = ",\n  ".join("{" + ",".join(f'"{k}":' + (json.dumps(v) if k == "date" else js_num(v))
                                       for k, v in rec.items()) + "}" for rec in daily)
    js = (f"// Auto-generated {now} by build_finance.py - do not edit\n"
          f'window.UTRAU_DATA={{"generated":"{now}","lastDate":"{status["lastDate"]}",'
          f'"status":{json.dumps(status, ensure_ascii=False)},"daily":[\n  {rows}\n]}};')
    OUT.write_text(js, encoding="utf-8")
    for w in status["warnings"]: print("⚠️", w)
    print(f"dashboard_data.js -> {len(daily)} дней, последняя дата с данными {status['lastDate']}")
    return 0

if __name__ == "__main__":
    sys.exit(build(offline="--offline" in sys.argv))
