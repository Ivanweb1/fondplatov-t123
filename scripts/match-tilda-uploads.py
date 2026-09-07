#!/usr/bin/env python3
"""
Сопоставляет уже загруженные в Tilda картинки (взятые из экспортированной
HTML-страницы галереи) с исходными локальными файлами в tilda-upload/ —
по содержимому картинки (перцептивный хэш), а не по имени файла, потому
что Tilda обрезает длинные имена файлов до ~20 символов и для слайдов
презентаций (кроме первых) это даёт совпадающие "имена" у разных файлов.

Заполняет tilda-upload/CHECKLIST.csv колонку tilda_url. Несовпавшие или
неоднозначные (двойное совпадение) строки помечает и печатает отдельно —
руками не подставляет, чтобы не приписать чужой ссылке не тот файл.

Запуск:  python scripts/match-tilda-uploads.py "<путь к экспортированной HTML-странице>"
"""
import csv
import io
import os
import re
import sys
import urllib.request

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(ROOT, "tilda-upload")
CHECKLIST = os.path.join(UPLOAD_DIR, "CHECKLIST.csv")
HASH_SIZE = 16  # aHash grid


def ahash_bits(img):
    small = img.convert("L").resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS)
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    return "".join("1" if p > avg else "0" for p in pixels)


def hamming(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)


def local_hash(path):
    with Image.open(path) as img:
        return ahash_bits(img)


def remote_hash(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    with Image.open(io.BytesIO(data)) as img:
        return ahash_bits(img)


def extract_gallery_urls(html_path):
    with open(html_path, encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(r'data-original="(https://static\.tildacdn\.com/[^"]+\.(?:png|jpg|jpeg|webp|svg))"')
    seen = []
    for url in pattern.findall(content):
        if url not in seen:
            seen.append(url)
    return seen


def main():
    if len(sys.argv) != 2:
        print("Использование: python scripts/match-tilda-uploads.py <html-файл галереи>")
        sys.exit(1)
    html_path = sys.argv[1]

    gallery_urls = extract_gallery_urls(html_path)
    print(f"Найдено картинок в галерее: {len(gallery_urls)}")

    with open(CHECKLIST, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    print(f"Строк в CHECKLIST.csv: {len(rows)}")

    print("Считаю хэши локальных файлов...")
    local_hashes = {}
    skipped_svg = []
    for row in rows:
        path = os.path.join(UPLOAD_DIR, row["upload_filename"])
        if not os.path.isfile(path):
            print("  нет файла:", path)
            continue
        if path.lower().endswith(".svg"):
            skipped_svg.append(row["upload_filename"])
            continue
        local_hashes[row["upload_filename"]] = local_hash(path)
    if skipped_svg:
        print("  SVG пропущены (сравниваются по имени отдельно):", skipped_svg)

    print("Скачиваю и хэширую картинки из Tilda (может занять пару минут)...")
    remote = []  # list of (url, hash)
    remote_svg_urls = []
    for i, url in enumerate(gallery_urls):
        if url.lower().endswith(".svg"):
            remote_svg_urls.append(url)
            continue
        try:
            h = remote_hash(url)
        except Exception as e:
            print(f"  [{i}] ошибка загрузки {url}: {e}")
            continue
        remote.append((url, h))
        if (i + 1) % 20 == 0:
            print(f"  ...{i + 1}/{len(gallery_urls)}")

    # Для каждого локального файла ищем ближайший по хэммингову расстоянию
    # remote-хэш; проверяем, что второй по близости заметно дальше — иначе
    # неоднозначно, не подставляем.
    matches = {}
    ambiguous = []
    unmatched = []
    used_remote = set()

    for name, lh in local_hashes.items():
        scored = sorted(((hamming(lh, rh), url) for url, rh in remote), key=lambda x: x[0])
        if not scored:
            unmatched.append(name)
            continue
        best_dist, best_url = scored[0]
        second_dist = scored[1][0] if len(scored) > 1 else 999
        if best_dist > 8:
            unmatched.append(name)
            continue
        if second_dist - best_dist < 4:
            ambiguous.append((name, scored[:3]))
            continue
        matches[name] = best_url
        used_remote.add(best_url)

    # SVG отдельно: хэшировать нельзя (векторный формат), сопоставляем по
    # имени файла — надёжно, только если и там, и там ровно один SVG.
    svg_names = [n for n in skipped_svg]
    if len(svg_names) == 1 and len(remote_svg_urls) == 1:
        matches[svg_names[0]] = remote_svg_urls[0]
    elif svg_names or remote_svg_urls:
        print(f"SVG: локально {svg_names}, в галерее {remote_svg_urls} — не сопоставляю автоматически (не 1:1)")

    print(f"\nОднозначно сопоставлено: {len(matches)}")
    print(f"Неоднозначно (пропущено): {len(ambiguous)}")
    for name, cand in ambiguous:
        print("  ?", name, "->", [(d, u.rsplit('/', 1)[-1]) for d, u in cand])
    print(f"Не найдено похожей картинки: {len(unmatched)}")
    for name in unmatched:
        print("  -", name)

    # записываем обратно CHECKLIST.csv
    for row in rows:
        if row["upload_filename"] in matches:
            row["tilda_url"] = matches[row["upload_filename"]]

    with open(CHECKLIST, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["original_path", "upload_filename", "tilda_url"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nCHECKLIST.csv обновлён: {CHECKLIST}")


if __name__ == "__main__":
    main()
