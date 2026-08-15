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
    """파일 없이 만들 수 있어야 코어 테스트가 빨라진다."""
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
    """탐지가 대소문자를 무시하므로 조회도 맞춘다."""
    g = Glossary([Term("Python", ("파이썬",))])
    assert g.get("Python").canonical == "Python"
    assert g.get("python").canonical == "Python"
    assert g.get("PYTHON").canonical == "Python"


def test_get_returns_none_for_unknown():
    g = Glossary([Term("Python")])
    assert g.get("Ruby") is None


# --- 번역어 ------------------------------------------------------------


def test_translation_defaults_to_canonical():
    """고정 번역어가 없으면 원문 유지가 기본값이다. Vue는 "뷰"가 되면 안 된다."""
    g = Glossary([Term("Vue", ("브이유",))])
    assert g.translation_for("Vue", "ko") == "Vue"
    assert g.translation_for("Vue", "en") == "Vue"


def test_translation_uses_fixed_value_when_present():
    g = Glossary([Term("의존성 주입", ("디펜던시 인젝션",), {"en": "dependency injection"})])
    assert g.translation_for("의존성 주입", "en") == "dependency injection"
    assert g.translation_for("의존성 주입", "ko") == "의존성 주입"


def test_translation_for_unknown_term_returns_input():
    """등록되지 않은 표준형도 예외 없이 원문을 돌려준다."""
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
    """별칭이 없는 용어도 등록 가능하다."""
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


# --- 검증 규칙 --------------------------------------------------------


def test_rule1_top_level_must_be_mapping(tmp_path):
    path = write_yaml(tmp_path, "- 그냥\n- 리스트\n")
    with pytest.raises(GlossaryError, match="최상위"):
        Glossary.from_yaml(path)


def test_rule2_version_must_be_present(tmp_path):
    path = write_yaml(tmp_path, "terms:\n  - canonical: Vue\n")
    with pytest.raises(GlossaryError, match="version 키가 없습니다"):
        Glossary.from_yaml(path)


def test_rule2_version_must_match_schema(tmp_path):
    path = write_yaml(tmp_path, "version: 2\nterms:\n  - canonical: Vue\n")
    with pytest.raises(GlossaryError, match=r"version이 2입니다"):
        Glossary.from_yaml(path)


def test_rule3_terms_must_be_a_list(tmp_path):
    path = write_yaml(tmp_path, "version: 1\nterms: 문자열\n")
    with pytest.raises(GlossaryError, match="terms가 리스트가 아닙니다"):
        Glossary.from_yaml(path)


def test_rule3_terms_key_is_required(tmp_path):
    path = write_yaml(tmp_path, "version: 1\n")
    with pytest.raises(GlossaryError, match="terms 키가 없습니다"):
        Glossary.from_yaml(path)


def test_term_entry_must_be_a_mapping(tmp_path):
    path = write_yaml(tmp_path, "version: 1\nterms: [문자열]\n")
    with pytest.raises(GlossaryError, match="매핑이 아닙니다"):
        Glossary.from_yaml(path)


def test_rule4_canonical_is_required(tmp_path):
    path = write_yaml(tmp_path, "version: 1\nterms:\n  - aliases: [뷰]\n")
    with pytest.raises(GlossaryError, match="canonical 키가 없습니다"):
        Glossary.from_yaml(path)


def test_rule4_canonical_must_not_be_blank(tmp_path):
    path = write_yaml(tmp_path, 'version: 1\nterms:\n  - canonical: "   "\n')
    with pytest.raises(GlossaryError, match="canonical이 비어 있거나"):
        Glossary.from_yaml(path)


def test_rule5_aliases_must_be_a_list(tmp_path):
    path = write_yaml(tmp_path, "version: 1\nterms:\n  - canonical: Vue\n    aliases: 브이유\n")
    with pytest.raises(GlossaryError, match="aliases가 리스트가 아닙니다"):
        Glossary.from_yaml(path)


def test_rule5_alias_must_not_be_blank(tmp_path):
    path = write_yaml(tmp_path, 'version: 1\nterms:\n  - canonical: Vue\n    aliases: ["", 브이유]\n')
    with pytest.raises(GlossaryError, match="aliases에 비어 있거나"):
        Glossary.from_yaml(path)


def test_rule6_translations_must_be_a_mapping(tmp_path):
    path = write_yaml(
        tmp_path,
        "version: 1\nterms:\n  - canonical: Vue\n    translations: [en, ko]\n",
    )
    with pytest.raises(GlossaryError, match="translations가 매핑이 아닙니다"):
        Glossary.from_yaml(path)


def test_rule6_translations_keys_and_values_must_be_strings(tmp_path):
    path = write_yaml(
        tmp_path,
        "version: 1\nterms:\n  - canonical: Vue\n    translations:\n      en: 123\n",
    )
    with pytest.raises(GlossaryError, match="translations의 키·값은 문자열이어야 합니다"):
        Glossary.from_yaml(path)


