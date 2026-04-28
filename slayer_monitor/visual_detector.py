"""HUD detection via OpenCV multi-scale template matching.

Estratégia anti-falso-positivo:
- Escalas testadas restritas a ~0.85x–1.15x (templates extraídos via
  `tools/capture.py` já estão na resolução da runtime).
- Templates muito reduzidos (< 24px de lado) são rejeitados — em escalas
  baixas pequenos ícones casam com ruído de fundo.
- Exige N matches mínimos entre os templates carregados, em vez de
  considerar 1 match suficiente.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np


log = logging.getLogger(__name__)

_VALID_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
_SCALES = (0.85, 0.92, 1.0, 1.08, 1.15)
_MIN_TEMPLATE_PX = 24


@dataclass
class TemplateScore:
    name: str
    score: float
    scale: float
    matched: bool


@dataclass
class DetectionResult:
    matched: bool
    matches: int
    required: int
    scores: List[TemplateScore]
    summary: str


@dataclass
class FrozenResult:
    frozen: bool
    mean_diff: float
    threshold: float


def detect_frozen(
    img_bytes_a: bytes,
    img_bytes_b: bytes,
    threshold: float = 0.005,
) -> FrozenResult:
    """Compara duas capturas. Frozen quando diff médio normalizado é mínimo.

    Slayer Legend em combate tem animação constante (efeitos, números de
    dano, mini-mapa, contador de andar). Dois screenshots a 5+ segundos
    de distância terão diff ≥ 0.01 em jogabilidade ativa. Diff < 0.005
    indica que o stream travou.
    """
    arr_a = cv2.imdecode(np.frombuffer(img_bytes_a, np.uint8), cv2.IMREAD_GRAYSCALE)
    arr_b = cv2.imdecode(np.frombuffer(img_bytes_b, np.uint8), cv2.IMREAD_GRAYSCALE)
    if arr_a is None or arr_b is None or arr_a.shape != arr_b.shape:
        return FrozenResult(frozen=False, mean_diff=1.0, threshold=threshold)
    diff = cv2.absdiff(arr_a, arr_b)
    mean_diff = float(diff.mean()) / 255.0
    return FrozenResult(
        frozen=mean_diff < threshold, mean_diff=mean_diff, threshold=threshold
    )


def load_templates(template_dir: Path) -> List[Tuple[str, np.ndarray]]:
    if not template_dir.exists():
        log.warning("Diretório de templates não encontrado: %s", template_dir)
        return []
    templates: List[Tuple[str, np.ndarray]] = []
    for path in sorted(template_dir.iterdir()):
        if path.suffix.lower() not in _VALID_EXT:
            continue
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            log.warning("Template inválido (ignorado): %s", path)
            continue
        if img.shape[0] < _MIN_TEMPLATE_PX or img.shape[1] < _MIN_TEMPLATE_PX:
            log.warning(
                "Template %s muito pequeno (%dx%d) — pode gerar falsos positivos.",
                path.name, img.shape[1], img.shape[0],
            )
        templates.append((path.name, img))
    if templates:
        log.info("Templates carregados: %s", [name for name, _ in templates])
    return templates


def _best_score_for_template(
    frame: np.ndarray, template: np.ndarray
) -> Tuple[float, float]:
    """Returns (best_score, scale_at_best)."""
    fh, fw = frame.shape[:2]
    best_score = 0.0
    best_scale = 1.0
    for scale in _SCALES:
        th = int(template.shape[0] * scale)
        tw = int(template.shape[1] * scale)
        # Reject scaled templates that are too small or larger than frame.
        if th < _MIN_TEMPLATE_PX or tw < _MIN_TEMPLATE_PX:
            continue
        if th > fh or tw > fw:
            continue
        scaled = (
            template
            if scale == 1.0
            else cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA)
        )
        result = cv2.matchTemplate(frame, scaled, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        if max_val > best_score:
            best_score = float(max_val)
            best_scale = scale
    return best_score, best_scale


def detect_hud(
    screenshot_bytes: bytes,
    templates: List[Tuple[str, np.ndarray]],
    threshold: float = 0.80,
    min_matches: int = 2,
) -> DetectionResult:
    if not templates:
        return DetectionResult(False, 0, min_matches, [], "Sem templates carregados.")

    arr = np.frombuffer(screenshot_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if frame is None:
        return DetectionResult(
            False, 0, min_matches, [], "Falha ao decodificar screenshot."
        )

    scores: List[TemplateScore] = []
    matches = 0
    for name, template in templates:
        score, scale = _best_score_for_template(frame, template)
        ok = score >= threshold
        scores.append(TemplateScore(name=name, score=score, scale=scale, matched=ok))
        if ok:
            matches += 1

    # Adjust required count if we have fewer templates than min_matches.
    required = min(min_matches, len(templates))
    matched = matches >= required

    # Rank scores for the log summary.
    scores.sort(key=lambda s: s.score, reverse=True)
    top = scores[:3]
    top_str = ", ".join(f"{s.name}@{s.scale:.2f}={s.score:.2f}" for s in top)
    summary = (
        f"{matches}/{required} matches (≥{threshold:.2f}). "
        f"Top: {top_str}."
    )
    return DetectionResult(matched, matches, required, scores, summary)
