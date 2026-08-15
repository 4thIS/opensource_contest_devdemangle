from devdemangle.correct import CorrectionResult, Match, correct
from devdemangle.glossary import Term

GITHUB = Term(canonical="GitHub", aliases=["깃허브", "깃헙"])
NPM_INSTALL = Term(canonical="npm install", aliases=["엔피엠 인스톨", "엠피엠 인스톨"])
README = Term(canonical="README", aliases=["리드미", "리드미 파일"])
BASE_TERMS = [GITHUB, NPM_INSTALL, README]


def test_single_token_alias_is_replaced():
    result = correct("깃허브 봤어요", terms=BASE_TERMS)
    assert result.text == "GitHub 봤어요"
    assert result.matches == [Match(original="깃허브", canonical="GitHub", start=0, end=3)]


def test_multi_token_alias_is_replaced():
    result = correct("엔피엠 인스톨 먼저 실행하세요", terms=BASE_TERMS)
    assert result.text == "npm install 먼저 실행하세요"
    assert result.matches == [
        Match(original="엔피엠 인스톨", canonical="npm install", start=0, end=7)
    ]


def test_text_without_alias_passes_through_unchanged():
    result = correct("오늘 날씨가 좋네요", terms=BASE_TERMS)
    assert result.text == "오늘 날씨가 좋네요"
    assert result.matches == []


def test_multiple_terms_in_one_sentence_keep_correct_offsets():
    result = correct("깃허브 리드미 봤어요", terms=BASE_TERMS)
    assert result.text == "GitHub README 봤어요"
    assert result.matches == [
        Match(original="깃허브", canonical="GitHub", start=0, end=3),
        Match(original="리드미", canonical="README", start=4, end=7),
    ]


def test_alias_followed_by_particle_is_not_replaced():
    """알려진 한계: 끝도 토큰 경계와 일치해야 하므로 조사가 바로 붙으면 미매칭."""
    result = correct("깃허브다", terms=BASE_TERMS)
    assert result.text == "깃허브다"
    assert result.matches == []


def test_longer_overlapping_alias_wins():
    short = Term(canonical="AAA", aliases=["가"])
    long = Term(canonical="BBB", aliases=["가 나"])
    result = correct("가 나 다", terms=[short, long])
    assert result.text == "BBB 다"
    assert result.matches == [Match(original="가 나", canonical="BBB", start=0, end=3)]


def test_empty_text_returns_empty_result():
    result = correct("", terms=BASE_TERMS)
    assert result == CorrectionResult(text="", matches=[])
