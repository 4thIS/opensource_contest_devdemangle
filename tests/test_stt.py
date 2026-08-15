from devdemangle.glossary import Term
from devdemangle.stt import hotwords_from


def test_hotwords_from_joins_canonicals_with_space():
    terms = [
        Term(canonical="GitHub", aliases=["깃허브"]),
        Term(canonical="repository", aliases=["레포지토리"]),
    ]
    assert hotwords_from(terms) == "GitHub repository"


def test_hotwords_from_empty_glossary_returns_empty_string():
    assert hotwords_from([]) == ""


def test_hotwords_from_ignores_aliases():
    """hotwords에는 표준형만 넣는다. alias를 넣으면 STT가 깨진 형태를 학습한다."""
    terms = [Term(canonical="Python", aliases=["파이썬", "파이선"])]
    assert hotwords_from(terms) == "Python"
