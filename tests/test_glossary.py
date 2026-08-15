from pathlib import Path

import pytest

from devdemangle.glossary import Glossary, GlossaryError
from devdemangle.types import Term


def write_yaml(tmp_path: Path, body: str) -> Path:
    """임시 용어집 파일을 만든다. 검증 테스트에서 재사용한다."""
    path = tmp_path / "terms.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# --- 생성 -------------------------------------------------------------


def test_construct_without_file():
    """파일 없이 만들 수 있어야 코어 테스트가 빨라진다 (C-IND-03)."""
    g = Glossary([Term("lodash", ("라다시",))])
    assert len(g) == 1


def test_iterates_terms():
    terms = [Term("lodash"), Term("Vue")]
    g = Glossary(terms)
    assert [t.canonical for t in g] == ["lodash", "Vue"]


def test_canonicals_preserves_original_spelling():
    """canonical은 공식 표기 그대로 보존된다 (출력 형태이므로)."""
    g = Glossary([Term("GitHub"), Term("FastAPI")])
    assert g.canonicals == ["GitHub", "FastAPI"]


# --- 조회 -------------------------------------------------------------


def test_get_ignores_case():
    """C-DET-03이 대소문자 무시 탐지를 요구하므로 조회도 맞춘다."""
    g = Glossary([Term("Python", ("파이썬",))])
    assert g.get("Python").canonical == "Python"
    assert g.get("python").canonical == "Python"
    assert g.get("PYTHON").canonical == "Python"


def test_get_returns_none_for_unknown():
    g = Glossary([Term("Python")])
    assert g.get("Ruby") is None


# --- 번역어 ------------------------------------------------------------


def test_translation_defaults_to_canonical():
    """T-GLOS-01 — 고정 번역어가 없으면 원문 유지가 기본값이다."""
    g = Glossary([Term("Vue", ("브이유",))])
    assert g.translation_for("Vue", "ko") == "Vue"
    assert g.translation_for("Vue", "en") == "Vue"


def test_translation_uses_fixed_value_when_present():
    g = Glossary([Term("의존성 주입", ("디펜던시 인젝션",), {"en": "dependency injection"})])
    assert g.translation_for("의존성 주입", "en") == "dependency injection"
    assert g.translation_for("의존성 주입", "ko") == "의존성 주입"


def test_translation_for_unknown_term_returns_input():
    """등록되지 않은 표준형도 예외 없이 원문을 돌려준다 (T-TRA-04와 같은 원칙)."""
    g = Glossary([Term("Vue")])
    assert g.translation_for("등록안된용어", "en") == "등록안된용어"


def test_translation_returns_official_spelling():
    """조회는 대소문자를 무시하지만 출력은 공식 표기다."""
    g = Glossary([Term("Vue")])
    assert g.translation_for("VUE", "ko") == "Vue"


# --- YAML 로딩 --------------------------------------------------------


def test_from_yaml_loads_terms(tmp_path):
    path = write_yaml(
        tmp_path,
        """
version: 1
terms:
  - canonical: lodash
    aliases: [라다시, 로대시]
  - canonical: 의존성 주입
    translations:
      en: dependency injection
""",
    )
    g = Glossary.from_yaml(path)
    assert len(g) == 2
    assert g.get("lodash").aliases == ("라다시", "로대시")
    assert g.translation_for("의존성 주입", "en") == "dependency injection"


def test_from_yaml_allows_term_without_optional_fields(tmp_path):
    """C-GLOS-03 — 별칭이 없는 용어도 등록 가능하다."""
    path = write_yaml(
        tmp_path,
        """
version: 1
terms:
  - canonical: Vue
""",
    )
    g = Glossary.from_yaml(path)
    assert g.get("Vue").aliases == ()
    assert g.get("Vue").translations == {}


def test_from_yaml_accepts_str_path(tmp_path):
    path = write_yaml(tmp_path, "version: 1\nterms:\n  - canonical: Vue\n")
    g = Glossary.from_yaml(str(path))
    assert len(g) == 1


def test_missing_file_raises_file_not_found(tmp_path):
    """파일 없음은 GlossaryError로 감싸지 않는다 — 메시지가 이미 명확하다."""
    with pytest.raises(FileNotFoundError):
        Glossary.from_yaml(tmp_path / "없는파일.yaml")


def test_malformed_yaml_raises_glossary_error(tmp_path):
    path = write_yaml(tmp_path, "version: 1\nterms: [불균형\n")
    with pytest.raises(GlossaryError):
        Glossary.from_yaml(path)
