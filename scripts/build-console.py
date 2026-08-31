# -*- coding: utf-8 -*-
"""
Собирает пульт переноса — одну самодостаточную страницу, в которую вшиты все
готовые к вставке файлы из папки tilda/. Код каждой страницы копируется кнопкой,
отметки о переносе хранятся в localStorage браузера.

Запуск из корня репозитория:  python scripts/build-console.py
Результат:                    tilda-console.html

Сначала должен отработать scripts/build-tilda.py — пульт читает готовые файлы.
"""

import base64
import io
import json
import os
import sys

OUT = 'tilda-console.html'
SRC_DIR = 'tilda'

# адреса, которые сохраняются со старого сайта fondplatov.ru
OLD_ADDRESSES = {
    '/film_page', '/step-work', '/presentation', '/sinopsis', '/sup',
    '/bitva_presentation', '/sup_bitva', '/kazak_presentation', '/sup_kazak',
    '/festival_presentation', '/sup_festival', '/politika',
}

TEMPLATE_NOTE = 'Собрана из общего шаблона, ключ проекта вшит в код'

# slug, название, адрес в Tilda, группа, примечание
ROWS = [
    ('video', 'Главная', '/', 'home',
     'Нужен ещё блок «Корзина» (T706) с ЮKassa — без него кнопка пожертвования не сработает'),
    ('about', 'О фонде', '/about', 'core', ''),
    ('contacts', 'Контакты', '/contacts', 'core',
     'Начать с неё — самая простая, на ней проверяем стили и шапку'),
    ('documents', 'Документы', '/documents', 'core',
     'Семь документов с якорями — на них ведут 301-редиректы'),
    ('policy', 'Политика обработки данных', '/politika', 'core', ''),
    ('news-top', 'Новости — верхний блок', '/news', 'core',
     'Страница из двух блоков: между ними в Tilda ставится блок Потоков «Список страниц»'),
    ('news-bottom', 'Новости — нижний блок', '/news', 'core',
     'Идёт после блока Потоков'),
    ('news-bitva-lukomore', '«Битва за Лукоморье» в музее', '/news/bitva-lukomore', 'core', ''),
    ('news-premiera-rostov', 'Показ фильма в Ростове', '/news/premiera-rostov', 'core', ''),
    ('project-7-facts', '01 · 7 фактов о Платове', '/project/7-facts', 'proj', TEMPLATE_NOTE),
    ('project-7-facts-film', '01 · Смотреть фильм', '/film_page', 'proj', ''),
    ('project-7-facts-stages', '01 · Стадия кинопроизводства', '/step-work', 'proj', ''),
    ('project-platov', '02 · Вихорь-атаман Матвей Платов', '/presentation', 'proj', TEMPLATE_NOTE),
    ('project-postoim', '03 · Постоим за честь державы', '/project/postoim', 'proj', TEMPLATE_NOTE),
    ('project-postoim-details', '03 · Синопсис цикла', '/sinopsis', 'proj', ''),
    ('project-postoim-video', '03 · Видео-презентация', '/project/postoim-video', 'proj',
     'На старом сайте была поп-апом'),
    ('project-postoim-support', '03 · Нас поддерживают', '/sup', 'proj', ''),
    ('project-bitva', '04 · Битва за Лукоморье', '/project/bitva', 'proj', ''),
    ('project-bitva-presentation', '04 · Презентация', '/bitva_presentation', 'proj', ''),
    ('project-bitva-support', '04 · Нас поддерживают', '/sup_bitva', 'proj', ''),
    ('project-kazak', '05 · Удалой казак', '/project/kazak', 'proj', ''),
    ('project-kazak-presentation', '05 · Презентация', '/kazak_presentation', 'proj', ''),
    ('project-kazak-support', '05 · Нас поддерживают', '/sup_kazak', 'proj', ''),
    ('project-likhie', '06 · Платов и его лихие казаки', '/project/likhie', 'proj', ''),
    ('project-likhie-presentation', '06 · Презентация', '/project/likhie-presentation', 'proj', ''),
    ('project-igra', '07 · Великая игра', '/project/igra', 'proj', ''),
    ('project-igra-presentation', '07 · Презентация', '/project/igra-presentation', 'proj', ''),
    ('project-festival', '08 · Всероссийский кинофестиваль', '/project/festival', 'proj', ''),
    ('project-festival-presentation', '08 · Презентация', '/festival_presentation', 'proj', ''),
    ('project-festival-support', '08 · Нас поддерживают', '/sup_festival', 'proj', ''),
    ('head-post-styles', 'Тёмная тема страниц постов', 'Настройки сайта → head', 'site',
     'Вставляется ОДИН раз на весь сайт: Настройки сайта → Ещё → HTML-код для вставки внутрь head. '
     'Красит страницы постов Потоков (/tpost/...) под сайт'),
]

