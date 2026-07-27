from pathlib import Path

import yaml

TERMS = Path(__file__).resolve().parent.parent / "data" / "terms.yaml"


def load():
    with open(TERMS, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_yaml_parses():
    data = load()
    assert data["version"] == 1
    assert len(data["terms"]) >= 20


def test_every_term_has_canonical():
    for t in load()["terms"]:
        assert "canonical" in t, f"canonical 없음: {t}"
        assert t["canonical"].strip(), "canonical이 비어 있음"


def test_no_duplicate_canonical():
    canons = [t["canonical"] for t in load()["terms"]]
    assert len(canons) == len(set(canons)), "canonical 중복이 있습니다"


def test_aliases_are_lists():
    for t in load()["terms"]:
        assert isinstance(t.get("aliases", []), list), f"aliases가 리스트가 아님: {t['canonical']}"


def test_no_alias_collides_with_other_canonical():
    """한 용어의 alias가 다른 용어의 canonical과 같으면 안 된다."""
    data = load()
    canons = {t["canonical"].lower() for t in data["terms"]}
    for t in data["terms"]:
        for a in t.get("aliases", []):
            assert a.lower() not in canons - {t["canonical"].lower()}, (
                f"'{a}'는 다른 용어의 canonical과 충돌합니다"
            )
