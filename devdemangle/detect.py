"""탐지 — 입력 텍스트에서 용어 위치를 찾는다.

detect()는 겹치는 후보를 전부 내보내고, resolve_overlaps()가 그중 하나를 고른다.
둘을 나눈 이유는 퍼지다 — 소리 유사도 후보가 나중에 합쳐지므로, 탐지 단계에서
미리 정리하면 그때 되살릴 수 없다. 합친 뒤 resolve_overlaps()를 한 번만 통과시킨다.
"""

import re

import ahocorasick

from devdemangle.glossary import Glossary
from devdemangle.types import Match, Method

# 용어집에 없는 식별자를 모양으로 잡는다. 신뢰도는 실제로 잰 값이 아니라
# "exact보다는 못 믿는다"는 자리표시자다 — 같은 method끼리만 비교해야 한다.
REGEX_CONFIDENCE = 0.8

# 겹칠 때 어느 method가 이기는가. 등록 용어가 정규식보다, 정규식이 소리 추정보다 앞선다.
# 신뢰도로 대신할 수 없다 — 퍼지 신뢰도는 실측값이라 0.8을 넘길 수 있는데,
# 그렇다고 미등록 식별자를 소리 추정이 이기게 둘 수는 없다.
METHOD_RANK = {Method.EXACT: 0, Method.REGEX: 1, Method.FUZZY: 2}

IDENTIFIER = re.compile(
    r"""
      # 문자 집합을 \w로 쓰지 않는다. \w는 한글도 포함해서 "--force로"의 조사까지
      # 물고 들어간다 — 용어가 "--force로"가 되면 번역 보호에 조사가 딸려 나간다.
      --?[a-zA-Z][a-zA-Z0-9-]*     # 명령행 플래그   --no-cache, -v
    | [a-z]+(?:[A-Z][a-z0-9]*)+    # camelCase      reactRouter
    | [a-z0-9]+(?:_[a-z0-9]+)+     # snake_case     user_id
    """,
    re.VERBOSE,
)

# 끝 경계를 완화할 때 허용하는 꼬리. 조사는 겹쳐 붙으므로 결합형을 나열하지 않고
# 낱개만 두고 조합한다 — "에서는"·"으로도"·"까지는"을 하나씩 적으면 곱셈으로 커진다.
PARTICLES = frozenset(
    """
    이 가 을 를 의 에 에서 에게 한테 께 으로 로 와 과 랑 이랑 보다 처럼
    은 는 도 만 까지 부터 마다 조차 밖에
    """.split()
)


def detect(text: str, glossary: Glossary) -> list[Match]:
    """텍스트에서 용어와 식별자를 찾는다.

    등록 용어는 Aho-Corasick으로, 용어집에 없는 식별자는 모양(정규식)으로 잡는다.
    소리 유사도로 찾는 일은 여기서 하지 않는다 — 퍼지는 별도 모듈이다.

    겹치는 후보를 골라내지 않고 전부 돌려준다. 고르는 건 resolve_overlaps()의 일이다.

    Returns:
        위치 순으로 정렬된 Match 목록. 같은 자리면 긴 것이 앞에 온다.
        **start·end는 입력 텍스트 기준이다** — 보정 후 좌표는 Span이 따로 있다.
    """
    matches = []

    automaton = ahocorasick.Automaton()
    for term in glossary:
        for pattern in (term.canonical, *term.aliases):
            automaton.add_word(_fold(pattern), (len(pattern), term.canonical))

    # 패턴이 하나도 없으면 자동자를 만들 수 없다. 정규식 경로는 그대로 돈다.
    if len(automaton):
        automaton.make_automaton()
        for end_idx, (length, canonical) in automaton.iter(_fold(text)):
            start = end_idx - length + 1
            end = end_idx + 1
            if not starts_token(text, start) or not _ends_token(text, end):
                continue
            matches.append(
                Match(start, end, canonical, text[start:end], Method.EXACT, 1.0)
            )

    for found in IDENTIFIER.finditer(text):
        start, end = found.span()
        if not starts_token(text, start) or not _ends_token(text, end):
            continue
        name = found.group()
        matches.append(Match(start, end, name, name, Method.REGEX, REGEX_CONFIDENCE))

    matches.sort(key=lambda m: (m.start, -(m.end - m.start)))
    return matches


