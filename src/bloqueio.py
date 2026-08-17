"""Bloqueio de processo para operações longas com promoção/publicação."""

from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

try:  # POSIX/Linux (ambiente de execução e deploy)
    import fcntl
except ImportError:  # pragma: no cover - exercido apenas no Windows
    fcntl = None


def _rejeitar_componentes_symlink(caminho: Path, recurso: str) -> None:
    """Rejeita componentes simbólicos sem resolver o alvo silenciosamente."""
    absoluto = caminho.absolute()
    atual = Path(absoluto.anchor)
    for parte in absoluto.parts[1:]:
        atual /= parte
        try:
            modo = atual.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RuntimeError(
                f"Caminho de lock inseguro para {recurso}."
            ) from exc
        if stat.S_ISLNK(modo):
            raise RuntimeError(f"Caminho de lock inseguro para {recurso}.")


def _abrir_arquivo_lock(caminho: Path, recurso: str) -> TextIO:
    """Abre um lock regular sem seguir symlink nem aceitar hardlink/FIFO."""
    _rejeitar_componentes_symlink(caminho.parent, recurso)
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Não foi possível preparar o lock de {recurso}.") from exc
    _rejeitar_componentes_symlink(caminho.parent, recurso)

    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descritor: int | None = None
    try:
        descritor = os.open(caminho, flags, 0o600)
        estado = os.fstat(descritor)
        if not stat.S_ISREG(estado.st_mode) or estado.st_nlink != 1:
            raise RuntimeError(f"Caminho de lock inseguro para {recurso}.")
        if hasattr(os, "fchmod"):
            os.fchmod(descritor, 0o600)
        arquivo = os.fdopen(descritor, "r+", encoding="utf-8")
        descritor = None
        return arquivo
    except RuntimeError:
        raise
    except OSError as exc:
        raise RuntimeError(f"Caminho de lock inseguro para {recurso}.") from exc
    finally:
        if descritor is not None:
            os.close(descritor)


@contextmanager
def bloqueio_exclusivo(caminho: Path, recurso: str):
    """Falha cedo se outro processo já estiver mutando o mesmo recurso.

    O arquivo permanece como inode estável entre execuções; o lock do kernel é
    liberado automaticamente até em encerramento abrupto do processo.
    """
    caminho = Path(caminho)
    arquivo = _abrir_arquivo_lock(caminho, recurso)
    adquirido = False
    try:
        arquivo.seek(0)
        if not arquivo.read(1):
            arquivo.seek(0)
            arquivo.write(" ")
            arquivo.flush()
        arquivo.seek(0)
        try:
            if fcntl is not None:
                fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:  # pragma: no cover - fallback Windows
                import msvcrt

                msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            adquirido = True
        except (BlockingIOError, OSError) as exc:
            raise RuntimeError(
                f"Outra execução já está processando {recurso}; aguarde-a ou "
                "encerre-a antes de tentar novamente."
            ) from exc
        arquivo.seek(0)
        arquivo.truncate()
        arquivo.write(f"pid={os.getpid()}\n")
        arquivo.flush()
        os.fsync(arquivo.fileno())
        yield
    finally:
        try:
            if adquirido:
                arquivo.seek(0)
                if fcntl is not None:
                    fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
                else:  # pragma: no cover - fallback Windows
                    import msvcrt

                    msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            arquivo.close()


@contextmanager
def bloqueio_compartilhado(caminho: Path, recurso: str):
    """Mantém um snapshot legível sem impedir outros leitores concorrentes."""
    caminho = Path(caminho)
    arquivo = _abrir_arquivo_lock(caminho, recurso)
    adquirido = False
    try:
        try:
            if fcntl is not None:
                fcntl.flock(arquivo.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            else:  # pragma: no cover - Windows não oferece flock compartilhado
                import msvcrt

                msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBRLCK, 1)
            adquirido = True
        except (BlockingIOError, OSError) as exc:
            raise RuntimeError(
                f"{recurso} está sendo reconstruído; tente novamente após a "
                "conclusão da operação."
            ) from exc
        yield
    finally:
        try:
            if adquirido:
                if fcntl is not None:
                    fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
                else:  # pragma: no cover
                    import msvcrt

                    msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            arquivo.close()
