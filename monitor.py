"""Slayer Legend uptime monitor for VMOS Cloud.

Loop contínuo (recomendado em produção 24/7):
    python monitor.py

Verificação única (útil para Task Scheduler / cron):
    python monitor.py --once

A cada ciclo executa, em ordem:
  1. API VMOS — confirma que a instância está online (padStatus=10) e
     que o pacote do jogo está instalado (listInstalledApp).
  2. Fallback visual (se ENABLE_VISUAL_FALLBACK=true) — pede um
     screenshot da instância pela própria API (getLongGenerateUrl) e
     faz template matching multi-escala contra os recortes do HUD.
  3. Frozen check (se ENABLE_FROZEN_CHECK=true e HUD detectado) — tira
     uma 2ª captura após FROZEN_CHECK_DELAY_SECONDS e compara pixel-a-
     pixel para detectar stream congelado.

Falha em qualquer etapa dispara um alerta no Telegram (com cooldown
de ALERT_COOLDOWN_SECONDS para não inundar o chat).
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

from slayer_monitor.config import Settings, load_settings
from slayer_monitor.telegram_notifier import TelegramNotifier
from slayer_monitor.vmos_client import PadStatus, VmosApiError, VmosClient


log = logging.getLogger("slayer_monitor")


@dataclass
class CheckResult:
    pad_code: str
    healthy: bool
    summary: str
    dedupe_key: str


_PAD_STATUS_LABELS = {
    10: "running",
    11: "restarting",
    12: "resetting",
    13: "upgrading",
    14: "abnormal",
    15: "not ready",
}


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _check_pad_via_api(
    client: VmosClient,
    settings: Settings,
    pad_code: str,
) -> CheckResult:
    try:
        details = client.pad_details([pad_code])
    except VmosApiError as exc:
        return CheckResult(
            pad_code,
            healthy=False,
            summary=f"Falha ao consultar API VMOS: {exc}",
            dedupe_key=f"{pad_code}:api_error",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            pad_code,
            healthy=False,
            summary=f"Erro inesperado consultando VMOS: {exc}",
            dedupe_key=f"{pad_code}:api_unexpected",
        )

    pad: Optional[PadStatus] = next((p for p in details if p.pad_code == pad_code), None)
    if pad is None:
        return CheckResult(
            pad_code,
            healthy=False,
            summary="Instância não retornada pela API (verifique padCode).",
            dedupe_key=f"{pad_code}:not_found",
        )

    if not pad.online:
        return CheckResult(
            pad_code,
            healthy=False,
            summary="Instância OFFLINE (online=0).",
            dedupe_key=f"{pad_code}:offline",
        )

    if pad.pad_status != 10:
        label = _PAD_STATUS_LABELS.get(pad.pad_status, f"status={pad.pad_status}")
        return CheckResult(
            pad_code,
            healthy=False,
            summary=f"Instância em estado anômalo: {label} (padStatus={pad.pad_status}).",
            dedupe_key=f"{pad_code}:padstatus_{pad.pad_status}",
        )

    try:
        if not client.has_package_installed(pad_code, settings.game_package):
            return CheckResult(
                pad_code,
                healthy=False,
                summary=f"Pacote {settings.game_package} NÃO está instalado na instância.",
                dedupe_key=f"{pad_code}:pkg_missing",
            )
    except VmosApiError as exc:
        log.warning("Não foi possível listar apps de %s: %s", pad_code, exc)
        # Não disparar alerta só por isso — instância está online.

    return CheckResult(
        pad_code,
        healthy=True,
        summary="API: instância online, padStatus=running, pacote instalado.",
        dedupe_key=f"{pad_code}:ok",
    )


def _check_pad_visual(
    settings: Settings,
    client: VmosClient,
    pad_code: str,
) -> CheckResult:
    """Optional fallback: confirm the game HUD is on screen via API screenshot."""
    from slayer_monitor.visual_detector import detect_frozen, detect_hud, load_templates

    templates = load_templates(settings.template_dir)
    if not templates:
        return CheckResult(
            pad_code,
            healthy=True,
            summary=(
                f"Visual fallback ignorado (sem templates em {settings.template_dir})."
            ),
            dedupe_key=f"{pad_code}:visual_no_templates",
        )

    try:
        png_a = client.fetch_screenshot(pad_code)
    except VmosApiError as exc:
        return CheckResult(
            pad_code,
            healthy=False,
            summary=f"Falha ao obter screenshot via API: {exc}",
            dedupe_key=f"{pad_code}:visual_api_error",
        )

    if png_a is None:
        return CheckResult(
            pad_code,
            healthy=False,
            summary="API não retornou URL de screenshot.",
            dedupe_key=f"{pad_code}:visual_no_url",
        )

    detection = detect_hud(
        png_a,
        templates,
        threshold=settings.match_threshold,
        min_matches=settings.min_template_matches,
    )
    if not detection.matched:
        return CheckResult(
            pad_code,
            healthy=False,
            summary=(
                f"HUD do Slayer Legend não detectado. {detection.summary} "
                f"Jogo pode ter fechado."
            ),
            dedupe_key=f"{pad_code}:visual_miss",
        )

    # HUD presente — opcionalmente confirma que o stream não está congelado.
    if settings.enable_frozen_check:
        time.sleep(settings.frozen_check_delay_seconds)
        try:
            png_b = client.fetch_screenshot(pad_code)
        except VmosApiError as exc:
            log.warning("Falha ao obter 2º screenshot para frozen check: %s", exc)
            png_b = None

        if png_b is not None:
            frozen = detect_frozen(
                png_a, png_b, threshold=settings.frozen_diff_threshold
            )
            log.info(
                "[Frozen] %s -> diff=%.5f (threshold=%.5f, frozen=%s)",
                pad_code, frozen.mean_diff, frozen.threshold, frozen.frozen,
            )
            if frozen.frozen:
                return CheckResult(
                    pad_code,
                    healthy=False,
                    summary=(
                        f"Frame CONGELADO: HUD presente mas sem animação "
                        f"(diff={frozen.mean_diff:.5f} < {frozen.threshold:.5f}). "
                        f"Jogo provavelmente travou — reinicie pelo painel."
                    ),
                    dedupe_key=f"{pad_code}:visual_frozen",
                )

    return CheckResult(
        pad_code,
        healthy=True,
        summary=f"HUD detectado — {detection.summary}",
        dedupe_key=f"{pad_code}:visual_ok",
    )


def _format_alert(pad_code: str, results: List[CheckResult]) -> str:
    lines = [f"<b>⚠ Slayer Legend — alerta</b>", f"Instância: <code>{pad_code}</code>"]
    for result in results:
        flag = "✅" if result.healthy else "❌"
        lines.append(f"{flag} {result.summary}")
    return "\n".join(lines)


def run_once(
    settings: Settings,
    client: VmosClient,
    notifier: TelegramNotifier,
) -> None:
    for pad_code in settings.pad_codes:
        log.info("Verificando instância %s ...", pad_code)
        api_result = _check_pad_via_api(client, settings, pad_code)
        log.info("[API] %s -> %s", pad_code, api_result.summary)

        results = [api_result]

        if not api_result.healthy:
            notifier.send(
                _format_alert(pad_code, results),
                dedupe_key=api_result.dedupe_key,
            )
            continue

        if settings.enable_visual_fallback:
            visual_result = _check_pad_visual(settings, client, pad_code)
            log.info("[Visual] %s -> %s", pad_code, visual_result.summary)
            results.append(visual_result)
            if not visual_result.healthy:
                notifier.send(
                    _format_alert(pad_code, results),
                    dedupe_key=visual_result.dedupe_key,
                )


def run_loop(
    settings: Settings,
    client: VmosClient,
    notifier: TelegramNotifier,
) -> None:
    stop = {"flag": False}

    def _handle_signal(signum, _frame):  # noqa: ANN001
        log.info("Sinal %s recebido — encerrando após o ciclo atual.", signum)
        stop["flag"] = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except (ValueError, OSError):
            pass  # Não disponível em alguns ambientes (ex.: thread no Windows).

    interval_min = settings.check_interval_seconds // 60
    startup_msg = (
        f"✅ <b>Monitor iniciado</b>\n"
        f"Instância: <code>{', '.join(settings.pad_codes)}</code>\n"
        f"Pacote: <code>{settings.game_package}</code>\n"
        f"Intervalo: {interval_min} min"
    )
    log.info(
        "Monitor iniciado. Intervalo=%ss, instâncias=%s, pacote=%s",
        settings.check_interval_seconds,
        settings.pad_codes,
        settings.game_package,
    )
    notifier.send(startup_msg, dedupe_key="monitor_startup")
    while not stop["flag"]:
        try:
            run_once(settings, client, notifier)
        except Exception as exc:  # noqa: BLE001 — não deixar o loop morrer.
            log.exception("Erro inesperado no ciclo de verificação: %s", exc)
            notifier.send(
                f"⚠ Monitor com erro inesperado: {exc}",
                dedupe_key="monitor_unexpected",
            )

        # Sleep com checagem do flag a cada 1s para encerrar rapidamente.
        for _ in range(settings.check_interval_seconds):
            if stop["flag"]:
                break
            time.sleep(1)


def main(argv: Optional[List[str]] = None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(description="Monitor Slayer Legend / VMOS Cloud.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa uma única verificação e sai (útil para cron).",
    )
    args = parser.parse_args(argv)

    try:
        settings = load_settings()
    except RuntimeError as exc:
        print(f"[CONFIG] {exc}", file=sys.stderr)
        return 2

    client = VmosClient(
        access_key=settings.vmos_access_key,
        secret_key=settings.vmos_secret_key,
        api_host=settings.vmos_api_host,
        timeout=settings.request_timeout_seconds,
    )
    notifier = TelegramNotifier(
        token=settings.telegram_token,
        chat_id=settings.telegram_chat_id,
        cooldown_seconds=settings.alert_cooldown_seconds,
    )

    if args.once:
        run_once(settings, client, notifier)
    else:
        run_loop(settings, client, notifier)
    return 0


if __name__ == "__main__":
    sys.exit(main())
