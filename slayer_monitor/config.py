"""Carregador de configuração.

Lê todos os parâmetros de variáveis de ambiente (ou de um arquivo
`.env` na raiz do projeto, via python-dotenv). Veja `.env.example`
para a lista completa e o significado de cada variável.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()


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
    # VMOS API
    vmos_access_key: str
    vmos_secret_key: str
    vmos_api_host: str
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
    pad_codes = _list("VMOS_PAD_CODES")
    if not pad_codes:
        raise RuntimeError(
            "VMOS_PAD_CODES está vazio. Informe ao menos um código de instância "
            "separado por vírgulas (ex.: VMOS_PAD_CODES=AC21020010391)."
        )

    template_dir = Path(_optional("VISUAL_TEMPLATE_DIR", "templates/hud"))
    try:
        threshold = float(_optional("VISUAL_MATCH_THRESHOLD", "0.80"))
    except ValueError as exc:
        raise RuntimeError("VISUAL_MATCH_THRESHOLD deve ser numérico") from exc

    return Settings(
        vmos_access_key=_required("VMOS_ACCESS_KEY"),
        vmos_secret_key=_required("VMOS_SECRET_KEY"),
        vmos_api_host=_optional("VMOS_API_HOST", "api.vmoscloud.com"),
        pad_codes=pad_codes,
        game_package=_optional("GAME_PACKAGE", "com.superplanet.slayerlegend"),
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
