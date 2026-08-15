from devdemangle.correct import Match
from devdemangle.demo import format_result
from devdemangle.pipeline import PipelineResult


def test_format_result_shows_raw_corrected_and_changes():
    result = PipelineResult(
        raw="깃허브 레포지토리",
        corrected="GitHub repository",
        matches=[
            Match(original="깃허브", canonical="GitHub", start=0, end=3),
            Match(original="레포지토리", canonical="repository", start=4, end=9),
        ],
    )
    assert format_result(result) == (
        "[전사] 깃허브 레포지토리\n"
        "[보정] GitHub repository\n"
        "[변경] 깃허브 → GitHub, 레포지토리 → repository"
    )


def test_format_result_without_matches_says_none():
    result = PipelineResult(raw="오늘 날씨", corrected="오늘 날씨", matches=[])
    assert format_result(result) == (
        "[전사] 오늘 날씨\n"
        "[보정] 오늘 날씨\n"
        "[변경] 없음"
    )
