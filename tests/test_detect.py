"""탐지 — 등록 용어(Aho-Corasick)와 미등록 식별자(정규식)를 찾는다."""

from pathlib import Path

import pytest

from devdemangle import Glossary, Match, Method, Term
from devdemangle.detect import detect, is_particle_tail, resolve_overlaps

TERMS = Path(__file__).resolve().parent.parent / "data" / "terms.yaml"


@pytest.fixture
def glossary() -> Glossary:
    return Glossary([Term(canonical="Docker", aliases=("도커",))])


@pytest.fixture(scope="module")
def seed_glossary() -> Glossary:
    return Glossary.from_yaml(TERMS)


def test_finds_canonical_term(glossary):
    """표준형이 그대로 있으면 찾는다."""
    assert detect("Docker 재시작할게", glossary) == [
        Match(0, 6, "Docker", "Docker", Method.EXACT, 1.0)
    ]


def test_alias_reports_canonical_but_keeps_matched_text(glossary):
    """별칭을 찾으면 term은 표준형, matched는 입력에 있던 글자 그대로다.

    보정은 term으로 갈아끼우고, matched는 "무엇이 깨져 있었는지"를 남기는 값이다.
    """
    assert detect("도커 재시작할게", glossary) == [
        Match(0, 2, "Docker", "도커", Method.EXACT, 1.0)
    ]


def test_ignores_match_starting_mid_token(glossary):
    """토큰 중간에서 시작하는 매치는 버린다.

    "윈도커널"의 1~3번째 글자가 "도커"다. 시작 경계를 안 보면 이런 게 다 걸린다.
    """
    assert detect("윈도커널 문제야", glossary) == []


def test_ignores_match_with_unknown_tail(glossary):
    """뒤에 남는 꼬리가 조사가 아니면 버린다.

    "Dockerfile"은 Docker가 아니라 그 자체로 다른 이름이다.
    """
    assert detect("Dockerfile 수정했어", glossary) == []


def test_allows_particle_tail(glossary):
    """꼬리가 조사면 통과시키고, 매치는 조사를 뺀 구간이다.

    한국어는 조사가 붙어 한 어절이 된다. 이걸 안 보면 실측 전사에서
    "Docker를"·"리액트랑" 같은 게 통째로 안 잡힌다.
    """
    assert detect("도커를 재시작할게", glossary) == [
        Match(0, 2, "Docker", "도커", Method.EXACT, 1.0)
    ]


def test_matches_ignoring_case():
    """대소문자는 무시한다.

    실측 전사에 "sql 문을"·"vs 코드로"처럼 소문자로 나온 게 있다.
    같은 글자를 다르게 적었을 뿐이라 탐지가 받아야 한다.
    """
    glossary = Glossary([Term(canonical="SQL")])
    assert detect("sql 문을 수정해야 합니다", glossary) == [
        Match(0, 3, "SQL", "sql", Method.EXACT, 1.0)
    ]


@pytest.mark.parametrize("tail", ["에서는", "로도", "까지는", "부터는", "에도", "보다는"])
def test_allows_stacked_particles(glossary, tail):
    """조사는 겹쳐 붙는다. 결합형을 하나씩 나열하면 목록이 곱셈으로 커진다.

    격조사 뒤에 보조사가 오는 게 기본형이고, 보조사끼리도 겹친다("까지는").
    """
    assert detect(f"도커{tail} 그래요", glossary) == [
        Match(0, 2, "Docker", "도커", Method.EXACT, 1.0)
    ]


@pytest.mark.parametrize(
    "tail,is_particle",
    [
        ("를", True),
        ("에서", True),
        ("에서는", True),
        ("에서의", True),
        ("컴포넌트", False),
        ("했어요", False),
        ("입니다", False),
    ],
)
def test_particle_tail_predicate_is_public(tail, is_particle):
    """조사 판정은 detect 밖에서도 부른다 — 퍼지 탐지가 같은 경계를 써야 한다.

    detect()를 거쳐서만 확인하면 판정 자체의 계약이 안 드러난다. 밖에서
    쓰는 함수가 됐으니 여기서 직접 고정한다.
    """
    assert is_particle_tail(tail) is is_particle


