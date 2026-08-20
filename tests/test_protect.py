"""번역 보호 — 용어를 플레이스홀더로 가려 번역하고 되돌린다.

실험 근거는 `experiments/results/risk2.md`·`risk2b.md`다. 대문자 단어
플레이스홀더(`TERMZERO` 계열)만 100% 살아남았고, 감싸기·특수문자는 전부 무너졌다.
여기서는 그 규칙을 지키는지와 좌표를 안 흘리는지를 본다.

번역기는 주입한다 — 모델을 올리지 않고 이 로직만 확인하기 위해서다.
"""

import pytest

from devdemangle.translate.protect import (
    PLACEHOLDER_PREFIX,
    TranslationResult,
    placeholder_for,
    translate_protected,
)
from devdemangle.types import Method, Span


def _span(start, end, term, matched=None):
    return Span(
        start=start,
        end=end,
        term=term,
        matched=matched or term,
        method=Method.EXACT,
        confidence=1.0,
    )


class Echo:
    """번역기 대역. 받은 문장을 그대로 돌려주고 무엇을 받았는지 기록한다."""

    def __init__(self, reply=None):
        self.seen = []
        self._reply = reply

    def translate(self, text: str) -> str:
        self.seen.append(text)
        return self._reply if self._reply is not None else text


def test_text_without_terms_is_passed_through():
    tr = Echo(reply="I fixed it.")
    result = translate_protected("고쳤어요", [], tr)
    assert result.text == "I fixed it."
    assert tr.seen == ["고쳤어요"]  # 가릴 게 없으면 원문 그대로 넘긴다
    assert result.lost == []


def test_term_is_masked_before_translation():
    """번역기에는 용어가 아니라 플레이스홀더가 가야 한다."""
    tr = Echo(reply="I saw TERMZERO.")
    translate_protected("GitHub 봤어요", [_span(0, 6, "GitHub")], tr)
    assert tr.seen == ["TERMZERO 봤어요"]


def test_placeholder_is_restored_after_translation():
    tr = Echo(reply="I saw TERMZERO.")
    result = translate_protected("GitHub 봤어요", [_span(0, 6, "GitHub")], tr)
    assert result.text == "I saw GitHub."
    assert result.lost == []


def test_multiple_terms_get_distinct_placeholders():
    text = "GitHub에서 README 봤어요"
    spans = [_span(0, 6, "GitHub"), _span(9, 15, "README")]
    tr = Echo(reply="I saw TERMONE on TERMZERO.")
    result = translate_protected(text, spans, tr)
    assert tr.seen == ["TERMZERO에서 TERMONE 봤어요"]
    assert result.text == "I saw README on GitHub."


def test_same_term_twice_gets_separate_placeholders():
    """같은 용어라도 자리마다 따로 가린다 — 문자열 치환이면 둘이 엉킨다."""
    text = "Docker 말고 Docker"
    spans = [_span(0, 6, "Docker"), _span(10, 16, "Docker")]
    tr = Echo()
    translate_protected(text, spans, tr)
    assert tr.seen == ["TERMZERO 말고 TERMONE"]


def test_lost_placeholder_is_reported_not_hidden():
    """번역이 플레이스홀더를 삼키면 조용히 넘어가지 않는다."""
    tr = Echo(reply="I saw something.")  # TERMZERO가 사라졌다
    result = translate_protected("GitHub 봤어요", [_span(0, 6, "GitHub")], tr)
    assert result.lost == ["GitHub"]
    assert "TERMZERO" not in result.text


def test_surviving_terms_restore_even_when_one_is_lost():
    text = "GitHub에서 README 봤어요"
    spans = [_span(0, 6, "GitHub"), _span(9, 15, "README")]
    tr = Echo(reply="I saw TERMONE.")  # TERMZERO만 사라졌다
    result = translate_protected(text, spans, tr)
    assert result.text == "I saw README."
    assert result.lost == ["GitHub"]


def test_placeholders_are_uppercase_letters_only():
    """risk2b: 생존을 가르는 건 기호가 아니라 대소문자다.

    숫자·밑줄·따옴표를 섞으면 생존율이 0%까지 떨어졌다. 글자만 쓴다.
    """
    for i in range(40):
        p = placeholder_for(i)
        assert p.isupper(), p
        assert p.isalpha(), p          # 숫자·기호 금지
        assert p.startswith(PLACEHOLDER_PREFIX), p


def test_placeholders_are_unique():
    seen = {placeholder_for(i) for i in range(40)}
    assert len(seen) == 40


def test_placeholder_matches_experiment_naming():
    """실험에서 100% 생존을 확인한 이름을 그대로 쓴다."""
    assert placeholder_for(0) == "TERMZERO"
    assert placeholder_for(1) == "TERMONE"
    assert placeholder_for(2) == "TERMTWO"


def test_spans_must_be_within_text():
    with pytest.raises(ValueError):
        translate_protected("짧다", [_span(0, 99, "GitHub")], Echo())


def test_overlapping_spans_are_rejected():
    """겹친 Span을 그대로 가리면 좌표가 어긋난다. 부르는 쪽 버그이므로 알린다."""
    spans = [_span(0, 6, "GitHub"), _span(3, 9, "README")]
    with pytest.raises(ValueError):
        translate_protected("GitHubREADME", spans, Echo())


def test_result_carries_what_was_protected():
    tr = Echo(reply="TERMZERO")
    result = translate_protected("GitHub", [_span(0, 6, "GitHub")], tr)
    assert isinstance(result, TranslationResult)
    assert result.protected == ["GitHub"]


# ── 보호 대상 선정 ────────────────────────────────────────────────
# correct()의 spans는 "바뀐 것"이고, 번역이 보호해야 할 건 "있는 것 전부"다.

def test_protection_covers_terms_that_were_not_changed():
    """이미 표준형이라 보정이 건드리지 않은 용어도 번역에선 보호해야 한다.

    risk2 실측에서 REST API가 'ReST APl'로, TypeScript가 'Type Type Type'으로
    무너졌다. 보정이 손댈 게 없었다고 해서 번역이 안전한 게 아니다.
    """
    from devdemangle.correct import default_glossary
    from devdemangle.translate.protect import spans_for_protection

    g = default_glossary()
    assert [s.term for s in spans_for_protection("Docker 컨테이너 재시작할게.", g)] == ["Docker"]
    assert [s.term for s in spans_for_protection("TypeScript 문법 에러라는데?", g)] == ["TypeScript"]


def test_protection_spans_point_at_the_right_place():
    from devdemangle.correct import default_glossary
    from devdemangle.translate.protect import spans_for_protection

    text = "Docker 컨테이너 재시작할게."
    span = spans_for_protection(text, default_glossary())[0]
    assert text[span.start:span.end] == "Docker"


def test_protection_spans_do_not_overlap():
    """겹친 채로 넘기면 mask()가 거부한다 — 여기서 이미 해소해 둔다."""
    from devdemangle.correct import default_glossary
    from devdemangle.translate.protect import spans_for_protection

    spans = spans_for_protection("npm install 하고 git commit 했어요", default_glossary())
    for a, b in zip(spans, spans[1:]):
        assert a.end <= b.start
