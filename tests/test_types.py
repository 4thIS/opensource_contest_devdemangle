import dataclasses

import pytest

from devdemangle.types import Match, Method, Span, Term


def test_method_values_are_plain_strings():
    """StrEnum이라 라이브러리 사용자가 문자열로 비교할 수 있다."""
    assert Method.EXACT == "exact"
    assert Method.REGEX == "regex"
    assert Method.FUZZY == "fuzzy"


def test_unknown_method_raises_attribute_error():
    """오타를 런타임에 잡는 것이 StrEnum을 쓰는 이유다."""
    with pytest.raises(AttributeError):
        Method.EXECT


def test_term_defaults_are_empty():
    t = Term(canonical="Vue")
    assert t.aliases == ()
    assert t.translations == {}


def test_term_default_dict_is_not_shared():
    """가변 기본값이 인스턴스 간에 공유되면 안 된다."""
    a = Term(canonical="Vue")
    b = Term(canonical="React")
    a.translations["en"] = "oops"
    assert b.translations == {}


def test_term_is_frozen():
    t = Term(canonical="Vue")
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.canonical = "React"


def test_match_holds_input_offsets():
    """Match의 start/end는 입력 텍스트 기준이다."""
    m = Match(0, 3, "lodash", "라다시", Method.EXACT, 1.0)
    assert "라다시 써서"[m.start : m.end] == m.matched


def test_span_holds_result_offsets():
    """Span의 start/end는 결과 텍스트 기준이다."""
    s = Span(0, 6, "lodash", "라다시", Method.EXACT, 1.0)
    assert "lodash 써서"[s.start : s.end] == s.term


def test_match_and_span_are_distinct_types():
    """좌표계가 다르므로 섞이면 안 된다."""
    assert Match is not Span