@pytest.mark.parametrize("tail", ["", "에서만의"])
def test_particle_tail_predicate_rejects_at_its_edges(tail):
    """부르는 쪽이 걸리기 쉬운 두 자리를 못 박아 둔다.

    빈 꼬리는 False다. 조사가 아니라 "조사가 없다"는 뜻이라 판정 대상이 아닌데,
    어절을 잘라가며 부르는 쪽에서는 꼬리 없는 경우가 먼저 나온다. detect()는
    그 갈래를 부르기 전에 따로 처리한다.

    조사 세 개는 받지 않는다. 목록을 층으로 나누는 대신 낱개 두 개까지로
    단순화하면서 "에서만의"가 밖으로 나갔다. 실측에 없어 그대로 뒀다.
    """
    assert is_particle_tail(tail) is False


def test_finds_unregistered_identifier_by_regex(glossary):
    """용어집에 없어도 식별자 모양이면 찾는다.

    번역·보정이 식별자를 건드리면 코드가 깨진다. 용어집을 100개로 늘려도
    남의 프로젝트 이름까지 담을 수는 없어서, 모양으로 잡는 경로가 따로 있다.
    term은 표준형이 없으므로 matched와 같다.
    """
    assert detect("reactRouter 수정했어", glossary) == [
        Match(0, 11, "reactRouter", "reactRouter", Method.REGEX, 0.8)
    ]


@pytest.mark.parametrize(
    "identifier,rest",
    [
        ("user_id", " 컬럼 추가했어"),
        ("--no-cache", " 옵션 줬어"),
        ("-v", " 붙여서 돌려봐"),
    ],
)
def test_regex_also_finds_snake_case_and_flags(glossary, identifier, rest):
    """식별자 모양은 camelCase만이 아니다. snake_case와 명령행 플래그도 같다."""
    assert detect(identifier + rest, glossary) == [
        Match(0, len(identifier), identifier, identifier, Method.REGEX, 0.8)
    ]


@pytest.mark.parametrize(
    "identifier,tail",
    [
        ("--no-cache", "를"),
        ("--force", "로"),
        ("-v", "도"),
        ("user_id", "를"),
        ("reactRouter", "에서"),
    ],
)
def test_regex_does_not_swallow_particles(glossary, identifier, tail):
    """식별자 바로 뒤에 조사가 붙어도 식별자까지만 잡는다.

    조사를 물고 들어가면 term이 "--no-cache를"이 되어 번역 보호에서 조사가
    영어 문장으로 딸려 나간다. 등록 용어 쪽은 꼬리를 떼는데 정규식 쪽만
    삼키면 같은 문장에서 두 경로가 다르게 동작한다.
    """
    assert detect(identifier + tail, glossary) == [
        Match(0, len(identifier), identifier, identifier, Method.REGEX, 0.8)
    ]


def test_keeps_overlapping_matches():
    """겹치는 후보를 골라내지 않고 전부 내보낸다.

    고르는 건 resolve_overlaps가 한다. 탐지가 미리 정리하면 나중에 합쳐지는
    퍼지 후보와 다시 겨룰 때 이미 버린 것을 되살릴 수 없다.
    """
    glossary = Glossary([Term(canonical="README", aliases=("리드미", "리드미 파일"))])

    found = detect("리드미 파일 수정해 뒀어요", glossary)

    assert {(m.start, m.end) for m in found} == {(0, 3), (0, 6)}


def test_matches_are_sorted_by_position():
    """긴 것이 앞에 오도록 위치 순으로 정렬해 내보낸다.

    겹치는 후보가 나란히 붙어 있어야 보정 쪽에서 묶어 보기 쉽다.
    """
    glossary = Glossary([Term(canonical="README", aliases=("리드미", "리드미 파일"))])

    found = detect("리드미 파일 수정해 뒀어요", glossary)

    assert [(m.start, m.end) for m in found] == [(0, 6), (0, 3)]


def _m(start, end, method=Method.EXACT, confidence=1.0, term="X"):
    """겹침 규칙만 보는 테스트용 Match. 여기서 중요한 건 좌표·method·신뢰도뿐이다."""
    return Match(start, end, term, term, method, confidence)


