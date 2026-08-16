"""탐지 결과를 표준형으로 되돌린다.

correct()는 오케스트레이션만 한다 — 무엇을 찾을지는 탐지 쪽 일이고, 여기서는
찾아온 것을 바꾸고 결과 좌표를 다시 센다.

탐지기는 `detect` 인자로 갈아끼운다. 기본값 `_detect_exact`는 detect.py가 없는
동안 쓰는 잠정 구현이다 — 계약(`(text, glossary) -> list[Match]`)이 같으므로
detect.py가 들어오면 기본값만 바꾸면 된다.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import ahocorasick

from devdemangle.glossary import Glossary
from devdemangle.types import Match, Method, Span

# 용어집 기본 위치. tests/test_terms_yaml.py와 같은 기준(저장소 루트)을 쓴다.
DEFAULT_TERMS_PATH = Path(__file__).resolve().parent.parent / "data" / "terms.yaml"

_TOKEN_RE = re.compile(r"\S+")

Detector = Callable[[str, Glossary], list[Match]]


@dataclass
class CorrectionResult:
    text: str
    spans: list[Span]


def _fold(text: str) -> str | None:
    """길이가 보존되는 소문자 변환만 돌려준다.

    일부 유니코드 문자는 lower()에서 길이가 바뀌어 오프셋이 어긋난다.
    그런 경우 None을 돌려 대소문자 무시 매칭을 포기한다 — 좌표가 틀리는
    것보다 몇 건 놓치는 쪽이 낫다.
    """
    lowered = text.lower()
    return lowered if len(lowered) == len(text) else None


def build_automaton(glossary: Glossary) -> ahocorasick.Automaton:
    """모든 alias를 소문자 키로 등록한 Aho-Corasick 자동자를 만든다.

    값으로 alias 문자열이 아니라 길이를 담는다. 실제 원문은 매칭 위치에서
    잘라 쓰기 때문에 대소문자가 달라도 그대로 살아난다.
    """
    automaton = ahocorasick.Automaton()
    for term in glossary:
        for alias in term.aliases:
            key = _fold(alias) or alias
            automaton.add_word(key, (len(key), term.canonical))
    if len(automaton) > 0:
        automaton.make_automaton()
    return automaton


@lru_cache(maxsize=1)
def default_glossary() -> Glossary:
    return Glossary.from_yaml(DEFAULT_TERMS_PATH)


@lru_cache(maxsize=1)
def _default_automaton() -> ahocorasick.Automaton:
    return build_automaton(default_glossary())


def _detect_exact(text: str, glossary: Glossary | None = None) -> list[Match]:
    """별칭을 정확히(대소문자만 무시) 찾는다. detect.py가 오기 전까지 쓰는 잠정 구현.

    - alias는 공백 기준 토큰 경계에서 시작·끝나야 매칭된다 (토큰 중간에
      우연히 걸리는 부분 매칭은 제외).
    - 이미 표준형인 구간은 되돌릴 게 없으므로 내보내지 않는다 (C-COR-02).
    - 좌표는 **입력 텍스트** 기준이다.
    """
    automaton = _default_automaton() if glossary is None else build_automaton(glossary)
    if len(automaton) == 0:
        return []

    # 자동자 키가 소문자라 건초더미도 소문자로 맞춘다. 길이가 안 맞으면
    # 원문 그대로 훑는다 (대소문자가 정확히 같은 것만 걸린다).
    haystack = _fold(text) or text

    token_spans = [(m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]
    token_starts = {s for s, _ in token_spans}
    token_ends = {e for _, e in token_spans}

    matches: list[Match] = []
    for end_index, (key_len, canonical) in automaton.iter(haystack):
        start = end_index - key_len + 1
        end = end_index + 1
        if start not in token_starts or end not in token_ends:
            continue
        matched = text[start:end]
        if matched == canonical:
            continue  # 이미 표준형이다
        matches.append(
            Match(
                start=start,
                end=end,
                term=canonical,
                matched=matched,
                method=Method.EXACT,
                confidence=1.0,
            )
        )
    return matches


def resolve_overlaps(matches: list[Match]) -> list[Match]:
    """겹치는 매치 중 남길 것을 고른다.

    우선순위는 ①길이 ②method(exact > regex > fuzzy) ③신뢰도 ④위치 순이다.
    """
    order = {Method.EXACT: 0, Method.REGEX: 1, Method.FUZZY: 2}
    ranked = sorted(
        matches,
        key=lambda m: (
            -(m.end - m.start),
            order.get(m.method, 9),
            -m.confidence,
            m.start,
        ),
    )

    accepted: list[Match] = []
    for match in ranked:
        if any(match.start < a.end and a.start < match.end for a in accepted):
            continue
        accepted.append(match)

    accepted.sort(key=lambda m: m.start)
    return accepted


def correct(
    text: str,
    glossary: Glossary | None = None,
    *,
    detect: Detector = _detect_exact,
) -> CorrectionResult:
    """탐지된 별칭을 표준형으로 바꾸고, 바뀐 위치를 결과 텍스트 좌표로 돌려준다.

    Match는 입력 좌표, Span은 결과 좌표다. 앞 용어가 길어지면 뒤가 밀리므로
    여기서 다시 센다.

    glossary 생략 시 기본 용어집(data/terms.yaml)을 쓰고 자동자를 캐싱한다.
    """
    if not text:
        return CorrectionResult(text="", spans=[])

    accepted = resolve_overlaps(detect(text, glossary))
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
