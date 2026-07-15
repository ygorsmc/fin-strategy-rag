"""Utilitários do runtime Ollama usados pelos adaptadores e pelo Gate L1."""

from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


def endpoint_ollama_e_loopback(base_url: str) -> bool:
    """Retorna ``True`` somente para um endpoint HTTP(S) em loopback."""
    partes = urlsplit(base_url)
    host = partes.hostname
    if partes.scheme not in {"http", "https"} or not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def raiz_api_ollama(base_url: str) -> str:
    """Converte a base OpenAI-compatible ``.../v1`` na raiz da API nativa."""
    partes = urlsplit(base_url)
    if partes.scheme not in {"http", "https"} or not partes.hostname:
        raise ValueError(f"OLLAMA_BASE_URL inválida: {base_url!r}")
    caminho = partes.path.rstrip("/")
    if caminho.endswith("/v1"):
        caminho = caminho[:-3]
    return urlunsplit((partes.scheme, partes.netloc, caminho, "", "")).rstrip("/")


def _obter_json(base_url: str, rota: str, timeout_s: float) -> dict:
    requisicao = Request(
        f"{raiz_api_ollama(base_url)}{rota}",
        headers={"Accept": "application/json"},
    )
    with urlopen(requisicao, timeout=min(timeout_s, 10.0)) as resposta:
        objeto = json.loads(resposta.read().decode("utf-8"))
    if not isinstance(objeto, dict):
        raise RuntimeError(f"Resposta Ollama inesperada em {rota}: {type(objeto).__name__}")
    return objeto


def obter_versao_ollama(base_url: str, timeout_s: float) -> str:
    """Obtém a versão real do daemon local para a evidência do gate."""
    versao = _obter_json(base_url, "/api/version", timeout_s).get("version")
    if not isinstance(versao, str) or not versao.strip():
        raise RuntimeError("Ollama não informou uma versão válida.")
    return versao.strip()


def resolver_identidade_modelo_ollama(
    base_url: str, modelo: str, timeout_s: float
) -> str:
    """Resolve uma tag mutável para ``tag@sha256:digest``.

    A identidade imutável é usada pela guarda RNF09 para impedir que um
    ``ollama pull`` troque silenciosamente os pesos sob a mesma tag.
    """
    modelos = _obter_json(base_url, "/api/tags", timeout_s).get("models")
    if not isinstance(modelos, list):
        raise RuntimeError("Ollama não retornou a lista de modelos instalada.")

    nomes_aceitos = {modelo}
    if ":" not in modelo:
        nomes_aceitos.add(f"{modelo}:latest")
    for item in modelos:
        if not isinstance(item, dict):
            continue
        nomes = {item.get("name"), item.get("model")}
        if nomes_aceitos.isdisjoint(nomes):
            continue
        digest = item.get("digest")
        if not isinstance(digest, str) or not digest.strip():
            raise RuntimeError(f"Ollama não informou o digest de {modelo!r}.")
        return f"{modelo}@sha256:{digest.strip()}"
    raise RuntimeError(f"Modelo Ollama não instalado: {modelo!r}.")
