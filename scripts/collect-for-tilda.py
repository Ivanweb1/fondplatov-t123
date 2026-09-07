#!/usr/bin/env python3
"""
Собирает все фото/картинки сайта (те, что сейчас отдаются с GitHub Pages)
в одну плоскую папку `tilda-upload/`, чтобы можно было одним разом
загрузить их в библиотеку файлов Tilda.

Одновременно пишет `tilda-upload/CHECKLIST.csv` — список файлов с пустой
колонкой для ссылки Tilda. После того как Иван загрузит папку в Tilda
и впишет в эту колонку итоговые ссылки (static.tildacdn.com/...),
файл возвращается сюда и скриптом apply-tilda-links.py ссылки
подставляются во все исходники сайта.

Запуск из корня репозитория:  python scripts/collect-for-tilda.py
"""
import csv
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = "https://ivanweb1.github.io/fondplatov-t123/"
OUT_DIR = os.path.join(ROOT, "tilda-upload")


def pages_files():
    with open(os.path.join(ROOT, "scripts", "build-tilda.py"), encoding="utf-8") as f:
        src = f.read()
    return sorted(set(re.findall(r"'(t123-[a-zA-Z0-9_.\-]+\.html)'", src)))


def css_files(html_files):
    found = set()
    for fn in html_files:
        with open(os.path.join(ROOT, fn), encoding="utf-8") as f:
            found.update(re.findall(r"assets/[A-Za-z0-9_.\-]+\.css", f.read()))
    return sorted(found)


def image_urls(all_files):
    found = set()
    pattern = re.compile(
        r"https://ivanweb1\.github\.io/fondplatov-t123/assets/[A-Za-z0-9_./\-]+\.(?:png|jpg|jpeg|webp|svg)"
    )
    for fn in all_files:
        with open(os.path.join(ROOT, fn), encoding="utf-8") as f:
            found.update(pattern.findall(f.read()) if False else pattern.findall(f.read()))
    return sorted(found)


def flatten_name(rel_path):
    """assets/foo.png -> foo.png
    assets/presentations/some-slides/slide-01.png -> some-slide-01.png"""
    parts = rel_path.split("/")
    parts = parts[1:]  # drop leading "assets"
    if len(parts) == 1:
        return parts[0]
    if parts[0] == "presentations" and len(parts) == 3:
        folder = parts[1]
        if folder.endswith("-slides"):
            folder = folder[: -len("-slides")]
        return f"{folder}-{parts[2]}"
    return "-".join(parts)


def main():
    html_files = pages_files()
    css = css_files(html_files)
    urls = image_urls(html_files + css)

    os.makedirs(OUT_DIR, exist_ok=True)

    rows = []
    seen_names = {}
    missing = []
    for url in urls:
        rel = url[len(PREFIX):]  # assets/....
        local_path = os.path.join(ROOT, rel)
        flat = flatten_name(rel)
        if flat in seen_names:
            raise SystemExit(f"Коллизия имён: {flat} <- {rel} и {seen_names[flat]}")
        seen_names[flat] = rel
        if not os.path.isfile(local_path):
            missing.append(rel)
            continue
        shutil.copyfile(local_path, os.path.join(OUT_DIR, flat))
        rows.append({"original_path": rel, "upload_filename": flat, "tilda_url": ""})

    with open(os.path.join(OUT_DIR, "CHECKLIST.csv"), "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["original_path", "upload_filename", "tilda_url"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Скопировано файлов: {len(rows)}")
    print(f"Папка: {OUT_DIR}")
    if missing:
        print("Не найдены на диске (пропущены):")
        for m in missing:
            print(" -", m)


if __name__ == "__main__":
    main()
