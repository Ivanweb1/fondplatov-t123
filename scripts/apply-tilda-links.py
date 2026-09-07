#!/usr/bin/env python3
"""
Вторая половина миграции картинок на Tilda.

Читает tilda-upload/CHECKLIST.csv (колонка tilda_url заполнена Иваном
после загрузки папки tilda-upload/ в библиотеку файлов Tilda) и во
всех исходниках сайта заменяет ссылки с GitHub Pages
(https://ivanweb1.github.io/fondplatov-t123/assets/...) на ссылки
Tilda (https://static.tildacdn.com/...).

После замены нужно пересобрать tilda/:  python scripts/build-tilda.py

Запуск из корня репозитория:  python scripts/apply-tilda-links.py
"""
import csv
import glob
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = "https://ivanweb1.github.io/fondplatov-t123/"
CHECKLIST = os.path.join(ROOT, "tilda-upload", "CHECKLIST.csv")


def main():
    with open(CHECKLIST, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    mapping = {}
    empty = []
    for row in rows:
        url = (row.get("tilda_url") or "").strip()
        original = PREFIX + row["original_path"]
        if not url:
            empty.append(row["original_path"])
            continue
        mapping[original] = url

    if empty:
        print(f"Пропущено (ссылка Tilda не заполнена в CHECKLIST.csv): {len(empty)}")
        for e in empty[:20]:
            print(" -", e)
        if len(empty) > 20:
            print(f"   ...и ещё {len(empty) - 20}")

    if not mapping:
        print("Нет ни одной заполненной ссылки — нечего заменять.")
        return

    targets = glob.glob(os.path.join(ROOT, "*.html")) + glob.glob(os.path.join(ROOT, "assets", "*.css"))
    total_replacements = 0
    changed_files = 0
    for path in targets:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        new_content = content
        file_replacements = 0
        for original, new_url in mapping.items():
            count = new_content.count(original)
            if count:
                new_content = new_content.replace(original, new_url)
                file_replacements += count
        if file_replacements:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_content)
            changed_files += 1
            total_replacements += file_replacements
            print(f"{os.path.relpath(path, ROOT)}: {file_replacements}")

    print(f"\nВсего заменено ссылок: {total_replacements} в {changed_files} файлах.")
    print("Дальше: python scripts/build-tilda.py, затем commit + push.")


if __name__ == "__main__":
    main()
