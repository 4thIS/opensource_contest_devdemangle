"""소리 유사도로 미등록 발음 변형을 찾는다.

용어집에 등록된 별칭은 정확 탐지가 먼저 잡는다. 이 모듈이 맡는 건 **사전에 없는 것**이다 —
STT가 "파이썬"을 "파일선"으로 뱉었을 때, 그 둘을 소리로 이어준다.

비교 대상은 표준형이 아니라 **한글 별칭**이다. 한국어 음차를 영어 철자와 맞대면
음운 구조가 달라 우연히 겹친다 — "리듬이"는 "README"와 0.55지만 "리드미"와는 1.00이다.

**이미 잡힌 구간은 보지 않는다.** 등록 별칭은 소리로도 자기 자신과 1.00이라, 걸러내지
않으면 같은 자리에 후보가 둘 생긴다. 그러면 방어를 겹침 해소 하나에만 맡기게 되는데,
그 해소는 겹치는 것끼리만 작동한다 — 등록 탐지가 경계 규칙으로 일부러 침묵한 자리는
막지 못한다.
"""

import re

from rapidfuzz import fuzz

from devdemangle.detect import is_particle_tail, starts_token
from devdemangle.glossary import Glossary
from devdemangle.romanize import phonetic_key
from devdemangle.types import Match, Method

# 배포 용어집(별칭 58개) 기준 오탐 최고 0.769("파일은") / 정답 최저 0.800("기터벳의").
# 그 사이가 유일한 안전 구간이고 여유는 0.031이다. 용어집을 늘리면 다시 재야 한다.
DEFAULT_THRESHOLD = 0.78

# 소리 키가 이보다 짧으면 보지 않는다. 짧은 음차는 일상어와 겹쳐도 유사도가 높게
# 나와 임계값으로 못 막는다("뷰"/"브이유"가 0.86이다).
MIN_KEY_LEN = 5

# 후보의 글자 수가 별칭보다 이 배수를 넘으면 버린다.
#
# 별칭이 덩어리의 일부일 때("우리"+"깃허브", "도커"+"피") 남는 글자는 점수를 조금
# 깎을 뿐 매치를 막지 못한다. 어미가 붙은 경우("깃허브"+"다")도 같다. 셋 다 어절
# 맨 앞에서 시작하고 전부 한글이라 시작 경계로도, 덩어리 제한으로도 안 걸린다.
#
# **소리 키 길이가 아니라 글자 수로 잰다.** 키는 정규화를 거치면서 길이가 왜곡된다 —
# "리액트"는 "eu" 제거로 6자가 되고 "리액터"는 8자로 남아, 같은 3음절인데 1.33배가
# 된다. 그러면 실측 정답 "리액터"가 오탐 "깃허브다"보다 불리해진다.
#
# 실측 36건(1차 21 + 2차 15)에서 글자 수 비율이 1.00을 넘는 정답은 "타입스트리트"
# 하나(1.20)뿐이고, 오탐 최소는 "깃허브다"의 1.33이다. 그 사이가 안전 구간이다.
#
# **하한은 두지 않는다.** 별칭보다 짧은 정답이 있다 — "넥스트"가 그렇다.
MAX_LENGTH_RATIO = 1.25


def _length(s: str) -> int:
    """비교용 글자 수. 별칭에 든 공백은 세지 않는다("타입 스트릿")."""
    return len(s.replace(" ", ""))


# 후보는 한글 덩어리만 본다. 라틴 식별자는 정규식 탐지가 모양으로 잡으므로 소리로
# 추정할 이유가 없고, 어절을 통째로 뽑으면 문장부호까지 소리 키에 섞인다.
_CHUNK_RE = re.compile(r"[가-힣]{2,}")

# 조사 최대 두 개까지 떼어 본다. 낱개가 두 글자까지라 합쳐서 넷이 상한이다.
_MAX_TAIL = 4


def _candidates(chunk: str) -> list[str]:
    """이 덩어리에서 용어일 수 있는 앞부분들.

    꼬리를 떼는 게 아니라 **뗀 것과 안 뗀 것을 모두 후보로 낸다.** 떼기만 하면
    조사 모양으로 끝나는 변형을 잃는다 — "리듬이"(README)의 "이"가 조사라서
    "리듬"으로 잘리고, 소리 키가 짧아져 후보에서 아예 빠진다.

    **많이 뗀 것부터 낸다.** 부르는 쪽이 동점에서 먼저 만난 후보를 쓰므로, 이 순서가
    "동점이면 꼬리를 더 뗀 쪽"이라는 규칙이 된다. "파일선으로"는 "파일선"과 "파일선으"가
    똑같이 0.933인데, 뒤엣것이 이기면 "으"가 구간에 남아 조사가 반만 잘린다.
    """
    forms = [
        chunk[:-cut]
        for cut in reversed(range(1, min(len(chunk), _MAX_TAIL + 1)))
        if chunk[:-cut] and is_particle_tail(chunk[-cut:])
    ]
    forms.append(chunk)
    return forms


def fuzzy_detect(
    text: str,
    glossary: Glossary,
    existing: list[Match] | None = None,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    min_key_len: int = MIN_KEY_LEN,
) -> list[Match]:
    """텍스트에서 소리가 비슷한 용어를 찾는다.

    겹침은 해소하지 않는다 — 후보를 그대로 내보내고 정리는 보정 단계가 맡는다.

    Args:
        existing: 이미 찾은 매치. 이 구간과 겹치는 덩어리는 건너뛴다.
        threshold: 이 값 미만이면 버린다.
        min_key_len: 소리 키가 이보다 짧은 후보는 아예 보지 않는다.

    Returns:
        입력 텍스트 기준 오프셋을 가진 Match 목록. 시작 위치 오름차순.
    """
    taken = [(m.start, m.end) for m in (existing or [])]

    alias_keys = [
        (phonetic_key(alias), _length(alias), term.canonical)
        for term in glossary
        for alias in term.aliases
    ]

    matches: list[Match] = []
    for chunk_match in _CHUNK_RE.finditer(text):
        start, end = chunk_match.span()

        # 등록 탐지와 같은 시작 경계를 쓴다. 앞에 다른 글자가 붙어 있으면 그건
        # 별개 단어의 일부다 — "윈도커널"의 "도커"를 안 잡는 이유와 같다.
        if not starts_token(text, start):
            continue
        if any(start < e and s < end for s, e in taken):
            continue

        best_score = 0.0
        best_term = ""
        best_form = ""
        for form in _candidates(chunk_match.group()):
            form_key = phonetic_key(form)
            if len(form_key) < min_key_len:
                continue
            form_len = _length(form)
            for alias_key, alias_len, canonical in alias_keys:
                if form_len > alias_len * MAX_LENGTH_RATIO:
                    continue
                score = fuzz.ratio(form_key, alias_key) / 100
                if score > best_score:
                    best_score, best_term, best_form = score, canonical, form

        if best_score >= threshold:
            matches.append(
                Match(
                    start=start,
                    end=start + len(best_form),
                    term=best_term,
                    matched=best_form,
                    method=Method.FUZZY,
                    confidence=best_score,
                )
            )
    return matches
