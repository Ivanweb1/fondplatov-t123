# -*- coding: utf-8 -*-
"""
Собирает из демо-версии (GitHub Pages) файлы, готовые к вставке в блоки T123 на Tilda.

Запуск из корня репозитория:  python scripts/build-tilda.py
Результат:                    папка tilda/, по одному файлу на страницу сайта.

Что делает скрипт:
  1) переписывает навигацию между страницами с адресов ivanweb1.github.io
     на адреса страниц Tilda (таблица PAGES ниже);
  2) оставляет ссылки на ассеты (css, картинки, pdf, видео) на GitHub Pages —
     благодаря этому в Tilda не нужно ничего загружать, только вставить код;
  3) убирает target="_top" — он нужен только демо-версии, которая открывается
     внутри iframe;
  4) подставляет ключ проекта в страницы, собранные из общего шаблона:
     в демо он читался из адреса (?project=facts), а у страницы Tilda
     такого параметра не будет;
  5) вшивает наши CSS прямо в блок вместо ссылок на GitHub Pages — так стили
     не зависят от репозитория и не отвалятся, если он станет недоступен.
     В исходниках остаются обычные <link>, чтобы демо работало, а стили
     правились в одном месте.

Дополнительно собирается tilda/head-post-styles.html — тёмная тема страниц
постов Потоков. Её нужно один раз вставить в Настройки сайта → Ещё →
HTML-код для вставки внутрь head.

Если адреса страниц в Tilda изменятся — поправьте таблицу PAGES и запустите заново.
"""

import io
import os
import re
import sys

BASE = 'https://ivanweb1.github.io/fondplatov-t123'
OUT_DIR = 'tilda'

# (папка демо, исходный t123-файл, адрес страницы в Tilda, ключ шаблона проектов)
#   ключ: None      — страница не собрана из общего шаблона
#         ''        — шаблон в базовом виде («Вихорь-атаман Матвей Платов»)
#         'facts'   — «7 фактов о Платове»
#         'postoim' — «Постоим за честь державы»
PAGES = [
    ('video',                        't123-video-background.html',             '/',                            None),
    ('about',                        't123-project-about.html',                '/about',                       None),
    ('contacts',                     't123-project-contacts.html',             '/contacts',                    None),
    ('documents',                    't123-project-documents.html',            '/documents',                   None),
    ('news-top',                     't123-project-news-top.html',             '/news',                        None),
    ('news-bottom',                  't123-project-news-bottom.html',          '/news',                        None),
    ('policy',                       't123-project-policy.html',               '/politika',                    None),
    ('news-bitva-lukomore',          't123-news-bitva-lukomore.html',          '/news/bitva-lukomore',         None),
    ('news-premiera-rostov',         't123-news-premiera-rostov.html',         '/news/premiera-rostov',        None),
    ('project-7-facts',              't123-project-platov-v5.html',            '/project/7-facts',             'facts'),
    ('project-7-facts-film',         't123-project-facts-film-v6.html',        '/film_page',                   None),
    ('project-7-facts-stages',       't123-project-facts-stages-v6.html',      '/step-work',                   None),
    ('project-platov',               't123-project-platov.html',               '/presentation',                ''),
    ('project-postoim',              't123-project-platov-v11.html',           '/project/postoim',             'postoim'),
    ('project-postoim-details',      't123-project-postoim-details.html',      '/sinopsis',                    None),
    ('project-postoim-video',        't123-project-postoim-video-v2.html',     '/project/postoim-video',       None),
    ('project-postoim-support',      't123-project-postoim-support-v2.html',   '/sup',                         None),
    ('project-bitva',                't123-project-bitva.html',                '/project/bitva',               None),
    ('project-bitva-presentation',   't123-project-bitva-presentation.html',   '/bitva_presentation',          None),
    ('project-bitva-support',        't123-project-bitva-support.html',        '/sup_bitva',                   None),
    ('project-kazak',                't123-project-kazak.html',                '/project/kazak',               None),
    ('project-kazak-presentation',   't123-project-kazak-presentation.html',   '/kazak_presentation',          None),
    ('project-kazak-support',        't123-project-kazak-support.html',        '/sup_kazak',                   None),
    ('project-likhie',               't123-project-likhie.html',               '/project/likhie',              None),
    ('project-likhie-presentation',  't123-project-likhie-presentation.html',  '/project/likhie-presentation', None),
    ('project-igra',                 't123-project-igra.html',                 '/project/igra',                None),
    ('project-igra-presentation',    't123-project-igra-presentation.html',    '/project/igra-presentation',   None),
    ('project-festival',             't123-project-festival.html',             '/project/festival',            None),
    ('project-festival-presentation','t123-project-festival-presentation.html','/festival_presentation',       None),
    ('project-festival-support',     't123-project-festival-support.html',     '/sup_festival',                None),
]

