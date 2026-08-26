"""실제 용어집 데이터가 검증을 통과하는지 본다.

규칙 하나하나가 제대로 동작하는지는 tests/test_glossary.py가 작은 픽스처로 확인한다.
이 파일은 진짜 data/terms.yaml만 본다.
"""

from pathlib import Path

import pytest

from devdemangle import Glossary

TERMS = Path(__file__).resolve().parent.parent / "data" / "terms.yaml"

# 리스크 1 녹음에서 STT가 실제로 뱉은 문자열 → 되돌려야 할 표준형.
# 추측이 아니라 측정값이라, 용어집에서 빠지면 실측 근거가 사라진 것이다.
# 원본 로그: experiments/results/risk1.md §5
MEASURED = [
    ("기터벳", "GitHub"),
    ("리포지토리", "repository"),
    ("리포지터리", "repository"),
    ("Git 커뮤니타", "git commit"),
    ("리듬이", "README"),
    ("도커", "Docker"),
    ("닷컬", "Docker"),
    ("타입스트리트", "TypeScript"),
    ("타입 스트릿", "TypeScript"),
    ("풀 리퀘스트", "pull request"),
    ("로컬 호스트", "localhost"),
    ("vs 코드", "VS Code"),
    ("베스트 API", "FastAPI"),
    ("파일선", "Python"),
    ("리액트", "React"),
]


@pytest.fixture(scope="module")
def glossary() -> Glossary:
    return Glossary.from_yaml(TERMS)


def test_seed_glossary_loads(glossary):
    """실제 용어집이 검증 규칙 10개를 모두 통과한다."""
    assert len(glossary) >= 20


@pytest.mark.parametrize("variant,canonical", MEASURED)
def test_measured_variant_maps_to_canonical(glossary, variant, canonical):
    """실측 변형이 표준형으로 이어진다.

    별칭 조회 API는 없다 — 별칭을 쓰는 건 탐지 쪽이라 용어집은 목록만 제공한다.
    """
    owners = [t.canonical for t in glossary if variant in t.aliases]
    assert owners == [canonical]


def test_vue_short_form_stays_unregistered(glossary):
    """짧은 음차 "뷰"는 실측됐지만 일부러 등록하지 않는다.

    일반 명사와 충돌하는데 유사도로는 못 거른다("뷰"/"브이유" 0.86).
    등록하려면 오탐 표본을 근거로 결정해야 하므로, 그전까지는 빠져 있는 게 맞다.
    """
    assert all("뷰" not in t.aliases for t in glossary)


# 2차 녹음에서 STT가 실제로 뱉은 문자열. 위 MEASURED와 나눠 두는 이유는 출처가
# 달라서다 — 이쪽은 화자 셋 모두 large-v3 / float16 / CUDA 전사에서 왔다.
# 어느 seed에서 나왔는지는 data/terms.yaml의 항목 주석에 적혀 있다.
MEASURED_2CHA = [
    ("기터브", "GitHub"),
    ("토커", "Docker"),
    ("라다씨", "lodash"),
    ("러데쉬", "lodash"),
    ("패스트 API", "FastAPI"),
    ("자바", "Java"),
    ("러스트", "Rust"),
    ("스프링", "Spring"),
    ("D장고", "Django"),
    ("next.jpg", "Next.js"),
    ("익스프레스", "Express"),
    ("엔진X", "Nginx"),
    ("레디스", "Redis"),
    ("몽고 디비", "MongoDB"),
    ("카프카", "Kafka"),
    ("엘라스틱 서치", "Elasticsearch"),
    ("킷랩", "GitLab"),
    ("젠킨스", "Jenkins"),
    ("포스트맨", "Postman"),
    ("피그마", "Figma"),
    ("인텔리제이", "IntelliJ"),
    ("웹팩", "webpack"),
    ("테라폼", "Terraform"),
    ("리팩토링", "리팩터링"),
    ("미드웨어", "미들웨어"),
    ("미들베어", "미들웨어"),
]


@pytest.mark.parametrize("variant,canonical", MEASURED_2CHA)
def test_measured_variant_from_second_round_maps_to_canonical(
    glossary, variant, canonical
):
    """2차 녹음 실측 변형이 표준형으로 이어진다."""
    owners = [t.canonical for t in glossary if variant in t.aliases]
    assert owners == [canonical]


