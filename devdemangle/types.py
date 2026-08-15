"""공개 데이터 타입 — 용어, 탐지 결과, 보정 결과 위치.

이 모듈은 의존성이 없다. 로직도 두지 않는다.
오디오·번역 라이브러리를 import하지 않는다 (요구사항 C-IND-01, C-IND-02).
"""

from dataclasses import dataclass, field
from enum import StrEnum


class Method(StrEnum):
    """용어를 찾아낸 방법.

    겹침 해소의 1순위 판단 근거다 (기술근거 04 §11).
    str을 상속하므로 `span.method == "exact"`로 비교할 수 있다.
    """

    EXACT = "exact"   # 표준형·별칭과 정확히 일치. confidence 1.0
    REGEX = "regex"   # 정규식으로 찾은 미등록 용어. confidence 0.8 고정
    FUZZY = "fuzzy"   # 소리 유사도로 찾음. confidence는 실제 유사도


@dataclass(frozen=True)
class Term:
    """용어집의 한 항목.

    값 검증은 여기서 하지 않는다. Glossary.from_yaml이 전부 검사하고,
    Term을 만드는 것은 Glossary뿐이다.
    """

    canonical: str
    aliases: tuple[str, ...] = ()
    translations: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Match:
    """탐지 결과.

    ⚠️ start/end는 **입력 텍스트** 기준이다. 보정 후 오프셋은 Span을 쓴다.
    """

    start: int
    end: int
    term: str          # 표준형. 미등록 용어(REGEX)는 matched와 같다
    matched: str       # 입력에 실제로 있던 문자열
    method: Method
    confidence: float


@dataclass(frozen=True)
class Span:
    """보정 결과의 용어 위치.

    ⚠️ start/end는 **결과 텍스트** 기준이다 (설계 03 §4).
    앞 용어가 길어지면 뒤 오프셋이 밀리며, 그 재계산은 correct.py의 일이다.
    """

    start: int
    end: int
    term: str
    matched: str
    method: Method
    confidence: float
