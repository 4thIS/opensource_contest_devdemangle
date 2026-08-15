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


def build_automaton(terms: list[Term]) -> ahocorasick.Automaton:
    """모든 alias를 키로 등록한 Aho-Corasick 자동자를 만든다."""
    automaton = ahocorasick.Automaton()
    for term in terms:
        for alias in term.aliases:
            automaton.add_word(alias, (alias, term.canonical))
    automaton.make_automaton()
    return automaton


@lru_cache(maxsize=1)
def _default_automaton() -> ahocorasick.Automaton:
    return build_automaton(load_glossary())


def correct(text: str, terms: list[Term] | None = None) -> CorrectionResult:
    """텍스트 안의 alias를 canonical로 교체한다.

    alias는 공백 기준 토큰 경계에서 시작·끝나야 매칭된다 (토큰 중간에
    우연히 걸리는 부분 매칭은 제외). terms 생략 시 기본 용어집(devdemangle/data/terms.yaml)을
    쓰고 자동자를 캐싱한다.
    """
    if not text:
        return CorrectionResult(text="", matches=[])

    automaton = build_automaton(terms) if terms is not None else _default_automaton()
    if len(automaton) == 0:
        return CorrectionResult(text=text, matches=[])

    token_spans = [(m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]
    token_starts = {s for s, _ in token_spans}
    token_ends = {e for _, e in token_spans}

    candidates = []
    for end_index, (alias, canonical) in automaton.iter(text):
        start = end_index - len(alias) + 1
        end = end_index + 1
        if start in token_starts and end in token_ends:
            candidates.append((start, end, alias, canonical))

    candidates.sort(key=lambda c: (c[0], -(c[1] - c[0])))

    accepted = []
    last_end = -1
    for start, end, alias, canonical in candidates:
        if start < last_end:
            continue
        accepted.append((start, end, alias, canonical))
        last_end = end

    result_text = text
    for start, end, _alias, canonical in sorted(accepted, key=lambda c: -c[0]):
        result_text = result_text[:start] + canonical + result_text[end:]

    matches = [
        Match(original=alias, canonical=canonical, start=start, end=end)
        for start, end, alias, canonical in accepted
    ]
    return CorrectionResult(text=result_text, matches=matches)
