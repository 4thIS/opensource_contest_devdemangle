"""탐지 결과를 표준형으로 되돌린다.

correct()는 오케스트레이션만 한다 — 무엇을 찾을지는 탐지 쪽 일이고, 여기서는
찾아온 것을 바꾸고 결과 좌표를 다시 센다.

탐지기는 `detect` 인자로 갈아끼울 수 있다. 기본값은 devdemangle.detect.detect다.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from devdemangle.detect import detect as _detect
from devdemangle.detect import resolve_overlaps
from devdemangle.glossary import Glossary
from devdemangle.types import Match, Span

# 용어집 기본 위치. tests/test_terms_yaml.py와 같은 기준(저장소 루트)을 쓴다.
DEFAULT_TERMS_PATH = Path(__file__).resolve().parent.parent / "data" / "terms.yaml"

Detector = Callable[[str, Glossary], list[Match]]


@dataclass
class CorrectionResult:
    text: str
    spans: list[Span]


@lru_cache(maxsize=1)
def default_glossary() -> Glossary:
    return Glossary.from_yaml(DEFAULT_TERMS_PATH)


def correct(
    text: str,
    glossary: Glossary | None = None,
    *,
    detect: Detector = _detect,
) -> CorrectionResult:
    """탐지된 별칭을 표준형으로 바꾸고, 바뀐 위치를 결과 텍스트 좌표로 돌려준다.

    Match는 입력 좌표, Span은 결과 좌표다. 앞 용어가 길어지면 뒤가 밀리므로
    여기서 다시 센다.

    glossary 생략 시 기본 용어집(data/terms.yaml)을 쓴다.
    """
    if not text:
        return CorrectionResult(text="", spans=[])

    resolved_glossary = glossary if glossary is not None else default_glossary()
    # detect()는 canonical 자신도 매치로 내보낸다(용어 위치 파악이 목적이라).
    # matched == term이면 이미 표준형이라 바꿀 게 없다 (C-COR-02).
    candidates = [m for m in detect(text, resolved_glossary) if m.matched != m.term]
    accepted = resolve_overlaps(candidates)
    if not accepted:
        return CorrectionResult(text=text, spans=[])

    parts: list[str] = []
    spans: list[Span] = []
    cursor = 0   # 입력 텍스트에서 아직 안 옮긴 위치
    written = 0  # 결과 텍스트에 지금까지 쓴 길이

    for match in accepted:
        parts.append(text[cursor:match.start])
        written += match.start - cursor

        parts.append(match.term)
        spans.append(
            Span(
                start=written,
                end=written + len(match.term),
                term=match.term,
                matched=match.matched,
                method=match.method,
                confidence=match.confidence,
            )
        )
        written += len(match.term)
        cursor = match.end

    parts.append(text[cursor:])
    return CorrectionResult(text="".join(parts), spans=spans)
