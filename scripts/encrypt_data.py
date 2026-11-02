# -*- coding: utf-8 -*-
"""
encrypt_data.py — шифрует данные портала перед публикацией (с 2026-11-02).

Репозиторий и GitHub Pages публичные: до 02.11.2026 data/*.js лежали открыто, и отчёты
открывались по прямой ссылке без пароля. Теперь на сайт уходят только зашифрованные копии
(data/enc/), а открытые data/*.js, health.json и сырые CSV остаются на этом ПК: их читают
Telegram-бот, push и check_health.py, в git они не попадают (.gitignore).

Шифр: AES-256-GCM, ключ = PBKDF2-SHA256(пароль портала, соль, 600 000 итераций).
Расшифровывает браузер после ввода пароля (js/secure.js). Пароль — PORTAL_PASSWORD
в backend/.env. Регистр, пробелы и дефисы в пароле не важны (так же в js/secure.js).
Сменили пароль → при следующем запуске новая соль, всё перешифруется, и портал у всех
попросит новый пароль.

Файл data/enc/<имя>.enc = 12 байт IV + шифротекст с тегом GCM, AAD = <имя>.
data/enc/meta.json — соль, число итераций и контрольная строка для проверки пароля.
Файл, который не изменился, не перешифровывается (иначе каждый день лишний коммит).

  python scripts/encrypt_data.py                                  — обычный запуск (auto_update.ps1)
  python scripts/encrypt_data.py --out DIR --password-file FILE   — тестовая копия
"""
import sys, json, base64, hashlib, secrets, argparse, re, os, unicodedata
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from dotenv import dotenv_values

try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
ENV = REPO / "backend" / ".env"
ITERATIONS = 600_000
CHECK_TEXT = b"utrau-portal-ok"

# имя в data/enc (оно же AAD и data-data="…" в js/secure.js)  ->  открытый файл в data/
FILES = {
    "finance": "dashboard_data.js",
    "budget":  "budget_data.js",
    "fnb":     "fnb_data.js",
    "spa":     "spa_data.js",
    "health":  "health.json",
}

def normalize(pw):
    return re.sub(r"[\s\-]+", "", unicodedata.normalize("NFC", pw).strip().lower())

def derive(pw, salt, iterations):
    return hashlib.pbkdf2_hmac("sha256", normalize(pw).encode("utf-8"), salt, iterations, 32)

def seal(key, plain, name):
    iv = secrets.token_bytes(12)
    return iv + AESGCM(key).encrypt(iv, plain, name.encode())

def unseal(key, blob, name):
    return AESGCM(key).decrypt(blob[:12], blob[12:], name.encode())

def b64(b): return base64.b64encode(b).decode()

def write_atomic(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DATA / "enc"))
    ap.add_argument("--password-file")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    if a.password_file:
        pw = Path(a.password_file).read_text(encoding="utf-8").strip()
    else:
        pw = (dotenv_values(ENV).get("PORTAL_PASSWORD") or "").strip()
    if len(normalize(pw)) < 12:
        print("encrypt: ОШИБКА — PORTAL_PASSWORD не задан в backend/.env или короче 12 символов; "
              "данные на сайте не обновлены")
        return 2

    # тот же пароль -> та же соль и тот же ключ: сотрудникам не придётся входить заново
    key = None
    try:
        meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        k = derive(pw, base64.b64decode(meta["salt"]), int(meta["iter"]))
        if unseal(k, base64.b64decode(meta["check"]), "check") == CHECK_TEXT and int(meta["iter"]) == ITERATIONS:
            key = k
    except (OSError, ValueError, KeyError, InvalidTag):
        pass
    if key is None:
        salt = secrets.token_bytes(16)
        key = derive(pw, salt, ITERATIONS)
        meta = {"v": 1, "kdf": "PBKDF2-SHA256", "iter": ITERATIONS, "salt": b64(salt),
                "check": b64(seal(key, CHECK_TEXT, "check"))}
        write_atomic(out / "meta.json", json.dumps(meta, indent=1).encode("utf-8"))
        print("encrypt: новый ключ (первый запуск или сменили пароль) — портал попросит пароль заново")

    changed, same, missing = [], [], []
    for name, src in FILES.items():
        p = DATA / src
        if not p.exists():
            missing.append(src); continue
        plain = p.read_bytes()
        dst = out / f"{name}.enc"
        try:
            if unseal(key, dst.read_bytes(), name) == plain:
                same.append(name); continue
        except (OSError, InvalidTag, ValueError):
            pass
        write_atomic(dst, seal(key, plain, name))
        changed.append(name)

    print(f"encrypt: data/enc — обновлено {len(changed)} ({', '.join(changed) or '—'}), "
          f"без изменений {len(same)}")
    if missing:
        print("encrypt: ОШИБКА — нет файлов: " + ", ".join(missing))
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