def test_resolve_keeps_the_longer_match():
    """method가 같으면 긴 쪽이 남는다. "npm install"과 "npm"은 둘 다 등록 용어다."""
    matches = [_m(0, 11, term="npm install"), _m(0, 3, term="npm")]

    assert resolve_overlaps(matches) == [_m(0, 11, term="npm install")]


def test_resolve_prefers_exact_over_regex_at_same_length():
    """등록 용어가 정규식보다 앞선다. 길이가 같아 method만으로 갈리는 경우다."""
    matches = [
        _m(0, 7, Method.REGEX, 0.8),
        _m(0, 7, Method.EXACT, 1.0),
    ]

    assert resolve_overlaps(matches) == [_m(0, 7, Method.EXACT, 1.0)]


def test_resolve_prefers_higher_confidence_within_same_method():
    """길이도 method도 같으면 신뢰도를 본다.

    퍼지끼리 겹칠 때만 갈리는 경우다 — exact는 전부 1.0이라 여기까지 안 온다.
    """
    matches = [
        _m(0, 3, Method.FUZZY, 0.72, term="Docker"),
        _m(0, 3, Method.FUZZY, 0.91, term="React"),
    ]

    assert resolve_overlaps(matches) == [_m(0, 3, Method.FUZZY, 0.91, term="React")]


def test_resolve_prefers_earlier_position_when_otherwise_tied():
    """앞의 셋이 모두 같으면 앞쪽을 남긴다. 순서가 입력에 좌우되면 안 된다."""
    matches = [_m(4, 7, term="B"), _m(2, 5, term="A")]

    assert resolve_overlaps(matches) == [_m(2, 5, term="A")]


def test_resolve_keeps_matches_that_do_not_overlap():
    """겹치지 않으면 아무것도 버리지 않는다. 맞닿기만 한 것도 겹침이 아니다."""
    matches = [_m(0, 3, term="A"), _m(3, 6, term="B"), _m(9, 12, term="C")]

    assert resolve_overlaps(matches) == matches


def test_resolve_returns_start_ascending():
    """돌려주는 순서는 위치 오름차순이다.

    고를 때는 method·길이 순으로 보지만 그 순서가 결과에 새어나오면 안 된다.
    """
    matches = [_m(8, 11, term="C"), _m(0, 5, term="A"), _m(6, 7, term="B")]

    assert [m.start for m in resolve_overlaps(matches)] == [0, 6, 8]


def test_resolve_drops_everything_that_overlaps_the_winner():
    """이긴 매치와 겹치는 건 전부 버린다. 진 것들끼리 다시 살아나지 않는다."""
    matches = [_m(0, 10, term="long"), _m(0, 3, term="a"), _m(7, 10, term="b")]

    assert resolve_overlaps(matches) == [_m(0, 10, term="long")]


def test_resolve_on_empty_list():
    """탐지 결과가 비면 빈 목록이다. 용어집이 비었을 때 이 경로로 들어온다."""
    assert resolve_overlaps([]) == []


def test_resolve_after_detect_leaves_one_match_per_position():
    """탐지 → 해소를 실제로 이어 붙인다.

    detect가 "리드미"와 "리드미 파일"을 둘 다 내보내고 해소가 긴 쪽을 남긴다.
    """
    glossary = Glossary([Term(canonical="README", aliases=("리드미", "리드미 파일"))])

    resolved = resolve_overlaps(detect("리드미 파일 수정해 뒀어요", glossary))

    assert [(m.start, m.end) for m in resolved] == [(0, 6)]


def test_empty_glossary_still_finds_identifiers():
    """용어집이 비어도 정규식 경로는 살아 있어야 한다.

    Aho-Corasick은 패턴이 하나도 없을 때 만들어지지 않는다. 그걸 안 막으면
    용어집 없이 식별자만 보호하려는 사용이 통째로 죽는다.
    """
    assert detect("reactRouter 수정했어", Glossary([])) == [
        Match(0, 11, "reactRouter", "reactRouter", Method.REGEX, 0.8)
    ]


