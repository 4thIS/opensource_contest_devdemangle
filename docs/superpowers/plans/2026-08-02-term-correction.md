# 용어 보정 모듈 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `data/terms.yaml`의 별칭(alias)을 표준형(canonical)으로 되돌리는 `devdemangle.correct()` 함수를 구현한다.

**Architecture:** `devdemangle/glossary.py`가 YAML을 `Term` 객체로 로드하고, `devdemangle/correct.py`가 `pyahocorasick` 자동자로 텍스트를 스캔해 공백 토큰 경계에 맞는 alias만 canonical로 치환한다. `devdemangle/__init__.py`에서 둘 다 공개 API로 내보낸다.

**Tech Stack:** Python 3.13, pyahocorasick, pyyaml, pytest (모두 `pyproject.toml`에 이미 선언된 의존성).

## Global Constraints

- Python >= 3.13 (`pyproject.toml`)
- 신규 의존성 추가 금지 — `pyahocorasick>=2.3.1`, `pyyaml>=6.0`이 이미 base dependencies에 있음
- 매칭 전략은 Aho-Corasick 정확 매칭만. 퍼지(편집거리) 매칭은 이번 스코프에 넣지 않는다
- alias 매칭은 공백 기준 토큰 경계에서 **시작·끝 모두** 정확히 일치해야 한다 (원안 유지 — 조사 결합 문장은 v1에서 미매칭, 알려진 한계)
- 겹치는 매칭은 더 긴 alias를 우선한다 (그리디, 왼쪽부터)
- 보정 결과는 `CorrectionResult(text: str, matches: list[Match])` 형태. `Match`는 `original`, `canonical`, `start`, `end`(문자 offset, exclusive) 필드를 가진다
- `data/terms.yaml` 스키마 검증은 기존 `tests/test_terms_yaml.py`가 담당하므로 신규 코드에서 재검증하지 않는다
- 참고 스펙: `docs/superpowers/specs/2026-08-02-term-correction-design.md`

---

### Task 1: 용어집 로더 (`devdemangle/glossary.py`)

**Files:**
- Create: `devdemangle/glossary.py`
- Test: `tests/test_glossary.py`

**Interfaces:**
- Produces:
  - `Term` dataclass — `canonical: str`, `aliases: list[str]`, `translations: dict[str, str] | None = None`
  - `load_glossary(path: Path | None = None) -> list[Term]` — `path` 생략 시 저장소 기본 위치(`data/terms.yaml`)를 읽는다

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_glossary.py` 새로 작성:

```python
from pathlib import Path

from devdemangle.glossary import Term, load_glossary

TERMS_PATH = Path(__file__).resolve().parent.parent / "data" / "terms.yaml"


def test_load_glossary_returns_term_objects():
    terms = load_glossary(TERMS_PATH)
    assert len(terms) >= 20
    assert all(isinstance(t, Term) for t in terms)


def test_load_glossary_parses_known_term():
    terms = load_glossary(TERMS_PATH)
    github = next(t for t in terms if t.canonical == "GitHub")
    assert "깃허브" in github.aliases
    assert "깃헙" in github.aliases


def test_load_glossary_parses_translations():
    terms = load_glossary(TERMS_PATH)
    di = next(t for t in terms if t.canonical == "의존성 주입")
    assert di.translations == {"en": "dependency injection"}


def test_load_glossary_term_without_translations_is_none():
    terms = load_glossary(TERMS_PATH)
    github = next(t for t in terms if t.canonical == "GitHub")
    assert github.translations is None


