from devdemangle.glossary import Glossary
from devdemangle.hotwords import DEFAULT_BUDGET, build
from devdemangle.types import Term


def test_joins_canonicals_with_space():
    glossary = Glossary([
        Term(canonical="GitHub", aliases=("깃허브",)),
        Term(canonical="repository", aliases=("레포지토리",)),
    ])
    assert build(glossary) == "GitHub repository"


def test_empty_glossary_returns_empty_string():
    assert build(Glossary([])) == ""


def test_ignores_aliases():
    """hotwords에는 표준형만 넣는다. alias를 넣으면 STT가 깨진 형태를 학습한다."""
    glossary = Glossary([Term(canonical="Python", aliases=("파이썬", "파이선"))])
    assert build(glossary) == "Python"


def test_stops_at_budget():
    """예산을 넘기면 거기서 멈춘다. 잘린 뒤쪽은 조용히 빠진다."""
    glossary = Glossary([Term(canonical=f"term{i:03d}") for i in range(200)])
    result = build(glossary, budget=10)

    assert result.startswith("term000 ")
    assert "term199" not in result
    assert len(result.split()) < 200


def test_default_budget_covers_seed_glossary():
    """씨앗 용어집은 예산에 걸리지 않아야 한다 — 걸리면 시연에서 뒤쪽 용어가 죽는다."""
    from devdemangle.correct import default_glossary

    glossary = default_glossary()
    # 표준형에 공백이 든 것이 있어(`npm install`) 단어 수로는 못 센다. 원문 그대로 나와야 한다.
    assert build(glossary) == " ".join(t.canonical for t in glossary)
    assert DEFAULT_BUDGET == 224
