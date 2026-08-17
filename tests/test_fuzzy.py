"""소리 유사도 기반 용어 탐지 테스트.

용어집에 **등록되지 않은** 발음 변형을 잡는 것이 목적이다.
등록된 별칭은 exact 탐지가 먼저 잡으므로 여기 오지 않는다.
"""

from devdemangle.fuzzy import fuzzy_detect
from devdemangle.glossary import Glossary
from devdemangle.types import Method, Term


def test_finds_unregistered_variant_by_sound():
    """용어집에 없는 변형을 등록 별칭과의 소리 유사도로 찾는다.

    "파일선"은 용어집에 없지만 별칭 "파이썬"과 소리가 가깝다(0.93).
    이게 이 모듈의 존재 이유다 — 사전에 없는 걸 잡는다.
    """
    glossary = Glossary([Term("Python", ("파이썬",))])

    matches = fuzzy_detect("파일선 스크립트 짰어요", glossary)

    assert len(matches) == 1
    assert matches[0].term == "Python"
    assert matches[0].matched == "파일선"


def test_skips_tokens_whose_sound_key_is_too_short():
    """소리 키가 짧은 토큰은 아예 보지 않는다.

    "뷰"는 별칭 "브이유"와 0.86이라 임계값으로는 못 막는다. 그런데 화면·전망을 뜻하는
    일상어라 잡으면 오탐이다. 짧은 음차는 유사도 밖의 조건으로 걸러야 한다.
    """
    glossary = Glossary([Term("Vue", ("브이유",))])

    assert fuzzy_detect("뷰 컴포넌트를 만들어요", glossary) == []


def test_compares_against_aliases_not_canonical():
    """비교 대상은 표준형이 아니라 한글 별칭이다.

    "리듬이"는 영문 "README"와 재면 0.55라 임계값에 못 미치지만,
    별칭 "리드미"와는 1.00이다. 한국어 음차는 한국어끼리 대야 한다.
    """
    with_alias = Glossary([Term("README", ("리드미",))])
    without_alias = Glossary([Term("README")])

    assert fuzzy_detect("리듬이 수정했어요", with_alias)[0].term == "README"
    assert fuzzy_detect("리듬이 수정했어요", without_alias) == []


def test_records_method_and_real_similarity():
    """method는 FUZZY, confidence는 실제로 잰 유사도다.

    exact·regex의 confidence는 측정값이 아니라 라벨이지만, fuzzy만은 잰 값이다.
    겹침 해소에서 fuzzy끼리 비교될 때 이 값이 실제로 쓰인다.

    (소리 키가 완전히 같아지면 1.00이 나온다 — "독커"/"도커"가 그렇다.
     여기서는 측정값임이 드러나도록 부분 일치 쌍을 쓴다.)
    """
    glossary = Glossary([Term("Python", ("파이썬",))])

    match = fuzzy_detect("파일선 스크립트", glossary)[0]

    assert match.method == Method.FUZZY
    assert 0.75 <= match.confidence < 1.0


def test_reports_offsets_of_the_input_text():
    """start/end는 입력 텍스트 기준이다 — 그 구간을 자르면 matched가 나온다."""
    glossary = Glossary([Term("Python", ("파이썬",))])
    text = "어제 파일선 썼어요"

    match = fuzzy_detect(text, glossary)[0]

    assert text[match.start : match.end] == match.matched


# --- 실측 기반 회귀 ---
#
# 아래 두 벌은 1주차 녹음의 실제 전사에서 나온 것이다. 임계값 0.75가 이 표본에서
# 정답 10건을 살리고 오탐 0건을 통과시킨다는 것이 이 모듈을 이 값으로 고정한 근거다.

_GLOSSARY = Glossary([
    Term("README", ("리드미",)),
    Term("repository", ("리포지토리",)),
    Term("Python", ("파이썬",)),
    Term("TypeScript", ("타입스크립트",)),
    Term("git commit", ("깃 커밋",)),
    Term("GitHub", ("깃허브",)),
    Term("FastAPI", ("패스트API",)),
    Term("Docker", ("독커",)),
    Term("pull request", ("풀리퀘스트",)),
])

