# Загородный клуб «Утрау» — Портал отчётов
## Техническая документация

---

### Структура проекта

```
DaniilK-utrau/
├── reports.html          # Главная страница портала (авторизация + меню)
├── finance.html          # Дашборд: доходность и загрузка
├── update.bat            # Запустить для обновления данных (двойной клик)
│
├── data/
│   ├── raw_2024.csv      # CSV из Google Sheets, вкладка 2024
│   ├── raw_2025.csv      # CSV из Google Sheets, вкладка 2025
│   ├── raw_2026.csv      # CSV из Google Sheets, вкладка 2026
│   └── dashboard_data.js # Сгенерированный JS-файл с данными (не редактировать)
│
├── scripts/
│   ├── download.ps1      # Скачивает CSV из Google Sheets
│   └── build.ps1         # Парсит CSV → генерирует dashboard_data.js
│
└── docs/
    └── README.md         # Этот файл
```

---

### Как обновить данные (ежедневно)

**Вариант 1 — двойной клик:**
Запустить `update.bat` в корне проекта. Скрипт скачает свежие CSV и пересоберёт дашборд.

**Вариант 2 — PowerShell вручную:**
```powershell
cd C:\путь\до\DaniilK-utrau
powershell -ExecutionPolicy Bypass -File .\scripts\download.ps1
```

**После обновления данных** — опубликовать на GitHub:
```powershell
git add data/
git commit -m "Update data $(Get-Date -Format 'yyyy-MM-dd')"
git push
```

---

### Подключение вкладок 2025 и 2026

1. Открыть таблицу: `https://docs.google.com/spreadsheets/d/1N9YFy76rV3KcZnN5EwSt8Y-Ji0Y7WpHkwkBrgndChuw`
2. Перейти на вкладку **2025** → в адресной строке найти `gid=XXXXXXXXX`
3. Открыть `scripts/download.ps1`, вставить значение в строку:
   ```powershell
   "2025" = "XXXXXXXXX"   # <-- сюда
   ```
4. Повторить для вкладки 2026
5. Запустить `update.bat`

---

### Источник данных

| Параметр | Значение |
|----------|----------|
| Google Sheets ID | `1N9YFy76rV3KcZnN5EwSt8Y-Ji0Y7WpHkwkBrgndChuw` |
| Вкладка 2024 (gid) | `1688657215` |
| Вкладка 2025 (gid) | *(добавить)* |
| Вкладка 2026 (gid) | *(добавить)* |
| Формат строк | `DD.MM.YYYY` — ежедневные данные |

---

### Колонки CSV (порядок зафиксирован)

| Индекс | Название | Описание |
|--------|----------|----------|
| 0 | Дата | DD.MM.YYYY |
| 2 | Доход за проживание | Выручка за день, ₽ |
| 3 | Продано номероночей | Кол-во проданных номероночей |
| 5 | Заезд гостей | Число прибывших гостей |
| 6 | Заезд номеров | Число заехавших номеров |
| 7 | ADR | Средняя цена за номер, ₽ |
| 8 | RevPAR | Доход на доступный номер, ₽ |
| 9 | ALS | Средняя длина пребывания |
| 10 | Всего номеров | Общий номерной фонд |
| 11 | На ремонте | Номера вне продажи |
| 12 | Всего доступно | Номеров в продаже |
| 13 | Общий % загрузки | Occupancy, % |

---

### Дашборд finance.html

**KPI-карточки** (6 штук):
- Доход за проживание — с дельтой к предыдущему году
- Загрузка % — средняя по периоду
- ADR — средняя цена: revenue / room nights
- RevPAR — revenue / available rooms
- Продано номероночей
- ALS — средняя длина пребывания

**Фильтры:**
- Год (кнопки — все доступные годы из данных)
- Период: Весь год / Q1 / Q2 / Q3 / Q4
- Месяц (выпадающий список)

**Графики:**
1. Выручка по месяцам — бары, все годы наложены
2. Загрузка % по месяцам — линии, все годы
3. ADR и RevPAR — двойная линия по месяцам
4. Выручка по дням недели — среднее, бары (выходные выделены)
5. Загрузка по дням недели — аналогично
6. Тепловая карта загрузки — calendar heatmap по дням года