def test_rule7_duplicate_canonical_is_rejected(tmp_path):
    """표준형이 중복되면 로딩할 때 거부한다."""
    path = write_yaml(
        tmp_path,
        "version: 1\nterms:\n  - canonical: Docker\n  - canonical: Docker\n",
    )
    with pytest.raises(GlossaryError, match="중복"):
        Glossary.from_yaml(path)


def test_rule7_duplicate_canonical_ignores_case(tmp_path):
    """Python과 python이 별개로 등록되면 어느 쪽으로 보정할지 정할 수 없다."""
    path = write_yaml(
        tmp_path,
        "version: 1\nterms:\n  - canonical: Python\n  - canonical: python\n",
    )
    with pytest.raises(GlossaryError, match="중복"):
        Glossary.from_yaml(path)


def test_rule8_alias_must_not_collide_with_other_canonical(tmp_path):
    path = write_yaml(
        tmp_path,
        "version: 1\nterms:\n  - canonical: Python\n  - canonical: Ruby\n    aliases: [python]\n",
    )
    with pytest.raises(GlossaryError, match="canonical과 충돌"):
        Glossary.from_yaml(path)


def test_rule8_allows_alias_equal_to_own_canonical(tmp_path):
    """자기 자신의 canonical과 같은 alias는 무의미하지만 모호하지는 않다."""
    path = write_yaml(
        tmp_path,
        "version: 1\nterms:\n  - canonical: Vue\n    aliases: [Vue]\n",
    )
    g = Glossary.from_yaml(path)
    assert len(g) == 1


def test_rule9_same_alias_in_two_terms_is_rejected(tmp_path):
    """'깃'이 git과 GitHub 양쪽에 있으면 어느 표준형으로 보정할지 정할 수 없다."""
    path = write_yaml(
        tmp_path,
        "version: 1\nterms:\n  - canonical: git\n    aliases: [깃]\n"
        "  - canonical: GitHub\n    aliases: [깃]\n",
    )
    with pytest.raises(GlossaryError, match="alias '깃'"):
        Glossary.from_yaml(path)


def test_rule10_unknown_key_is_rejected(tmp_path):
    """'aliases'를 'alias'로 잘못 적으면 별칭이 조용히 사라진다."""
    path = write_yaml(
        tmp_path,
        "version: 1\nterms:\n  - canonical: Docker\n    alias: [도커]\n",
    )
    with pytest.raises(GlossaryError, match="알 수 없는 키"):
        Glossary.from_yaml(path)


# --- 오류 수집 --------------------------------------------------------


def test_all_errors_are_reported_together(tmp_path):
    """고치고-다시돌리기를 반복하지 않도록 전부 모아 보고한다."""
    path = write_yaml(
        tmp_path,
        "version: 1\nterms:\n"
        "  - canonical: Docker\n"
        "  - canonical: Docker\n"          # 규칙 7 위반
        "  - canonical: Vue\n"
        "    aliases: 브이유\n"             # 규칙 5 위반
        "  - canonical: Python\n"
        "    alias: [파이썬]\n",            # 규칙 10 위반
    )
    with pytest.raises(GlossaryError) as exc:
        Glossary.from_yaml(path)

    message = str(exc.value)
    assert "3건" in message
    assert "중복" in message
    assert "aliases" in message
    assert "알 수 없는 키" in message


def test_error_message_includes_term_index(tmp_path):
    """어느 항목이 문제인지 알아야 100개 중에서 찾을 수 있다."""
    path = write_yaml(
        tmp_path,
        "version: 1\nterms:\n  - canonical: Vue\n  - canonical: Docker\n    alias: [도커]\n",
    )
    with pytest.raises(GlossaryError, match=r"terms\[1\]"):
        Glossary.from_yaml(path)


def test_errors_accumulate_within_a_single_term(tmp_path):
    """한 항목이 여러 규칙을 어기면 그것들도 전부 보고된다."""
    path = write_yaml(
        tmp_path,
        'version: 1\nterms:\n  - aliases: "브이유"\n',
    )
    with pytest.raises(GlossaryError) as exc:
        Glossary.from_yaml(path)

    message = str(exc.value)
    assert "canonical" in message
    assert "aliases" in message
    assert "2건" in message


def test_rule8_detects_collision_with_later_canonical(tmp_path):
    """규칙 8이 두 번 순회하는 이유 — 뒤에 나오는 canonical과도 충돌을 잡아야 한다."""
    path = write_yaml(
        tmp_path,
        "version: 1\nterms:\n  - canonical: Ruby\n    aliases: [python]\n  - canonical: Python\n",
    )
    with pytest.raises(GlossaryError, match="canonical과 충돌"):
        Glossary.from_yaml(path)
