"""Captura um screenshot atual da instância via API VMOS e salva em disco.

Use este script para gerar uma imagem de referência da qual você vai
recortar os templates do HUD (em vez de usar prints da tela do PC).

Uso:
    python tools/capture.py
    python tools/capture.py --pad APP64N6T7S3N8L6K
    python tools/capture.py --output captura.png
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from slayer_monitor.config import load_settings
from slayer_monitor.vmos_client import VmosApiError, VmosClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Captura screenshot da instância via API.")
    parser.add_argument(
        "--pad",
        help="padCode da instância. Default: primeiro de VMOS_PAD_CODES.",
    )
    parser.add_argument(
        "--output",
        help="Caminho do arquivo de saída. Default: screenshots/<padCode>_<timestamp>.png",
    )
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=1280)
    parser.add_argument("--quality", type=int, default=80)
    args = parser.parse_args()

    try:
        settings = load_settings()
    except RuntimeError as exc:
        print(f"[CONFIG] {exc}", file=sys.stderr)
        return 2

    pad_code = args.pad or (settings.pad_codes[0] if settings.pad_codes else None)
    if not pad_code:
        print("Nenhum padCode fornecido nem em VMOS_PAD_CODES.", file=sys.stderr)
        return 2

    output = args.output
    if not output:
        os.makedirs("screenshots", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"screenshots/{pad_code}_{ts}.png"

    client = VmosClient(
        access_key=settings.vmos_access_key,
        secret_key=settings.vmos_secret_key,
        api_host=settings.vmos_api_host,
        timeout=settings.request_timeout_seconds,
    )

    print(f"Solicitando screenshot de {pad_code} ({args.width}x{args.height}, q={args.quality}) ...")
    try:
        png = client.fetch_screenshot(
            pad_code, width=args.width, height=args.height, quality=args.quality
        )
    except VmosApiError as exc:
        print(f"❌  Erro da API: {exc}", file=sys.stderr)
        return 1

    if png is None:
        print("❌  API não retornou URL de screenshot.", file=sys.stderr)
        return 1

    with open(output, "wb") as f:
        f.write(png)
    size_kb = len(png) / 1024
    print(f"✅  Screenshot salvo: {output} ({size_kb:.1f} KB)")
    print(
        "\nAgora abra a imagem, recorte os elementos do HUD do jogo (ex: botão de\n"
        "ataque, barra de HP do boss, mini-mapa) e salve em templates/hud/."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