**Сравнение периодов** (переключатель в фильтр-баре):
- Выбор Год A + месяц vs Год B + месяц
- Таблица: все 6 метрик, абсолютная и процентная дельта

**YoY-дельта в KPI — «сопоставимый период» (YTD):**
Если выбранный год неполный (напр. 2026 заполнен до 31 мая), дельта к предыдущему
году считается не от полного года, а от **того же отрезка дат** (1 янв – 31 мая 2025).
Иначе неполный год сравнивался бы с полным и давал бы заниженную дельту.
- Логика: `renderAll()` находит максимальную дату текущего года и обрезает
  предыдущий год по тому же `месяц-день` (функция `monthDay()`).
- Для завершённых лет (2024, 2025) обрезка не срабатывает — сравнение полное.
- Когда обрезка активна, на карточках выручки/загрузки выводится подпись
  **«vs ГГГГ (тот же период)»**, чтобы база сравнения была явной.
- Значение KPI остаётся фактическим YTD; обрезается только база дельты.

---

### Авторизация (reports.html)

- Механизм: SHA-256 хеш, localStorage
- Ключ: `utrau_ok`
- Дефолтный пароль: `utrau2026`

**Смена пароля:**
1. Придумать новый пароль
2. Вычислить SHA-256 (например: `certutil -hashfile` или онлайн)
3. В `reports.html` заменить строку `var HASH = '8c9c5ba2...'`

---

### Публикация (GitHub Pages)

- Репозиторий: `anastasiafrolova933-sys/DaniilK-utrau`
- URL портала: `https://anastasiafrolova933-sys.github.io/DaniilK-utrau/reports.html`
- URL дашборда: `https://anastasiafrolova933-sys.github.io/DaniilK-utrau/finance.html`
- Ветка: `master`, папка: `/` (корень)

---

### Перенос на другой компьютер

1. Скопировать папку `DaniilK-utrau` целиком
2. Убедиться что PowerShell 5+ установлен (есть на любом Windows 10/11)
3. Запустить `update.bat` для обновления данных
4. Открыть `reports.html` в браузере (Chrome/Edge/Firefox)

> Интернет-зависимости: Google Fonts (шрифты), Chart.js CDN, Google Sheets (данные).
> Для работы без интернета нужно скачать шрифты и Chart.js локально.

---

### Автоматизация через Task Scheduler — НАСТРОЕНА ✅

Ежедневное обновление работает автоматически, как у портала Baden.

**Задача:** `UtrauDashboardUpdate`
**Расписание:** каждый день в 10:00
**Что делает:** запускает `scripts/auto_update.ps1`, который:
1. Скачивает свежие CSV из Google Sheets (`download.ps1`)
2. Пересобирает `dashboard_data.js` (`build.ps1`)
3. `git commit` + `git pull --rebase` + `git push` → сайт обновляется сам

Ручной запуск меня (Claude) **не требуется** — всё крутится через Планировщик Windows.
Git-push использует учётные данные из Windows Credential Manager (уже сохранены).

**Лог:** `data/update.log` (последние запуски, успех/ошибки). В git не попадает.

**Проверить статус задачи:**
```powershell
Get-ScheduledTaskInfo -TaskName "UtrauDashboardUpdate"   # LastTaskResult 0 = успех
```

**Запустить вручную сейчас:**
```powershell
Start-ScheduledTask -TaskName "UtrauDashboardUpdate"
```

**Изменить время запуска / частоту:**
```powershell
$t = New-ScheduledTaskTrigger -Daily -At 09:00
Set-ScheduledTask -TaskName "UtrauDashboardUpdate" -Trigger $t
```

**Пересоздать задачу с нуля** (если перенесли проект в другую папку):
```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\НОВЫЙ_ПУТЬ\DaniilK-utrau\scripts\auto_update.ps1"'
$trigger = New-ScheduledTaskTrigger -Daily -At 10:00
Register-ScheduledTask -TaskName "UtrauDashboardUpdate" -Action $action -Trigger $trigger -Force
```

> При переносе на другой ПК задачу нужно пересоздать (путь к скрипту меняется).
> На исходном компьютере она уже работает.

---

*Создан: 2026-06-29 | Проект: ООО Бест Глэмп | Разработка: Claude Code*