GROUPS = [
    ('home', 'Главная',
     'Ставим последней — на ней корзина пожертвований, её проверяем, когда остальное уже стоит'),
    ('core', 'Основные страницы',
     'Шапка, подвал и навигация здесь одинаковые — если они верны на одной, верны на всех'),
    ('proj', 'Проекты',
     'Порядок 01–08 повторяет старый сайт'),
    ('site', 'Настройки сайта',
     'Не страница — вставляется один раз в настройках и действует на весь сайт'),
]

REDIRECTS = [
    ('/ustav', '/documents#ustav'),
    ('/certificate', '/documents#certificate'),
    ('/egrul', '/documents#egrul'),
    ('/fondcard', '/documents#fondcard'),
    ('/oferta', '/documents#oferta'),
    ('/otc', '/documents#reports'),
]

CSS = """
  :root {
    --ground: #0c0e10; --surface: #14171a; --raised: #1b1f23; --line: #262b30;
    --ink: #e9e6df; --muted: #8e8a80; --dim: #63605a;
    --gold: #c9a227; --gold-soft: #e2c981; --done: #7ea36f;
    --sans: "IBM Plex Sans", system-ui, sans-serif;
    --mono: "IBM Plex Mono", ui-monospace, monospace;
    --display: "Prata", Georgia, serif;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--ground); color: var(--ink); font: 400 15px/1.55 var(--sans); }
  .shell { width: min(100% - 40px, 1080px); margin-inline: auto; }
  .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
  :focus-visible { outline: 2px solid var(--gold-soft); outline-offset: 2px; }

  header.top { padding: 56px 0 30px; border-bottom: 1px solid var(--line); }
  .eyebrow { margin: 0 0 18px; color: var(--gold); font-size: 11px; font-weight: 500; letter-spacing: .16em; text-transform: uppercase; }
  h1 { margin: 0 0 14px; font: 400 clamp(34px, 5vw, 52px)/1.08 var(--display); letter-spacing: -.02em; text-wrap: balance; }
  .lead { max-width: 62ch; margin: 0; color: var(--muted); }

  .bar { position: sticky; top: 0; z-index: 5; padding: 14px 0; border-bottom: 1px solid var(--line); background: rgba(12,14,16,.94); backdrop-filter: blur(10px); }
  .bar .shell { display: flex; align-items: center; gap: 20px; }
  .tally { font: 500 14px/1 var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .tally b { color: var(--gold-soft); font-weight: 500; }
  .track { flex: 1; height: 3px; background: var(--line); overflow: hidden; }
  .fill { display: block; height: 100%; width: 0; background: var(--gold); transition: width .35s ease; }
  .reset { padding: 0; border: 0; background: none; color: var(--dim); font: inherit; font-size: 12px; text-decoration: underline; text-underline-offset: 3px; cursor: pointer; }
  .reset:hover { color: var(--muted); }

  main { padding: 12px 0 40px; }
  .group { margin-top: 44px; }
  .ghead { display: flex; align-items: baseline; gap: 12px; }
  .ghead h2 { margin: 0; font: 400 26px/1.2 var(--display); }
  .count { color: var(--dim); font: 400 13px/1 var(--mono); }
  .ghint { margin: 8px 0 20px; max-width: 68ch; color: var(--dim); font-size: 13px; }

  .rows { display: grid; gap: 1px; margin: 0; padding: 0; list-style: none; background: var(--line); border: 1px solid var(--line); }
  .row { display: grid; grid-template-columns: 44px minmax(0, 1fr) minmax(0, 250px) 78px auto; align-items: center; gap: 14px;
         padding: 14px 16px 14px 8px; background: var(--surface); transition: background-color .18s ease; }
  .row:hover { background: var(--raised); }
  .row.done { background: #111417; }
  .row.done .what h3, .row.done .addr code { color: var(--dim); }
  .row.done .addr code { text-decoration: line-through; text-decoration-color: var(--dim); }

  .check { display: grid; place-items: center; cursor: pointer; }
  .check input { position: absolute; opacity: 0; }
  .check span { display: grid; place-items: center; width: 21px; height: 21px; border: 1px solid #3a4046; border-radius: 3px; transition: .18s; }
  .check span::after { content: ""; width: 10px; height: 5px; border: 2px solid var(--ground); border-top: 0; border-right: 0; transform: rotate(-45deg) scale(.4); opacity: 0; transition: .18s; }
  .check input:checked + span { background: var(--done); border-color: var(--done); }
  .check input:checked + span::after { opacity: 1; transform: rotate(-45deg) scale(1); }
  .check input:focus-visible + span { outline: 2px solid var(--gold-soft); outline-offset: 2px; }

  .what h3 { margin: 0; font-size: 15px; font-weight: 500; }
  .note { margin: 5px 0 0; color: var(--gold); font-size: 12px; line-height: 1.45; }
  .addr { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
  .addr code { color: var(--gold-soft); font: 400 13px/1.4 var(--mono); word-break: break-all; }
  .tag { padding: 3px 7px; border: 1px solid #3a4046; color: var(--dim); font-size: 9px; letter-spacing: .08em; text-transform: uppercase; white-space: nowrap; }
  .size { color: var(--dim); font: 400 12px/1 var(--mono); font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }
  .act { display: flex; gap: 7px; }

  .btn { padding: 8px 14px; border: 1px solid var(--gold); background: none; color: var(--gold-soft); font: 500 12px/1 var(--sans); letter-spacing: .03em; cursor: pointer; transition: .18s; white-space: nowrap; }
  .btn:hover { background: var(--gold); color: #14110a; }
  .btn.ghost { border-color: #3a4046; color: var(--muted); }
  .btn.ghost:hover { border-color: var(--muted); background: none; color: var(--ink); }
  .btn.ok, .btn.ok:hover { border-color: var(--done); background: none; color: var(--done); }

  .code { grid-column: 1 / -1; }
  .code textarea { width: 100%; height: 190px; padding: 12px; border: 1px solid var(--line); background: var(--ground); color: var(--muted); font: 400 11px/1.5 var(--mono); resize: vertical; }

  .ref { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 1px; margin: 56px 0 0; background: var(--line); border: 1px solid var(--line); }
  .panel { padding: 26px 24px; background: var(--surface); }
  .panel h2 { margin: 0 0 16px; font: 400 20px/1.25 var(--display); }
  .panel ol, .panel ul { margin: 0; padding-left: 19px; color: var(--muted); font-size: 13.5px; line-height: 1.65; }
  .panel li + li { margin-top: 9px; }
  .panel table { width: 100%; border-collapse: collapse; }
  .panel td { padding: 7px 0; border-bottom: 1px solid var(--line); }
  .panel td:last-child { text-align: right; }
  .panel code { color: var(--gold-soft); font: 400 12px/1.4 var(--mono); }
  .lede { margin: 0 0 12px; color: var(--dim); font-size: 13px; }
  .warn { margin: 14px 0 0; padding: 12px 14px; border-left: 2px solid var(--gold); color: var(--muted); font-size: 12.5px; line-height: 1.6; background: rgba(201,162,39,.06); }

  footer { margin-top: 56px; padding: 26px 0 60px; border-top: 1px solid var(--line); color: var(--dim); font-size: 12.5px; line-height: 1.7; }
  footer code { color: var(--muted); font: 400 12px/1.4 var(--mono); }

  @media (max-width: 860px) {
    .row { grid-template-columns: 36px minmax(0, 1fr); row-gap: 10px; padding: 14px 14px 14px 6px; }
    .addr, .size, .act { grid-column: 2; }
    .size { text-align: left; }
    .bar .shell { flex-wrap: wrap; }
  }
  @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

JS = """
(() => {
  const PAGES = {};
  for (const p of JSON.parse(document.getElementById('pages').textContent)) PAGES[p.slug] = p;
  const KEY = 'fondplatov-tilda-progress';
  const total = Object.keys(PAGES).length;

  const decode = b64 => new TextDecoder().decode(Uint8Array.from(atob(b64), c => c.charCodeAt(0)));
  const read = () => { try { return new Set(JSON.parse(localStorage.getItem(KEY)) || []); } catch (e) { return new Set(); } };
  const write = set => { try { localStorage.setItem(KEY, JSON.stringify([...set])); } catch (e) {} };
  let done = read();

  const tallyEl = document.getElementById('tally-n');
  const fillEl = document.getElementById('fill');

  const paint = () => {
    tallyEl.textContent = done.size;
    fillEl.style.width = (done.size / total * 100) + '%';
    document.querySelectorAll('.row').forEach(row => {
      const on = done.has(row.dataset.slug);
      row.classList.toggle('done', on);
      row.querySelector('.check input').checked = on;
    });
  };

  document.addEventListener('change', e => {
    const box = e.target.closest('.check input');
    if (!box) return;
    if (box.checked) done.add(box.dataset.slug); else done.delete(box.dataset.slug);
    write(done);
    paint();
  });

  document.getElementById('reset').addEventListener('click', () => {
    done = new Set();
    write(done);
    paint();
  });

  const flash = (btn, text) => {
    const was = btn.dataset.label || btn.textContent;
    btn.dataset.label = was;
    btn.textContent = text;
    btn.classList.add('ok');
    clearTimeout(btn._t);
    btn._t = setTimeout(() => { btn.textContent = was; btn.classList.remove('ok'); }, 2000);
  };

  const legacyCopy = text => {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:-1000px;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    ta.remove();
    return ok;
  };

  const openCode = (row, slug) => {
    const panel = row.querySelector('.code');
    const ta = panel.querySelector('textarea');
    if (!ta.value) ta.value = decode(PAGES[slug].b64);
    panel.hidden = false;
    const show = row.querySelector('.show');
    show.setAttribute('aria-expanded', 'true');
    show.textContent = 'Скрыть';
    return ta;
  };

  document.addEventListener('click', async e => {
    const copyBtn = e.target.closest('.copy');
    if (copyBtn) {
      const slug = copyBtn.dataset.slug;
      const code = decode(PAGES[slug].b64);
      let ok = false;
      try { await navigator.clipboard.writeText(code); ok = true; } catch (err) { ok = legacyCopy(code); }
      if (ok) { flash(copyBtn, 'Скопировано'); return; }
      const ta = openCode(copyBtn.closest('.row'), slug);
      ta.focus();
      ta.select();
      flash(copyBtn, 'Нажмите Ctrl+C');
      return;
    }
    const showBtn = e.target.closest('.show');
    if (showBtn) {
      const row = showBtn.closest('.row');
      const panel = row.querySelector('.code');
      if (panel.hidden) {
        openCode(row, showBtn.dataset.slug);
      } else {
        panel.hidden = true;
        showBtn.setAttribute('aria-expanded', 'false');
        showBtn.textContent = 'Код';
      }
    }
  });

  paint();
})();
"""

ROW_TPL = """      <li class="row" data-slug="{slug}">
        <label class="check"><input type="checkbox" data-slug="{slug}"><span aria-hidden="true"></span><em class="sr">Перенесено: {name}</em></label>
        <div class="what"><h3>{name}</h3>{note}</div>
        <div class="addr"><code>{addr}</code>{tag}</div>
        <div class="size">{kb}&thinsp;КБ</div>
        <div class="act"><button class="btn copy" type="button" data-slug="{slug}">Скопировать</button><button class="btn ghost show" type="button" data-slug="{slug}" aria-expanded="false">Код</button></div>
        <div class="code" hidden><textarea readonly spellcheck="false" aria-label="Код страницы {name}"></textarea></div>
      </li>"""


def collect():
    pages = []
    for slug, name, addr, group, note in ROWS:
        path = os.path.join(SRC_DIR, slug + '.html')
        raw = io.open(path, encoding='utf-8').read().encode('utf-8')
        pages.append({
            'slug': slug, 'name': name, 'addr': addr, 'group': group, 'note': note,
            'old': addr in OLD_ADDRESSES, 'kb': round(len(raw) / 1024.0, 1),
            'b64': base64.b64encode(raw).decode('ascii'),
        })
    return pages


def render(pages):
    by_slug = {p['slug']: p for p in pages}

    sections = []
    for key, title, hint in GROUPS:
        items = [by_slug[slug] for slug, _, _, group, _ in ROWS if group == key]
        body = '\n'.join(
            ROW_TPL.format(
                slug=p['slug'], name=p['name'], addr=p['addr'], kb=p['kb'],
                note=('<p class="note">%s</p>' % p['note']) if p['note'] else '',
                tag='<span class="tag">старый адрес</span>' if p['old'] else '',
            )
            for p in items
        )
        sections.append(
            '    <section class="group">\n'
            '      <div class="ghead"><h2>%s</h2><span class="count">%d</span></div>\n'
            '      <p class="ghint">%s</p>\n'
            '      <ol class="rows">\n%s\n      </ol>\n'
            '    </section>' % (title, len(items), hint, body)
        )

    redirects = '\n'.join(
        '        <tr><td><code>%s</code></td><td><code>%s</code></td></tr>' % pair
        for pair in REDIRECTS
    )

    payload = json.dumps(pages, ensure_ascii=False).replace('<', '\\u003c')

    return HTML.format(
        css=CSS,
        total=len(pages),
        sections='\n'.join(sections),
        redirects=redirects,
        payload=payload,
        js=JS,
    )


HTML = """<title>Платов на Tilda</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Prata&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">