# 리스크 1 녹음에서 STT가 실제로 뱉은 문장 → 그 문장에서 나와야 할 표준형.
# 전부 조사나 문장부호가 붙어 있어서, 어절이 정확히 일치할 때만 잡는 방식으로는
# 통째로 놓치던 것들이다. 규칙이 후퇴하면 여기가 먼저 깨진다.
MEASURED_SENTENCES = [
    ("console.log를 한번 확인해볼게요", {"console.log"}),
    ("리액트랑 타입스트리트 같이 쓰고 있어요", {"React", "TypeScript"}),
    ("Docker를 배포했어요", {"Docker"}),
    ("파일선으로 작성했어", {"Python"}),
    ("로컬 호스트로 들어가면 돼요", {"localhost"}),
    ("sql 문을 수정해야 합니다", {"SQL"}),
    ("재시작할게 도커.", {"Docker"}),
    ("이거 리듬이?", {"README"}),
    ("GitHub에서의 리포지터리 만들었어.", {"GitHub", "repository"}),
    ("npm install부터 진행해야지.", {"npm install"}),
    ("타입 스트릿을 같이 쓰고 있어요.", {"TypeScript"}),
    ("Git 커뮤니타가 걸렸어요.", {"git commit"}),
]


@pytest.mark.parametrize("sentence,expected", MEASURED_SENTENCES)
def test_finds_terms_in_measured_transcripts(seed_glossary, sentence, expected):
    """실측 전사문에서 용어를 찾는다."""
    found = {m.term for m in detect(sentence, seed_glossary) if m.method is Method.EXACT}
    assert expected <= found


def test_finds_terms_in_readme_headline_example(seed_glossary):
    """README 첫 화면에 적힌 대표 예시가 실제로 동작한다.

    바깥에 내건 예시가 안 되면 그게 제일 먼저 들키는 자리다.
    실측 전사와 달리 이건 우리가 내세운 목표라, 위 목록과 섞지 않고 따로 둔다.
    """
    found = {m.term for m in detect("라다시 디바운스 써서 처리했어요", seed_glossary)}
    assert {"lodash", "debounce"} <= found


# 용어가 문장 끝에 오는 문장. 1주차 코퍼스에는 이런 게 **한 건도 없어서**
# 녹음을 다시 해도 이 구간은 안 보인다. 손으로 써서 채운다.
# 시연 대본이 용어를 문장 끝에 두는 구성이라, 여기가 촬영에서 처음 터지면 늦는다.
SENTENCE_FINAL_FOUND = [
    ("배포에 쓰는 건 도커.", {"Docker"}),
    ("프론트는 전부 리액트", {"React"}),
    ("고친 건 리드미랑 리포지터리.", {"README", "repository"}),
    ("설정은 로컬 호스트에서만.", {"localhost"}),
    ("붙일 건 라다시?", {"lodash"}),
]

# 같은 자리인데 뒤에 서술격이 붙은 것. **일부러 안 잡는다.**
# "입니다"·"예요"는 조사가 아니라 어미라, 조사 목록에 넣으면 닫힌 집합이라는 전제가 깨진다.
# 넣을지는 오탐을 재고 정한다 — 그때 이 목록이 판단 근거가 된다.
SENTENCE_FINAL_NOT_FOUND = [
    ("컨테이너 도구는 도커입니다.", "Docker"),
    ("프레임워크는 리액트예요.", "React"),
    ("언어는 파일선이야.", "Python"),
    ("빌드는 타입스트리트거든요.", "TypeScript"),
]


@pytest.mark.parametrize("sentence,expected", SENTENCE_FINAL_FOUND)
def test_finds_terms_at_sentence_end(seed_glossary, sentence, expected):
    """용어가 문장 끝에 와도 찾는다."""
    found = {m.term for m in detect(sentence, seed_glossary) if m.method is Method.EXACT}
    assert expected <= found


