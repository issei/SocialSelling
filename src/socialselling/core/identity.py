"""Identidade canônica de entidade — única fonte de verdade do entity_id.

Consumido pelo corpus (ADR-006) e pelas CLIs publish/pull-feedback (ADR-010).
"""

from __future__ import annotations

import hashlib
import unicodedata
from urllib.parse import urlsplit


def canonical_entity_id(
    website: str | None,
    name: str,
    city: str | None,
) -> str:
    """Identidade canônica do lead — estável entre runs e entre provedores.

    1) Se há host válido no website: domínio normalizado é o entity_id.
       Normalização: urlsplit (aceita com/sem scheme), casefold, remove
       "www." inicial, remove porta, descarta path/query/fragment,
       remove "." final.

    2) Fallback determinístico (sem site): SHA-256 de
       f"{nome_normalizado}|{cidade_normalizada}" → "sha256:<hex64>".
       Normalização de texto: NFKD → ASCII (remove acentos), casefold,
       espaços colapsados para um, strip. Cidade ausente = "".
    """
    host = _extract_host(website)
    if host:
        return host
    return _fallback_id(name, city)


def _extract_host(website: str | None) -> str:
    """Extrai e normaliza o host do website. Retorna "" se inválido/ausente."""
    if not website:
        return ""
    raw = website.strip()
    if not raw:
        return ""
    # urlsplit precisa de scheme para separar host de path
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname or ""
    except Exception:  # pragma: no cover
        return ""
    if not host:
        return ""
    # casefold, remover "www." inicial, remover "." final
    host = host.casefold()
    if host.startswith("www."):
        host = host[4:]
    host = host.rstrip(".")
    # descarta se sobrou vazio (ex.: URL malformada)
    return host if "." in host else ""


def _normalize_text(text: str) -> str:
    """NFKD → ASCII (remove acentos), casefold, espaços colapsados, strip."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_bytes = nfkd.encode("ascii", errors="ignore")
    normalized = ascii_bytes.decode("ascii").casefold()
    return " ".join(normalized.split())


def _fallback_id(name: str, city: str | None) -> str:
    """SHA-256 de '{nome_normalizado}|{cidade_normalizada}'."""
    norm_name = _normalize_text(name)
    norm_city = _normalize_text(city) if city else ""
    raw = f"{norm_name}|{norm_city}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