<style>{css}</style>

<header class="top">
  <div class="shell">
    <p class="eyebrow">Благотворительный фонд имени М. И. Платова</p>
    <h1>Перенос на Tilda</h1>
    <p class="lead">Двадцать девять страниц, готовых к вставке в блоки&nbsp;T123. Код каждой копируется одной кнопкой, отметки о переносе сохраняются в этом браузере.</p>
  </div>
</header>

<div class="bar">
  <div class="shell">
    <span class="tally"><b id="tally-n">0</b> из {total} перенесено</span>
    <span class="track"><span class="fill" id="fill"></span></span>
    <button class="reset" id="reset" type="button">Сбросить отметки</button>
  </div>
</div>

<main class="shell">
{sections}

  <div class="ref">
    <div class="panel">
      <h2>Как вставлять</h2>
      <ol>
        <li>Создать страницу в Tilda и задать ей адрес из таблицы — без слэша на конце.</li>
        <li>Добавить блок T123 (Другое → HTML-код).</li>
        <li>Нажать «Скопировать» и вставить код целиком.</li>
        <li>Опубликовать.</li>
      </ol>
      <p class="warn">Если на сайте включено глобальное меню Tilda, на этих страницах его нужно отключить — иначе оно продублирует нашу шапку.</p>
    </div>

    <div class="panel">
      <h2>После публикации</h2>
      <ul>
        <li>Шапка чёрная во всю ширину, логотип на месте.</li>
        <li>Тёмный фон и антиквенные заголовки — значит стили с GitHub подтянулись.</li>
        <li>Бургер-меню на мобильном открывается.</li>
        <li>Ссылки ведут на адреса вида <code>/about</code>, а не на github.io. Пока страница не создана, ссылка даст 404 — это нормально.</li>
        <li>PDF документов открываются.</li>
      </ul>
    </div>

    <div class="panel">
      <h2>Редиректы</h2>
      <p class="lede">Настройки сайта → SEO → Редиректы страниц (Code&nbsp;301).</p>
      <table>
{redirects}
      </table>
      <p class="warn">Сначала снять старые страницы с публикации: Tilda применяет 301 только к несуществующим адресам.</p>
    </div>
  </div>
</main>

<footer class="shell">
  <p>Файлы в Tilda загружать не нужно — стили, логотип, документы, слайды и видеофон остаются на GitHub&nbsp;Pages и подтягиваются по абсолютным адресам. Обратная сторона: сайт зависит от репозитория <code>Ivanweb1/fondplatov-t123</code>.</p>
  <p>Страницы собраны скриптом <code>scripts/build-tilda.py</code>. Если адрес страницы меняется — правится таблица в скрипте, и всё перегенерируется заново.</p>
</footer>

<script id="pages" type="application/json">{payload}</script>
<script>{js}</script>
"""


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    pages = collect()
    html = render(pages)
    io.open(OUT, 'w', encoding='utf-8', newline='').write(html)
    print('Страниц вшито:', len(pages))
    print('Размер %s: %.0f КБ' % (OUT, len(html.encode('utf-8')) / 1024.0))
