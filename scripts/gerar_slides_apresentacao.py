#!/usr/bin/env python3
"""Gera `docs/etapa1/apresentacao_etapa1.pptx` — 6 slides do vídeo da Etapa 1.

Fora do pipeline e fora do `requirements.txt` de propósito: `python-pptx` só
serve para emitir este arquivo e não tem por que entrar no deploy enxuto
(RNF12). Para rodar, num ambiente à parte:

    python -m venv /tmp/venv-pptx && /tmp/venv-pptx/bin/pip install python-pptx
    /tmp/venv-pptx/bin/python scripts/gerar_slides_apresentacao.py

O `.pptx` é ARTEFATO GERADO: editar aqui e reemitir, nunca no PowerPoint, pela
mesma razão que vale para `docs/etapa1/documentacao.html`.

O roteiro falado, com os tempos, está em `docs/etapa1/roteiro_apresentacao_etapa1.md`.
Os slides são o fundo dele — quem lê os dois junto vê que nenhum slide repete a
fala, porque slide que se lê em voz alta compete com quem apresenta.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "docs" / "etapa1" / "apresentacao_etapa1.pptx"
LOGO = RAIZ / "docs" / "etapa1" / "logo.png"

NAVY = RGBColor(0x0B, 0x25, 0x45)
AZUL = RGBColor(0x13, 0x40, 0x74)
TEAL = RGBColor(0x1D, 0x78, 0x74)
CINZA = RGBColor(0x45, 0x52, 0x63)
CLARO = RGBColor(0xEE, 0xF2, 0xF7)
BRANCO = RGBColor(0xFF, 0xFF, 0xFF)
AMBAR = RGBColor(0xB4, 0x6A, 0x0B)

LARGURA = Inches(13.333)
ALTURA = Inches(7.5)
MARGEM = Inches(0.9)


def _texto(
    slide,
    conteudo: str,
    *,
    esquerda,
    topo,
    largura,
    altura=Inches(1.0),
    tamanho=18,
    cor=CINZA,
    negrito=False,
    italico=False,
    alinhamento=PP_ALIGN.LEFT,
    espaco=Pt(6),
):
    """Caixa de texto com quebra automática — o retorno permite encadear."""
    caixa = slide.shapes.add_textbox(esquerda, topo, largura, altura)
    quadro = caixa.text_frame
    quadro.word_wrap = True
    linhas = conteudo.split("\n")
    for i, linha in enumerate(linhas):
        paragrafo = quadro.paragraphs[0] if i == 0 else quadro.add_paragraph()
        paragrafo.alignment = alinhamento
        paragrafo.space_after = espaco
        corrida = paragrafo.add_run()
        corrida.text = linha
        corrida.font.size = Pt(tamanho)
        corrida.font.color.rgb = cor
        corrida.font.bold = negrito
        corrida.font.italic = italico
        corrida.font.name = "Calibri"
    return caixa


def _faixa(slide, cor=NAVY, altura=Inches(0.22)):
    """Faixa superior — o único elemento que se repete em todos os slides."""
    forma = slide.shapes.add_shape(1, 0, 0, LARGURA, altura)
    forma.fill.solid()
    forma.fill.fore_color.rgb = cor
    forma.line.fill.background()
    forma.shadow.inherit = False
    return forma


def _cartao(slide, esquerda, topo, largura, altura, cor=CLARO):
    forma = slide.shapes.add_shape(1, esquerda, topo, largura, altura)
    forma.fill.solid()
    forma.fill.fore_color.rgb = cor
    forma.line.color.rgb = RGBColor(0xD6, 0xDE, 0xE8)
    forma.line.width = Pt(0.75)
    forma.shadow.inherit = False
    return forma


# Acima disto, o título quebra em duas linhas a 34 pt na largura útil. Medido
# renderizando: sem esta conta o subtítulo do slide 5 ficava POR CIMA da segunda
# linha do título — caixa de texto no python-pptx não empurra a seguinte.
_LIMITE_TITULO_UMA_LINHA = 38


def _titulo(slide, texto, subtitulo=None):
    duas_linhas = len(texto) > _LIMITE_TITULO_UMA_LINHA
    _texto(
        slide, texto,
        esquerda=MARGEM, topo=Inches(0.55), largura=LARGURA - 2 * MARGEM,
        altura=Inches(1.35) if duas_linhas else Inches(0.8),
        tamanho=34, cor=NAVY, negrito=True,
    )
    if subtitulo:
        _texto(
            slide, subtitulo,
            esquerda=MARGEM,
            topo=Inches(1.85) if duas_linhas else Inches(1.32),
            largura=LARGURA - 2 * MARGEM,
            altura=Inches(0.5), tamanho=16, cor=TEAL, italico=True,
        )


def _rodape(slide, texto):
    _texto(
        slide, texto,
        esquerda=MARGEM, topo=ALTURA - Inches(0.72),
        largura=LARGURA - 2 * MARGEM, altura=Inches(0.35),
        tamanho=11, cor=RGBColor(0x8A, 0x96, 0xA6),
    )


def _slide_vazio(apresentacao):
    return apresentacao.slides.add_slide(apresentacao.slide_layouts[6])


def _notas(slide, texto: str) -> None:
    """Preenche as notas do apresentador — texto puro, sem markdown.

    Fonte única: `docs/etapa1/roteiro_apresentacao_etapa1.md`. Mudou a fala lá, muda
    aqui — os dois arquivos descrevem o mesmo roteiro, e divergirem seria pior
    do que não ter notas.
    """
    slide.notes_slide.notes_text_frame.text = texto


# --------------------------------------------------------------------------- #
# Slides
# --------------------------------------------------------------------------- #


def slide_capa(apresentacao) -> None:
    slide = _slide_vazio(apresentacao)
    fundo = slide.shapes.add_shape(1, 0, 0, LARGURA, ALTURA)
    fundo.fill.solid()
    fundo.fill.fore_color.rgb = NAVY
    fundo.line.fill.background()
    fundo.shadow.inherit = False

    if LOGO.is_file():
        # O PNG institucional não tem canal alfa: o fundo é branco sólido. Sobre
        # a capa escura isso vira um retângulo branco de qualquer jeito, então
        # ele é emoldurado de propósito, como selo, em vez de parecer defeito.
        altura_logo = Inches(1.5)
        largura_logo = Emu(int(altura_logo * 286 / 263))
        recuo = Inches(0.16)
        selo = slide.shapes.add_shape(
            5,
            Inches(1.0) - recuo, Inches(1.5) - recuo,
            largura_logo + 2 * recuo, altura_logo + 2 * recuo,
        )
        selo.fill.solid()
        selo.fill.fore_color.rgb = BRANCO
        selo.line.fill.background()
        selo.shadow.inherit = False
        slide.shapes.add_picture(
            str(LOGO), Inches(1.0), Inches(1.5), height=altura_logo
        )

    _texto(
        slide, "Assistente de Research Financeiro",
        esquerda=Inches(1.0), topo=Inches(3.25), largura=Inches(11),
        altura=Inches(1.0), tamanho=44, cor=BRANCO, negrito=True,
    )
    _texto(
        slide,
        "RAG sobre releases de resultado e o painel contábil da CVM",
        esquerda=Inches(1.0), topo=Inches(4.25), largura=Inches(11),
        altura=Inches(0.5), tamanho=20, cor=RGBColor(0x9E, 0xC5, 0xD4),
    )
    _texto(
        slide,
        "Etapa 1 · Challenge Based Learning\n"
        "AI Factory: Building Intelligent Systems",
        esquerda=Inches(1.0), topo=Inches(5.3), largura=Inches(11),
        altura=Inches(1.0), tamanho=15, cor=RGBColor(0x7E, 0x9A, 0xB5),
    )

    _notas(
        slide,
        "ABERTURA · 5 s (acumulado 0:05)\n\n"
        "Este slide fica no ar só durante a primeira frase do bloco do "
        "problema (texto completo nas notas do próximo slide). Comece a "
        "falar já com este slide aberto e troque para o slide 2 ao terminar "
        "a primeira frase.",
    )


def slide_problema(apresentacao) -> None:
    slide = _slide_vazio(apresentacao)
    _faixa(slide)
    _titulo(
        slide,
        "Divulgar não é informar",
        "Os cinco bancos do corpus publicam duas versões do mesmo trimestre",
    )

    largura_cartao = Inches(5.5)
    for i, (rotulo, corpo, cor) in enumerate(
        (
            (
                "Release de resultados",
                "PDF de centenas de páginas, escrito para o mercado.\n"
                "Métrica ajustada, na leitura da própria administração.",
                AZUL,
            ),
            (
                "Formulários ITR / DFP",
                "Entregues à CVM pelo mesmo banco, no mesmo período.\n"
                "Número contábil, padronizado e auditado.",
                TEAL,
            ),
        )
    ):
        esquerda = MARGEM + i * (largura_cartao + Inches(0.5))
        _cartao(slide, esquerda, Inches(2.15), largura_cartao, Inches(1.55))
        _texto(
            slide, rotulo,
            esquerda=esquerda + Inches(0.3), topo=Inches(2.35),
            largura=largura_cartao - Inches(0.6), altura=Inches(0.4),
            tamanho=17, cor=cor, negrito=True,
        )
        _texto(
            slide, corpo,
            esquerda=esquerda + Inches(0.3), topo=Inches(2.8),
            largura=largura_cartao - Inches(0.6), altura=Inches(0.8),
            tamanho=13,
        )

    _texto(
        slide,
        "As duas são públicas e gratuitas. Quase ninguém abre as duas.",
        esquerda=MARGEM, topo=Inches(4.0), largura=LARGURA - 2 * MARGEM,
        altura=Inches(0.45), tamanho=19, cor=NAVY, negrito=True,
    )
    _texto(
        slide,
        "Quem é de fora   →   não entende o que leu.\n"
        "Quem é de dentro   →   não pode citar número que a fonte não sustenta,\n"
        "e leva tempo demais para achá-lo entre centenas de páginas.",
        esquerda=MARGEM, topo=Inches(4.6), largura=LARGURA - 2 * MARGEM,
        altura=Inches(1.3), tamanho=16,
    )
    _rodape(
        slide,
        "Pergunta essencial: como saber quando a própria tecnologia está errada?",
    )

    _notas(
        slide,
        "PROBLEMA · 25 s (acumulado 0:30)\n\n"
        "Fala:\n"
        "\"Todo trimestre, os cinco bancos deste projeto publicam duas "
        "versões do mesmo resultado: o release em PDF, escrito para o "
        "mercado, e os formulários que o mesmo banco entrega à CVM. As duas "
        "são públicas, e quase ninguém abre as duas.\n\n"
        "Quem é de fora não entende o que leu. Quem é de dentro não pode "
        "citar um número que a fonte não sustenta — e leva tempo demais "
        "para achá-lo.\"",
    )


def slide_relevancia(apresentacao) -> None:
    """Critério 1 da rubrica (desafio e relevância).

    Os dois números vêm da medição do próprio projeto — o da divergência
    gerencial está citado em `app_streamlit.py` como motivo da deferência à
    camada documental, e o do `3.09` é o que torna o gate G4 bloqueante
    (AGENTS.md §5). Relevância argumentada com dado medido, não com adjetivo.
    """
    slide = _slide_vazio(apresentacao)
    _faixa(slide)
    _titulo(
        slide,
        "O problema não é hipotético",
        "Os dois casos abaixo foram medidos dentro deste próprio projeto",
    )

    largura_cartao = Inches(5.5)
    cartoes = (
        (
            "O mesmo trimestre, dois números certos",
            "Santander, 2T2025",
            "R$ 1,93 bi",
            "contábil, arquivado na CVM",
            "R$ 3,66 bi",
            "gerencial, no release",
            "Nenhum dos dois está errado. Eles medem coisas\n"
            "diferentes — e quase o dobro separa um do outro.",
            AZUL,
        ),
        (
            "O mesmo código, contas diferentes",
            "Conta 3.09 no plano da CVM",
            "3 de 5",
            "bancos: é lucro líquido",
            "2 de 5",
            "bancos: é outra coisa",
            "Uma consulta ingênua devolve número plausível,\n"
            "não nulo e errado — sem nenhum sinal disso.",
            TEAL,
        ),
    )
    for i, (titulo, legenda, v1, r1, v2, r2, nota, cor) in enumerate(cartoes):
        esquerda = MARGEM + i * (largura_cartao + Inches(0.5))
        _cartao(slide, esquerda, Inches(2.15), largura_cartao, Inches(3.0))
        _texto(
            slide, titulo,
            esquerda=esquerda + Inches(0.3), topo=Inches(2.32),
            largura=largura_cartao - Inches(0.6), altura=Inches(0.4),
            tamanho=16, cor=cor, negrito=True,
        )
        _texto(
            slide, legenda,
            esquerda=esquerda + Inches(0.3), topo=Inches(2.72),
            largura=largura_cartao - Inches(0.6), altura=Inches(0.3),
            tamanho=12, cor=RGBColor(0x8A, 0x96, 0xA6), italico=True,
        )
        for j, (valor, rotulo) in enumerate(((v1, r1), (v2, r2))):
            topo_valor = Inches(3.15) + j * Inches(0.72)
            _texto(
                slide, valor,
                esquerda=esquerda + Inches(0.3), topo=topo_valor,
                largura=Inches(1.9), altura=Inches(0.5),
                tamanho=26, cor=cor, negrito=True,
            )
            _texto(
                slide, rotulo,
                esquerda=esquerda + Inches(2.25), topo=topo_valor + Inches(0.12),
                largura=largura_cartao - Inches(2.55), altura=Inches(0.4),
                tamanho=13,
            )
        _texto(
            slide, nota,
            esquerda=esquerda + Inches(0.3), topo=Inches(4.55),
            largura=largura_cartao - Inches(0.6), altura=Inches(0.6),
            tamanho=12, cor=NAVY, espaco=Pt(2),
        )

    _texto(
        slide,
        "Quem responde sem saber disso acerta em três bancos, erra em dois — e "
        "não tem como perceber a diferença.",
        esquerda=MARGEM, topo=Inches(5.45), largura=LARGURA - 2 * MARGEM,
        altura=Inches(0.5), tamanho=18, cor=NAVY, negrito=True,
    )
    _rodape(
        slide,
        "É por isso que o projeto trata a conferência entre as duas fontes como "
        "o problema, e não como um detalhe de implementação.",
    )

    _notas(
        slide,
        "RELEVÂNCIA — OS DOIS NÚMEROS MEDIDOS · 30 s (acumulado 1:00)\n\n"
        "Sustenta o critério de relevância com dois números medidos dentro "
        "do próprio projeto. Deixe cada um no ar alguns segundos.\n\n"
        "Fala:\n"
        "\"Não é hipotético, e eu tenho dois números do próprio projeto.\n\n"
        "No segundo trimestre de 2025, o lucro do Santander é um vírgula "
        "nove bilhões pelo contábil arquivado na CVM, e três vírgula sete "
        "bilhões pelo gerencial do release. Mesmo trimestre, mesma empresa, "
        "nenhum dos dois errado.\n\n"
        "O segundo caso é pior, porque é invisível: a conta 3.09 é lucro "
        "líquido em três dos cinco bancos; nos outros dois, é outra coisa. "
        "Consultar sem saber disso devolve número plausível e errado, sem "
        "nenhum sinal.\"",
    )


def slide_como_responde(apresentacao) -> None:
    """Como a resposta é montada — e o que é construído mas ainda não medido.

    A camada de agentes aparece com o estado real: existe em código e tem o
    isolamento travado por teste, mas **não** está ligada à interface e a
    comparação dos três braços não rodou. Anunciá-la como funcionando seria
    exatamente o tipo de afirmação que o resto do slide diz que o sistema
    recusa fazer.
    """
    slide = _slide_vazio(apresentacao)
    _faixa(slide)
    _titulo(
        slide,
        "Como a resposta é montada",
        "A maioria das perguntas é respondida sem nenhuma geração de texto",
    )

    _cartao(slide, MARGEM, Inches(2.0), LARGURA - 2 * MARGEM, Inches(1.72),
            RGBColor(0xE7, 0xF1, 0xF0))
    _texto(
        slide, "SEM modelo de linguagem   ·   custo zero, resposta determinística",
        esquerda=MARGEM + Inches(0.3), topo=Inches(2.14),
        largura=Inches(11), altura=Inches(0.35),
        tamanho=15, cor=TEAL, negrito=True,
    )
    # Rótulos curtos por medida, não por estilo: a 13 pt cabem ~22 caracteres na
    # coluna, e o que passa disso quebra em duas linhas e cai por cima do corpo.
    etapas = (
        ("Casar o padrão", "período e conceito saem\nda pergunta, por regex"),
        ("Resolver o código", "a companhia vira CD_CVM;\nnome ambíguo vira pergunta"),
        ("Mapa semântico", "o conceito vira a conta\ncerta DAQUELE banco"),
        ("SQL no DuckDB", "lê o valor arquivado\ne a procedência dele"),
        ("Montar a frase", "o texto sai de template\nem Python, nunca gerado"),
    )
    largura_etapa = Inches(2.22)
    for i, (rotulo, corpo) in enumerate(etapas):
        esquerda = MARGEM + Inches(0.28) + i * largura_etapa
        _texto(
            slide, f"{i + 1}. {rotulo}",
            esquerda=esquerda, topo=Inches(2.58),
            largura=largura_etapa - Inches(0.18), altura=Inches(0.32),
            tamanho=13, cor=NAVY, negrito=True,
        )
        _texto(
            slide, corpo,
            esquerda=esquerda, topo=Inches(2.92),
            largura=largura_etapa - Inches(0.18), altura=Inches(0.7),
            tamanho=11, espaco=Pt(1),
        )

    _cartao(slide, MARGEM, Inches(3.92), Inches(6.0), Inches(1.5))
    _texto(
        slide, "COM modelo   ·   só nestes dois casos",
        esquerda=MARGEM + Inches(0.3), topo=Inches(4.06),
        largura=Inches(5.4), altura=Inches(0.35),
        tamanho=15, cor=AZUL, negrito=True,
    )
    _texto(
        slide,
        "Narrativa do release  →  RAG, com citação de página\n"
        "Conceito fora do painel  →  o modelo só interpreta a intenção",
        esquerda=MARGEM + Inches(0.3), topo=Inches(4.48),
        largura=Inches(5.4), altura=Inches(0.8), tamanho=12,
    )

    _cartao(slide, MARGEM + Inches(6.3), Inches(3.92), Inches(5.2), Inches(1.5),
            RGBColor(0xF7, 0xF1, 0xE6))
    _texto(
        slide, "Dois agentes   ·   construído e testado",
        esquerda=MARGEM + Inches(6.6), topo=Inches(4.06),
        largura=Inches(4.6), altura=Inches(0.35),
        tamanho=15, cor=AMBAR, negrito=True,
    )
    _texto(
        slide,
        "O Investigador responde e registra como chegou lá.\n"
        "O Auditor recebe só a afirmação e as fontes — nunca\n"
        "o rastro — e tenta derrubá-la por conta própria.",
        esquerda=MARGEM + Inches(6.6), topo=Inches(4.48),
        largura=Inches(4.6), altura=Inches(0.8), tamanho=12, espaco=Pt(1),
    )

    _texto(
        slide,
        "O isolamento entre os dois é verificado por 16 testes que falham se o "
        "rastro vazar. A comparação dos três braços é da próxima etapa.",
        esquerda=MARGEM, topo=Inches(5.62), largura=LARGURA - 2 * MARGEM,
        altura=Inches(0.5), tamanho=14, cor=AMBAR, italico=True,
    )
    _rodape(
        slide,
        "O modelo só entra onde a resposta é texto. Onde a resposta é número, "
        "quem responde é o painel.",
    )

    _notas(
        slide,
        "COMO A RESPOSTA É MONTADA · 30 s (acumulado 1:48)\n\n"
        "Responde à pergunta que o corretor vai ter: se tem RAG, o que o "
        "modelo faz quando o rodapé diz \"nenhuma chamada externa\"?\n\n"
        "Fala:\n"
        "\"A maioria das perguntas não passa pelo modelo. São cinco passos "
        "determinísticos: uma expressão regular tira período e conceito, a "
        "companhia vira código CVM, o mapa semântico acha a conta certa "
        "daquele banco — é ele que resolve o problema do slide anterior —, "
        "o DuckDB devolve o valor com a procedência, e a frase sai de um "
        "template em Python.\n\n"
        "O modelo entra em dois casos só: narrativa do release, e conceito "
        "fora do painel. E há dois agentes construídos, com o isolamento "
        "travado por dezesseis testes; medir os três braços é da próxima "
        "etapa.\"\n\n"
        "Ao terminar: vire para a tela compartilhada.",
    )


def slide_arquitetura(apresentacao) -> None:
    slide = _slide_vazio(apresentacao)
    _faixa(slide)
    _titulo(
        slide,
        "Uma pergunta, até quatro portas",
        "A ordem é a que gasta menos: só chega ao modelo o que as anteriores não resolvem",
    )

    etapas = (
        ("1", "Guardrails", "Recusa recomendação (CVM 19 e 20/2021)\ne anonimiza PII antes de sair da máquina", AMBAR, "custo zero"),
        ("2", "Painel contábil", "DuckDB sobre ITR/DFP.\nResponde sem modelo de linguagem nenhum", TEAL, "custo zero"),
        ("3", "LLM intérprete", "O modelo extrai a intenção.\nSQL por template, aritmética em Python", AZUL, "1 chamada"),
        ("4", "RAG documental", "Chroma + BM25 sobre 20 releases.\nGeração com citação obrigatória", NAVY, "1 chamada"),
    )
    largura = Inches(2.75)
    for i, (numero, titulo, corpo, cor, custo) in enumerate(etapas):
        esquerda = MARGEM + i * (largura + Inches(0.24))
        _cartao(slide, esquerda, Inches(2.2), largura, Inches(2.5))
        _texto(
            slide, numero,
            esquerda=esquerda + Inches(0.22), topo=Inches(2.32),
            largura=Inches(0.6), altura=Inches(0.5),
            tamanho=26, cor=cor, negrito=True,
        )
        _texto(
            slide, titulo,
            esquerda=esquerda + Inches(0.22), topo=Inches(2.85),
            largura=largura - Inches(0.44), altura=Inches(0.4),
            tamanho=16, cor=cor, negrito=True,
        )
        _texto(
            slide, corpo,
            esquerda=esquerda + Inches(0.22), topo=Inches(3.3),
            largura=largura - Inches(0.44), altura=Inches(1.0),
            tamanho=12,
        )
        _texto(
            slide, custo,
            esquerda=esquerda + Inches(0.22), topo=Inches(4.28),
            largura=largura - Inches(0.44), altura=Inches(0.3),
            tamanho=11, cor=cor, italico=True,
        )

    _texto(
        slide,
        "O modelo nunca escreve SQL, nunca escolhe conta contábil e nunca vê o "
        "número antes de ele ser validado.",
        esquerda=MARGEM, topo=Inches(5.15), largura=LARGURA - 2 * MARGEM,
        altura=Inches(0.5), tamanho=17, cor=NAVY, negrito=True,
    )
    _rodape(
        slide,
        "Streamlit · ChromaDB · rank-bm25 · BGE-M3 (Ollama, local) · DuckDB · "
        "Mistral OCR · Gemini 3.5 Flash Lite",
    )

    _notas(
        slide,
        "ARQUITETURA: QUATRO PORTAS · 18 s (acumulado 1:18)\n\n"
        "Fala:\n"
        "\"É uma interface de chat em Streamlit, e a pergunta passa por até "
        "quatro portas: guardrails, o painel contábil sem modelo nenhum, o "
        "modelo como intérprete, e o RAG. A ordem é a que gasta menos — só "
        "chega ao modelo o que as anteriores não resolvem.\"",
    )


def slide_demonstracao(apresentacao) -> None:
    slide = _slide_vazio(apresentacao)
    _faixa(slide)
    _titulo(slide, "Demonstração", "O que observar na tela, nesta ordem")

    itens = (
        ("UX writing", "Semestre virou trimestre, valor derivado marcado,\nprocedência à vista", TEAL),
        ("UX writing", "Pergunta sem período: a interface pergunta de volta,\nem vez de chutar ou despejar a série", TEAL),
        ("System prompt", "Pedido de recomendação recusado citando a norma,\nantes de qualquer chamada externa", AMBAR),
        ("RAG + streaming", "A resposta só é transmitida depois de validada —\né por isso que o texto demora a aparecer", AZUL),
        ("Session state", "Cota de perguntas e orçamento da sessão\ncaindo na barra lateral", NAVY),
    )
    topo = Inches(2.05)
    for rotulo, corpo, cor in itens:
        _cartao(slide, MARGEM, topo, LARGURA - 2 * MARGEM, Inches(0.8))
        _texto(
            slide, rotulo,
            esquerda=MARGEM + Inches(0.28), topo=topo + Inches(0.17),
            largura=Inches(2.6), altura=Inches(0.4),
            tamanho=15, cor=cor, negrito=True,
        )
        _texto(
            slide, corpo,
            esquerda=MARGEM + Inches(3.1), topo=topo + Inches(0.08),
            largura=LARGURA - 2 * MARGEM - Inches(3.4), altura=Inches(0.7),
            tamanho=13, espaco=Pt(1),
        )
        topo += Inches(0.9)

    _rodape(slide, "Painel e guardrails: custo zero · RAG: uma chamada paga, ~US$ 0,0014")

    _notas(
        slide,
        "DEMONSTRAÇÃO AO VIVO · 1 min 45 s (acumulado 3:33)\n"
        "Este slide fica de fundo durante toda a demonstração. Cole as "
        "perguntas em vez de digitar — o roteiro não tem folga para digitar "
        "ao vivo.\n\n"
        "— D1 · 20 s — UX writing e valor derivado —\n"
        "Digite: Qual foi o lucro do Itaú no segundo semestre de 2025?\n"
        "Fala: \"Semestre não existe no painel — ele guarda trimestre. O "
        "sistema traduz, soma os dois e responde em uma frase. Repare no "
        "valor legível ao lado do exato, na marca de valor derivado — o "
        "quarto trimestre não existe como ITR, foi calculado — e na "
        "procedência abaixo.\"\n\n"
        "— D2 · 15 s — a interface pergunta de volta —\n"
        "Digite: Qual foi o lucro do Itaú?\n"
        "Fala: \"Sem período, ele não chuta e não despeja a série inteira: "
        "pergunta de volta, e diz em que formato responder. Isso é UX "
        "writing escrito para este domínio — a pergunta incompleta é do "
        "usuário, mas quem resolve é a interface.\"\n\n"
        "— D3 · 12 s — guardrail —\n"
        "Digite: Devo comprar ações do Itaú agora?\n"
        "Fala: \"Recomendação de investimento é atividade privativa de "
        "analista credenciado, pela Resolução CVM 20/2021. O sistema recusa "
        "citando a norma — e recusa antes de qualquer chamada externa, com "
        "custo zero.\"\n\n"
        "— D4 · 45 s — RAG com streaming —\n"
        "Digite: Segundo a análise gerencial do Itaú Unibanco, qual foi o "
        "resultado recorrente gerencial no 2T2025?\n"
        "Narre durante os ~13 s de espera antes do texto aparecer — o "
        "silêncio é parte do desenho, não um defeito:\n"
        "Fala: \"Essa é a única das quatro que chama o modelo, e ela demora "
        "uns treze segundos antes de aparecer texto — de propósito. Ele "
        "recupera os trechos, gera a resposta, e só então confere se cada "
        "número aparece nos trechos citados. Se não aparecer, vira recusa. "
        "Ou seja: o que chega à tela já passou pela validação, e é por isso "
        "que o streaming começa tarde. O system prompt proíbe responder de "
        "memória e obriga a citação.\"\n"
        "Quando o texto aparecer, fala: \"R$ 11.508 milhões, com o "
        "documento e a página de onde saiu.\"\n\n"
        "— D5 · 13 s — session state —\n"
        "Aponte para a barra lateral.\n"
        "Fala: \"E aqui na lateral: as perguntas livres caíram de cinco "
        "para quatro, e o orçamento da sessão foi debitado. Esse session "
        "state é o que impede uma demonstração aberta de virar uma conta "
        "aberta.\"\n\n"
        "ANTES DE GRAVAR: HABILITAR_PERGUNTAS_LIVRES=1 no .env com o app "
        "reiniciado; modo Pergunta livre selecionado (D4 só funciona nesse "
        "modo); Ollama ativo; saldo e cota com folga; lateral visível na "
        "janela.\n"
        "NÃO demonstrar: comparação entre bancos ou variação entre "
        "trimestres — a rota determinística intercepta as duas e responde "
        "sem comparar nem calcular.\n"
        "Custo desta sequência: ~US$ 0,003, já validado no ensaio de 18/09 "
        "(R$ 11.508 milhões, página 5).",
    )


def slide_garantias(apresentacao) -> None:
    slide = _slide_vazio(apresentacao)
    _faixa(slide)
    _titulo(
        slide,
        "Por que o sistema não inventa número",
        "O modelo provavelmente já leu esses releases — e um número convincente e errado é pior que não responder",
    )

    _cartao(slide, MARGEM, Inches(2.1), LARGURA - 2 * MARGEM, Inches(1.15),
            RGBColor(0xE7, 0xF1, 0xF0))
    _texto(
        slide, "System prompt escrito para este cenário",
        esquerda=MARGEM + Inches(0.3), topo=Inches(2.25),
        largura=Inches(11), altura=Inches(0.35),
        tamanho=16, cor=TEAL, negrito=True,
    )
    _texto(
        slide,
        "Proíbe responder de memória · obriga citar documento e página · manda "
        "copiar o número exatamente como impresso, sem converter escala nem arredondar",
        esquerda=MARGEM + Inches(0.3), topo=Inches(2.62),
        largura=LARGURA - 2 * MARGEM - Inches(0.6), altura=Inches(0.5),
        tamanho=13,
    )

    regras = (
        ("Sem evidência, recusa", "O valor da resposta é conferido contra o trecho citado. Não bate, vira recusa."),
        ("Valor derivado sai marcado", "O 4º trimestre não existe como ITR: é calculado, e a tela diz isso."),
        ("Companhia por código", "Resolvida por CD_CVM, nunca por nome. Nome ambíguo gera pergunta."),
        ("Ausência é declarada", "Falta no painel, no corpus ou nos dois — e a resposta diz em qual."),
    )
    topo = Inches(3.5)
    for rotulo, corpo in regras:
        _texto(
            slide, f"▪  {rotulo}",
            esquerda=MARGEM, topo=topo, largura=Inches(4.3),
            altura=Inches(0.35), tamanho=14, cor=NAVY, negrito=True,
        )
        _texto(
            slide, corpo,
            esquerda=MARGEM + Inches(4.4), topo=topo,
            largura=LARGURA - 2 * MARGEM - Inches(4.4), altura=Inches(0.35),
            tamanho=13,
        )
        topo += Inches(0.52)

    _texto(
        slide,
        "Guardrails medidos:  20/20 ataques bloqueados  ·  0/45 falso bloqueio "
        "nas perguntas legítimas",
        esquerda=MARGEM, topo=Inches(5.75), largura=LARGURA - 2 * MARGEM,
        altura=Inches(0.45), tamanho=16, cor=TEAL, negrito=True,
    )

    _notas(
        slide,
        "POR QUE NÃO INVENTA NÚMERO · 15 s (acumulado 3:48)\n\n"
        "Curto de propósito: o system prompt já foi explicado no slide 5 e "
        "a recusa já apareceu na demonstração. Se o tempo estourar, este é "
        "o slide a cortar.\n\n"
        "Fala:\n"
        "\"Tudo isso são regras que não são texto: são código com teste. E "
        "foram medidas — vinte de vinte ataques bloqueados, e zero falso "
        "bloqueio nas quarenta e cinco perguntas legítimas.\"",
    )


def slide_fecho(apresentacao) -> None:
    slide = _slide_vazio(apresentacao)
    fundo = slide.shapes.add_shape(1, 0, 0, LARGURA, ALTURA)
    fundo.fill.solid()
    fundo.fill.fore_color.rgb = NAVY
    fundo.line.fill.background()
    fundo.shadow.inherit = False

    _texto(
        slide, "O que está aqui é o que está medido",
        esquerda=Inches(1.0), topo=Inches(1.5), largura=Inches(11.3),
        altura=Inches(0.8), tamanho=36, cor=BRANCO, negrito=True,
    )

    colunas = (
        ("Entregue e verificado",
         "20 releases indexados, com hash e manifesto\n"
         "Painel CVM 2025–2026 conferido banco a banco\n"
         "Interface nos dois modos, com e sem segredo\n"
         "Suíte de testes verde a cada mudança",
         RGBColor(0x8F, 0xD1, 0x9E)),
        ("Em aberto, e escrito na entrega",
         "Auditoria humana de groundedness pendente\n"
         "Pergunta comparativa ainda não calcula a comparação\n"
         "Camada de agentes medida em conjunto próprio\n"
         "Resultado publicado mesmo quando desfavorável",
         RGBColor(0xF0, 0xC0, 0x7A)),
    )
    for i, (titulo, corpo, cor) in enumerate(colunas):
        esquerda = Inches(1.0) + i * Inches(5.8)
        _texto(
            slide, titulo,
            esquerda=esquerda, topo=Inches(2.85), largura=Inches(5.3),
            altura=Inches(0.4), tamanho=17, cor=cor, negrito=True,
        )
        _texto(
            slide, corpo,
            esquerda=esquerda, topo=Inches(3.35), largura=Inches(5.3),
            altura=Inches(1.8), tamanho=14,
            cor=RGBColor(0xC8, 0xD6, 0xE2), espaco=Pt(8),
        )

    _texto(
        slide,
        "Projeto demonstrativo e educacional. Não constitui recomendação de "
        "investimento.",
        esquerda=Inches(1.0), topo=Inches(6.1), largura=Inches(11.3),
        altura=Inches(0.4), tamanho=13,
        cor=RGBColor(0x7E, 0x9A, 0xB5), italico=True,
    )

    _notas(
        slide,
        "FECHO · 8 s (acumulado 3:56)\n\n"
        "Fala:\n"
        "\"O que está aqui é o que está medido. O que ainda não está, eu "
        "deixei escrito na entrega. Obrigado.\"\n\n"
        "Lembrete geral para toda a apresentação: não afirmar que os dois "
        "agentes rodam na demonstração — eles estão construídos e "
        "testados, não ligados à interface.",
    )


def main() -> int:
    apresentacao = Presentation()
    apresentacao.slide_width = Emu(int(LARGURA))
    apresentacao.slide_height = Emu(int(ALTURA))

    slide_capa(apresentacao)
    slide_problema(apresentacao)
    slide_relevancia(apresentacao)
    slide_arquitetura(apresentacao)
    slide_como_responde(apresentacao)
    slide_demonstracao(apresentacao)
    slide_garantias(apresentacao)
    slide_fecho(apresentacao)

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    apresentacao.save(SAIDA)
    print(f"{len(apresentacao.slides.__iter__.__self__._sldIdLst)} slides → {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
