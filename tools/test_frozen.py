"""Mede o diff médio entre dois screenshots consecutivos.

Use para calibrar FROZEN_DIFF_THRESHOLD no .env. Rode com o jogo
ativamente em combate para ver qual diff típico aparece em jogabilidade
real, depois rode no momento de "frame congelado" pra ver o diff
quando travado.

Uso:
    python tools/test_frozen.py             # 1 medição com delay padrão
    python tools/test_frozen.py --delay 10  # delay maior
    python tools/test_frozen.py --runs 5    # várias medições seguidas
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from slayer_monitor.config import load_settings
from slayer_monitor.vmos_client import VmosClient
from slayer_monitor.visual_detector import detect_frozen


def main() -> int:
    parser = argparse.ArgumentParser(description="Mede diff entre 2 screenshots.")
    parser.add_argument("--pad", help="padCode (default: VMOS_PAD_CODES[0])")
    parser.add_argument("--delay", type=float, default=6.0, help="Segundos entre capturas.")
    parser.add_argument("--runs", type=int, default=1, help="Número de medições.")
    args = parser.parse_args()

    settings = load_settings()
    pad_code = args.pad or settings.pad_codes[0]
    client = VmosClient(
        access_key=settings.access_key,
        secret_key=settings.secret_key,
        api_host=settings.api_host,
        path_prefix=settings.api_path_prefix,
        timeout=settings.request_timeout_seconds,
    )

    print(f"Instância: {pad_code}, delay={args.delay}s, runs={args.runs}\n")
    diffs = []
    for i in range(1, args.runs + 1):
        print(f"  [{i}/{args.runs}] Capturando A ...", end=" ", flush=True)
        a = client.fetch_screenshot(pad_code)
        if a is None:
            print("falhou")
            continue
        print(f"OK ({len(a)} bytes). Aguardando {args.delay}s ...", end=" ", flush=True)
        time.sleep(args.delay)
        print("Capturando B ...", end=" ", flush=True)
        b = client.fetch_screenshot(pad_code)
        if b is None:
            print("falhou")
            continue
        result = detect_frozen(a, b, threshold=settings.frozen_diff_threshold)
        diffs.append(result.mean_diff)
        flag = "🧊 FROZEN" if result.frozen else "🎬 ATIVO"
        print(f"diff={result.mean_diff:.5f}  {flag}")

    if diffs:
        avg = sum(diffs) / len(diffs)
        mn = min(diffs)
        mx = max(diffs)
        print(f"\nResumo: min={mn:.5f}  avg={avg:.5f}  max={mx:.5f}")
        print(
            f"Threshold atual: {settings.frozen_diff_threshold:.5f}\n\n"
            f"Sugestão: defina FROZEN_DIFF_THRESHOLD um pouco abaixo do mínimo\n"
            f"em jogabilidade ativa (ex: {min(mn / 2, 0.01):.5f})."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