def resolve_overlaps(matches: list[Match]) -> list[Match]:
    """겹치는 후보 중 하나만 남긴다.

    순서는 ①method ②길이 ③신뢰도 ④위치다. method가 앞서는 게 중요하다 —
    긴 정규식이 짧은 등록 용어를 이기면 안 되고, 어절을 통째로 잡는 소리 추정이
    조사를 뗀 등록 용어를 밀어내서도 안 된다. "npm install"과 "npm"은 둘 다
    exact라 method가 같고, 그다음 길이에서 긴 쪽이 남는다.

    detect()에서 떼어 둔 이유는 퍼지 때문이다. 소리 유사도로 찾은 후보는
    탐지가 끝난 뒤에 합쳐지는데, 탐지가 미리 정리해 버리면 그때 버린 후보를
    되살릴 수 없다. **탐지 결과와 퍼지 결과를 합친 다음 여기 한 번만 통과시킨다.**

    맞닿기만 한 것은 겹침이 아니다(끝과 시작이 같은 경우).

    Returns:
        위치 오름차순. 고를 때 쓴 순서는 결과에 드러나지 않는다.
    """
    kept: list[Match] = []
    for m in sorted(matches, key=_priority):
        if not any(m.start < k.end and k.start < m.end for k in kept):
            kept.append(m)
    return sorted(kept, key=lambda m: m.start)


def _priority(m: Match) -> tuple:
    """겹침에서 이기는 순서. 작을수록 먼저 고른다.

    **method가 길이보다 먼저다.** 길이를 먼저 보면 두 가지가 무너진다 —
    긴 정규식이 짧은 등록 용어를 이기고(등록 용어 우선 규칙 위반),
    어절을 통째로 잡는 소리 추정이 조사를 뗀 등록 용어를 밀어낸다.

    "npm install"과 "npm"은 둘 다 등록 용어라 method가 같고, 그다음 길이에서
    갈린다 — 긴 쪽이 남는 규칙은 그대로 지켜진다.
    """
    return (METHOD_RANK[m.method], -(m.end - m.start), -m.confidence, m.start)


def starts_token(text: str, start: int) -> bool:
    """매치 시작이 토큰 시작과 같은가.

    시작 경계는 완화하지 않는다. 한국어에서 앞에 붙는 건 조사가 아니라
    다른 단어라, 허용하면 "윈도커널"의 "도커"까지 걸린다.

    소리 탐지도 같은 판정을 써야 해서 공개한다. 규칙을 두 벌 두면 한쪽만
    고쳤을 때 두 모듈이 다르게 동작하고, 그건 문장을 넣어보기 전에는 드러나지 않는다.
    """
    return start == 0 or not text[start - 1].isalnum()


def _fold(s: str) -> str:
    """대소문자만 지우고 길이는 그대로 두는 변환.

    그냥 lower()를 쓰면 글자 수가 늘어나는 문자가 있다(İ → i̇). Match의 start·end가
    입력 텍스트 기준이라, 한 글자라도 밀리면 보정이 엉뚱한 자리를 자른다.
    """
    return "".join(c.lower() if len(c.lower()) == 1 else c for c in s)


def _ends_token(text: str, end: int) -> bool:
    """매치 끝이 토큰 끝이거나, 남는 꼬리가 조사인가.

    끝 경계만 완화한다. "뭐든 붙어도 통과"가 아니라 명시적 목록이다 —
    조사는 닫힌 집합이라 목록으로 관리되지만 어미는 그렇지 않다.
    """
    if end == len(text) or not text[end].isalnum():
        return True
    return is_particle_tail(_tail(text, end))


def is_particle_tail(tail: str) -> bool:
    """꼬리를 조사 최대 두 개로 쪼갤 수 있는가.

    퍼지 탐지도 같은 판정이 필요해서 공개한다. 목록을 두 벌 두면 한쪽만 고쳤을 때
    두 모듈이 다르게 동작하고, 그건 문장을 넣어보기 전에는 드러나지 않는다.

    처음엔 "격조사는 맨 앞에만 온다"로 제한했는데, 실측 전사의 "GitHub에서의"가
    거기서 걸렸다. 에서(부사격) 뒤의 의(관형격)도 격조사라 조합이 막혔다.
    문법 층위로 순서를 정하려던 것을 버리고 낱개 두 개까지로 단순화한다 —
    "이가" 같은 조합도 통과하지만 그런 어절은 실제로 나오지 않는다.

    서술격("입니다"·"예요")은 조사가 아니라 어미라 뺐다. 오탐을 재고 나서 판단한다.
    """
    if tail in PARTICLES:
        return True
    return any(
        tail[:i] in PARTICLES and tail[i:] in PARTICLES
        for i in range(1, len(tail))
    )


def _tail(text: str, end: int) -> str:
    """매치 끝부터 토큰 끝까지 남는 글자."""
    stop = end
    while stop < len(text) and text[stop].isalnum():
        stop += 1
    return text[end:stop]
