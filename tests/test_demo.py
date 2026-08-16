from devdemangle.demo import format_result
from devdemangle.pipeline import PipelineResult
from devdemangle.types import Method, Span


def test_format_result_shows_raw_corrected_and_changes():
    result = PipelineResult(
        raw="깃허브 레포지토리",
        corrected="GitHub repository",
        spans=[
            Span(0, 6, "GitHub", "깃허브", Method.EXACT, 1.0),
            Span(7, 17, "repository", "레포지토리", Method.EXACT, 1.0),
        ],
    )
    assert format_result(result) == (
        "[전사] 깃허브 레포지토리\n"
        "[보정] GitHub repository\n"
        "[변경] 깃허브 → GitHub, 레포지토리 → repository"
    )


def test_format_result_without_matches_says_none():
    result = PipelineResult(raw="오늘 날씨", corrected="오늘 날씨", spans=[])
    assert format_result(result) == (
        "[전사] 오늘 날씨\n"
        "[보정] 오늘 날씨\n"
        "[변경] 없음"
    )
