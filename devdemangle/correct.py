"""terms.yaml 별칭(alias)을 표준형(canonical)으로 되돌리는 보정 모듈."""

import re
from dataclasses import dataclass
from functools import lru_cache

import ahocorasick

from devdemangle.glossary import Term, load_glossary

_TOKEN_RE = re.compile(r"\S+")


@dataclass
class Match:
    original: str
    canonical: str
    start: int
    end: int


@dataclass
class CorrectionResult:
    text: str
    matches: list[Match]


def _fold(text: str) -> str | None:
    """길이가 보존되는 소문자 변환만 돌려준다.

    일부 유니코드 문자는 lower()에서 길이가 바뀌어 오프셋이 어긋난다.
    그런 경우 None을 돌려 대소문자 무시 매칭을 포기한다 — 좌표가 틀리는
    것보다 몇 건 놓치는 쪽이 낫다.
    """
    lowered = text.lower()
    return lowered if len(lowered) == len(text) else None


def build_automaton(terms: list[Term]) -> ahocorasick.Automaton:
    """모든 alias를 소문자 키로 등록한 Aho-Corasick 자동자를 만든다.

    값으로 alias 문자열이 아니라 길이를 담는다. 실제 원문은 매칭 위치에서
    잘라 쓰기 때문에 대소문자가 달라도 그대로 살아난다.
    """
    automaton = ahocorasick.Automaton()
    for term in terms:
        for alias in term.aliases:
            key = _fold(alias) or alias
            automaton.add_word(key, (len(key), term.canonical))
    automaton.make_automaton()
    return automaton


@lru_cache(maxsize=1)
def _default_automaton() -> ahocorasick.Automaton:
    return build_automaton(load_glossary())


def correct(text: str, terms: list[Term] | None = None) -> CorrectionResult:
    """텍스트 안의 alias를 canonical로 교체한다.

    - alias는 공백 기준 토큰 경계에서 시작·끝나야 매칭된다 (토큰 중간에
      우연히 걸리는 부분 매칭은 제외).
    - 대소문자를 무시하고 찾되 **표준형으로 되돌리는 방향만** 적용한다.
      이미 표준형인 구간은 건드리지 않는다 (C-COR-02).
    - 구간이 겹치면 **긴 쪽이 이긴다.** 길이가 같으면 앞선 쪽이 이긴다.

    terms 생략 시 기본 용어집(devdemangle/data/terms.yaml)을 쓰고 자동자를 캐싱한다.
    """
    if not text:
        return CorrectionResult(text="", matches=[])

    automaton = build_automaton(terms) if terms is not None else _default_automaton()
    if len(automaton) == 0:
        return CorrectionResult(text=text, matches=[])

    # 자동자 키가 소문자라 건초더미도 소문자로 맞춘다. 길이가 안 맞으면
    # 원문 그대로 훑는다 (대소문자가 정확히 같은 것만 걸린다).
    haystack = _fold(text) or text

    token_spans = [(m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]
    token_starts = {s for s, _ in token_spans}
    token_ends = {e for _, e in token_spans}

    candidates = []
    for end_index, (key_len, canonical) in automaton.iter(haystack):
        start = end_index - key_len + 1
        end = end_index + 1
        if start not in token_starts or end not in token_ends:
            continue
        original = text[start:end]
        if original == canonical:
            continue  # 이미 표준형이다
        candidates.append((start, end, original, canonical))

    # 겹침 우선순위: 길이 1순위, 시작 위치 2순위
    candidates.sort(key=lambda c: (-(c[1] - c[0]), c[0]))

    accepted: list[tuple[int, int, str, str]] = []
    for start, end, original, canonical in candidates:
        if any(start < taken_end and taken_start < end for taken_start, taken_end, _, _ in accepted):
            continue
        accepted.append((start, end, original, canonical))

    accepted.sort(key=lambda c: c[0])

    result_text = text
    for start, end, _original, canonical in reversed(accepted):
        result_text = result_text[:start] + canonical + result_text[end:]

    matches = [
        Match(original=original, canonical=canonical, start=start, end=end)
        for start, end, original, canonical in accepted
    ]
    return CorrectionResult(text=result_text, matches=matches)
