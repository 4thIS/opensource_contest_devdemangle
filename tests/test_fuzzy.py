"""소리 유사도 기반 용어 탐지 테스트.

용어집에 **등록되지 않은** 발음 변형을 잡는 것이 목적이다.
등록된 별칭은 exact 탐지가 먼저 잡으므로 여기 오지 않는다.
"""

import pytest

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
# 아래 두 벌은 1주차 녹음의 실제 전사에서 나온 것이다. 임계값 0.78이 이 표본에서
# 정답 6건을 살리고 오탐 0건을 통과시킨다는 것이 이 모듈을 이 값으로 고정한 근거다.
#
# 여기 두 벌은 꼬리를 뗀 맨몸 형태다. 조사·문장부호가 붙은 실문장 형태는 아래
# "조사·문장부호 꼬리" 절에서 따로 다룬다 — 안전 구간은 그쪽 기준으로 잡혀 있다.

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

    "라디오"·"다시는"·"다시마"는 lodash 별칭("라다시"·"로다시")이 들어오면서 0.727까지
    올라온 것들이다. 임계값과 0.05 차이라 "라-다-시" 꼴 별칭을 더 넣으면 여기가 먼저 넘는다.
    """
    glossary = _real_glossary()

    for token in ["파일은", "있어요", "뒀어요", "한번", "그대로인가", "재시작할게",
                  "라디오", "다시는", "다시마"]:
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

# --- 조사·문장부호 꼬리 ---
#
# 실측 전사는 용어를 맨몸으로 뱉지 않는다. "기터벳의"처럼 조사가 붙고, 21문장 중 17개에
# 마침표가 붙는다. 꼬리는 소리 키에 그대로 섞여 들어가 점수를 0.05~0.17 깎는데,
# 임계값 여유는 0.02였다. 즉 맨몸으로 잰 임계값은 실문장에서 성립하지 않는다.


def test_finds_term_that_carries_a_particle():
    """조사가 붙어도 찾는다.

    "기터벳의"는 실측 전사에 있는 형태다. 통째로 재면 0.706이라 임계값에 못 미쳐
    후보로 나오지도 않는다. 조사를 뗀 "기터벳"으로 재야 0.800이 나온다.
    """
    glossary = Glossary([Term("GitHub", ("깃허브",))])

    matches = fuzzy_detect("기터벳의 리포지토리 만들었어?", glossary)

    assert [m.term for m in matches] == ["GitHub"]


def test_excludes_the_particle_from_the_matched_span():
    """조사는 매치 구간 밖에 둔다.

    구간이 조사까지 덮으면 치환할 때 조사가 같이 사라진다("도커를 배포했어요" →
    "Docker 배포했어요"). 정확 탐지는 조사를 떼고 구간을 잡으므로, 겹침 해소에서
    길이가 긴 퍼지 쪽이 이겨 그 결과를 덮어쓴다.
    """
    glossary = Glossary([Term("Docker", ("도커",))])
    text = "도커를 배포했어요"

    match = fuzzy_detect(text, glossary)[0]

    assert match.matched == "도커"
    assert text[match.start : match.end] == "도커"


def test_finds_term_that_carries_a_particle_and_punctuation():
    """조사와 문장부호가 함께 붙어도 찾는다 — Whisper가 마침표를 붙인다."""
    glossary = Glossary([Term("GitHub", ("깃허브",))])

    assert [m.term for m in fuzzy_detect("기터벳의.", glossary)] == ["GitHub"]


def test_keeps_variants_that_merely_look_like_they_end_in_a_particle():
    """조사 모양으로 끝나는 변형을 조사 분리가 잡아먹지 않는다.

    "리듬이"는 README의 실측 변형인데 "이"가 조사라 분리 대상으로 보인다. 떼면
    "리듬"이 되어 소리 키가 짧아져 후보에서 아예 빠진다(1.00 → 0.00).

    **떼기만 하는 구현에서 이 테스트가 깨진다.** 꼬리를 뗀 형태와 안 뗀 형태를
    모두 재고 높은 쪽을 쓰는 것이 이 테스트를 통과하는 이유다.
    """
    glossary = Glossary([Term("README", ("리드미",))])

    match = fuzzy_detect("리듬이 수정했어요", glossary)[0]

    assert match.term == "README"
    assert match.matched == "리듬이"

def test_strips_the_whole_particle_when_scores_tie():
    """두 글자 조사를 반만 떼고 멈추지 않는다.

    "파일선으로"는 "파일선"과 "파일선으" 둘 다 조사를 뗀 형태로 성립하고,
    소리 키가 같아져 **점수가 0.933으로 동점**이다. 덜 깎인 쪽이 이기면
    "으"가 구간에 남아 치환 결과가 "Python로"가 된다.

    동점이면 많이 뗀 쪽을 쓴다 — 조사를 반만 남길 이유가 없다.
    """
    glossary = Glossary([Term("Python", ("파이썬",))])

    match = fuzzy_detect("파일선으로 작성했어", glossary)[0]

    assert match.matched == "파일선"



# --- 이미 잡힌 구간 ---


def test_skips_spans_that_are_already_detected():
    """이미 잡힌 자리는 다시 보지 않는다.

    등록 별칭은 소리로도 자기 자신과 1.00이라, 걸러내지 않으면 같은 자리에
    후보가 둘 생긴다. 방어를 겹침 해소 하나에만 맡기게 되는데, 그 해소는
    **겹치는 것끼리만** 작동한다.
    """
    from devdemangle.detect import detect

    glossary = Glossary([Term("Docker", ("도커",))])
    text = "도커 재시작할게요"
    already = detect(text, glossary)

    assert fuzzy_detect(text, glossary, already) == []


def test_still_finds_variants_outside_detected_spans():
    """이미 잡힌 자리 밖은 그대로 본다."""
    from devdemangle.detect import detect

    glossary = Glossary([Term("Docker", ("도커",)), Term("Python", ("파이썬",))])
    text = "도커에 더커도 있어요"
    already = detect(text, glossary)

    found = fuzzy_detect(text, glossary, already)

    assert [m.matched for m in found] == ["더커"]


def test_default_threshold_is_exposed():
    """임계값 기본치를 부르는 쪽이 가져다 쓸 수 있다.

    보정 쪽이 이 값을 기본 인자로 노출하므로, 두 곳에 숫자를 적어두면 갈린다.
    """
    from devdemangle.fuzzy import DEFAULT_THRESHOLD

    assert 0 < DEFAULT_THRESHOLD < 1


# --- 길이 비율 ---
#
# 소리 탐지는 덩어리를 통째로 근사 비교한다. 별칭이 덩어리의 일부일 때
# ("우리"+"깃허브") 남는 글자는 점수를 조금 깎을 뿐 매치를 막지 못한다.
# 유사도만으로는 안 갈리고, 길이 비율로는 갈린다.


def _ratio_glossary():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    return Glossary.from_yaml(root / "data" / "terms.yaml")


@pytest.mark.xfail(
    strict=True,
    reason="정답과 오탐이 두 축 모두에서 겹친다 — 리듬이네와 도커피가 0.833/1.40으로 같다",
)
def test_known_limit_ending_fuses_with_registered_alias():
    """⚠️ 알려진 한계 — 어미가 붙은 등록 별칭은 되돌리지 못한다.

    2차 녹음 실측에서 "README에"가 "리듬이네"로 융합돼 나왔다. "리듬이"는 등록
    별칭인데 "네"가 조사 목록에 없어 정확 탐지가 막고, 소리 탐지는 길이 비율에
    걸린다.

    **상한을 올려서 풀 수 없다.** 오탐 "도커피"와 두 축이 소수점까지 같다.

        리듬이네 ~ 리드미   유사도 0.833   비율 1.40   정답
        도커피   ~ 독커     유사도 0.833   비율 1.40   오탐

    상한을 1.40까지 올리면 "도커피"가 그대로 따라 들어온다. 어미를 규칙에서 뺀
    판단의 비용이 처음으로 실측된 자리다. 그 판단을 다시 볼지는 서술격 표본이
    더 들어온 뒤에 정한다.
    """
    glossary = _ratio_glossary()

    assert [m.term for m in fuzzy_detect("문서는 리듬이네", glossary)] == ["README"]


def test_rejects_chunks_much_longer_than_the_alias():
    """별칭보다 지나치게 긴 덩어리는 버린다.

    셋 다 어절 맨 앞에서 시작하고 전부 한글이라, 시작 경계도 덩어리 제한도
    막지 못한다. 유사도는 0.82~0.88로 임계값을 넘는다.
    """
    glossary = _ratio_glossary()

    for chunk in ["우리깃허브", "깃허브다", "도커피"]:
        assert fuzzy_detect(chunk, glossary) == [], f"{chunk}에서 오탐"


def test_keeps_variants_that_are_slightly_longer():
    """조금 긴 것은 그대로 잡는다 — 정답 최대가 1.20이다."""
    glossary = _ratio_glossary()

    for chunk, expected in [("더커", "Docker"), ("도컬", "Docker"), ("라다쉬", "lodash")]:
        found = fuzzy_detect(chunk, glossary)
        assert found and found[0].term == expected, f"{chunk} → {expected} 실패"


def test_keeps_variants_shorter_than_the_alias():
    """별칭보다 짧은 정답이 있다 — 하한을 걸면 안 된다.

    "닷커"는 별칭 "닷컬"보다 짧아 비율이 0.86이다.
    """
    glossary = _ratio_glossary()

    found = fuzzy_detect("닷커 컨테이너", glossary)

    assert found and found[0].term == "Docker"


@pytest.mark.xfail(
    strict=True,
    reason="파일럿이 별칭 파일선과 0.800 — 정답 최저와 같은 값이라 임계값으로 못 가른다",
)
def test_known_limit_pilot_is_mistaken_for_python():
    """⚠️ 알려진 한계 — 일상 외래어가 별칭과 소리로 겹친다.

    "파일럿"(pilot)이 Python의 실측 별칭 "파일선"과 0.800이다. 정답 최저인
    "기터벳의"와 **정확히 같은 값**이라 임계값을 올리면 정답이 먼저 죽고,
    길이 비율도 0.88이라 안 걸린다. 동음이의 계열과 같은 구조다.

    용어집에 `Copilot`이 들어오면 "파일럿"은 그쪽과 0.875로 더 가까워져
    Python 대신 Copilot으로 붙는다. **오탐이 사라지는 게 아니라 더 그럴듯한
    쪽으로 옮겨간다** — 개발 대화에서 "파일럿"은 Copilot일 가능성이 높다.
    """
    glossary = _real_glossary()

    assert fuzzy_detect("파일럿에서 발견", glossary) == []
