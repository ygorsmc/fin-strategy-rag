"""Caixa de ferramentas da camada de agentes (spec 5.9 · RN04 · RN07 · RN09).

Quatro ferramentas, e só quatro:

| Ferramenta | O que faz |
|---|---|
| `verificar_cobertura` | resolve a entidade por `CD_CVM` e classifica a cobertura nos três estados da RN12 |
| `buscar_trechos` | recuperação documental com filtro de metadados (camada de `src.recuperacao`) |
| `consultar_cvm` | SQL somente-leitura sobre `fatos_semanticos`, **nunca** sobre `fatos_contabeis` cru (RN09) |
| `calcular_indicadores` | indicadores já materializados, por `CD_CVM` e trimestre |

**`prever_risco` não existe** e não entra aqui sob nenhum nome (RN07). O modelo
preditivo permanece como módulo analítico; expor juízo prospectivo sobre
companhia nomeada é a fronteira que a RN05 defende.

Este módulo **não reimplementa** guarda nenhuma: as da RN04 (somente-leitura,
lista branca, DDL/DML bloqueado por análise sintática, `LIMIT`, timeout) vivem
em `src.dados_estruturados.validar_sql` e são chamadas daqui. A lista branca já
exclui `fatos_contabeis`, então a RN09 é aplicada pela mesma porta.

O que este módulo acrescenta é **contenção** (5.9.5): teto de chamadas por
consulta e registro de cada chamada. Estourado o teto, o chamador tem o
histórico do que foi reunido até ali para montar uma resposta parcial — nunca um
laço aberto pagando token.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.cobertura import (
    FatoEstruturado,
    IndiceCobertura,
    LeitorDeFatos,
    RespostaDeterministica,
    carregar_indice_cobertura,
    extrair_mencoes,
    responder_por_gabarito,
    resolver_entidade,
    triar_entidade,
)
from src.config import TABELAS_PERMITIDAS_SQL, Config
from src.dados_estruturados import (
    ResultadoSQL,
    abrir_conexao_somente_leitura,
    executar_sql,
)
from src.mapa_contas import CONCEITOS, normalizar_cd_cvm
from src.recuperacao import Estrategia, Recuperador

registrador = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Contrato da caixa
# --------------------------------------------------------------------------- #

FERRAMENTAS_DISPONIVEIS: tuple[str, ...] = (
    "verificar_cobertura",
    "buscar_trechos",
    "consultar_cvm",
    "calcular_indicadores",
)

# Nomes que a caixa NUNCA pode expor. `prever_risco` foi removido em 07/08/2026
# por três razões convergentes (spec 5.9.5): emitir juízo prospectivo sobre
# companhia listada nominada é a fronteira da RN05; a regra de fora-de-domínio
# do modelo já recusaria 100% das perguntas sobre os cinco bancos do corpus; e
# nenhum dos 26 trimestres-banco observados teve prejuízo, então a saída seria
# constante. Reintroduzi-lo sob outro nome é a mesma violação.
FERRAMENTAS_PROIBIDAS: frozenset[str] = frozenset({"prever_risco"})


class ErroFerramenta(RuntimeError):
    """Falha de uso de ferramenta — argumento inválido ou dependência ausente."""


class TetoChamadasExcedidoError(ErroFerramenta):
    """O teto de `AGENTES_MAX_CHAMADAS_FERRAMENTA` foi atingido.

    Não é erro de infraestrutura: é a contenção da 5.9.5 funcionando. Quem
    chamou deve montar a resposta com a melhor evidência do `registro` e
    marcá-la como parcial.
    """


@dataclass(frozen=True)
class RegistroChamada:
    """Uma chamada de ferramenta, para custo, auditoria (RNF08) e resposta parcial."""

    ferramenta: str
    argumentos: Mapping[str, Any] = field(default_factory=dict)
    resumo: str = ""
    erro: str | None = None

    @property
    def falhou(self) -> bool:
        return self.erro is not None

    def como_dicionario(self) -> dict:
        return {
            "ferramenta": self.ferramenta,
            "argumentos": dict(self.argumentos),
            "resumo": self.resumo,
            "erro": self.erro,
        }


# --------------------------------------------------------------------------- #
# Leitor de fatos do painel (implementa o protocolo do braço C)
# --------------------------------------------------------------------------- #


class LeitorPainelDuckDB(LeitorDeFatos):
    """Lê um conceito × companhia × trimestre de `fatos_semanticos`.

    Usa a visão semântica, jamais `fatos_contabeis`: `cd_conta` não identifica o
    conceito contábil entre companhias (RN09). Consulta parametrizada e fixa —
    não há SQL de modelo passando por aqui.
    """

    _SQL = """
        SELECT cd_cvm, denom_social, trimestre, conceito, valor_reais,
               origem, max(ds_conta) AS ds_conta
        FROM fatos_semanticos
        WHERE cd_cvm = ? AND conceito = ? AND trimestre = ?
        GROUP BY cd_cvm, denom_social, trimestre, conceito, valor_reais, origem
        ORDER BY origem
        LIMIT 2
    """

    def __init__(self, config: Config, caminho: Path | None = None) -> None:
        self.config = config
        self.caminho = caminho

    def ler(
        self, cd_cvm: str, conceito: str, trimestre: str
    ) -> FatoEstruturado | None:
        conexao = abrir_conexao_somente_leitura(self.config, self.caminho)
        try:
            linhas = conexao.execute(
                self._SQL, [normalizar_cd_cvm(cd_cvm), conceito, trimestre]
            ).fetchall()
        finally:
            conexao.close()
        if not linhas:
            return None
        if len(linhas) > 1:
            # Mesma companhia, mesmo trimestre, mesmo conceito, dois valores:
            # devolver um deles seria escolher em silêncio.
            registrador.warning(
                "ferramentas: %s/%s/%s tem %d valores no painel; nenhum foi "
                "escolhido",
                cd_cvm,
                conceito,
                trimestre,
                len(linhas),
            )
            return None
        codigo, denom, tri, conc, valor, origem, ds_conta = linhas[0]
        return FatoEstruturado(
            cd_cvm=codigo,
            denom_social=denom,
            trimestre=tri,
            conceito=conc,
            valor_reais=float(valor),
            origem=origem,
            ds_conta=ds_conta or "",
        )


# --------------------------------------------------------------------------- #
# Caixa de ferramentas
# --------------------------------------------------------------------------- #


class CaixaDeFerramentas:
    """As ferramentas que Investigador e Auditor compartilham.

    Todas as dependências são injetáveis, e é isso que torna a camada testável
    sem rede, sem LLM e sem o painel real. O Auditor recebe uma **instância
    própria** — o isolamento de contexto da 5.9.1 exige que ele reexecute as
    consultas por conta própria, e um contador compartilhado faria a segunda
    execução herdar o orçamento gasto pela primeira.
    """

    def __init__(
        self,
        config: Config,
        *,
        indice_cobertura: IndiceCobertura | None = None,
        recuperador: Recuperador | None = None,
        leitor: LeitorDeFatos | None = None,
        caminho_painel: Path | None = None,
        max_chamadas: int | None = None,
    ) -> None:
        self.config = config
        self.caminho_painel = caminho_painel
        self._indice = indice_cobertura
        self._recuperador = recuperador
        self._leitor = leitor
        teto = (
            config.agentes_max_chamadas_ferramenta
            if max_chamadas is None
            else max_chamadas
        )
        if type(teto) is not int or teto <= 0:
            raise ValueError("max_chamadas deve ser um inteiro positivo")
        self.max_chamadas = teto
        self._registro: list[RegistroChamada] = []

    # -- estado da contenção ------------------------------------------------ #

    @property
    def registro(self) -> tuple[RegistroChamada, ...]:
        return tuple(self._registro)

    @property
    def chamadas_feitas(self) -> int:
        return len(self._registro)

    @property
    def chamadas_restantes(self) -> int:
        return max(0, self.max_chamadas - self.chamadas_feitas)

    @property
    def teto_atingido(self) -> bool:
        return self.chamadas_restantes == 0

    def _reservar(self, ferramenta: str, argumentos: Mapping[str, Any]) -> None:
        """Consome uma vaga do orçamento ANTES de executar.

        Chamada bloqueada também consome: sem isso, um laço de SQL recusado
        rodaria para sempre de graça, que é o oposto da contenção.
        """
        if self.teto_atingido:
            raise TetoChamadasExcedidoError(
                f"teto de {self.max_chamadas} chamadas de ferramenta atingido; "
                "monte a resposta com a evidência já reunida e marque-a como "
                "parcial (spec 5.9.5)"
            )
        self._registro.append(
            RegistroChamada(ferramenta=ferramenta, argumentos=dict(argumentos))
        )

    def _concluir(self, resumo: str, erro: str | None = None) -> None:
        anterior = self._registro[-1]
        self._registro[-1] = RegistroChamada(
            ferramenta=anterior.ferramenta,
            argumentos=anterior.argumentos,
            resumo=resumo,
            erro=erro,
        )

    # -- dependências preguiçosas ------------------------------------------- #

    def indice_cobertura(self) -> IndiceCobertura:
        if self._indice is None:
            self._indice = carregar_indice_cobertura(
                self.config, self.caminho_painel
            )
        return self._indice

    def leitor(self) -> LeitorDeFatos:
        if self._leitor is None:
            self._leitor = LeitorPainelDuckDB(self.config, self.caminho_painel)
        return self._leitor

    def recuperador(self) -> Recuperador:
        if self._recuperador is None:
            self._recuperador = Recuperador(self.config)
        return self._recuperador

    # -- ferramentas -------------------------------------------------------- #

    def verificar_cobertura(
        self, entidade: str, trimestre: str | None = None
    ) -> dict:
        """Resolve a entidade e classifica a cobertura nos três estados da RN12.

        Aceita nome, apelido, `CD_CVM` ou uma pergunta inteira. Nome que resolve
        para mais de uma companhia devolve `desambiguacao` preenchido e
        `estado` nulo — a escolha é do usuário, nunca do sistema (RN11).
        """
        self._reservar(
            "verificar_cobertura", {"entidade": entidade, "trimestre": trimestre}
        )
        try:
            if not isinstance(entidade, str) or not entidade.strip():
                raise ErroFerramenta("entidade deve ser texto não vazio")
            indice = self.indice_cobertura()
            termos = extrair_mencoes(entidade, indice)
            if not termos:
                # Termo curto ou nome fora do vocabulário: tenta o termo cru
                # antes de desistir, para não devolver "nenhuma" sem ter olhado.
                termos = (entidade.strip(),)
            triagens = [triar_entidade(termo, indice, trimestre) for termo in termos]
        except Exception as erro:
            self._concluir("", erro=f"{type(erro).__name__}: {erro}")
            raise
        resultado = {
            "consulta": entidade,
            "trimestre": trimestre,
            "entidades": [t.como_dicionario() for t in triagens],
            "desambiguacao": [
                t.pergunta_desambiguacao()
                for t in triagens
                if t.precisa_desambiguacao
            ],
        }
        estados = [
            t.cobertura.estado.value if t.cobertura else "desambiguacao"
            for t in triagens
        ]
        self._concluir(f"{len(triagens)} entidade(s): {', '.join(estados)}")
        return resultado

    def buscar_trechos(
        self,
        pergunta: str,
        estrategia: str | Estrategia | None = None,
        top_k: int | None = None,
    ) -> list[dict]:
        """Trechos recuperados, com os metadados que a RN01 exige citar.

        Devolve `empresa`, `documento`, `trimestre` e páginas por trecho: sem
        eles a citação obrigatória não é verificável por código, e a verificação
        da RN01 não migra para dentro do agente (5.9.5).
        """
        self._reservar(
            "buscar_trechos",
            {"pergunta": pergunta, "estrategia": str(estrategia or ""), "top_k": top_k},
        )
        try:
            if not isinstance(pergunta, str) or not pergunta.strip():
                raise ErroFerramenta("pergunta deve ser texto não vazio")
            escolhida = Estrategia(estrategia or self.config.estrategia_padrao)
            if escolhida is Estrategia.CLOSED_BOOK:
                raise ErroFerramenta(
                    "closed_book não recupera nada: é a estratégia de "
                    "diagnóstico E0, não uma ferramenta do agente"
                )
            resultados = self.recuperador().recuperar(
                pergunta, escolhida, top_k=top_k
            )
        except Exception as erro:
            self._concluir("", erro=f"{type(erro).__name__}: {erro}")
            raise
        trechos = [
            {
                "id": r.chunk.id,
                "empresa": r.chunk.empresa,
                "documento": r.chunk.documento,
                "trimestre": r.chunk.trimestre,
                "pagina_inicio": r.chunk.pagina_inicio,
                "pagina_fim": r.chunk.pagina_fim,
                "texto": r.chunk.texto,
                "score": float(r.score),
                "origem": r.origem.value,
            }
            for r in resultados
        ]
        self._concluir(f"{len(trechos)} trecho(s) por {escolhida.value}")
        return trechos

    def consultar_cvm(self, sql: str) -> dict:
        """SQL somente-leitura sobre a camada semântica (RN04 + RN09).

        As guardas são as de `src.dados_estruturados`: `fatos_contabeis` está
        fora da lista branca e `cd_conta` é coluna bloqueada, então consulta que
        tente escolher código de conta é recusada **antes** de executar. Aqui
        não há guarda nova — reimplementá-la criaria duas versões da mesma regra
        e uma delas ficaria desatualizada.
        """
        self._reservar("consultar_cvm", {"sql": sql})
        try:
            resultado: ResultadoSQL = executar_sql(
                sql, self.config, self.caminho_painel
            )
        except Exception as erro:
            self._concluir("", erro=f"{type(erro).__name__}: {erro}")
            raise
        self._concluir(f"{resultado.total_linhas} linha(s)")
        return {
            "sql": resultado.sql,
            "colunas": list(resultado.colunas),
            "linhas": [list(linha) for linha in resultado.linhas],
            "total_linhas": resultado.total_linhas,
            "tabelas_permitidas": sorted(TABELAS_PERMITIDAS_SQL),
        }

    def calcular_indicadores(
        self, cd_cvm: str, trimestre: str | None = None
    ) -> dict:
        """Indicadores materializados de uma companhia, por `CD_CVM` (RN11).

        Recusa nome de propósito: quem quer partir de um nome passa antes por
        `verificar_cobertura`, que é onde a desambiguação acontece. Aceitar nome
        aqui reintroduziria a escolha automática pela porta dos fundos.

        `liquidez` não existe na saída: o balanço de instituição financeira
        publicado na CVM não traz a separação circulante/não circulante que o
        índice pressupõe. Ausência declarada, não esquecimento.
        """
        self._reservar(
            "calcular_indicadores", {"cd_cvm": cd_cvm, "trimestre": trimestre}
        )
        try:
            bruto = str(cd_cvm or "").strip()
            if not bruto.isdigit():
                raise ErroFerramenta(
                    f"cd_cvm inválido: {cd_cvm!r}. A companhia é resolvida por "
                    "código, nunca por nome (RN11) — use verificar_cobertura "
                    "para obter o CD_CVM antes de calcular indicadores."
                )
            codigo = normalizar_cd_cvm(bruto)
            filtro = "AND trimestre = ?" if trimestre else ""
            parametros: list[Any] = [codigo]
            if trimestre:
                parametros.append(trimestre)
            conexao = abrir_conexao_somente_leitura(self.config, self.caminho_painel)
            try:
                cursor = conexao.execute(
                    "SELECT * FROM indicadores "
                    f"WHERE cd_cvm = ? {filtro} ORDER BY trimestre",
                    parametros,
                )
                linhas = cursor.fetchall()
                colunas = tuple(d[0] for d in (cursor.description or ()))
            finally:
                conexao.close()
        except Exception as erro:
            self._concluir("", erro=f"{type(erro).__name__}: {erro}")
            raise
        registros = [dict(zip(colunas, linha)) for linha in linhas]
        self._concluir(f"{len(registros)} trimestre(s) para {codigo}")
        return {
            "cd_cvm": codigo,
            "trimestre": trimestre,
            "indicadores": registros,
            # RN10: um trimestre com qualquer componente derivado sai marcado.
            "derivado": any(r.get("origem") == "derivado" for r in registros),
            "ausentes_declarados": ["liquidez"],
        }

    # -- descrição para o agente -------------------------------------------- #

    def descrever(self) -> tuple[dict, ...]:
        """Esquema das ferramentas, para montar o prompt do agente.

        Gerado a partir de `FERRAMENTAS_DISPONIVEIS`, não escrito à mão: uma
        ferramenta que exista no código e não apareça aqui (ou o contrário)
        seria divergência silenciosa entre o que o agente pode chamar e o que
        ele acha que pode.
        """
        descricoes = {
            "verificar_cobertura": (
                "Resolve a companhia por CD_CVM e devolve o estado de cobertura "
                "(ambas | so_painel | nenhuma). Nome ambíguo devolve pergunta de "
                "desambiguação em vez de escolher."
            ),
            "buscar_trechos": (
                "Recupera trechos do corpus documental com filtro por empresa e "
                "trimestre; devolve os metadados de citação obrigatórios."
            ),
            "consultar_cvm": (
                "Executa SELECT somente-leitura sobre a camada semântica do "
                "painel (fatos_semanticos, companhias, indicadores, "
                "mapa_contas). LIMIT obrigatório; cd_conta é bloqueado."
            ),
            "calcular_indicadores": (
                "Devolve ROE, margem líquida e alavancagem já materializados "
                "para um CD_CVM (e trimestre opcional)."
            ),
        }
        return tuple(
            {
                "nome": nome,
                "descricao": descricoes[nome],
                "assinatura": getattr(self, nome).__doc__.strip().splitlines()[0],
            }
            for nome in FERRAMENTAS_DISPONIVEIS
        )

    # -- braço C ------------------------------------------------------------ #

    def responder_deterministico(self, pergunta: str) -> RespostaDeterministica:
        """Braço C da 5.9.3 — o piso honesto, sem nenhuma chamada de LLM.

        Roda a resolução de entidade, a triagem de cobertura e o gabarito fixo
        de `src.cobertura`, com o painel como leitor de valores. Conta como
        chamada de ferramenta porque consome as mesmas fontes que os outros
        braços — comparar custo entre braços exige contar do mesmo jeito.
        """
        self._reservar("verificar_cobertura", {"entidade": pergunta})
        try:
            resposta = responder_por_gabarito(
                pergunta, self.indice_cobertura(), self.leitor()
            )
        except Exception as erro:
            self._concluir("", erro=f"{type(erro).__name__}: {erro}")
            raise
        self._concluir(
            f"braço C: recusa={resposta.recusa} parcial={resposta.parcial} "
            f"fatos={len(resposta.fatos)}"
        )
        return resposta


def conceitos_consultaveis() -> tuple[str, ...]:
    """Conceitos que `consultar_cvm` reconhece na coluna `conceito`."""
    return tuple(CONCEITOS)


def sql_de_conceito(
    cd_cvm: Sequence[str] | str,
    conceito: str,
    trimestres: Sequence[str] | None = None,
    limite: int = 20,
) -> str:
    """Monta um SELECT válido sobre `fatos_semanticos`, com `LIMIT` obrigatório.

    Existe para que o agente não precise inventar SQL para o caso comum, e para
    que o exemplo que ele copia já esteja dentro das guardas da RN04. O texto
    continua passando por `validar_sql` na execução — este atalho não é um
    desvio da validação.
    """
    codigos = [cd_cvm] if isinstance(cd_cvm, str) else list(cd_cvm)
    if not codigos:
        raise ErroFerramenta("informe ao menos um cd_cvm")
    if conceito not in CONCEITOS:
        raise ErroFerramenta(
            f"conceito desconhecido: {conceito!r}; conhecidos={list(CONCEITOS)}"
        )
    if type(limite) is not int or limite <= 0:
        raise ErroFerramenta("limite deve ser inteiro positivo")
    lista = ", ".join(f"'{normalizar_cd_cvm(c)}'" for c in codigos)
    filtro_trimestre = ""
    if trimestres:
        periodos = ", ".join(f"'{t}'" for t in trimestres)
        filtro_trimestre = f"\n  AND trimestre IN ({periodos})"
    return (
        "SELECT cd_cvm, denom_social, trimestre, conceito, valor_reais, origem\n"
        "FROM fatos_semanticos\n"
        f"WHERE cd_cvm IN ({lista})\n"
        f"  AND conceito = '{conceito}'{filtro_trimestre}\n"
        "ORDER BY cd_cvm, trimestre\n"
        f"LIMIT {limite}"
    )


__all__ = [
    "CaixaDeFerramentas",
    "ErroFerramenta",
    "FERRAMENTAS_DISPONIVEIS",
    "FERRAMENTAS_PROIBIDAS",
    "LeitorPainelDuckDB",
    "RegistroChamada",
    "TetoChamadasExcedidoError",
    "conceitos_consultaveis",
    "resolver_entidade",
    "sql_de_conceito",
]
