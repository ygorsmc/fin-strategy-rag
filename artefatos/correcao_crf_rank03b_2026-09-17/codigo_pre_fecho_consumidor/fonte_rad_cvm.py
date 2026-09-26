"""Aquisição e leitura de formulários ITR/DFP individuais da CVM (RAD).

Contrato: `resultados/contratos_lote_b_rank03b_2026-09-16.md`, cláusulas V1, X1
e N1. **Não corrige nada e não calcula estatística de rótulo** (cláusula O1).

## Por que o formulário individual

Os ZIPs anuais da CVM guardam **uma** versão dos números de cada documento — a
maior. Medido em 16/09: 3.863 de 24.925 documentos do universo do Rank 3-B têm
mais de uma versão, e o intervalo entre a primeira e a última chega a 2.093
dias. Para saber o que se sabia numa data, é preciso a versão que existia
naquela data, e ela só está no formulário daquela versão.

Pelo mesmo caminho vem a **evidência de escala**: o `CodigoEscalaMoeda` do
formulário é a *origem* do rótulo que o CSV reproduz, então não serve para
adjudicá-lo. O texto das notas explicativas, escrito pela companhia no mesmo
arquivamento, serve.

## Três armadilhas medidas no reconhecimento

1. **Consolidado e individual convivem no mesmo XML.** A conta `1` aparece duas
   vezes; só `CodigoTipoInformacaoFinanceira = 2` é o consolidado que a carga
   compartilhada usa. Ler a primeira ocorrência dá o balanço da controladora.
2. **`ValorConta{N}` não é o N-ésimo período em ordem de data**: é o período
   cujo `NumeroIdentificacaoPeriodo` vale N.
3. **O PDF renderizado do pacote não é confiável** (veio com exatamente 2²³
   bytes, duas vezes: o servidor corta em 8 MiB). Nada aqui depende dele.

## Dois formatos, escolhidos pelo CONTEÚDO do pacote

Medido no piloto de 16/09: até o início de 2021 o pacote traz um formulário
`.itr`/`.dfp` (outro ZIP, com `InfoFinaDFin.xml`); a partir de 2021 aparece o
**XML único** (`025704ITR30-09-2024v1.xml`), e os dois convivem no mesmo ano.
Escolher pelo ano erraria. O XML único tem suas próprias armadilhas: valores em
**texto pt-BR** (`2.555.870`), colunas **nomeadas por papel**
(`TrimestreAtual`, `AcumuladoExercicioAnterior`) e datas num cabeçalho à parte.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import subprocess
import threading
import time
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from xml.etree import ElementTree as ET

RAIZ = Path(__file__).resolve().parents[1]
DIRETORIO = RAIZ / "artefatos" / "painel_pesquisa_rank03b" / "rad"
BRUTOS = DIRETORIO / "brutos"
MANIFESTO = DIRETORIO / "manifesto_aquisicao.jsonl"
COOKIES = DIRETORIO / ".cookies_cvm"

#: V1.1 — espera entre requisições bem-sucedidas, por conexão.
PAUSA_ENTRE_DOCUMENTOS = 1.0
AGENTE_HTTP = "Mozilla/5.0 (compatible; pesquisa academica; dados publicos CVM)"
URL_DOCUMENTO = (
    "https://www.rad.cvm.gov.br/ENETCONSULTA/frmDownloadDocumento.aspx"
    "?CodigoInstituicao=1&NumeroSequencialDocumento={id_doc}"
)

#: Contas extraídas (X1.1): as do candidato e as de identidade contábil.
CONTAS = ("1", "1.01.01", "2", "6.01", "6.02", "6.03", "6.04", "6.05",
          "6.05.01", "6.05.02")
#: `CodigoTipoInformacaoFinanceira` do consolidado (X1.1) e do individual.
CONSOLIDADO = "2"
INDIVIDUAL = "1"
#: Membros sem os quais o formulário não serve (V1.2).
MEMBROS_EXIGIDOS = ("InfoFinaDFin.xml", "PeriodoDemonstracaoFinanceira.xml")
PREFIXO_FORMULARIO = "FormularioDemonstracaoFinanceira"
#: XML único (formato a partir de 2021): `025704ITR30-09-2024v1.xml`.
XML_UNICO = re.compile(r"\d{6}(ITR|DFP)\d{2}-\d{2}-\d{4}v\d+\.xml", re.IGNORECASE)
RAIZES_XML_UNICO = {
    "XmlInformacoesTrimestraisFinanceiras": "DadosITR",
    "XmlDemonstracoesFinanceiras": "DadosDFP",
}

#: Vocabulário FECHADO de declaração de unidade (N1.2), fixado no contrato
#: antes de qualquer leitura em massa. O texto é normalizado (minúsculas,
#: espaços colapsados) antes da busca.
PADROES_DE_UNIDADE: dict[str, tuple[str, ...]] = {
    "MIL": (
        r"em milhares de reais",
        r"em milhares de r\$",
        r"r\$ ?mil\b",
        r"expressos? em milhares",
        r"em r\$ ?milhares",
    ),
    "UNIDADE": (
        r"em reais(?! ?mil)(?! ?milh)",
        r"expressos? em reais",
    ),
    "MILHAO": (
        r"em milh[õo]es de reais",
        r"r\$ ?milh[õo]es\b",
    ),
}
CLASSES_DE_UNIDADE = (
    "declara_MIL", "declara_UNIDADE", "declara_MILHAO", "contraditorio", "ausente",
)
TRECHO_MINIMO = 60


class PacoteInvalido(Exception):
    """O pacote baixado não é um formulário íntegro (V1.2).

    `tipo` separa duas causas que pedem reações diferentes: `transporte` (ZIP
    truncado ou ilegível — tentar de novo resolve) e `formato` (ZIP íntegro com
    outra estrutura — tentar de novo não resolve, e chamar isso de "falha de
    acesso" daria o nome errado à causa).
    """

    def __init__(self, mensagem: str, tipo: str = "transporte"):
        super().__init__(mensagem)
        self.tipo = tipo


class FormatoNaoReconhecido(Exception):
    """Pacote íntegro cuja estrutura não é a esperada. Guardado para inspeção."""


class FalhaDeAcesso(Exception):
    """Nenhuma tentativa produziu pacote íntegro. **Não** prova inexistência."""


#: Variável de ambiente que proíbe download (reexecuções só sobre o disco).
#: Ambiente, e não monkeypatch, para valer também nos processos filhos.
SEM_REDE = "RAD_SEM_REDE"


class RedeBloqueada(RuntimeError):
    """Download pedido numa execução declarada sem rede."""


# --- aquisição ---------------------------------------------------------------

def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def validar_pacote(caminho: Path) -> str:
    """Devolve o nome do formulário interno, ou levanta `PacoteInvalido`.

    O RAD responde `HTTP 200` e corta conexão no meio (medido no piloto
    bancário); só a estrutura denuncia. Aqui a estrutura é dupla: o ZIP externo
    e o formulário `.itr`/`.dfp`, que é outro ZIP.
    """
    try:
        with zipfile.ZipFile(caminho) as externo:
            if externo.testzip() is not None:
                raise PacoteInvalido(f"{caminho.name}: membro corrompido no ZIP externo")
            formularios = [
                n for n in externo.namelist()
                if n.lower().endswith((".itr", ".dfp"))
            ]
            xml_unico = [n for n in externo.namelist() if XML_UNICO.fullmatch(n)]
            if not formularios and len(xml_unico) == 1:
                try:
                    raiz = ET.fromstring(externo.read(xml_unico[0]))
                except ET.ParseError as erro:
                    raise PacoteInvalido(
                        f"{caminho.name}: XML único malformado ({erro})") from None
                if raiz.tag not in RAIZES_XML_UNICO:
                    raise PacoteInvalido(
                        f"{caminho.name}: raiz {raiz.tag!r} não reconhecida", tipo="formato")
                return xml_unico[0]
            if len(formularios) != 1:
                raise PacoteInvalido(
                    f"{caminho.name}: {len(formularios)} formulários no pacote, esperado 1",
                    tipo="formato",
                )
            interno = io.BytesIO(externo.read(formularios[0]))
    except zipfile.BadZipFile as erro:
        raise PacoteInvalido(f"{caminho.name}: ZIP externo ilegível ({erro})") from None
    try:
        with zipfile.ZipFile(interno) as form:
            if form.testzip() is not None:
                raise PacoteInvalido(f"{caminho.name}: formulário interno corrompido")
            nomes = set(form.namelist())
    except zipfile.BadZipFile as erro:
        raise PacoteInvalido(f"{caminho.name}: formulário interno ilegível ({erro})") from None
    faltando = [m for m in MEMBROS_EXIGIDOS if m not in nomes]
    if faltando or not any(n.startswith(PREFIXO_FORMULARIO) for n in nomes):
        raise PacoteInvalido(
            f"{caminho.name}: formulário sem {faltando or PREFIXO_FORMULARIO}",
            tipo="formato",
        )
    return formularios[0]


def baixar(id_doc: str, destino: Path, tentativas: int = 4,
           espera: float = 3.0, executar=None, cookies: Path | None = None) -> str:
    """Baixa o pacote de `id_doc` e o valida. Devolve o SHA-256.

    Falha íntegra depois de todas as tentativas levanta `FalhaDeAcesso` — o
    chamador registra como falha de ACESSO, nunca como documento inexistente.
    """
    if not str(id_doc).isdigit():
        raise ValueError(f"ID_DOC inválido: {id_doc!r}")
    if os.environ.get(SEM_REDE):
        # Não é `FalhaDeAcesso`: uma reexecução que pediria download é defeito
        # de escopo e tem de parar alto, não virar documento indecidível.
        raise RedeBloqueada(f"ID_DOC {id_doc}: download pedido com {SEM_REDE} ligado")
    # Resolvido na CHAMADA, não na definição: um padrão `=subprocess.run`
    # congela a referência e escapa de dublês — um teste chegou a chamar o
    # `curl` real por isso.
    executar = executar or subprocess.run
    # Sessão por trabalhador: duas conexões não podem disputar o mesmo arquivo
    # de cookies.
    cookies = cookies or COOKIES
    destino.parent.mkdir(parents=True, exist_ok=True)
    cookies.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".parcial")
    ultimo_erro = "sem tentativa"
    for tentativa in range(1, tentativas + 1):
        parcial.unlink(missing_ok=True)
        executar(
            ["curl", "-sS", "-L", "--http1.1", "--connect-timeout", "30",
             "--max-time", "300",
             # Transferência parada aborta em 60 s em vez de esperar o teto:
             # medido em 16/09, o RAD às vezes para de mandar bytes.
             "--speed-limit", "5000", "--speed-time", "60",
             "-c", str(cookies), "-b", str(cookies), "-A", AGENTE_HTTP,
             "-o", str(parcial), URL_DOCUMENTO.format(id_doc=id_doc)],
            capture_output=True, text=True,
        )
        if parcial.is_file():
            try:
                validar_pacote(parcial)
            except PacoteInvalido as erro:
                if erro.tipo == "formato":
                    guardado = destino.parent / "nao_reconhecidos" / destino.name
                    guardado.parent.mkdir(parents=True, exist_ok=True)
                    parcial.replace(guardado)
                    raise FormatoNaoReconhecido(f"ID_DOC {id_doc}: {erro}") from None
                ultimo_erro = str(erro)
            else:
                parcial.replace(destino)
                return sha256(destino)
        else:
            ultimo_erro = "nenhum arquivo recebido"
        if tentativa < tentativas:
            time.sleep(espera * tentativa)
    parcial.unlink(missing_ok=True)
    raise FalhaDeAcesso(
        f"ID_DOC {id_doc}: nenhum pacote íntegro em {tentativas} tentativas "
        f"({ultimo_erro}). Falha de ACESSO — não prova que o documento não exista."
    )


_TRAVA_DO_MANIFESTO = threading.Lock()


def registrar(registro: dict, manifesto: Path = MANIFESTO) -> None:
    manifesto.parent.mkdir(parents=True, exist_ok=True)
    linha = json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n"
    with _TRAVA_DO_MANIFESTO, open(manifesto, "a", encoding="utf-8") as saida:
        saida.write(linha)


def adquirir(documento: dict, brutos: Path = BRUTOS, manifesto: Path = MANIFESTO,
             **kwargs) -> dict:
    """Baixa (ou reaproveita) o pacote de um documento do cadastro e registra.

    `documento` traz `id_doc`, `cd_cvm`, `conjunto`, `dt_refer`, `versao`.
    Pacote já presente é **revalidado** antes de reaproveitado: arquivo em
    disco não é prova de integridade.
    """
    destino = brutos / f"{documento['id_doc']}.zip"
    base = {k: documento[k] for k in ("id_doc", "cd_cvm", "conjunto", "dt_refer", "versao")}
    base["dt_refer"] = str(base["dt_refer"])
    if destino.is_file():
        try:
            validar_pacote(destino)
            return {**base, "estado": "integro", "sha256": sha256(destino),
                    "tamanho": destino.stat().st_size, "reaproveitado": True}
        except PacoteInvalido:
            destino.unlink()
    guardado = brutos / "nao_reconhecidos" / destino.name
    if guardado.is_file():
        # Revalidado com o validador ATUAL: um formato não reconhecido ontem
        # (o XML único, na primeira execução do piloto) pode ser suportado hoje.
        try:
            validar_pacote(guardado)
        except PacoteInvalido as erro:
            if erro.tipo == "formato":
                return {**base, "estado": "formato_nao_reconhecido", "reaproveitado": True,
                        "motivo": str(erro)}
            guardado.unlink()
        else:
            guardado.replace(destino)
            registro = {**base, "estado": "integro", "sha256": sha256(destino),
                        "tamanho": destino.stat().st_size,
                        "promovido_de": "nao_reconhecidos",
                        "promovido_em": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            # A mudança de estado é procedência: o manifesto dizia "não
            # reconhecido" para um pacote que hoje é lido.
            registrar(registro, manifesto)
            return {**registro, "reaproveitado": True}
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pausa = kwargs.pop("pausa", PAUSA_ENTRE_DOCUMENTOS)
    try:
        digest = baixar(documento["id_doc"], destino, **kwargs)
        # V1.1: espera também depois de um download bem-sucedido. (Auditoria de
        # 16/09: a aquisição S4 rodou com três conexões e sem esta pausa.)
        time.sleep(pausa)
    except FalhaDeAcesso as erro:
        registro = {**base, "estado": "falha_de_acesso", "motivo": str(erro),
                    "baixado_em": agora}
    except FormatoNaoReconhecido as erro:
        registro = {**base, "estado": "formato_nao_reconhecido", "motivo": str(erro),
                    "baixado_em": agora}
    else:
        registro = {**base, "estado": "integro", "sha256": digest,
                    "tamanho": destino.stat().st_size, "baixado_em": agora,
                    "url": URL_DOCUMENTO.format(id_doc=documento["id_doc"])}
    registrar(registro, manifesto)
    return {**registro, "reaproveitado": False}


# --- leitura do formulário ----------------------------------------------------

@dataclass
class Formulario:
    formulario: str
    codigo_escala_moeda: str | None
    #: Formato antigo: `{NumeroIdentificacaoPeriodo: (dt_ini, dt_fim)}`.
    #: XML único: `{nome da coluna: (dt_ini, dt_fim)}`.
    periodos: dict
    #: `[(conta, dt_ini, dt_fim, valor)]`, só consolidado, só períodos declarados
    valores: list[tuple[str, date | None, date, float]]
    #: `[(indice_do_anexo, [texto por página])]`
    anexos: list[tuple[int, list[str]]] = field(default_factory=list)
    formato: str = "formulario_zip"
    #: `{indice_do_anexo: NumeroGrupoRelacionado}` — 193/412 são as notas.
    grupos_anexos: dict[int, str] = field(default_factory=dict)
    #: Mesma forma de `valores`, do balanço INDIVIDUAL. Só serve à guarda de
    #: perímetro da evidência numérica (contrato E1e de 17/09); nunca é valor
    #: do painel.
    valores_individuais: list[tuple[str, date | None, date, float]] = field(default_factory=list)


def _data(texto: str | None) -> date | None:
    if not texto:
        return None
    valor = datetime.fromisoformat(texto.strip()).date()
    # O formulário usa 0001-01-01 como "sem data" (balanço não tem início).
    return None if valor.year == 1 else valor


def _periodos(xml: bytes) -> dict[int, tuple[date | None, date]]:
    raiz = ET.fromstring(xml)
    saida: dict[int, tuple[date | None, date]] = {}
    for p in raiz:
        numero = int(p.findtext("NumeroIdentificacaoPeriodo"))
        fim = _data(p.findtext("DataFimPeriodo"))
        if fim is None:
            raise PacoteInvalido(f"período {numero} sem data de fim")
        saida[numero] = (_data(p.findtext("DataInicioPeriodo")), fim)
    return saida


def _valores(xml: bytes, periodos: dict, tipo_desejado: str = CONSOLIDADO
             ) -> list[tuple[str, date | None, date, float]]:
    saida = []
    for _, elemento in ET.iterparse(io.BytesIO(xml), events=("end",)):
        if elemento.tag != "InfoFinaDFin":
            continue
        conta = (elemento.findtext("PlanoConta/NumeroConta") or "").strip()
        tipo = (elemento.findtext(
            "PlanoConta/VersaoPlanoConta/CodigoTipoInformacaoFinanceira") or "").strip()
        if conta in CONTAS and tipo == tipo_desejado:
            for filho in elemento:
                casamento = re.fullmatch(r"ValorConta(\d+)", filho.tag)
                if not casamento:
                    continue
                numero = int(casamento.group(1))
                if numero not in periodos:
                    # X1.2: coluna sem período só é aceitável se vazia (zero
                    # de preenchimento do formulário); com valor, é erro.
                    if float(filho.text or 0) != 0.0:
                        raise PacoteInvalido(
                            f"conta {conta}: ValorConta{numero} com valor e sem período"
                        )
                    continue
                dt_ini, dt_fim = periodos[numero]
                saida.append((conta, dt_ini, dt_fim, float(filho.text or 0)))
        elemento.clear()
    return saida


def _anexos(xml: bytes, grupos: frozenset | set | None = None
            ) -> tuple[list[tuple[int, list[str]]], dict[int, str]]:
    """Texto por página de cada PDF anexado, e o grupo de cada anexo.

    O grupo vem do elemento pai do PDF (`NumeroGrupoRelacionado`), no formato
    antigo e no XML único.
    """
    import pdfplumber  # dependência de leitura, só quando há anexo

    anexos: list[tuple[int, list[str]]] = []
    grupo_por_indice: dict[int, str] = {}
    indice = 0
    for _, elemento in ET.iterparse(io.BytesIO(xml), events=("end",)):
        pdf_b64 = elemento.find("ImagemObjetoArquivoPdf")
        if pdf_b64 is None:
            continue
        conteudo = (pdf_b64.text or "").strip()
        grupo = (elemento.findtext("NumeroGrupoRelacionado") or "").strip()
        elemento.clear()
        if not conteudo:
            continue
        grupo_por_indice[indice] = grupo
        if grupos is not None and grupo not in grupos:
            # Índice preservado: a página citada como evidência aponta para o
            # mesmo anexo, leia-se tudo ou só as notas.
            indice += 1
            continue
        pdf = base64.b64decode(conteudo)
        try:
            with pdfplumber.open(io.BytesIO(pdf)) as documento:
                paginas = [(p.extract_text() or "") for p in documento.pages]
        except Exception:  # anexo ilegível não invalida o formulário
            paginas = []
        anexos.append((indice, paginas))
        indice += 1
    return anexos, grupo_por_indice


#: Contas de POSIÇÃO (balanço): valem numa data, não num intervalo.
CONTAS_DE_POSICAO = frozenset({"1", "1.01.01", "2"})


def por_chave(formulario: Formulario) -> dict[tuple, float]:
    """Valores indexados como o ZIP os indexa: posição por data, fluxo por período.

    No formulário, a conta de balanço aparece em **toda** coluna de período — o
    trimestre e o acumulado do ano terminam no mesmo dia, um preenchido e outro
    zerado. Colapsar por data de fim exige regra: vale o único valor não nulo;
    dois não nulos **diferentes** na mesma data é contradição do formulário e
    levanta, em vez de escolher um.
    """
    saida: dict[tuple, float] = {}
    posicoes: dict[tuple, set[float]] = {}
    for conta, dt_ini, dt_fim, valor in formulario.valores:
        if conta in CONTAS_DE_POSICAO:
            posicoes.setdefault((conta, None, dt_fim), set())
            if valor != 0.0:
                posicoes[(conta, None, dt_fim)].add(valor)
        else:
            saida[(conta, dt_ini, dt_fim)] = valor
    for chave, valores in posicoes.items():
        if len(valores) > 1:
            raise PacoteInvalido(
                f"conta {chave[0]} em {chave[2]}: valores não nulos distintos {sorted(valores)}"
            )
        saida[chave] = next(iter(valores)) if valores else 0.0
    return saida


#: Blocos do XML único que contêm as contas extraídas (as outras demonstrações
#: reusam códigos de outros planos).
BLOCOS_XML_UNICO = ("BalancoPatrimonialAtivo", "BalancoPatrimonialPassivo",
                    "DemonstracaoFluxoCaixa")
#: Filhos de `<Conta>` que não são coluna de valor.
NAO_VALOR = frozenset({"ContaFixa", "CodigoConta", "DescricaoConta", "Metodo"})


def numero_ptbr(texto: str | None) -> float:
    """`'2.555.870'` → 2555870.0; `'-1.234,5'` → -1234.5; `'(10)'` → -10.0.

    Vazio é zero, como o CSV da CVM grava a célula não preenchida. Qualquer
    outra coisa que não seja número levanta — texto inesperado não vira zero.
    """
    t = (texto or "").strip()
    if not t:
        return 0.0
    negativo = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(".", "").replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        raise PacoteInvalido(f"valor não numérico no XML único: {texto!r}", tipo="formato")
    valor = float(t)
    return -valor if negativo else valor


def _data_br(texto: str | None) -> date | None:
    t = (texto or "").strip()
    return datetime.strptime(t, "%d/%m/%Y").date() if t else None


def _mover_meses(d: date, meses: int) -> date:
    total = d.year * 12 + (d.month - 1) + meses
    return date(total // 12, total % 12 + 1, d.day)


def periodos_xml_unico(raiz: ET.Element) -> dict[str, tuple[date | None, date]]:
    """Datas de cada COLUNA do XML único, a partir do cabeçalho.

    O acumulado do exercício anterior no ITR não tem data própria no cabeçalho:
    é o mesmo recorte do exercício corrente, deslocado pela distância entre os
    dois inícios de exercício (fim do trimestre + 1 dia, recuado N meses, − 1
    dia — preserva fim de mês). A prova de que isso está certo é X1.3: o valor
    tem de bater com o `PENÚLTIMO` do ZIP **na mesma chave de datas**.
    """
    cab = raiz.find(RAIZES_XML_UNICO[raiz.tag])
    g = lambda tag: _data_br(cab.findtext(tag))  # noqa: E731
    if raiz.tag == "XmlInformacoesTrimestraisFinanceiras":
        fim_tri = g("DtFimTrimestreAtual")
        ini_ex, ini_ant = g("DtInicioExercicioSocialCurso"), g("DtInicioExercicioSocialAnterior")
        periodos = {
            "TrimestreAtual": (g("DtInicioTrimestreAtual"), fim_tri),
            "ExercicioAnterior": (ini_ant, g("DtFimExercicioSocialAnterior")),
            "AcumuladoAtualExercicio": (ini_ex, fim_tri),
        }
        if fim_tri and ini_ex and ini_ant:
            meses = (ini_ex.year - ini_ant.year) * 12 + (ini_ex.month - ini_ant.month)
            fim_ant = _mover_meses(fim_tri + timedelta(days=1), -meses) - timedelta(days=1)
            periodos["AcumuladoExercicioAnterior"] = (ini_ant, fim_ant)
    else:
        periodos = {}
        for papel in ("Ultimo", "Penultimo", "Antepenultimo"):
            ini = g(f"DtInicio{papel}ExercicioSocial") or g(f"DtInicio{papel}ExercicioSocialField")
            fim = g(f"DtFim{papel}ExercicioSocial") or g(f"DtFim{papel}ExercicioSocialField")
            periodos[f"{papel}Exercicio"] = (ini, fim)
    return {k: v for k, v in periodos.items() if v[1] is not None}


def _valores_xml_unico(cab: ET.Element, caminho: str, periodos: dict
                       ) -> list[tuple[str, date | None, date, float]]:
    valores = []
    bloco_raiz = cab.find(caminho)
    for bloco in (bloco_raiz if bloco_raiz is not None else []):
        if bloco.tag not in BLOCOS_XML_UNICO:
            continue
        for conta in bloco.iter("Conta"):
            codigo = (conta.findtext("CodigoConta") or "").strip()
            if codigo not in CONTAS:
                continue
            for coluna in conta:
                if coluna.tag in NAO_VALOR:
                    continue
                valor = numero_ptbr(coluna.text)
                if coluna.tag not in periodos:
                    if valor != 0.0:
                        raise PacoteInvalido(
                            f"conta {codigo}: coluna {coluna.tag} com valor e sem período")
                    continue
                dt_ini, dt_fim = periodos[coluna.tag]
                valores.append((codigo, dt_ini, dt_fim, valor))
    return valores


def _ler_xml_unico(dados: bytes, nome: str) -> Formulario:
    raiz = ET.fromstring(dados)
    cab = raiz.find(RAIZES_XML_UNICO[raiz.tag])
    periodos = periodos_xml_unico(raiz)
    codigo_escala = cab.findtext("EscalaMoeda")
    return Formulario(
        formulario=nome,
        codigo_escala_moeda=codigo_escala.strip() if codigo_escala else None,
        periodos=periodos,
        valores=_valores_xml_unico(cab, "Formulario/DfConsolidadas", periodos),
        valores_individuais=_valores_xml_unico(cab, "Formulario/DfIndividuais", periodos),
        formato="xml_unico",
    )


def ler(caminho: Path, com_anexos: bool = True,
        grupos: frozenset | set | None = None) -> Formulario:
    """`grupos` restringe a extração de texto aos anexos desses grupos."""
    nome = validar_pacote(caminho)
    with zipfile.ZipFile(caminho) as externo:
        dados = externo.read(nome)
    if XML_UNICO.fullmatch(nome):
        formulario = _ler_xml_unico(dados, nome)
        if com_anexos:
            formulario.anexos, formulario.grupos_anexos = _anexos(dados, grupos)
        return formulario
    with zipfile.ZipFile(io.BytesIO(dados)) as interno:
        nomes = interno.namelist()
        form_xml = next(n for n in nomes if n.startswith(PREFIXO_FORMULARIO))
        codigo = ET.fromstring(interno.read(form_xml)).findtext(".//CodigoEscalaMoeda")
        periodos = _periodos(interno.read("PeriodoDemonstracaoFinanceira.xml"))
        info = interno.read("InfoFinaDFin.xml")
        valores = _valores(info, periodos)
        individuais = _valores(info, periodos, INDIVIDUAL)
        anexos, grupos = (
            _anexos(interno.read("AnexoDocumento.xml"), grupos)
            if com_anexos and "AnexoDocumento.xml" in nomes else ([], {})
        )
    return Formulario(
        formulario=nome,
        codigo_escala_moeda=codigo.strip() if codigo else None,
        periodos=periodos, valores=valores, anexos=anexos, grupos_anexos=grupos,
        valores_individuais=individuais,
    )


# --- evidência textual de unidade ---------------------------------------------

def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.replace("\xa0", " ")).lower()


def classificar_unidade(anexos: list[tuple[int, list[str]]]) -> dict:
    """Classe N1.3 do documento, com página e trecho de cada declaração."""
    evidencias = []
    for indice, paginas in anexos:
        for numero, pagina in enumerate(paginas, start=1):
            texto = _normalizar(pagina)
            for unidade, padroes in PADROES_DE_UNIDADE.items():
                for padrao in padroes:
                    for m in re.finditer(padrao, texto):
                        inicio = max(0, m.start() - 40)
                        trecho = texto[inicio:m.end() + 40]
                        if len(trecho) < TRECHO_MINIMO:
                            trecho = texto[max(0, m.start() - 60):m.end() + 60]
                        evidencias.append({
                            "unidade": unidade, "padrao": padrao,
                            "anexo": indice, "pagina": numero, "trecho": trecho,
                        })
    unidades = sorted({e["unidade"] for e in evidencias})
    if not unidades:
        classe = "ausente"
    elif len(unidades) > 1:
        classe = "contraditorio"
    else:
        classe = f"declara_{unidades[0]}"
    contagem: dict[str, int] = {}
    for e in evidencias:
        contagem[e["unidade"]] = contagem.get(e["unidade"], 0) + 1
    return {"classe": classe, "contagem": contagem, "evidencias": evidencias[:20]}


# --- RA3: evidência nas notas explicativas --------------------------------------

#: Grupos de anexo das notas explicativas: 193 no ITR, 412 na DFP (medido nos
#: dois formatos, 2011–2025).
GRUPOS_NOTAS = frozenset({"193", "412"})
#: Vocabulário de cabeçalho da ressalva RA3 (lote B), como foi implementado na
#: primeira execução. **Preservado** porque gerou o artefato do piloto e a
#: execução 1 da adjudicação; a ressalva RC1 do lote C mostrou dois defeitos
#: dele (flexão não coberta; rodapé por ação tomado por cabeçalho).
CABECALHOS_V1: dict[str, tuple[str, ...]] = {
    "MIL": (
        r"expressos? em milhares de reais",
        r"\(em milhares de reais",
        r"em milhares de reais, exceto",
        r"valores em milhares de reais",
    ),
    "UNIDADE": (
        r"expressos? em reais",
        r"\(em reais",
        r"em reais, exceto",
        r"valores em reais\b",
    ),
}
CLASSES_DE_CABECALHO = ("MIL", "UNIDADE", "contraditorio", "ausente", "sem_notas")
CLASSES_NUMERICAS = ("bruto", "dividido", "multiplicado", "nenhum", "conflitante", "sem_notas")
#: Só números com separador de milhar contam: "12" casa por acaso em qualquer texto.
MODULO_MINIMO = 1000


def texto_das_notas(formulario: Formulario) -> str | None:
    paginas = [
        p for indice, ps in formulario.anexos
        if formulario.grupos_anexos.get(indice) in GRUPOS_NOTAS
        for p in ps
    ]
    return _normalizar(" ".join(paginas)) if paginas else None


CABECALHOS = CABECALHOS_V1  # nome usado pelo piloto (RA3)


def classificar_cabecalho(texto: str | None) -> dict:
    """Classe RA3 **v1**, sobre o texto corrido das notas (medida do piloto)."""
    if texto is None:
        return {"classe": "sem_notas", "contagem": {}}
    contagem = {
        u: sum(len(re.findall(p, texto)) for p in padroes)
        for u, padroes in CABECALHOS_V1.items()
    }
    presentes = [u for u, n in contagem.items() if n]
    classe = ("ausente" if not presentes
              else presentes[0] if len(presentes) == 1 else "contraditorio")
    return {"classe": classe, "contagem": contagem}


def _inteiro_ptbr(valor: float) -> str:
    return f"{int(round(abs(valor))):,}".replace(",", ".")


def _aparece(numero: str, texto: str) -> bool:
    # Isolado: nem colado a outro dígito, nem continuação de milhar ("2.862.762.000").
    return re.search(rf"(?<![\d.]){re.escape(numero)}(?!\d|\.\d)", texto) is not None


def evidencia_numerica(formulario: Formulario, texto: str | None) -> dict:
    """Os valores do formulário aparecem nas notas como estão, ÷1.000 ou ×1.000?

    Discrimina o que o cabeçalho sozinho não discrimina: formulário em reais com
    notas em milhares mostra ÷1.000 nas notas; formulário em milhares com o
    rótulo `UNIDADE` errado mostra o valor bruto sob cabeçalho de milhares.
    """
    if texto is None:
        return {"classe": "sem_notas", "contagem": {}}
    valores = {abs(v) for c, _, _, v in formulario.valores if v and abs(v) >= MODULO_MINIMO}
    contagem = {"bruto": 0, "dividido": 0, "multiplicado": 0}
    for v in sorted(valores):
        if _aparece(_inteiro_ptbr(v), texto):
            contagem["bruto"] += 1
        if abs(v) / 1000 >= MODULO_MINIMO and _aparece(_inteiro_ptbr(v / 1000), texto):
            contagem["dividido"] += 1
        if _aparece(_inteiro_ptbr(v * 1000), texto):
            contagem["multiplicado"] += 1
    presentes = [k for k, n in contagem.items() if n]
    classe = ("nenhum" if not presentes
              else presentes[0] if len(presentes) == 1 else "conflitante")
    return {"classe": classe, "contagem": contagem, "valores_testados": len(valores)}


# --- RC1: cabeçalho DE APRESENTAÇÃO (lote C, parte 2) ------------------------------

#: Vocabulário v2: o da RA3 com as flexões de "expresso" e "apresentado".
CABECALHOS_V2: dict[str, tuple[str, ...]] = {
    "MIL": (
        r"express[oa]s? em milhares de reais",
        r"apresentad[oa]s? em milhares de reais",
        r"\(em milhares de reais",
        r"em milhares de reais, exceto",
        r"valores em milhares de reais",
    ),
    "UNIDADE": (
        r"express[oa]s? em reais\b",
        r"apresentad[oa]s? em reais\b",
        r"\(em reais\b",
        r"em reais, exceto",
        r"valores em reais\b",
    ),
}
#: RC1(2): a frase está no título da página...
INICIO_DE_PAGINA = 300
#: ...ou fala do objeto da apresentação nos caracteres anteriores.
JANELA_DO_OBJETO = 200
OBJETOS_DA_APRESENTACAO = (
    "demonstrações financeiras", "demonstrações contábeis",
    "informações trimestrais", "informações financeiras",
    "informações contábeis", "notas explicativas",
)


def cabecalhos_de_apresentacao(formulario: Formulario) -> list[dict]:
    """Toda frase de unidade que conta como cabeçalho de apresentação (RC1)."""
    achados = []
    for indice, paginas in formulario.anexos:
        if formulario.grupos_anexos.get(indice) not in GRUPOS_NOTAS:
            continue
        for numero, pagina in enumerate(paginas, start=1):
            texto = _normalizar(pagina)
            for unidade, padroes in CABECALHOS_V2.items():
                for padrao in padroes:
                    for m in re.finditer(padrao, texto):
                        antes = texto[max(0, m.start() - JANELA_DO_OBJETO):m.start()]
                        no_titulo = m.start() < INICIO_DE_PAGINA
                        fala_do_objeto = any(o in antes for o in OBJETOS_DA_APRESENTACAO)
                        if not (no_titulo or fala_do_objeto):
                            continue
                        achados.append({
                            "unidade": unidade, "anexo": indice, "pagina": numero,
                            "posicao": m.start(), "padrao": padrao,
                            "por": "titulo" if no_titulo else "objeto",
                            "trecho": texto[max(0, m.start() - 60):m.end() + 60],
                        })
    achados.sort(key=lambda a: (a["anexo"], a["pagina"], a["posicao"], a["padrao"]))
    return achados


def classificar_cabecalho_de_apresentacao(formulario: Formulario) -> dict:
    """Classe do cabeçalho pela regra RC1-bis: só `MIL` é evidência de escala.

    "Em reais" declara a MOEDA (parágrafo de moeda funcional) e aparece em
    rodapés por ação; é contado e publicado, mas não decide. Classes: `MIL`,
    `ausente` (nenhum cabeçalho de milhares aceito) ou `sem_notas`.
    """
    if texto_das_notas(formulario) is None:
        return {"classe": "sem_notas", "contagem": {}}
    achados = cabecalhos_de_apresentacao(formulario)
    contagem = {u: sum(1 for a in achados if a["unidade"] == u) for u in CABECALHOS_V2}
    return {"classe": "MIL" if contagem["MIL"] else "ausente", "contagem": contagem}


#: O1.3 — o que substitui, no trecho publicado, um valor de caixa do formulário.
VALOR_DE_CAIXA_OMITIDO = "[valor de caixa omitido]"


def mascarar_valores_de_caixa(trecho: str, formulario: Formulario) -> str:
    """O1.3: nenhum valor da DFC (`6.x`) do formulário sai no trecho publicado.

    Cobre o valor como está, ÷1.000 e ×1.000 — as três formas em que a
    evidência numérica o procura. Só módulos ≥ `MODULO_MINIMO`: abaixo disso o
    número coincide com numeração de nota e de página, e a guarda apagaria
    evidência sem proteger nada. (Auditoria de 16/09: o teste de O1.3 excluía
    justamente o trecho da verificação.)
    """
    formas = set()
    # O individual também (17/09): o FCO da controladora sai na mesma linha
    # da tabela das notas que o consolidado.
    for conta, _, _, v in (*formulario.valores, *formulario.valores_individuais):
        if not conta.startswith("6") or not v:
            continue
        for x in (abs(v), abs(v) / 1000, abs(v) * 1000):
            if x >= MODULO_MINIMO:
                formas.add(_inteiro_ptbr(x))
    # As formas mais longas primeiro, para "1.153.918" não virar "1.[…]".
    for numero in sorted(formas, key=len, reverse=True):
        trecho = re.sub(rf"(?<![\d.]){re.escape(numero)}(?!\d|\.\d)",
                        VALOR_DE_CAIXA_OMITIDO, trecho)
    return trecho


def evidencia_de_cabecalho(formulario: Formulario, unidade: str) -> dict | None:
    """Primeiro cabeçalho de apresentação de `unidade`, com anexo, página e trecho.

    Contrato do lote C, S8: correção sem trecho legível de ao menos
    `TRECHO_MINIMO` caracteres não pode ser registrada — devolve `None` e o
    chamador trata o documento como indecidível.
    """
    for achado in cabecalhos_de_apresentacao(formulario):
        if achado["unidade"] != unidade:
            continue
        if len(achado["trecho"]) < TRECHO_MINIMO:
            return None
        evidencia = {k: achado[k] for k in ("anexo", "pagina", "padrao", "trecho", "por")}
        evidencia["trecho"] = mascarar_valores_de_caixa(evidencia["trecho"], formulario)
        return evidencia
    return None


# --- v3: evidência numérica LOCALIZADA (contratos RF-01, 17/09) -------------------
#
# A v2 (`evidencia_numerica`) reduzia o formulário a um conjunto de magnitudes e
# as procurava no texto corrido das notas: perdia conta, período, perímetro e
# unidade da tabela. Na conferência de 17/09, `ESC-0101` foi "confirmada" por
# `1.000` — o saldo inicial de caixa de 2024 — casando com "dividido em 1.000
# (mil) ações", e corrigiu para `MIL` um ativo que estava certo em reais.
# `evidencia_numerica` fica como estava: reproduz o piloto e as execuções 1–2.

#: E2 — rótulo que a LINHA precisa conter para o número valer por aquela conta.
#: Tirado da descrição da conta no plano padrão, não das linhas casadas.
ROTULOS_DE_CONTA: dict[str, tuple[str, ...]] = {
    "1": (r"total do ativo(?! (n[ãa]o )?circulante)", r"\bativo total\b"),
    "2": (r"total do passivo(?! (n[ãa]o )?circulante)", r"\bpassivo total\b"),
    "1.01.01": (r"caixa e equivalentes de caixa",),
    "6.01": (r"atividades operacionais",),
    "6.02": (r"atividades de investimento",),
    "6.03": (r"atividades de financiamento",),
    "6.04": (r"varia[çc][ãa]o cambial",),
    "6.05": (r"(aumento|redu[çc][ãa]o|varia[çc][ãa]o).*caixa",),
    "6.05.01": (r"caixa.*(in[íi]cio|inicial)", r"(in[íi]cio|inicial).*caixa"),
    "6.05.02": (r"caixa.*\b(final|fim)\b", r"\b(final|fim)\b.*caixa"),
}
#: E1c — linha que fala de ações conta quantidade, não reais.
LINHA_DE_ACOES = re.compile(r"\baç(ão|ões)\b")
#: Multiplicador que leva o valor do formulário ao número impresso nas notas.
FORMAS = {"bruto": 1.0, "dividido": 1 / 1000, "multiplicado": 1000.0}
#: E3 — casamentos publicados por documento.
CASAMENTOS_PUBLICADOS = 5
#: Padrões com que uma PÁGINA declara a tabela em milhares (E1d).
MIL_NA_PAGINA = tuple(dict.fromkeys(PADROES_DE_UNIDADE["MIL"] + CABECALHOS_V2["MIL"]))


def pagina_em_milhares(texto_normalizado: str) -> bool:
    """E1d: a página declara milhares e não se intitula em reais."""
    if not any(re.search(p, texto_normalizado) for p in MIL_NA_PAGINA):
        return False
    titulo = texto_normalizado[:INICIO_DE_PAGINA]
    return not any(re.search(p, titulo) for p in CABECALHOS_V2["UNIDADE"])


def _como_data_iso(d) -> date:
    return d if isinstance(d, date) else date.fromisoformat(str(d)[:10])


def _formas_de(valor: float) -> dict[str, str]:
    """`{forma: texto}` das formas com módulo ≥ `MODULO_MINIMO`."""
    return {f: _inteiro_ptbr(abs(valor) * m) for f, m in FORMAS.items()
            if abs(valor) * m >= MODULO_MINIMO}


def _trecho_publicavel(linha: str, conta: str, formulario: Formulario) -> str:
    """O1.3: linha de conta de caixa sai sem número nenhum."""
    if conta.startswith("6"):
        return re.sub(r"\d[\d.,]*", VALOR_DE_CAIXA_OMITIDO, linha)
    return mascarar_valores_de_caixa(linha, formulario)


def evidencia_numerica_localizada(formulario: Formulario, dt_refer) -> dict:
    """Regra v3 (contrato E1): o número vale só na linha, página e perímetro certos.

    Devolve a mesma classe da v2 (`bruto`, `dividido`, `multiplicado`,
    `nenhum`, `conflitante`, `sem_notas`), a contagem de valores do formulário
    achados em cada forma, até `CASAMENTOS_PUBLICADOS` casamentos com conta,
    forma, anexo, página e trecho, e quantas ocorrências cada condição recusou.
    """
    if texto_das_notas(formulario) is None:
        return {"classe": "sem_notas", "contagem": {}, "casamentos": [], "recusas": {}}
    corrente = _como_data_iso(dt_refer)
    testados = sorted({
        (c, abs(v)) for c, _, fim, v in formulario.valores
        if v and abs(v) >= MODULO_MINIMO and fim == corrente and c in ROTULOS_DE_CONTA
    })
    # E1e: todas as formas de todos os valores da mesma conta, por forma.
    formas_da_conta: dict[str, dict[str, set[str]]] = {}
    for c, _, _, v in (*formulario.valores, *formulario.valores_individuais):
        if not v:
            continue
        for forma, texto in _formas_de(v).items():
            formas_da_conta.setdefault(c, {}).setdefault(forma, set()).add(texto)

    paginas = []
    for indice, ps in formulario.anexos:
        if formulario.grupos_anexos.get(indice) not in GRUPOS_NOTAS:
            continue
        for numero, pagina in enumerate(ps, start=1):
            linhas = [_normalizar(l) for l in pagina.splitlines()]
            paginas.append((indice, numero, pagina_em_milhares(_normalizar(pagina)), linhas))

    achados: dict[str, set[tuple[str, float]]] = {f: set() for f in FORMAS}
    casamentos: list[dict] = []
    recusas = {"sem_rotulo": 0, "linha_de_acoes": 0, "pagina_sem_milhares": 0, "ambiguo": 0}
    for conta, valor in testados:
        rotulos = ROTULOS_DE_CONTA[conta]
        for forma, texto in _formas_de(valor).items():
            outras = set().union(*(s for f, s in formas_da_conta.get(conta, {}).items()
                                   if f != forma))
            for indice, numero, em_milhares, linhas in paginas:
                for linha in linhas:
                    if not _aparece(texto, linha):
                        continue
                    if not any(re.search(r, linha) for r in rotulos):
                        recusas["sem_rotulo"] += 1
                    elif LINHA_DE_ACOES.search(linha):
                        recusas["linha_de_acoes"] += 1
                    elif not em_milhares:
                        recusas["pagina_sem_milhares"] += 1
                    elif texto in outras:
                        recusas["ambiguo"] += 1
                    else:
                        achados[forma].add((conta, valor))
                        if len(casamentos) < CASAMENTOS_PUBLICADOS:
                            casamentos.append({
                                "conta": conta, "forma": forma, "anexo": indice,
                                "pagina": numero,
                                "trecho": _trecho_publicavel(linha, conta, formulario),
                            })
    contagem = {f: len(s) for f, s in achados.items()}
    presentes = [f for f, n in contagem.items() if n]
    classe = ("nenhum" if not presentes
              else presentes[0] if len(presentes) == 1 else "conflitante")
    return {"classe": classe, "contagem": contagem, "valores_testados": len(testados),
            "casamentos": casamentos, "recusas": recusas, "regra": "v3"}


# CRF-01: v4 estrita para SALDOS. Não extrapolar data final para intervalo DFC.
ROTULOS_SALDOS_V4 = {
    "ativo total": "1", "total do ativo": "1",
    "passivo total": "2", "total do passivo": "2",
    "total do passivo e patrimônio líquido": "2",
    "total do passivo e do patrimônio líquido": "2",
    "caixa e equivalentes de caixa": "1.01.01",
}
UNIDADE_LOCAL_V4 = re.compile(
    r"\(?(?:valores )?(?:(?:expressos|apresentados) )?em milhares de reais\)?")
DATA_CELULA_V4 = re.compile(r"(?:\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})")
NUMERO_CELULA_V4 = r"(?:\(?[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?\)?|[-–—])"
LINHA_CELULAS_V4 = re.compile(
    rf"(?P<rotulo>[^\d]+?)\s+(?P<celulas>{NUMERO_CELULA_V4}(?:\s+{NUMERO_CELULA_V4})*)")


def _datas_de_colunas_v4(linha: str) -> list[str] | None:
    itens = linha.replace("|", " ").split()
    if not itens or not all(DATA_CELULA_V4.fullmatch(x) for x in itens):
        return None
    try:
        datas = [(datetime.strptime(x, "%d/%m/%Y").date() if "/" in x
                  else date.fromisoformat(x)).isoformat() for x in itens]
    except ValueError:
        return None
    return datas if len(datas) == len(set(datas)) else None


def _cabecalho_local_v4(anteriores: list[str]) -> bool:
    if len(anteriores) != 2 or anteriores.count("consolidado") != 1:
        return False
    unidade = next(l for l in anteriores if l != "consolidado")
    return UNIDADE_LOCAL_V4.fullmatch(unidade) is not None


def _celulas_da_linha_v4(linha: str):
    m = LINHA_CELULAS_V4.fullmatch(linha)
    if not m:
        return None
    itens = m["celulas"].split()
    if any(x.startswith("(") != x.endswith(")") for x in itens):
        return None
    return m["rotulo"].strip(), itens


def validar_escopo_numerico_v4(c: dict, dt_refer: str) -> None:
    """Produtor E consumidor: uma prova histórica sem coluna não vira v4."""
    datas = _datas_de_colunas_v4(c.get("datas_colunas", ""))
    ok = (c.get("regra") == "v4" and c.get("perimetro") == "consolidado"
          and c.get("unidade") == "MIL" and c.get("dt_fim") == dt_refer
          and c.get("conta") in set(ROTULOS_SALDOS_V4.values())
          and c.get("forma") in FORMAS
          and type(c.get("anexo")) is int and c["anexo"] >= 0
          and all(type(c.get(k)) is int and c[k] > 0 for k in ("pagina", "linha", "coluna"))
          and isinstance(c.get("cabecalho_local"), list)
          and _cabecalho_local_v4(c["cabecalho_local"]) and bool(c.get("trecho")))
    if not ok or not datas or c["coluna"] > len(datas) or datas[c["coluna"] - 1] != dt_refer:
        raise AssertionError("evidência numérica sem escopo de conta/coluna v4")
    # O consumidor também verifica o vínculo do rótulo à conta e a
    # cardinalidade de células; metadata plausível não conserta outra linha.
    row = _celulas_da_linha_v4(c["trecho"].replace("[valor omitido]", "1"))
    if (re.search(r"\d", c["trecho"]) or row is None
            or ROTULOS_SALDOS_V4.get(row[0]) != c["conta"] or len(row[1]) != len(datas)):
        raise AssertionError("evidência v4 sem rótulo/células correspondentes à conta")


def evidencia_numerica_tabular(formulario: Formulario, dt_refer) -> dict:
    """CRF-01/C1: só célula identificada sob cabeçalho local explícito.

    Rejeição aqui é incapacidade deste extrator, não prova de escala contrária.
    A v3 permanece intacta para reproduzir sua execução histórica.
    """
    corrente = _como_data_iso(dt_refer)
    candidatos: dict[str, set[Decimal]] = {}
    for conta, _, fim, valor in formulario.valores:
        if conta in ROTULOS_SALDOS_V4.values() and fim == corrente and valor is not None:
            candidatos.setdefault(conta, set()).add(Decimal(str(valor)))
    # C1.5: unicidade ANTES do módulo; +x e -x são declarações distintas.
    valores = {c: abs(next(iter(vs))) for c, vs in candidatos.items()
               if len(vs) == 1 and next(iter(vs)).is_finite() and abs(next(iter(vs))) >= MODULO_MINIMO}
    outras_formas = {}
    for conta, _, _, valor in (*formulario.valores, *formulario.valores_individuais):
        if valor:
            for forma, texto in _formas_de(valor).items():
                outras_formas.setdefault(conta, {}).setdefault(forma, set()).add(texto)
    achados = {f: set() for f in FORMAS}
    casamentos = []
    tabelas = 0
    for anexo, paginas in formulario.anexos:
        if formulario.grupos_anexos.get(anexo) not in GRUPOS_NOTAS:
            continue
        for pagina, texto in enumerate(paginas, 1):
            anteriores = []
            contexto = None
            for nlinha, original in enumerate(texto.splitlines(), 1):
                linha = _normalizar(original)
                datas = _datas_de_colunas_v4(linha)
                if datas and _cabecalho_local_v4(anteriores[-2:]) and corrente.isoformat() in datas:
                    contexto = (datas, anteriores[-2:], linha)
                    tabelas += 1
                elif contexto:
                    row = _celulas_da_linha_v4(linha)
                    if row is None or len(row[1]) != len(contexto[0]):
                        contexto = None
                    else:
                        rotulo, celulas = row
                        conta = ROTULOS_SALDOS_V4.get(rotulo)
                        if conta in valores:
                            coluna = contexto[0].index(corrente.isoformat())
                            celula = celulas[coluna]
                            if celula not in ("-", "–", "—"):
                                impresso = abs(Decimal(celula.strip("()").replace(".", "").replace(",", ".")))
                                for forma, fator in (("bruto", Decimal(1)),
                                                     ("dividido", Decimal("0.001")),
                                                     ("multiplicado", Decimal(1000))):
                                    esperado = valores[conta] * fator
                                    if forma == "dividido" and esperado < MODULO_MINIMO:
                                        continue
                                    alvo = esperado if "," in celula else esperado.quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
                                    concorrentes = set().union(*(v for f, v in outras_formas.get(conta, {}).items() if f != forma))
                                    if impresso and impresso == alvo and _inteiro_ptbr(float(impresso)) not in concorrentes:
                                        achados[forma].add(conta)
                                        if len(casamentos) < CASAMENTOS_PUBLICADOS:
                                            c = {"regra": "v4", "conta": conta, "forma": forma,
                                                 "anexo": anexo, "pagina": pagina, "linha": nlinha,
                                                 "coluna": coluna + 1, "dt_fim": corrente.isoformat(),
                                                 "perimetro": "consolidado", "unidade": "MIL",
                                                 "cabecalho_local": contexto[1], "datas_colunas": contexto[2],
                                                 "trecho": re.sub(r"\d[\d.,]*", "[valor omitido]", linha)}
                                            validar_escopo_numerico_v4(c, corrente.isoformat())
                                            casamentos.append(c)
                if linha:
                    anteriores.append(linha)
    contagem = {f: len(v) for f, v in achados.items()}
    presentes = [f for f, n in contagem.items() if n]
    classe = "nenhum" if not presentes else presentes[0] if len(presentes) == 1 else "conflitante"
    return {"classe": classe, "contagem": contagem, "valores_testados": len(valores),
            "casamentos": casamentos, "tabelas_com_cabecalho_local": tabelas, "regra": "v4"}
