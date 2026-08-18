"""소리 유사도로 미등록 발음 변형을 찾는다.

용어집에 등록된 별칭은 정확 탐지가 먼저 잡는다. 이 모듈이 맡는 건 **사전에 없는 것**이다 —
STT가 "파이썬"을 "파일선"으로 뱉었을 때, 그 둘을 소리로 이어준다.

비교 대상은 표준형이 아니라 **한글 별칭**이다. 한국어 음차를 영어 철자와 맞대면
음운 구조가 달라 우연히 겹친다 — "리듬이"는 "README"와 0.55지만 "리드미"와는 1.00이다.
"""

import re

from rapidfuzz import fuzz

from devdemangle.detect import is_particle_tail
from devdemangle.glossary import Glossary
from devdemangle.romanize import phonetic_key
from devdemangle.types import Match, Method

_TOKEN_RE = re.compile(r"\S+")
_PUNCT = ".,?!\"')]}…"
_MAX_TAIL = 4


def _candidates(token: str) -> list[str]:
    """이 어절에서 용어일 수 있는 앞부분들.

    꼬리를 떼는 게 아니라 **뗀 것과 안 뗀 것을 모두 후보로 낸다.** 떼기만 하면
    조사 모양으로 끝나는 변형을 잃는다 — "리듬이"(README)의 "이"가 조사라서
    "리듬"으로 잘리고, 소리 키가 짧아져 후보에서 아예 빠진다.

    어느 쪽이 맞는지는 여기서 정하지 않고 점수가 정하게 둔다.

    **많이 뗀 것부터 낸다.** 부르는 쪽이 동점에서 먼저 만난 후보를 쓰므로, 이 순서가
    "동점이면 꼬리를 더 뗀 쪽"이라는 규칙이 된다. "파일선으로"는 "파일선"과 "파일선으"가
    똑같이 0.933인데, 뒤엣것이 이기면 "으"가 구간에 남아 조사가 반만 잘린다.
    """
    core = token.rstrip(_PUNCT)
    forms = [
        core[:-cut]
        for cut in reversed(range(1, min(len(core), _MAX_TAIL + 1)))
        if core[:-cut] and is_particle_tail(core[-cut:])
    ]
    if core and core != token:
        forms.append(core)
    forms.append(token)
    return forms


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
        threshold: 이 값 미만이면 버린다. 배포 용어집(별칭 58개) 기준으로 **오탐 최고가
            "파일은"의 0.769, 정답 최저가 "기터벳의"의 0.800**이라 그 사이가 유일한
            안전 구간이다. 여유가 0.031뿐이라 용어집을 늘릴 때 다시 재야 한다.

            정답 쪽은 조사·문장부호가 붙은 **실문장 형태**로 쟀다. 맨몸 토큰으로 재면
            "기터벳" 0.800이 나오지만 실측 전사에 있는 형태는 "기터벳의"이고, 꼬리를
            다루기 전에는 그게 0.706이라 이 값으로 안 잡혔다.
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
        best_score = 0.0
        best_term = ""
        best_form = ""
        for form in _candidates(token_match.group()):
            form_key = phonetic_key(form)
            if len(form_key) < min_key_len:
                continue
            for alias_key, canonical in alias_keys:
                score = fuzz.ratio(form_key, alias_key) / 100
                if score > best_score:
                    best_score, best_term, best_form = score, canonical, form

        if best_score >= threshold:
            matches.append(
                Match(
                    start=token_match.start(),
                    end=token_match.start() + len(best_form),
                    term=best_term,
                    matched=best_form,
                    method=Method.FUZZY,
                    confidence=best_score,
                )
            )
    return matches
