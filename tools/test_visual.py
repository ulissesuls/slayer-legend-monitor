"""Testa o detector visual contra um screenshot atual da API.

Imprime o score de cada template (todas as escalas) para ajudar a
calibrar VISUAL_MATCH_THRESHOLD e VISUAL_MIN_MATCHES no .env.

Uso:
    python tools/test_visual.py             # captura screenshot novo via API
    python tools/test_visual.py --image foo.png  # usa imagem local
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from slayer_monitor.config import load_settings
from slayer_monitor.vmos_client import VmosApiError, VmosClient
from slayer_monitor.visual_detector import detect_hud, load_templates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Testa template matching contra um screenshot."
    )
    parser.add_argument("--image", help="Caminho de imagem local (pula API).")
    parser.add_argument("--pad", help="padCode (default: VMOS_PAD_CODES[0])")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--min-matches", type=int, default=None)
    args = parser.parse_args()

    settings = load_settings()
    threshold = args.threshold if args.threshold is not None else settings.match_threshold
    min_matches = (
        args.min_matches if args.min_matches is not None else settings.min_template_matches
    )

    if args.image:
        with open(args.image, "rb") as f:
            png = f.read()
        print(f"📷  Usando imagem: {args.image}")
    else:
        pad_code = args.pad or settings.pad_codes[0]
        client = VmosClient(
            access_key=settings.access_key,
            secret_key=settings.secret_key,
            api_host=settings.api_host,
            path_prefix=settings.api_path_prefix,
            timeout=settings.request_timeout_seconds,
        )
        print(f"📷  Capturando screenshot via API ({pad_code}) ...")
        try:
            png = client.fetch_screenshot(pad_code)
        except VmosApiError as exc:
            print(f"❌  {exc}", file=sys.stderr)
            return 1
        if png is None:
            print("❌  API não retornou screenshot.", file=sys.stderr)
            return 1
        # Salva pra inspeção
        os.makedirs("screenshots", exist_ok=True)
        debug_path = "screenshots/_test_visual.png"
        with open(debug_path, "wb") as f:
            f.write(png)
        print(f"   Imagem salva em {debug_path}")

    templates = load_templates(settings.template_dir)
    if not templates:
        print(f"❌  Nenhum template em {settings.template_dir}", file=sys.stderr)
        return 1

    detection = detect_hud(
        png, templates, threshold=threshold, min_matches=min_matches
    )

    print(f"\n=== Detecção (threshold={threshold:.2f}, min_matches={min_matches}) ===\n")
    for s in detection.scores:
        flag = "✅" if s.matched else "❌"
        bar = "█" * int(s.score * 30)
        print(f"  {flag} {s.score:.3f} (escala {s.scale:.2f}) {bar:<30} {s.name}")

    print(f"\n  Total: {detection.matches}/{detection.required} matches.")
    if detection.matched:
        print("  🎯  HUD DETECTADO — jogo está em foreground.")
    else:
        print("  ⚠   HUD NÃO detectado — jogo provavelmente fechado/fora da tela.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