@pytest.mark.parametrize("sentence,term", SENTENCE_FINAL_NOT_FOUND)
def test_predicate_ending_is_not_treated_as_particle(seed_glossary, sentence, term):
    """서술격이 붙으면 못 찾는다 — 알려진 한계이자 의도한 선택이다.

    이 테스트가 깨진다면 누군가 조사 목록에 어미를 넣은 것이다.
    그 자체가 틀렸다는 게 아니라, 오탐을 재고 나서 할 일이라는 뜻이다.
    """
    found = {m.term for m in detect(sentence, seed_glossary) if m.method is Method.EXACT}
    assert term not in found


# 별칭 모양이 나오지만 용어가 아닌 문장. 지금까지 오탐 표본이 전부 개발 대화에서
# 나와서, 이런 어절은 표본에 들어올 수가 없었다 — 개발 얘기 중엔 뱀도 속편도 안 나온다.
@pytest.mark.parametrize(
    "sentence,forbidden",
    [
        ("창밖 뷰가 좋아요", "Vue"),            # 별칭 미등록이라 안 걸린다
        ("리드미컬한 음악이네", "README"),        # 꼬리가 조사가 아니다
        ("도커피 한 잔 마실래", "Docker"),       # 토큰 중간에서 시작한다
    ],
)
def test_boundary_rules_block_lookalike_words(seed_glossary, sentence, forbidden):
    """경계 규칙이 막아내는 것들 — 여기는 별칭 문제가 아니다."""
    found = {m.term for m in detect(sentence, seed_glossary) if m.method is Method.EXACT}
    assert forbidden not in found


@pytest.mark.xfail(strict=True, reason="별칭이 일상어와 동음이라 경계 규칙으로는 못 막는다")
@pytest.mark.parametrize(
    "sentence,forbidden",
    [
        ("제이슨이 어제 왔어", "JSON"),          # 사람 이름 Jason
        ("제이슨한테 물어봐", "JSON"),
        ("그 영화 시퀄이 나온대", "SQL"),         # 속편 sequel
        ("시퀄은 별로였어", "SQL"),
        ("파이선은 큰 뱀이야", "Python"),         # 뱀 python
        ("파이선이 무섭다", "Python"),
    ],
)
def test_homonym_aliases_currently_false_positive(seed_glossary, sentence, forbidden):
    """동음이의 별칭은 지금 오탐이 난다. 고쳐지면 이 테스트가 먼저 알려준다.

    조사를 떼는 건 제대로 동작한다 — 문제는 떼고 남은 게 진짜 용어가 아니라는 것이다.
    경계를 조여도 안 풀린다. 별칭을 빼거나 문맥을 봐야 하는 문제다.
    """
    found = {m.term for m in detect(sentence, seed_glossary) if m.method is Method.EXACT}
    assert forbidden not in found


def test_resolve_prefers_exact_even_when_the_other_is_longer():
    """길이보다 method가 먼저다 — 긴 소리 추정이 짧은 등록 용어를 이기면 안 된다.

    등록 탐지는 경계 규칙에 맞는 구간만 내보내고, 소리 추정은 어절을 통째로 잡는
    경향이 있어 더 길어진다. 길이를 먼저 보면 "도커를"(fuzzy)이 "도커"(exact)를
    밀어내고, 치환에서 조사가 함께 사라진다.
    """
    matches = [
        _m(0, 3, Method.FUZZY, 0.95, term="Docker"),
        _m(0, 2, Method.EXACT, 1.0, term="Docker"),
    ]

    assert resolve_overlaps(matches) == [_m(0, 2, Method.EXACT, 1.0, term="Docker")]


def test_resolve_prefers_exact_even_when_regex_is_longer():
    """정규식이 더 길어도 등록 용어가 앞선다.

    등록 용어가 정규식보다 우선한다는 규칙과, 겹치면 긴 쪽을 남긴다는 규칙이
    충돌하는 자리다. 등록 용어 쪽을 택한다 — 정규식은 모양만 보고 잡은 추정이고
    용어집은 사람이 확인해 넣은 것이다.
    """
    matches = [
        _m(0, 10, Method.REGEX, 0.8, term="get_user_id"),
        _m(0, 3, Method.EXACT, 1.0, term="SQL"),
    ]

    assert resolve_overlaps(matches) == [_m(0, 3, Method.EXACT, 1.0, term="SQL")]
