import pandas as pd
import psycopg2
from itertools import zip_longest
from pandas.testing import assert_frame_equal

TXT_FOLDER_PATH = "./Lab2-ExpectedResults"
SOLUTION_FOLDER_PATH = "./sqls"

def normalize_numeric_cols(df):
    for col in df.columns:
        try:
            df[col] = df[col].apply(lambda x: f"{float(x):.2f}" if pd.notna(x) and x != '' else x)
        except ValueError:
            pass
    return df

SKIP_TASKS = []

user_input = input("Введите номер задачи (1-15) или 'all' для всех задач: ").strip().lower()

if user_input == 'all':
    tasks_to_run = [t for t in range(1, 16) if t not in SKIP_TASKS]
else:
    try:
        task_num = int(user_input)
        if task_num < 1 or task_num > 15:
            print("Ошибка: номер задачи должен быть от 1 до 15")
            exit(1)
        if task_num in SKIP_TASKS:
            print(f"Задача {task_num} пропущена (не работает)")
            exit(0)
        tasks_to_run = [task_num]
    except ValueError:
        print("Ошибка: введите число от 1 до 15 или 'all'")
        exit(1)

for task in tasks_to_run:
    print(f"\n{'='*60}")
    print(f"Задача {task}  (сравниваю {task}.txt ↔ {task}.sql)")
    print(f"{'='*60}")
    
    # --- TXT: читаем ожидаемый результат ---
    file_path = f"{TXT_FOLDER_PATH}/{task}.txt"
    df_txt = pd.read_csv(file_path, sep="|", engine="python", skipinitialspace=True, dtype=str)
    df_txt = df_txt.dropna(axis=1, how="all")
    df_txt = df_txt.apply(lambda c: c.str.strip())
    # иногда первая строка может быть пустым эхо заголовков — удалим без ошибки
    df_txt = df_txt.drop(0, errors="ignore")
    first_col = df_txt.columns[0]
    df_txt = df_txt[~df_txt[first_col].str.match(r"^\(\d+\s+rows\)$", na=False)]
    df_txt = df_txt.reset_index(drop=True)

    # нормализуем заголовки TXT
    df_txt.columns = [c.strip() for c in df_txt.columns]

    # --- SQL: выполняем соответствующий запрос ---
    conn = psycopg2.connect(
        host="", port=5432, dbname="", user="", password=""
    )
    query_file_path = f"{SOLUTION_FOLDER_PATH}/{task}.sql"
    with open(query_file_path, 'r', encoding='utf-8') as f:
        query = f.read()
    df_sql = pd.read_sql_query(query, conn).astype(str).apply(lambda c: c.str.strip())
    conn.close()
    df_sql = df_sql.reset_index(drop=True)

    # нормализуем заголовки SQL
    df_sql.columns = [c.strip() for c in df_sql.columns]

    # Нормализация числовых значений (не трогаем заголовки)
    df_txt = normalize_numeric_cols(df_txt.copy())
    df_sql = normalize_numeric_cols(df_sql.copy())

    # 1) ЯВНАЯ ПРОВЕРКА КОЛОНОК И ИХ ПОРЯДКА
    txt_cols = list(df_txt.columns)
    sql_cols = list(df_sql.columns)

    if txt_cols != sql_cols:
        print("❌ Колонки отличаются по названиям и/или порядку.")
        print("Порядок колонок (TXT vs SQL):")
        for i, (a, b) in enumerate(zip_longest(txt_cols, sql_cols, fillvalue="—")):
            print(f"{i:>2}: {a}  |  {b}")
        missing_in_sql = [c for c in txt_cols if c not in df_sql.columns]
        missing_in_txt = [c for c in sql_cols if c not in df_txt.columns]
        if missing_in_sql:
            print("Нет в SQL:", missing_in_sql)
        if missing_in_txt:
            print("Нет в TXT:", missing_in_txt)
        # Колонки не совпали — дальше строки сравнивать бессмысленно
        continue
    else:
        print("✅ Колонки совпадают по названиям и порядку.")

    # 2) СРАВНЕНИЕ РАЗМЕРОВ
    if df_txt.shape != df_sql.shape:
        print("Разный размер таблиц")
        print(f"txt:  {df_txt.shape}, sql: {df_sql.shape}")
        continue

    # 3) СРАВНЕНИЕ ЗНАЧЕНИЙ (строго, учитывая порядок)
    try:
        assert_frame_equal(df_txt, df_sql, check_dtype=False, check_like=False)
        print("Полное совпадение: и порядок, и значения.")
    except AssertionError:
        neq_mask = (df_txt.values != df_sql.values).any(axis=1)
        bad_idx = list(pd.Index(range(len(df_txt)))[neq_mask])

        if len(bad_idx) == 0:
            print("✅ Таблицы совпадают по значениям (различия только технические).")
        else:
            print("Таблицы различаются (учитывая порядок).")
            print(f"Первых 10 несовпадений (из {len(bad_idx)}):")
            for i in bad_idx[:10]:
                start = max(0, i-2); end = min(len(df_txt), i+3)
                print(f"\n--- mismatch at row {i} ---")
                print("TXT rows:")
                print(df_txt.iloc[start:end].to_string(index=True))
                print("SQL rows:")
                print(df_sql.iloc[start:end].to_string(index=True))
            if bad_idx:
                i = bad_idx[0]
                row_diff = pd.DataFrame({
                    "col": df_txt.columns,
                    "txt": df_txt.iloc[i].values,
                    "sql": df_sql.iloc[i].values,
                    "equal": df_txt.iloc[i].values == df_sql.iloc[i].values
                })
                print("\nПодробно по первой отличающейся строке:")
                print(row_diff.to_string(index=False))
