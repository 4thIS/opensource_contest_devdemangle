"""보정 결과와 좌표를 확인한다.

⚠️ Span은 **결과 텍스트** 기준 좌표다. 앞 용어가 길어지면 뒤가 밀린다.
"""

from devdemangle.correct import CorrectionResult, correct
from devdemangle.glossary import Glossary
from devdemangle.types import Method, Term

GITHUB = Term(canonical="GitHub", aliases=("깃허브", "깃헙"))
NPM_INSTALL = Term(canonical="npm install", aliases=("엔피엠 인스톨", "엠피엠 인스톨"))
README = Term(canonical="README", aliases=("리드미", "리드미 파일"))
BASE = Glossary([GITHUB, NPM_INSTALL, README])


def _pairs(result):
    return [(s.matched, s.term) for s in result.spans]


def test_single_token_alias_is_replaced():
    result = correct("깃허브 봤어요", BASE)
    assert result.text == "GitHub 봤어요"
    assert _pairs(result) == [("깃허브", "GitHub")]


def test_multi_token_alias_is_replaced():
    result = correct("엔피엠 인스톨 먼저 실행하세요", BASE)
    assert result.text == "npm install 먼저 실행하세요"
    assert _pairs(result) == [("엔피엠 인스톨", "npm install")]


def test_text_without_alias_passes_through_unchanged():
    result = correct("오늘 날씨가 좋네요", BASE)
    assert result.text == "오늘 날씨가 좋네요"
    assert result.spans == []


def test_span_offsets_follow_the_result_text():
    """두 용어가 모두 길어지면 뒤쪽 Span이 그만큼 밀린다."""
    result = correct("깃허브 리드미 봤어요", BASE)
    assert result.text == "GitHub README 봤어요"

    first, second = result.spans
    assert (first.start, first.end) == (0, 6)
    assert (second.start, second.end) == (7, 13)
    # 결과 텍스트에서 그 구간을 잘라내면 표준형이 나온다 — 좌표가 맞다는 증거
    assert result.text[first.start:first.end] == "GitHub"
    assert result.text[second.start:second.end] == "README"


def test_alias_followed_by_particle_is_not_replaced():
    """알려진 한계: 끝도 토큰 경계와 일치해야 하므로 조사가 바로 붙으면 미매칭."""
    result = correct("깃허브다", BASE)
    assert result.text == "깃허브다"
    assert result.spans == []


def test_alias_inside_larger_token_is_not_replaced():
    """알려진 한계 테스트와 대칭: alias가 토큰 뒤쪽에 붙어 시작 경계가 안 맞는 경우."""
    result = correct("우리깃허브 봤어요", BASE)
    assert result.text == "우리깃허브 봤어요"
    assert result.spans == []


def test_longer_overlapping_alias_wins():
    glossary = Glossary([
        Term(canonical="AAA", aliases=("가",)),
        Term(canonical="BBB", aliases=("가 나",)),
    ])
    result = correct("가 나 다", glossary)
    assert result.text == "BBB 다"
    assert _pairs(result) == [("가 나", "BBB")]


def test_longest_match_wins_even_when_it_starts_later():
    """겹침 우선순위는 길이가 1순위다. 짧고 앞선 것이 긴 것을 이기면 안 된다."""
    glossary = Glossary([
        Term(canonical="SHORT", aliases=("가 나",)),
        Term(canonical="LONG", aliases=("나 다 라",)),
    ])
    result = correct("가 나 다 라", glossary)
    assert result.text == "가 LONG"
    assert _pairs(result) == [("나 다 라", "LONG")]


def test_equal_length_overlap_prefers_earlier_start():
    glossary = Glossary([
        Term(canonical="FIRST", aliases=("가 나",)),
        Term(canonical="SECOND", aliases=("나 다",)),
    ])
    result = correct("가 나 다", glossary)
    assert result.text == "FIRST 다"


def test_empty_text_returns_empty_result():
    assert correct("", BASE) == CorrectionResult(text="", spans=[])


def test_empty_glossary_passes_text_through_unchanged():
    result = correct("깃허브 봤어요", Glossary([]))
    assert result.text == "깃허브 봤어요"
    assert result.spans == []


def test_lowercase_alias_is_corrected_to_canonical():
    """Whisper가 소문자로 뱉은 실측 케이스(`sql 문을`)를 잡는다."""
    glossary = Glossary([Term(canonical="SQL", aliases=("SQL", "에스큐엘"))])
    result = correct("sql 문을 짰어", glossary)
    assert result.text == "SQL 문을 짰어"
    assert _pairs(result) == [("sql", "SQL")]


def test_already_canonical_is_left_alone():
    """C-COR-02: 이미 표준형인 것은 건드리지 않는다 (Span으로도 안 잡힌다)."""
    glossary = Glossary([Term(canonical="SQL", aliases=("SQL", "에스큐엘"))])
    result = correct("SQL 문을 짰어", glossary)
    assert result.text == "SQL 문을 짰어"
    assert result.spans == []


def test_span_keeps_source_casing_in_matched():
    """치환은 표준형으로 하되, 무엇을 바꿨는지는 원문 그대로 남긴다."""
    glossary = Glossary([Term(canonical="VS Code", aliases=("VS Code", "브이에스 코드"))])
    result = correct("vs code 켰어", glossary)
    assert result.text == "VS Code 켰어"
    assert result.spans[0].matched == "vs code"


def test_exact_detection_reports_method_and_confidence():
    """잠정 탐지기는 정확 일치만 하므로 EXACT/1.0이다."""
    result = correct("깃허브 봤어요", BASE)
    assert result.spans[0].method == Method.EXACT
    assert result.spans[0].confidence == 1.0


def test_detector_is_replaceable():
    """detect.py가 들어오면 기본값만 바꾸면 되도록 인자로 뽑아뒀다."""
    from devdemangle.types import Match

    def fake_detect(text, glossary):
        return [Match(0, 2, "REPLACED", text[0:2], Method.REGEX, 0.8)]

    result = correct("XX 나머지", BASE, detect=fake_detect)
    assert result.text == "REPLACED 나머지"
    assert result.spans[0].method == Method.REGEX


def test_default_glossary_corrects_known_alias():
    """glossary 인자 없이 기본 용어집(data/terms.yaml)으로 동작하는지 확인."""
    from devdemangle import correct as public_correct

    result = public_correct("파이썬 좋아해요")
    assert result.text == "Python 좋아해요"
    assert result.spans[0].term == "Python"
