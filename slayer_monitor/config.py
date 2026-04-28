"""Carregador de configuração.

Lê todos os parâmetros de variáveis de ambiente (ou de um arquivo
`.env` na raiz do projeto, via python-dotenv). Veja `.env.example`
para a lista completa e o significado de cada variável.

Suporta múltiplos provedores de Android-on-cloud via `CLOUD_PROVIDER`:
- `vmos` (default): VMOS Cloud — host api.vmoscloud.com, paths /vcpcloud/api/padApi
- `vsphone`:        VSPhone     — host api.vsphone.com,    paths /vsphone/api/padApi

As credenciais e padCodes são lidos das variáveis com prefixo do provedor
(`VMOS_ACCESS_KEY` quando provider=vmos, `VSPHONE_ACCESS_KEY` quando
provider=vsphone, etc.). O algoritmo de assinatura HMAC-SHA256 e os
schemas de resposta são idênticos entre os dois — apenas host e prefixo
de path mudam.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()


# Perfis dos provedores suportados. Para adicionar UGPhone ou outro,
# basta acrescentar uma entrada aqui (host + path_prefix) e configurar
# as variáveis de ambiente <PROVIDER>_ACCESS_KEY etc.
PROVIDER_PROFILES: Dict[str, Dict[str, str]] = {
    "vmos": {
        "default_host": "api.vmoscloud.com",
        "path_prefix": "/vcpcloud/api/padApi",
    },
    "vsphone": {
        "default_host": "api.vsphone.com",
        "path_prefix": "/vsphone/api/padApi",
    },
}


def _required(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(
            f"Variável de ambiente obrigatória ausente: {key}. "
            f"Defina-a no arquivo .env (veja .env.example)."
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _int(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Valor inválido para {key}: {raw!r}") from exc


def _list(key: str) -> List[str]:
    raw = os.getenv(key, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # Cloud provider
    cloud_provider: str           # "vmos", "vsphone", ...
    access_key: str
    secret_key: str
    api_host: str                 # ex: api.vmoscloud.com / api.vsphone.com
    api_path_prefix: str          # ex: /vcpcloud/api/padApi / /vsphone/api/padApi

    pad_codes: List[str]
    game_package: str

    # Telegram
    telegram_token: str
    telegram_chat_id: str

    # Loop
    check_interval_seconds: int
    request_timeout_seconds: int

    # Visual fallback (screenshot via API)
    enable_visual_fallback: bool
    template_dir: Path
    match_threshold: float
    min_template_matches: int

    # Frozen-frame detection
    enable_frozen_check: bool
    frozen_check_delay_seconds: int
    frozen_diff_threshold: float

    # Behaviour
    alert_cooldown_seconds: int


def load_settings() -> Settings:
    provider = _optional("CLOUD_PROVIDER", "vmos").lower()
    if provider not in PROVIDER_PROFILES:
        supported = ", ".join(sorted(PROVIDER_PROFILES))
        raise RuntimeError(
            f"CLOUD_PROVIDER inválido: {provider!r}. Suportados: {supported}."
        )
    profile = PROVIDER_PROFILES[provider]
    prefix = provider.upper()  # ex: "VMOS", "VSPHONE"

    pad_codes = _list(f"{prefix}_PAD_CODES")
    if not pad_codes:
        raise RuntimeError(
            f"{prefix}_PAD_CODES está vazio. Informe ao menos um código de instância "
            f"separado por vírgulas (ex.: {prefix}_PAD_CODES=APP64N6T7S3N8L6K)."
        )

    template_dir = Path(_optional("VISUAL_TEMPLATE_DIR", "templates/hud"))
    try:
        threshold = float(_optional("VISUAL_MATCH_THRESHOLD", "0.80"))
    except ValueError as exc:
        raise RuntimeError("VISUAL_MATCH_THRESHOLD deve ser numérico") from exc

    return Settings(
        cloud_provider=provider,
        access_key=_required(f"{prefix}_ACCESS_KEY"),
        secret_key=_required(f"{prefix}_SECRET_KEY"),
        api_host=_optional(f"{prefix}_API_HOST", profile["default_host"]),
        api_path_prefix=profile["path_prefix"],
        pad_codes=pad_codes,
        game_package=_optional("GAME_PACKAGE", "com.gear2.growslayer"),
        telegram_token=_required("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_required("TELEGRAM_CHAT_ID"),
        check_interval_seconds=_int("CHECK_INTERVAL_SECONDS", 1200),
        request_timeout_seconds=_int("REQUEST_TIMEOUT_SECONDS", 20),
        enable_visual_fallback=_bool("ENABLE_VISUAL_FALLBACK", False),
        template_dir=template_dir,
        match_threshold=threshold,
        min_template_matches=_int("VISUAL_MIN_MATCHES", 2),
        enable_frozen_check=_bool("ENABLE_FROZEN_CHECK", False),
        frozen_check_delay_seconds=_int("FROZEN_CHECK_DELAY_SECONDS", 6),
        frozen_diff_threshold=float(_optional("FROZEN_DIFF_THRESHOLD", "0.005")),
        alert_cooldown_seconds=_int("ALERT_COOLDOWN_SECONDS", 1800),
    )
