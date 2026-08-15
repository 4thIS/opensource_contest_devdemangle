"""실제 용어집 데이터가 검증을 통과하는지 본다.

규칙 하나하나가 제대로 동작하는지는 tests/test_glossary.py가 작은 픽스처로 확인한다.
이 파일은 진짜 data/terms.yaml만 본다.
"""

from pathlib import Path

from devdemangle import Glossary

TERMS = Path(__file__).resolve().parent.parent / "data" / "terms.yaml"


def test_seed_glossary_loads():
    """실제 용어집이 검증 규칙 10개를 모두 통과한다."""
    g = Glossary.from_yaml(TERMS)
    assert len(g) >= 20
