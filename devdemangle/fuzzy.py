"""소리 유사도로 미등록 발음 변형을 찾는다.

용어집에 등록된 별칭은 정확 탐지가 먼저 잡는다. 이 모듈이 맡는 건 **사전에 없는 것**이다 —
STT가 "파이썬"을 "파일선"으로 뱉었을 때, 그 둘을 소리로 이어준다.

비교 대상은 표준형이 아니라 **한글 별칭**이다. 한국어 음차를 영어 철자와 맞대면
음운 구조가 달라 우연히 겹친다 — "리듬이"는 "README"와 0.55지만 "리드미"와는 1.00이다.
"""

import re

from rapidfuzz import fuzz

from devdemangle.glossary import Glossary
from devdemangle.romanize import phonetic_key
from devdemangle.types import Match, Method

_TOKEN_RE = re.compile(r"\S+")


def fuzzy_detect(
    text: str,
    glossary: Glossary,
    *,
    threshold: float = 0.78,
    min_key_len: int = 5,
) -> list[Match]:
    """텍스트에서 소리가 비슷한 용어를 찾는다.

    겹침은 해소하지 않는다 — 후보를 그대로 내보내고 정리는 보정 단계가 맡는다.

    Args:
        threshold: 이 값 미만이면 버린다. 배포 용어집 기준으로 **오탐 최고가
            "파일은"의 0.77, 정답 최저가 "기터벳"의 0.80**이라 그 사이가 유일한
            안전 구간이다. 여유가 0.02뿐이라 용어집을 늘릴 때 다시 재야 한다.
        min_key_len: 소리 키가 이보다 짧은 토큰은 아예 보지 않는다.
            짧은 음차는 일상어와 겹쳐도 유사도가 높게 나와 임계값으로 못 막는다
            ("뷰"/"브이유"가 0.86이다).

    Returns:
        입력 텍스트 기준 오프셋을 가진 Match 목록. 시작 위치 오름차순.
    """
    # 별칭 키는 토큰마다 다시 계산할 이유가 없다.
    alias_keys = [
        (phonetic_key(alias), term.canonical)
        for term in glossary
        for alias in term.aliases
    ]

    matches: list[Match] = []
    for token_match in _TOKEN_RE.finditer(text):
        token = token_match.group()
        token_key = phonetic_key(token)
        if len(token_key) < min_key_len:
            continue

        best_score = 0.0
        best_term = ""
        for alias_key, canonical in alias_keys:
            score = fuzz.ratio(token_key, alias_key) / 100
            if score > best_score:
                best_score, best_term = score, canonical

        if best_score >= threshold:
            matches.append(
                Match(
                    start=token_match.start(),
                    end=token_match.end(),
                    term=best_term,
                    matched=token,
                    method=Method.FUZZY,
                    confidence=best_score,
                )
            )
    return matches
