#!/usr/bin/env python3
"""Gera `docs/documentacao.html` — a entrega escrita da Etapa 1.

Mesmo padrão do documento do projeto anterior: páginas em Markdown dentro de
`docs/`, convertidas para um HTML único e autocontido, com abas fixas e índice
suspenso por aba. O HTML é artefato gerado — **edite o Markdown, nunca ele**.

Uso:
    python scripts/build_docs_html.py
"""

from __future__ import annotations

import os
import re

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(PROJECT, "docs")

# Ordem das abas: (id, rótulo, arquivo Markdown)
PAGES = [
    ("inicio", "🎯 Visão Geral", "00_visao_geral.md"),
    ("desafio", "💡 Desafio CBL", "01_desafio_cbl.md"),
    ("arquitetura", "⚙️ Arquitetura", "02_arquitetura.md"),
]
# Fora da entrega da Etapa 1, de propósito: `docs/nao_entregue_etapa1/` guarda
# evidências medidas e limitações. A Etapa 1 pede a declaração do desafio e o
# sistema funcional; material além disso confunde a correção. Ver o LEIA-ME de
# lá — as duas páginas voltam a esta lista na Etapa 3.

TITULO = "Assistente de Research Financeiro — Documentação da Etapa 1"
SUBTITULO = "AI Factory: Building Intelligent Systems · Etapa 1 (CBL — Engajar)"
LOGO = "logo.png"  # mesmo logo do projeto anterior do Ygor (ai_factory_ii_project)


def apply_inline(text: str) -> str:
    """Formatação de linha: imagem, negrito, itálico, código e link."""
    text = re.sub(
        r"!\[(.*?)\]\((.*?)\)",
        r'<div style="text-align:center; margin:20px 0;">'
        r'<img src="\2" alt="\1" style="max-width:100%; border-radius:8px; '
        r'box-shadow: 0 4px 12px rgba(0,0,0,0.15);"></div>',
        text,
    )
    # `***x***` ANTES de `**x**`: pela ordem inversa, o negrito consome dois dos
    # três asteriscos e o itálico fecha cruzado (`<strong><em>x</strong></em>`).
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


def slugify(texto: str, usados: set[str]) -> str:
    """Âncora estável e ÚNICA — dois títulos iguais não podem colidir.

    Sem o desempate, o índice suspenso levaria os dois ao primeiro deles.
    """
    base = re.sub(r"[^a-z0-9]+", "-", texto.lower().strip()).strip("-")[:48]
    base = base or "secao"
    slug, n = base, 2
    while slug in usados:
        slug, n = f"{base}-{n}", n + 1
    usados.add(slug)
    return slug


