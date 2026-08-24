"""탐지 결과를 표준형으로 되돌린다.

correct()는 두 탐지를 순서대로 돌리고, 찾아온 것을 바꾸고 결과 좌표를 다시 센다.

**등록 탐지가 먼저, 소리 탐지가 나중이다.** 소리 탐지는 이미 잡힌 자리를 건너뛰므로
순서가 뒤바뀌면 근사 매치가 정확 매치를 밀어낸다.

임계값을 여기서 받는 이유는, 용어집이 커지면 안전 구간이 움직이기 때문이다.
값을 코드에 박아두면 재측정한 뒤 라이브러리를 고쳐야 한다.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from devdemangle.detect import detect, resolve_overlaps
from devdemangle.fuzzy import DEFAULT_THRESHOLD, fuzzy_detect
from devdemangle.glossary import Glossary
from devdemangle.types import Span

# 용어집 기본 위치. tests/test_terms_yaml.py와 같은 기준(저장소 루트)을 쓴다.
DEFAULT_TERMS_PATH = Path(__file__).resolve().parent.parent / "data" / "terms.yaml"


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
    threshold: float = DEFAULT_THRESHOLD,
) -> CorrectionResult:
    """탐지된 별칭을 표준형으로 바꾸고, 바뀐 위치를 결과 텍스트 좌표로 돌려준다.

    Match는 입력 좌표, Span은 결과 좌표다. 앞 용어가 길어지면 뒤가 밀리므로
    여기서 다시 센다.

    Args:
        glossary: 생략하면 기본 용어집(data/terms.yaml)을 쓴다.
        threshold: 소리 유사도 하한. 이 값 미만이면 보정하지 않는다.
    """
    if not text:
        return CorrectionResult(text="", spans=[])

    resolved_glossary = glossary if glossary is not None else default_glossary()
    # 거르지 않고 전부 겹침 해소에 넣는다. 표준형 매치를 미리 빼면 그 자리를
    # 다른 용어의 짧은 별칭이 무경쟁으로 가져간다 — "REST API"를 먼저 빼면
    # 다른 용어의 별칭 "API"가 이겨 엉뚱한 치환이 일어난다.
    found = detect(text, resolved_glossary)
    found += fuzzy_detect(text, resolved_glossary, found, threshold=threshold)
    accepted = resolve_overlaps(found)
    if not accepted:
        return CorrectionResult(text=text, spans=[])

    parts: list[str] = []
    spans: list[Span] = []
    cursor = 0   # 입력 텍스트에서 아직 안 옮긴 위치
    written = 0  # 결과 텍스트에 지금까지 쓴 길이

    for match in accepted:
        parts.append(text[cursor:match.start])
        written += match.start - cursor

        # 이미 표준형이거나 정규식으로 찾은 식별자는 term == matched라 바뀌는 게
        # 없다. 그래도 **결과에는 싣는다** — 하이라이트와 번역 보호가 이 목록을
        # 입력으로 쓴다. "바꿀 게 없다"와 "지킬 게 없다"는 다르다.
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