def test_django_keeps_the_letter_that_stt_left_behind(glossary):
    """"D장고"를 줄여 "장고"만 두면 안 된다.

    시작 경계가 매치 앞 글자를 보는데 "D"가 영숫자라 "장고"는 걸리지 않는다
    ("윈도커널"의 "도커"를 막는 그 규칙이다). 실측 문자열을 통째로 가지고 있어야 한다.
    """
    django = glossary.get("Django")
    assert "D장고" in django.aliases


def test_kotlin_has_no_alias_on_purpose(glossary):
    """Kotlin은 실측 형태 셋을 다 재보고 셋 다 못 써서 비어 있다 — 빠뜨린 게 아니다.

    "코트를"은 조사를 떼면 옷("코트")이 되고, 실제로 "코트를 옷장에 걸어놨어요"를
    Kotlin으로 바꿔 놓는다. "코틀린"은 실측 전사 "커리는"(쿼리는)과 0.833이다.
    "코틀리"는 낱말이 아니지만, 넣으면 Kotlin이 한글 별칭을 갖게 되면서 같은
    "커리는"이 0.800으로 끌려온다 — 소리 비교는 한글 별칭끼리 하기 때문이다.
    임계값이 0.81 위로 올라가면 "코틀리"는 그때 넣을 수 있다.
    """
    assert glossary.get("Kotlin").aliases == ()
    assert all("코틀린" not in t.aliases for t in glossary)
    assert all("코트를" not in t.aliases for t in glossary)


def test_pilot_and_plastic_stay_unregistered_but_that_does_not_block_them(glossary):
    """일상어 실측 형태는 등록하지 않는다. 다만 그게 방어가 되지는 않는다.

    소리 비교는 한글 별칭끼리 하므로, 같은 용어에 다른 한글 별칭이 남아 있으면
    뺀 자리가 그대로 메워진다 — "플라스틱"은 "플라스크"를 타고 0.833으로,
    "파일럿"은 "코파일럿"을 타고 0.875로 잡힌다.
    여기서 확인하는 건 "등록하지 않았다"까지다. 막혔다고 읽으면 안 된다.
    """
    assert all("플라스틱" not in t.aliases for t in glossary)
    assert all("파일럿" not in t.aliases for t in glossary)


def test_truncated_form_stays_unregistered(glossary):
    """"Swag"는 등록하지 않는다 — 음성이 아니라 정밀도가 만든 형태였다.

    정밀도를 낮춰(int8/CPU) 돌렸을 때만 뒤가 잘렸고, 같은 음성의 float16 전사에서는
    "Swagger"가 온전히 살아남았다. 영어 낱말과도 겹친다.
    """
    assert all("Swag" not in t.aliases for t in glossary)


def test_non_hangul_forms_are_registered_because_fuzzy_cannot_reach_them(glossary):
    """소리 탐지는 한글 덩어리만 후보로 보므로, 라틴 문자로 깨진 형태는 여기 없으면 못 잡는다.

    셋 다 표준형을 hotwords로 넘긴 조건에서 나왔다 — 힌트를 줘도 이렇게 깨진다.
    """
    assert "Midware" in glossary.get("미들웨어").aliases
    assert "Lada C" in glossary.get("lodash").aliases
    assert "next.jpg" in glossary.get("Next.js").aliases


def test_spaced_forms_are_registered_alongside_joined_ones(glossary):
    """STT가 긴 영어 용어 가운데 공백을 넣는 일이 반복된다.

    붙은 형태만 두면 공백 하나에 놓친다. 소리로도 못 구한다 — 한글 덩어리만 후보로
    보는 구조라 앞 조각만 남아 점수가 깎인다("패스트"가 0.769로 임계값 아래다).
    """
    for spaced, canonical in [
        ("패스트 API", "FastAPI"),
        ("몽고 디비", "MongoDB"),
        ("엘라스틱 서치", "Elasticsearch"),
        ("쿠버 네티스", "Kubernetes"),
    ]:
        assert spaced in glossary.get(canonical).aliases