def md_to_html(md_text: str) -> str:
    """Conversão de Markdown suficiente para estas páginas."""
    linhas_html: list[str] = []
    usados: set[str] = set()
    em_tabela = em_codigo = em_lista = em_citacao = False

    for linha in md_text.split("\n"):
        # Blocos de código
        if linha.strip().startswith("```"):
            if em_codigo:
                linhas_html.append("</code></pre>")
                em_codigo = False
            else:
                lang = linha.strip().replace("`", "") or "text"
                linhas_html.append(f'<pre><code class="lang-{lang}">')
                em_codigo = True
            continue
        if em_codigo:
            linhas_html.append(linha.replace("<", "&lt;").replace(">", "&gt;"))
            continue

        # Citações
        if linha.strip().startswith("> "):
            if not em_citacao:
                linhas_html.append("<blockquote>")
                em_citacao = True
            linhas_html.append(f"<p>{apply_inline(linha.strip()[2:])}</p>")
            continue
        if em_citacao:
            linhas_html.append("</blockquote>")
            em_citacao = False

        if em_lista and not re.match(r"^\s*(?:[-*]|\d+\.)\s+", linha):
            linhas_html.append("</ul>")
            em_lista = False

        if em_tabela and not linha.strip().startswith("|"):
            linhas_html.append("</table></div>")
            em_tabela = False

        if linha.strip() == "---":
            linhas_html.append("<hr>")
            continue

        if not linha.strip():
            linhas_html.append("")
            continue

        # Títulos
        cabecalho = re.match(r"^(#{1,4})\s+(.*)", linha)
        if cabecalho:
            nivel = len(cabecalho.group(1))
            texto = apply_inline(cabecalho.group(2))
            slug = slugify(re.sub(r"<[^>]+>", "", texto), usados)
            linhas_html.append(f'<h{nivel} id="{slug}">{texto}</h{nivel}>')
            continue

        # Tabelas
        if linha.strip().startswith("|"):
            celulas = [c.strip() for c in linha.strip().split("|")[1:-1]]
            if all(re.match(r"^[-:]+$", c) for c in celulas if c):
                continue
            if not em_tabela:
                linhas_html.append('<div class="table-wrap"><table>')
                em_tabela = True
                linhas_html.append(
                    "<tr>"
                    + "".join(f"<th>{apply_inline(c)}</th>" for c in celulas)
                    + "</tr>"
                )
            else:
                linhas_html.append(
                    "<tr>"
                    + "".join(f"<td>{apply_inline(c)}</td>" for c in celulas)
                    + "</tr>"
                )
            continue

        # Listas
        item = re.match(r"^\s*(?:[-*]|(\d+)\.)\s+(.*)", linha)
        if item:
            if not em_lista:
                classe = ' class="ordered"' if item.group(1) else ""
                linhas_html.append(f"<ul{classe}>")
                em_lista = True
            linhas_html.append(f"<li>{apply_inline(item.group(2))}</li>")
            continue

        linhas_html.append(f"<p>{apply_inline(linha)}</p>")

    if em_tabela:
        linhas_html.append("</table></div>")
    if em_lista:
        linhas_html.append("</ul>")
    if em_citacao:
        linhas_html.append("</blockquote>")
    return "\n".join(linhas_html)


def sem_emoji(titulo: str) -> str:
    """Tira o emoji e a pontuação do começo do título, preservando o resto."""
    limpo = re.sub(r"^\W+", "", titulo, flags=re.UNICODE).strip()
    return limpo or titulo


def extrair_secoes(html: str) -> list[tuple[str, str]]:
    """Títulos H1/H2 de uma página, para o índice suspenso da aba."""
    return [
        (m.group(1), re.sub(r"<[^>]+>", "", m.group(2)))
        for m in re.finditer(r'<h[12] id="([^"]+)">(.+?)</h[12]>', html)
    ]


def construir() -> str:
    paginas = []
    for pid, rotulo, arquivo in PAGES:
        caminho = os.path.join(DOCS, arquivo)
        with open(caminho, encoding="utf-8") as f:
            html = md_to_html(f.read())
        paginas.append((pid, rotulo, html, extrair_secoes(html)))

    abas = []
    for i, (pid, rotulo, _, secoes) in enumerate(paginas):
        # O índice suspenso vai sem o emoji do título: dentro da aba ele é
        # ruído, e a mesma decisão vale no documento que serviu de modelo.
        itens = "\n".join(
            f'<a href="#{sid}" class="dropdown-link" data-page="{pid}">'
            f"{sem_emoji(titulo)}</a>"
            for sid, titulo in secoes
        )
        dropdown = f'<div class="tab-dropdown">\n{itens}\n</div>' if itens else ""
        abas.append(
            f'''
    <div class="tab-wrapper" data-page="{pid}">
        <button class="tab-btn{" active" if i == 0 else ""}" data-page="{pid}">{rotulo}</button>
        {dropdown}
    </div>'''
        )

    conteudo = "\n".join(
        f'<div class="page-content{" active" if i == 0 else ""}" id="page-{pid}">\n'
        f'<div class="content-wrapper">{html}</div>\n</div>'
        for i, (pid, _, html, _) in enumerate(paginas)
    )
    return TEMPLATE.format(
        titulo=TITULO,
        subtitulo=SUBTITULO,
        logo=LOGO,
        tabs_html="\n".join(abas),
        content_html=conteudo,
    )


TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titulo}</title>
<style>
:root {{
    --color-primary: #1b3a4b;
    --color-accent: #2e7d9a;
    --color-bg: #f6f8f9;
    --color-surface: #ffffff;
    --color-text: #2b2f33;
    --color-border: #dde3e7;
    --radius: 8px;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: var(--color-bg);
    color: var(--color-text);
    line-height: 1.65;
}}

.site-header {{
    position: relative;
    background: var(--color-surface);
    color: var(--color-primary);
    padding: 40px 20px;
    text-align: center;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    margin-bottom: 20px;
}}
.header-logo {{
    position: absolute;
    top: 20px;
    left: 40px;
    height: 110px;
    width: auto;
}}
.site-header h1 {{ font-size: 1.9em; margin-bottom: 8px; color: var(--color-primary); }}
.site-header p {{ color: #6b7a82; font-style: italic; margin-top: 0; }}

.sticky-nav {{
    position: sticky;
    top: 0;
    z-index: 1000;
    background: var(--color-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
    overflow: visible;
    padding: 0 10px;
}}
.tab-wrapper {{ position: relative; display: inline-block; }}
.tab-btn {{
    background: none;
    border: none;
    color: #b9c9d1;
    padding: 15px 20px;
    font-size: 0.9em;
    font-weight: bold;
    cursor: pointer;
    white-space: nowrap;
    border-bottom: 3px solid transparent;
    transition: all 0.2s;
}}
.tab-btn:hover {{ color: white; background: rgba(255,255,255,0.1); }}
.tab-btn.active {{
    color: white;
    border-bottom-color: var(--color-accent);
    background: rgba(255,255,255,0.05);
}}

.tab-dropdown {{
    visibility: hidden;
    opacity: 0;
    position: absolute;
    top: 100%;
    left: 0;
    background: #f9fafb;
    min-width: 280px;
    max-height: 70vh;
    overflow-y: auto;
    box-shadow: 0 8px 16px rgba(0,0,0,0.2);
    border-radius: 0 0 4px 4px;
    z-index: 2000;
    transition: opacity 0.2s, visibility 0.2s;
    margin-top: 2px;
}}
.tab-wrapper::after {{
    content: '';
    position: absolute;
    bottom: -10px;
    left: 0;
    width: 100%;
    height: 10px;
}}
.tab-wrapper:hover .tab-dropdown {{ visibility: visible; opacity: 1; }}
.dropdown-link {{
    display: block;
    padding: 8px 16px;
    color: #222;
    text-decoration: none;
    font-size: 0.9em;
    border-bottom: 1px solid #eee;
    white-space: normal;
}}
.dropdown-link:hover {{ background: #eef2f4; }}

.container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
.page-content {{ display: none; }}
.page-content.active {{ display: block; animation: fadeIn 0.3s; }}
@keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

.content-wrapper {{
    background: var(--color-surface);
    padding: 40px;
    border-radius: var(--radius);
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}}
h1 {{
    font-size: 1.75em;
    margin: 45px 0 15px;
    padding-bottom: 10px;
    border-bottom: 3px solid var(--color-accent);
    color: var(--color-primary);
}}
h1:first-child {{ margin-top: 0; }}
h2 {{
    font-size: 1.4em;
    margin: 35px 0 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid #eef2f4;
    color: var(--color-primary);
}}
h3 {{ font-size: 1.15em; margin: 25px 0 10px; color: #35505f; }}
p {{ margin: 14px 0; }}
ul, ol {{ margin: 14px 0 14px 25px; }}
li {{ margin: 6px 0; }}
blockquote {{
    border-left: 4px solid var(--color-accent);
    background: #eef6f9;
    padding: 15px 20px;
    margin: 20px 0;
    border-radius: 0 4px 4px 0;
}}
pre {{
    background: #1b3a4b;
    color: #eef2f4;
    padding: 16px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 20px 0;
    line-height: 1.45;
}}
code {{ font-family: Consolas, Monaco, monospace; font-size: 0.9em; }}
pre code {{ background: none; padding: 0; }}
p code, li code, td code {{
    background: #eef2f4;
    padding: 2px 5px;
    border-radius: 4px;
    color: #b5432c;
}}
a {{ color: var(--color-accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.table-wrap {{ overflow-x: auto; margin: 20px 0; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.95em; }}
th, td {{ border: 1px solid var(--color-border); padding: 11px; text-align: left; vertical-align: top; }}
th {{ background: #eef2f4; }}
tr:nth-child(even) td {{ background: #fbfcfd; }}

footer {{
    text-align: center;
    padding: 30px;
    color: #6b7a82;
    font-size: 0.9em;
    margin-top: 50px;
}}

@media (max-width: 800px) {{
    .content-wrapper {{ padding: 20px; }}
    .header-logo {{ position: static; display: block; margin: 0 auto 15px; height: 80px; }}
}}
@media (max-width: 500px) {{
    .tab-btn {{ padding: 12px 15px; }}
}}
@media print {{
    .sticky-nav {{ display: none; }}
    .page-content {{ display: block !important; page-break-before: always; }}
    .content-wrapper {{ box-shadow: none; padding: 0; }}
}}
</style>
</head>
<body>

<header class="site-header">
    <img src="{logo}" alt="Logo do projeto" class="header-logo">
    <h1>{titulo}</h1>
    <p>{subtitulo}</p>
</header>

<nav class="sticky-nav" id="mainNav">
    {tabs_html}
</nav>

<main class="container">
    {content_html}
</main>

<footer>
    <p>Assistente de Research Financeiro — RAG sobre releases públicos + painel contábil da CVM</p>
    <p>Documento gerado por <code>scripts/build_docs_html.py</code> · demonstração em vídeo entregue à parte</p>
</footer>

<script>
document.querySelectorAll('.tab-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
        const page = btn.dataset.page;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.page-content').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('page-' + page).classList.add('active');
        window.scrollTo({{top: 0, behavior: 'smooth'}});
    }});
}});

document.querySelectorAll('.dropdown-link').forEach(link => {{
    link.addEventListener('click', (e) => {{
        const targetAttr = link.getAttribute('href');
        if (!targetAttr || !targetAttr.startsWith('#')) return;
        e.preventDefault();
        const targetId = targetAttr.slice(1);
        const page = link.dataset.page;
        if (page) {{
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.page-content').forEach(p => p.classList.remove('active'));
            document.querySelector('.tab-btn[data-page="' + page + '"]').classList.add('active');
            document.getElementById('page-' + page).classList.add('active');
        }}
        const dropdown = link.closest('.tab-dropdown');
        if (dropdown) {{
            dropdown.style.display = 'none';
            setTimeout(() => dropdown.style.display = '', 100);
        }}
        setTimeout(() => {{
            const el = document.getElementById(targetId);
            if (el) {{
                const navHeight = document.getElementById('mainNav').offsetHeight;
                const pos = el.getBoundingClientRect().top + window.pageYOffset - navHeight - 20;
                window.scrollTo({{top: pos, behavior: 'smooth'}});
            }}
        }}, 50);
    }});
}});
</script>
</body>
</html>"""


if __name__ == "__main__":
    saida = os.path.join(DOCS, "documentacao.html")
    with open(saida, "w", encoding="utf-8") as f:
        f.write(construir())
    print(f"✅ Gerado: {saida}")
    print(f"   {len(PAGES)} páginas · {os.path.getsize(saida) // 1024} KB")