def test_load_glossary_default_path_finds_real_file():
    terms = load_glossary()
    canons = {t.canonical for t in terms}
    assert "GitHub" in canons
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tests/test_glossary.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'devdemangle.glossary'`

- [ ] **Step 3: 최소 구현 작성**

`devdemangle/glossary.py` 새로 작성:

```python
"""data/terms.yaml 용어집 로더."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_TERMS_PATH = Path(__file__).resolve().parent.parent / "data" / "terms.yaml"


@dataclass
class Term:
    canonical: str
    aliases: list[str] = field(default_factory=list)
    translations: dict[str, str] | None = None


def load_glossary(path: Path | None = None) -> list[Term]:
    """terms.yaml을 읽어 Term 리스트로 반환한다.

    path 생략 시 저장소 기본 위치(data/terms.yaml)를 쓴다.
    """
    target = path or DEFAULT_TERMS_PATH
    with open(target, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return [
        Term(
            canonical=t["canonical"],
            aliases=list(t.get("aliases", [])),
            translations=t.get("translations"),
        )
        for t in data["terms"]
    ]
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest tests/test_glossary.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add devdemangle/glossary.py tests/test_glossary.py
git commit -m "feat: terms.yaml 용어집 로더 추가"
```

---

### Task 2: 보정 엔진 (`devdemangle/correct.py`)

**Files:**
- Create: `devdemangle/correct.py`
- Test: `tests/test_correct.py`

**Interfaces:**
- Consumes: `devdemangle.glossary.Term` (canonical: str, aliases: list[str]) — Task 1에서 정의됨
- Produces:
  - `Match` dataclass — `original: str`, `canonical: str`, `start: int`, `end: int`
  - `CorrectionResult` dataclass — `text: str`, `matches: list[Match]`
  - `build_automaton(terms: list[Term]) -> ahocorasick.Automaton`
  - `correct(text: str, terms: list[Term] | None = None) -> CorrectionResult`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_correct.py` 새로 작성:

```python
from devdemangle.correct import CorrectionResult, Match, correct
from devdemangle.glossary import Term

GITHUB = Term(canonical="GitHub", aliases=["깃허브", "깃헙"])
NPM_INSTALL = Term(canonical="npm install", aliases=["엔피엠 인스톨", "엠피엠 인스톨"])
README = Term(canonical="README", aliases=["리드미", "리드미 파일"])
BASE_TERMS = [GITHUB, NPM_INSTALL, README]


def test_single_token_alias_is_replaced():
    result = correct("깃허브 봤어요", terms=BASE_TERMS)
    assert result.text == "GitHub 봤어요"
    assert result.matches == [Match(original="깃허브", canonical="GitHub", start=0, end=3)]


def test_multi_token_alias_is_replaced():
    result = correct("엔피엠 인스톨 먼저 실행하세요", terms=BASE_TERMS)
    assert result.text == "npm install 먼저 실행하세요"
    assert result.matches == [
        Match(original="엔피엠 인스톨", canonical="npm install", start=0, end=7)
    ]


def test_text_without_alias_passes_through_unchanged():
    result = correct("오늘 날씨가 좋네요", terms=BASE_TERMS)
    assert result.text == "오늘 날씨가 좋네요"
    assert result.matches == []


def test_multiple_terms_in_one_sentence_keep_correct_offsets():
    result = correct("깃허브 리드미 봤어요", terms=BASE_TERMS)
    assert result.text == "GitHub README 봤어요"
    assert result.matches == [
        Match(original="깃허브", canonical="GitHub", start=0, end=3),
        Match(original="리드미", canonical="README", start=4, end=7),
    ]


def test_alias_followed_by_particle_is_not_replaced():
    """알려진 한계: 끝도 토큰 경계와 일치해야 하므로 조사가 바로 붙으면 미매칭."""
    result = correct("깃허브다", terms=BASE_TERMS)
    assert result.text == "깃허브다"
    assert result.matches == []


def test_longer_overlapping_alias_wins():
    short = Term(canonical="AAA", aliases=["가"])
    long = Term(canonical="BBB", aliases=["가 나"])
    result = correct("가 나 다", terms=[short, long])
    assert result.text == "BBB 다"
    assert result.matches == [Match(original="가 나", canonical="BBB", start=0, end=3)]


def test_empty_text_returns_empty_result():
    result = correct("", terms=BASE_TERMS)
    assert result == CorrectionResult(text="", matches=[])
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tests/test_correct.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'devdemangle.correct'`

- [ ] **Step 3: 구현 작성**

`devdemangle/correct.py` 새로 작성:

```python
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
    우연히 걸리는 부분 매칭은 제외). terms 생략 시 기본 용어집(data/terms.yaml)을
    쓰고 자동자를 캐싱한다.
    """
    if not text:
        return CorrectionResult(text="", matches=[])

    automaton = build_automaton(terms) if terms is not None else _default_automaton()

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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest tests/test_correct.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: 커밋**

```bash
git add devdemangle/correct.py tests/test_correct.py
git commit -m "feat: Aho-Corasick 기반 용어 보정 엔진 추가"
```

---

### Task 3: 패키지 공개 API (`devdemangle/__init__.py`)

**Files:**
- Modify: `devdemangle/__init__.py` (전체 내용 교체)
- Test: `tests/test_correct.py` (Task 2 파일에 통합 테스트 1개 추가)

**Interfaces:**
- Consumes: `devdemangle.glossary.{Term, load_glossary}` (Task 1), `devdemangle.correct.{Match, CorrectionResult, correct}` (Task 2)
- Produces: `devdemangle` 패키지 최상위에서 `correct`, `load_glossary`, `Term`, `Match`, `CorrectionResult` import 가능

- [ ] **Step 1: 실패하는 통합 테스트 작성**

`tests/test_correct.py` 끝에 추가:

```python
def test_default_glossary_corrects_known_alias():
    """terms 인자 없이 기본 용어집(data/terms.yaml)으로 동작하는지 확인."""
    from devdemangle import correct as public_correct

    result = public_correct("파이썬 좋아해요")
    assert result.text == "Python 좋아해요"
    assert result.matches[0].canonical == "Python"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tests/test_correct.py::test_default_glossary_corrects_known_alias -v`
Expected: FAIL — `ImportError: cannot import name 'correct' from 'devdemangle'`

- [ ] **Step 3: `devdemangle/__init__.py` 교체**

기존 내용:

```python
"""DevDemangle - 음성인식·번역이 뭉갠 개발 용어를 되돌린다."""

__version__ = "0.1.0"
```

교체 후:

```python
"""DevDemangle - 음성인식·번역이 뭉갠 개발 용어를 되돌린다."""

from devdemangle.correct import CorrectionResult, Match, correct
from devdemangle.glossary import Term, load_glossary

__version__ = "0.1.0"

__all__ = [
    "CorrectionResult",
    "Match",
    "Term",
    "correct",
    "load_glossary",
]
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest tests/test_correct.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 전체 테스트 스위트 실행 → 회귀 확인**

Run: `uv run pytest -v`
Expected: 기존 `tests/test_terms_yaml.py`, `tests/test_cuda.py` 포함 전체 PASS (GPU 없는 환경이면 `test_cuda.py`는 원래도 실패/스킵 대상이었는지 먼저 확인 — 이번 변경과 무관한 실패면 무시)

- [ ] **Step 6: 커밋**

```bash
git add devdemangle/__init__.py tests/test_correct.py
git commit -m "feat: devdemangle 패키지 공개 API에 correct/load_glossary 노출"
```
