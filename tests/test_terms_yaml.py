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
