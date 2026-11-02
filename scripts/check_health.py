# -*- coding: utf-8 -*-
"""
check_health.py — ежедневная проверка «живы ли данные» всех отчётов Утрау.

Зачем (02.11.2026): данные стояли 2+ месяца, а портал писал «Обновлено <сегодня>» —
это было время СБОРКИ, а не дата ДАННЫХ. Никто не заметил. Теперь после каждой сборки:
  * по каждому отчёту считается, по какую дату/месяц есть данные и насколько это отстаёт
    от ожидаемого; собираются все проблемы сборщиков (закрытые файлы, пустые вкладки,
    сдвиг колонок, нечитаемые ячейки, ошибки реестра);
  * результат -> data/health.json (его читает портал: плашка «данные по …») и готовый текст
    сводки -> для лога, push и будущего Telegram-бота.

Запуск: python scripts/check_health.py   (печатает сводку; код выхода 0 — ok, 1 — warn, 2 — error)
"""
import re, sys, json, datetime
from pathlib import Path

try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT  = DATA / "health.json"

# ── пороги ────────────────────────────────────────────────────────────────────
DAILY_WARN_DAYS  = 3     # «Доходность»: данные по дням; >3 дн. без новых строк — предупреждение
DAILY_ERROR_DAYS = 7     #                                  >7 дн. — тревога
MONTH_READY_DAY = {      # к какому числу следующего месяца закрытый месяц уже должен быть в отчёте
    "budget": 25,        # бухгалтерия закрывает месяц к ~25-му
    "fnb": 15,
    "spa": 15,
}
STALE_BUILD_HOURS = 26   # файл данных не пересобирался дольше — сломан сам конвейер

MONTHS_GEN = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
              "сентябрь", "октябрь", "ноябрь", "декабрь"]

def load_js(name, var):
    path = DATA / name
    if not path.exists(): return None, f"нет файла {name}"
    s = path.read_text(encoding="utf-8-sig")
    try:
        body = s[s.index(var + "=") + len(var) + 1:].rstrip().rstrip(";")
        # старый формат dashboard_data.js (до 02.11.2026) — ключи без кавычек
        body = re.sub(r'([{,])\s*(generated|daily)\s*:', r'\1"\2":', body)
        return json.loads(body), None
    except Exception as e:
        return None, f"{name} не читается ({type(e).__name__})"

def ym(y, m):            return y * 12 + (m - 1)
def ym_str(v):           return f"{v // 12}-{v % 12 + 1:02d}"
def ym_label(v):         return f"{MONTHS_GEN[v % 12]} {v // 12}"
def key_ym(k):           y, m = k.split("-"); return ym(int(y), int(m))

def expected_month(today, ready_day):
    """последний месяц, который к сегодняшнему дню уже должен быть закрыт"""
    cur = ym(today.year, today.month)
    return cur - 1 if today.day >= ready_day else cur - 2

def month_state(lag):
    return "ok" if lag <= 0 else ("warn" if lag == 1 else "error")

def build_age_problem(gen, now):
    try:
        t = datetime.datetime.strptime(gen, "%Y-%m-%d %H:%M")
    except Exception:
        return None
    h = (now - t).total_seconds() / 3600
    return f"файл не пересобирался {h:.0f} ч (последняя сборка {t:%d.%m %H:%M}) — проверьте задачу UtrauDashboardUpdate" \
        if h > STALE_BUILD_HOURS else None

def worst(*states):
    order = {"ok": 0, "warn": 1, "error": 2}
    return max(states, key=lambda s: order[s]) if states else "ok"

