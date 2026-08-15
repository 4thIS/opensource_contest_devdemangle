# 용어 보정 모듈 설계

날짜: 2026-08-02
상태: 승인됨

## 배경

DevDemangle은 음성인식·번역이 뭉갠 개발 용어를 표준형으로 되돌리는 라이브러리다.
1주차에 완료된 실험(`experiments/results/risk1.md`, `risk2.md`, `risk2b.md`)으로
STT hotwords 효과(+39.1%p)와 번역 플레이스홀더 방식(TERMZERO, 생존율 100%)이
검증됐지만, 실제 프로덕션 코드는 아직 없다 (`devdemangle/__init__.py`는 버전 스텁뿐).

이 스펙은 파이프라인의 첫 구현 단위인 **용어 보정 모듈**을 다룬다. STT가 뱉은
한국어 문장에서 `data/terms.yaml`에 등록된 별칭(alias)을 찾아 표준형(canonical)으로
치환하는 기능이다.

```
"라다시 디바운스 써서 처리했어요"  →  "lodash debounce 써서 처리했어요"
```

STT(hotwords)와 번역 보호(TERMZERO)는 스코프 밖이며, 이후 별도 스펙으로 다룬다.

## 스코프

- 포함: `data/terms.yaml`의 aliases를 정확 매칭으로 canonical에 교체하는 모듈과 테스트
- 제외: 퍼지(편집거리) 매칭, STT 연동, 번역 연동, hotwords 선별
  - 이유: aliases에 등록되지 않은 변형(예: Python→"파일선")까지 잡으려면 오탐 위험
    측정이 필요하다. 1차는 정확 매칭만으로 안전하게 간다 (아래 "결정 사항" 참고)

## 결정 사항 (브레인스토밍에서 확정)

1. **매칭 전략**: Aho-Corasick 정확 매칭만. 퍼지 매칭은 다음 이터레이션.
2. **매칭 단위**: 공백 기준 토큰 경계. alias는 토큰 경계에서 시작·끝나야 매칭된다
   (문자열 중간에 우연히 걸리는 것 방지).
3. **출력 형태**: 보정된 문자열 + 변경 내역 리스트(원문, canonical, 위치).

## 아키텍처

신규 모듈 2개를 `devdemangle/` 아래 추가한다. 기존 `_cuda.py`는 건드리지 않는다.

```
devdemangle/
  __init__.py     # correct, load_glossary, Term, Match, CorrectionResult export 추가
  glossary.py     # 신규 — terms.yaml 로딩
  correct.py      # 신규 — Aho-Corasick 보정
  _cuda.py        # 기존, 무변경
```

### `devdemangle/glossary.py`

```python
@dataclass
class Term:
    canonical: str
    aliases: list[str]
    translations: dict[str, str] | None = None

def load_glossary(path: Path | None = None) -> list[Term]:
    """data/terms.yaml을 읽어 Term 리스트로 반환한다.
    path 생략 시 패키지 기준 기본 위치(data/terms.yaml)를 쓴다."""
```

스키마 검증(중복 canonical, alias 충돌 등)은 이미 `tests/test_terms_yaml.py`가
하고 있으므로 이 함수에서 재검증하지 않는다. YAML 파싱 실패 시 예외는 그대로
전파한다.

### `devdemangle/correct.py`

```python
@dataclass
class Match:
    original: str      # 매칭된 원문 조각
    canonical: str      # 교체된 표준형
    start: int           # 원문 문자열 내 시작 offset
    end: int              # 끝 offset (exclusive)

@dataclass
class CorrectionResult:
    text: str            # 보정된 문자열
    matches: list[Match]

def build_automaton(terms: list[Term]) -> ahocorasick.Automaton:
    """모든 alias를 키로 등록. value는 (alias, canonical)."""

def correct(text: str, terms: list[Term] | None = None) -> CorrectionResult:
    """terms 생략 시 load_glossary()로 기본 용어집을 로드한다.
    build_automaton은 매 호출마다 새로 만들지 않고 terms 인자가 없을 때
    기본 자동자를 모듈 레벨에서 캐싱한다 (lru_cache)."""
```

## 데이터 흐름 (`correct()` 내부)

1. 토큰화: 텍스트를 공백 기준으로 분리하면서 각 토큰의 `(start, end)` 문자 offset을
   같이 기록한다.
2. 스캔: `automaton.iter(text)`로 텍스트 전체에서 모든 alias 후보 매칭을 얻는다
   (문자열 아무 위치나 걸리는 원시 매칭).
3. 경계 필터: 각 후보 매칭의 시작 offset이 어떤 토큰의 시작과, 끝 offset이 그
   토큰(또는 연속 토큰들, 다단어 alias의 경우)의 끝과 정확히 일치하는 것만 남긴다.
4. 겹침 해소: 남은 매칭을 시작 offset 기준으로 정렬하고, 왼쪽부터 그리디하게
   채택한다. 같은 시작 위치에 여러 후보가 있으면 더 긴 alias를 우선한다. 이미
   채택된 매칭과 구간이 겹치는 후보는 버린다.
5. 치환: 채택된 매칭들을 뒤에서 앞으로(offset이 밀리지 않도록) canonical로
   문자열 치환하고, `Match` 리스트를 구성해 반환한다.

## 에러 처리

- `terms.yaml`이 없거나 파싱 실패 → `load_glossary()`가 예외를 그대로 던진다.
  이 모듈은 잡지 않는다 (호출부가 원인을 알아야 하므로).
- alias가 하나도 없는 텍스트 → 원문 그대로, `matches=[]`.
- 빈 문자열 입력 → `CorrectionResult(text="", matches=[])`.

## 알려진 한계 (v1)

- 토큰에 붙은 구두점(`"뷰,"`, `"Docker."` 등)은 토큰 경계가 정확히 안 맞아
  매칭에 실패한다. 구두점 스트리핑은 다음 이터레이션 대상.
- `data/terms.yaml`에 없는 변형(퍼지 매칭 대상, 예: Python→"파일선")은 이
  모듈의 스코프가 아니다.

## 테스트 (`tests/test_correct.py`, 신규)

- terms.yaml의 실제 alias로 단일 토큰 보정 (예: "깃허브" → "GitHub")
- 다단어 alias 보정 (예: "엔피엠 인스톨" → "npm install", 토큰 2개 소비)
- alias가 없는 문장은 원문 그대로 통과
- 한 문장에 용어 2개 이상 동시 보정 (offset이 밀리지 않는지 확인)
- 토큰 경계를 벗어난 부분 매칭은 교체되지 않음 (예: alias가 다른 단어 중간에
  우연히 포함된 경우)
- `matches`에 원문·canonical·위치가 정확히 기록되는지