# STT가 실제로 뱉은 변형 → 되돌려야 할 표준형
_MEASURED_VARIANTS = [
    ("리듬이", "README"),
    ("리포지터리", "repository"),
    ("파일선", "Python"),
    ("타입스트리트", "TypeScript"),
    ("기터벳", "GitHub"),
    ("도커", "Docker"),
]

# 전사문에서 뽑은, 용어가 아닌 어절. 하나도 잡히면 안 된다.
_NON_TERMS = ["파일은", "있어요", "뒀어요", "한번", "컴포넌트를", "그리고", "지금", "다시"]


def test_recovers_measured_variants():
    """실측 변형을 표준형으로 되돌린다."""
    for variant, canonical in _MEASURED_VARIANTS:
        matches = fuzzy_detect(variant, _GLOSSARY)
        assert matches, f"{variant} → 아무것도 못 찾음"
        assert matches[0].term == canonical, f"{variant} → {matches[0].term}"


def test_does_not_fire_on_non_terms():
    """용어가 아닌 어절에는 반응하지 않는다.

    "파일은"이 "파이썬"과 0.67로 가장 위험하다. 임계값을 0.65로 낮추면 여기가 먼저 터진다.
    """
    for token in _NON_TERMS:
        assert fuzzy_detect(token, _GLOSSARY) == [], f"{token}에서 오탐"


# --- 실제 용어집 기반 회귀 ---
#
# 위 축소 용어집과 달리 배포되는 용어집 전체를 쓴다. 별칭이 늘면 오탐 표면도 같이
# 넓어지기 때문에, 용어집을 고쳤을 때 여기서 걸리게 해둔다.


def _real_glossary() -> Glossary:
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    return Glossary.from_yaml(root / "data" / "terms.yaml")


def test_real_glossary_does_not_fire_on_common_words():
    """배포 용어집으로도 일상 어절에 반응하지 않는다.

    "파일은"은 별칭 "파일선"(Python 실측 변형)이 등록되면서 0.67 → 0.77로 올랐다.
    **별칭을 추가하면 재현율은 오르지만 오탐 표면도 같이 넓어진다** — 이 테스트가 그 경계다.
    """
    glossary = _real_glossary()

    for token in ["파일은", "있어요", "뒀어요", "한번", "그대로인가", "재시작할게"]:
        assert fuzzy_detect(token, glossary) == [], f"{token}에서 오탐"


def test_recovers_variants_that_are_not_registered():
    """별칭에 없는 변형도 소리로 잡는다 — 이 모듈의 존재 이유.

    각 변형을 별칭에서 빼고(미등록 상황) 잡히는지 본다. 등록된 채로 재면
    정확 매칭을 재는 셈이라 퍼지 성능이 안 나온다.
    """
    from devdemangle.types import Term

    full = _real_glossary()

    for variant, canonical in [
        ("리듬이", "README"),
        ("리포지터리", "repository"),
        ("파일선", "Python"),
        ("타입스트리트", "TypeScript"),
        ("기터벳", "GitHub"),
    ]:
        unregistered = Glossary([
            Term(t.canonical, tuple(a for a in t.aliases if a != variant), t.translations)
            for t in full
        ])
        matches = fuzzy_detect(variant, unregistered)
        assert any(m.term == canonical for m in matches), f"{variant} → {canonical} 실패"


def test_known_limit_multiword_terms_are_missed():
    """⚠️ 알려진 한계 — 어절 하나씩만 본다.

    실측 변형 중 "Git 커뮤니타"(git commit)와 "베스트 API"(FastAPI)는 두 어절이라
    통째로 비교되지 않는다. 어절을 넘는 윈도우를 넣으면 잡히지만 오탐 면적이 함께 커진다.

    이 테스트는 **현재 동작을 고정**한다. 윈도우를 넣게 되면 여기가 먼저 깨져서
    "의도한 변경"임을 확인하게 된다.
    """
    glossary = Glossary([Term("FastAPI", ("패스트API",))])

    assert fuzzy_detect("베스트 API 서버 열었어", glossary) == []