# ── отчёты ────────────────────────────────────────────────────────────────────
def check_finance(today, now):
    r = {"title": "Доходность и загрузка", "page": "finance.html", "problems": [], "notes": []}
    d, err = load_js("dashboard_data.js", "window.UTRAU_DATA")
    if err:
        r.update(state="error", summary=err); r["problems"].append(err); return r
    daily = d.get("daily") or []
    if not daily:
        r.update(state="error", summary="нет ни одного дня с данными"); return r
    last = max(x["date"] for x in daily)
    lag = (today - datetime.date.fromisoformat(last)).days
    r.update(dataTo=last, dataToLabel=datetime.date.fromisoformat(last).strftime("%d.%m.%Y"), lagDays=lag, built=d.get("generated"))
    state = "ok" if lag <= DAILY_WARN_DAYS else ("warn" if lag <= DAILY_ERROR_DAYS else "error")
    if state != "ok":
        r["problems"].append(f"последний день с цифрами — {r['dataToLabel']}, новых строк нет {lag} дн. "
                             f"(таблица «Доходность и загрузка» не заполняется)")
    st = d.get("status") or {}
    for t in st.get("tabs", []):
        name = t.get("tab")
        if t.get("state") in ("no_header", "missing_required"):
            # служебные вкладки без шапки — не ошибка, но видно, что их не читаем
            r["notes"].append(f"вкладка «{name}» без шапки «Дата / Доход за проживание» — не читается")
        elif t.get("state") in ("download_error", "no_file"):
            r["problems"].append(f"вкладка «{name}» не скачалась: {t.get('download_error', t.get('state'))}"); state = worst(state, "error")
        if t.get("download_error") and t.get("state") == "ok":
            r["problems"].append(f"вкладка «{name}» не скачалась сегодня — показана прошлая копия"); state = worst(state, "warn")
        if t.get("missing_columns"):
            r["problems"].append(f"вкладка «{name}»: нет колонок {', '.join(t['missing_columns'])}"); state = worst(state, "warn")
        if t.get("bad_cells"):
            r["problems"].append(f"вкладка «{name}»: нечитаемые ячейки ({len(t['bad_cells'])}): {'; '.join(t['bad_cells'][:5])}")
            state = worst(state, "warn")
        if t.get("placeholders") and t.get("placeholder_range"):
            a, b = t["placeholder_range"]
            r["notes"].append(f"во вкладке «{name}» заготовлены пустые даты {a[8:]}.{a[5:7]}–{b[8:]}.{b[5:7]} без цифр")
    for w in st.get("warnings", []):
        r["problems"].append(w); state = worst(state, "warn")
    ba = build_age_problem(d.get("generated"), now)
    if ba: r["problems"].append(ba); state = "error"
    r["state"] = state
    r["summary"] = f"данные по {r['dataToLabel']}" + ("" if lag <= DAILY_WARN_DAYS else f" — {lag} дн. без новых строк")
    return r

def check_budget(today, now):
    r = {"title": "Бюджет (БДР / БДДС)", "page": "budget.html", "problems": [], "notes": []}
    d, err = load_js("budget_data.js", "window.UTRAU_BUDGET")
    if err:
        r.update(state="error", summary=err); r["problems"].append(err); return r
    st = d.get("status") or {}
    year = st.get("year") or 2026
    lf = (st.get("lastFactMonth") or {})
    last_m = min(v for v in [lf.get("bdr"), lf.get("bdds")] if v is not None) if lf else 0
    exp = expected_month(today, MONTH_READY_DAY["budget"])
    if not last_m:
        r.update(state="error", summary="факт не заполнен ни за один месяц", built=d.get("generated"))
        r["problems"].append("в бюджете нет ни одного месяца с фактической выручкой")
        return r
    last = ym(year, last_m); lag = exp - last
    r.update(dataTo=ym_str(last), dataToLabel=ym_label(last), lagMonths=lag, built=d.get("generated"))
    state = month_state(lag)
    if lag > 0:
        r["problems"].append(f"факт 2026 заполнен по {ym_label(last)}; к этой дате ждём по {ym_label(exp)} "
                             f"(отстаёт на {lag} мес.)")
    if lf.get("bdr") != lf.get("bdds"):
        r["notes"].append(f"факт в БДР по {MONTHS_GEN[(lf.get('bdr') or 1) - 1]}, в БДДС по {MONTHS_GEN[(lf.get('bdds') or 1) - 1]}")
    for w in st.get("warnings", []):
        r["problems"].append(w); state = worst(state, "warn")
    if (st.get("layout") or {}).get("bdr") == "fallback" or (st.get("layout") or {}).get("bdds") == "fallback":
        state = worst(state, "error")
    ba = build_age_problem(d.get("generated"), now)
    if ba: r["problems"].append(ba); state = "error"
    r["state"] = state
    r["summary"] = f"факт по {ym_label(last)}" + ("" if lag <= 0 else f" — ждём по {ym_label(exp)}")
    return r

FNB_STATE_TEXT = {
    "no_access": "файл закрыт — владельцу открыть «Доступ по ссылке → Просмотр»",
    "not_found": "файл не найден (удалён или ссылка неверная)",
    "error": "не скачался",
    "unknown_format": "формат файла не распознан",
    "empty": "файл пустой",
}