# Папки демо, у которых больше нет собственного файла на выходе, но ссылки на
# них в вёрстке остались. Страница новостей разрезана на два блока для Tilda,
# а в демо она по-прежнему одна — /news/.
ALIASES = {
    'news': '/news',
}

ASSET_RE = re.compile(r'\.(css|js|png|jpe?g|webp|svg|pdf|mp4)')
STYLE_LINK_RE = re.compile(
    r'[ \t]*<link rel="stylesheet" href="' + re.escape(BASE)
    + r'/assets/([\w.-]+\.css)(?:\?[^"]*)?">[ \t]*\n?')

FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700'
    '&family=Prata&display=swap" rel="stylesheet">\n'
)

POST_STYLES_OUT = 'head-post-styles.html'
FONT_IMPORT_RE = re.compile(r"@import url\('https://fonts\.googleapis\.com[^']*'\);\n?")


def read_css(name):
    return io.open(os.path.join('assets', name), encoding='utf-8').read().strip()


def inline_styles(html):
    """Меняет ссылки на наши CSS их содержимым."""
    return STYLE_LINK_RE.sub(lambda m: '<style>\n' + read_css(m.group(1)) + '\n</style>\n', html)


def build_post_styles():
    """Сниппет для head сайта: шрифты ссылкой, тёмная тема постов — текстом."""
    css = FONT_IMPORT_RE.sub('', read_css('tilda-post-dark.css'))
    return FONTS_LINK + '<style>\n' + css + '\n</style>\n'


TEMPLATE_CALL = "new URLSearchParams(window.location.search).get('project')"


def build():
    urls = {slug: addr for slug, _, addr, _ in PAGES}
    urls.update(ALIASES)
    # длинные слаги первыми: иначе /project-postoim/ подменится раньше,
    # чем /project-postoim-details/, и адрес получится битым
    slugs = sorted(urls, key=len, reverse=True)

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    rows = []
    for slug, src, addr, key in PAGES:
        html = io.open(src, encoding='utf-8').read()
        before = html.count(BASE)

        for name in slugs:
            # адреса страниц Tilda пишутся без завершающего слэша, кроме главной
            html = html.replace(BASE + '/' + name + '/', urls[name])
            html = html.replace(BASE + '/' + name, urls[name])

        html = re.sub(r'\s+target="_top"', '', html)

        if key is not None:
            html = html.replace(TEMPLATE_CALL, ("'%s'" % key) if key else 'null')

        html = inline_styles(html)

        io.open(os.path.join(OUT_DIR, slug + '.html'), 'w', encoding='utf-8', newline='').write(html)
        rows.append((slug, addr, before - html.count(BASE), html.count(BASE)))

    io.open(os.path.join(OUT_DIR, POST_STYLES_OUT), 'w', encoding='utf-8',
            newline='').write(build_post_styles())

    return rows


def check():
    """Ни одной навигационной ссылки на github.io остаться не должно."""
    leftovers = []
    for slug, _, _, _ in PAGES:
        path = os.path.join(OUT_DIR, slug + '.html')
        html = io.open(path, encoding='utf-8').read()
        for m in re.finditer(re.escape(BASE) + r'([^"\')\s]*)', html):
            if not ASSET_RE.search(m.group(1)):
                leftovers.append((slug, m.group(1)))
    return leftovers


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    rows = build()
    print('%-32s %-28s %6s %8s' % ('страница', 'адрес в Tilda', 'нав.', 'ассеты'))
    for slug, addr, fixed, left in rows:
        print('%-32s %-28s %6d %8d' % (slug, addr, fixed, left))
    print()
    print('Страниц собрано:', len(rows))
    print('Навигационных ссылок переписано:', sum(r[2] for r in rows))
    print('Ссылок на ассеты GitHub осталось:', sum(r[3] for r in rows))

    leftovers = check()
    if leftovers:
        print()
        print('ВНИМАНИЕ, навигация на github.io осталась:')
        for slug, path in leftovers:
            print('  %s -> %s' % (slug, path))
        sys.exit(1)
    print('Проверка: навигационных ссылок на github.io не осталось.')
