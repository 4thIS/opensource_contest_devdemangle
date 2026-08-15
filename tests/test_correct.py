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


def test_alias_inside_larger_token_is_not_replaced():
    """알려진 한계 테스트와 대칭: 이번엔 alias가 토큰 뒤쪽에 붙어 있어 시작 경계가 안 맞는 경우."""
    result = correct("우리깃허브 봤어요", terms=BASE_TERMS)
    assert result.text == "우리깃허브 봤어요"
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


def test_empty_terms_list_passes_text_through_unchanged():
    result = correct("깃허브 봤어요", terms=[])
    assert result.text == "깃허브 봤어요"
    assert result.matches == []


def test_default_glossary_corrects_known_alias():
    """terms 인자 없이 기본 용어집(devdemangle/data/terms.yaml)으로 동작하는지 확인."""
    from devdemangle import correct as public_correct

    result = public_correct("파이썬 좋아해요")
    assert result.text == "Python 좋아해요"
    assert result.matches[0].canonical == "Python"


def test_lowercase_alias_is_corrected_to_canonical():
    """Whisper가 소문자로 뱉은 실측 케이스(`sql 문을`)를 잡는다."""
    sql = Term(canonical="SQL", aliases=["SQL", "에스큐엘"])
    result = correct("sql 문을 짰어", terms=[sql])
    assert result.text == "SQL 문을 짰어"
    assert result.matches == [Match(original="sql", canonical="SQL", start=0, end=3)]


def test_already_canonical_is_left_alone():
    """C-COR-02: 이미 표준형인 것은 건드리지 않는다 (매치로도 잡히지 않는다)."""
    sql = Term(canonical="SQL", aliases=["SQL", "에스큐엘"])
    result = correct("SQL 문을 짰어", terms=[sql])
    assert result.text == "SQL 문을 짰어"
    assert result.matches == []


def test_match_original_keeps_source_casing():
    """치환은 표준형으로 하되, 무엇을 바꿨는지는 원문 그대로 남긴다."""
    vscode = Term(canonical="VS Code", aliases=["VS Code", "브이에스 코드"])
    result = correct("vs code 켰어", terms=[vscode])
    assert result.text == "VS Code 켰어"
    assert result.matches[0].original == "vs code"


def test_longest_match_wins_even_when_it_starts_later():
    """겹침 우선순위는 길이가 1순위다. 짧고 앞선 것이 긴 것을 이기면 안 된다."""
    short = Term(canonical="SHORT", aliases=["가 나"])
    long = Term(canonical="LONG", aliases=["나 다 라"])
    result = correct("가 나 다 라", terms=[short, long])
    assert result.text == "가 LONG"
    assert result.matches == [Match(original="나 다 라", canonical="LONG", start=2, end=7)]


def test_equal_length_overlap_prefers_earlier_start():
    first = Term(canonical="FIRST", aliases=["가 나"])
    second = Term(canonical="SECOND", aliases=["나 다"])
    result = correct("가 나 다", terms=[first, second])
    assert result.text == "FIRST 다"