def check_fnb(today, now):
    r = {"title": "F&B (ресторан)", "page": "fnb.html", "problems": [], "notes": []}
    d, err = load_js("fnb_data.js", "window.UTRAU_FNB")
    if err:
        r.update(state="error", summary=err); r["problems"].append(err); return r
    months = d.get("months") or {}
    status = d.get("status") or {}
    exp = expected_month(today, MONTH_READY_DAY["fnb"])
    state = "ok"
    have = sorted(key_ym(k) for k in months)
    last = have[-1] if have else None
    r["built"] = d.get("generated")
    for mk, s in sorted(status.items()):
        v = key_ym(mk)
        if s.get("state") in FNB_STATE_TEXT:
            r["problems"].append(f"{ym_label(v)}: {FNB_STATE_TEXT[s['state']]}"); state = "error"
        elif s.get("state") == "cache":
            r["problems"].append(f"{ym_label(v)}: сегодня не скачался — показана прошлая копия"); state = worst(state, "warn")
        for w in s.get("warnings", []):
            text = re.sub(r"^\[\d{4}-\d{2}\]\s*", "", w).replace("⚠️", "").strip()
            r["problems"].append(f"{ym_label(v)}: {text}")
            state = worst(state, "warn")
    for it in d.get("registry_issues") or []:
        r["problems"].append(f"реестр, строка {it['row']} «{it['text']}»: {it['problem']}"); state = worst(state, "warn")
    if last is not None:
        in_reg = {key_ym(k) for k in status}
        missing = [m for m in range(have[0], exp + 1) if m not in in_reg]
        if missing:
            r["problems"].append("нет в реестре: " + ", ".join(ym_label(m) for m in missing))
        lag = exp - last
        r.update(dataTo=ym_str(last), dataToLabel=ym_label(last), lagMonths=lag)
        state = worst(state, month_state(lag))
        r["summary"] = f"данные по {ym_label(last)}" + ("" if lag <= 0 else f" — ждём по {ym_label(exp)}")
    else:
        state = "error"; r["summary"] = "нет ни одного месяца"
    ba = build_age_problem(d.get("generated"), now)
    if ba: r["problems"].append(ba); state = "error"
    r["state"] = state
    return r

def check_spa(today, now):
    r = {"title": "СПА / Банный комплекс", "page": "spa.html", "problems": [], "notes": []}
    d, err = load_js("spa_data.js", "window.UTRAU_SPA")
    if err:
        r.update(state="error", summary=err); r["problems"].append(err); return r
    months = d.get("months") or {}
    st = d.get("status") or {}
    exp = expected_month(today, MONTH_READY_DAY["spa"])
    have = sorted(key_ym(k) for k in months)
    r["built"] = d.get("generated")
    if not have:
        r.update(state="error", summary="нет ни одного месяца"); return r
    last = have[-1]; lag = exp - last
    r.update(dataTo=ym_str(last), dataToLabel=ym_label(last), lagMonths=lag)
    state = month_state(lag)
    empty_due = [t for t in st.get("empty_tabs", []) if t.get("month") and key_ym(t["month"]) <= exp]
    if empty_due:
        r["problems"].append("вкладки созданы, но пустые: " + ", ".join(f"«{t['tab']}»" for t in empty_due))
    gaps = [m for m in range(have[0], exp + 1) if m not in set(have)
            and not any(t.get("month") and key_ym(t["month"]) == m for t in empty_due)]
    if gaps:
        r["problems"].append("нет вкладки за: " + ", ".join(ym_label(m) for m in gaps))
    if lag > 0 and not empty_due and not gaps:
        r["problems"].append(f"данные по {ym_label(last)}; ждём по {ym_label(exp)}")
    for t in st.get("unrecognized_tabs", []):
        r["problems"].append(f"вкладка «{t}»: не понять месяц по имени — не читается"); state = worst(state, "warn")
    for x in st.get("same_month_tabs", []):
        r["problems"].append(f"{x['month']} в двух вкладках ({', '.join(x['tabs'])}) — взята большая"); state = worst(state, "warn")
    for x in st.get("duplicate_content", []):
        r["notes"].append(f"вкладки «{x['tabs'][0]}» и «{x['tabs'][1]}» совпадают построчно — похоже, скопирована и не обновлена")
    ba = build_age_problem(d.get("generated"), now)
    if ba: r["problems"].append(ba); state = "error"
    r["state"] = state
    r["summary"] = f"данные по {ym_label(last)}" + ("" if lag <= 0 else f" — ждём по {ym_label(exp)}")
    return r

ICON = {"ok": "✅", "warn": "⚠️", "error": "❌"}

def main():
    now = datetime.datetime.now(); today = now.date()
    reports = {"finance": check_finance(today, now), "budget": check_budget(today, now),
               "fnb": check_fnb(today, now), "spa": check_spa(today, now)}
    overall = worst(*[r["state"] for r in reports.values()])
    lines = [f"Утрау — проверка данных {now:%d.%m.%Y %H:%M}"]
    for r in reports.values():
        lines.append(f"{ICON[r['state']]} {r['title']}: {r.get('summary', '')}")
        for p in r["problems"]:
            lines.append(f"    • {p}")
        for n in r["notes"]:
            lines.append(f"    · {n}")
    short = "; ".join(f"{r['title']} — {r.get('summary', '')}" for r in reports.values() if r["state"] != "ok")
    health = {"checked": now.strftime("%Y-%m-%d %H:%M"), "overall": overall,
              "short": short or "все отчёты свежие", "text": "\n".join(lines), "reports": reports}
    OUT.write_text(json.dumps(health, ensure_ascii=False, indent=1), encoding="utf-8")
    print(health["text"])
    print(f"HEALTH: {overall}")
    return {"ok": 0, "warn": 1, "error": 2}[overall]

if __name__ == "__main__":
    sys.exit(main())
