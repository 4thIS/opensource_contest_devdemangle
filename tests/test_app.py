"""데모 앱의 순수 로직 — 하이라이트 조각 만들기.

UI 조립은 테스트하지 않는다. gradio를 띄워야 하고, 띄운다고 확인되는 것도 없다.
여기서 붙잡는 건 **Span 목록이 화면 조각으로 옳게 번역되는가** 하나다.

이 함수가 틀리면 하이라이트가 엉뚱한 글자를 덮는다. 그건 데모의 핵심 화면이고,
좌표가 한 칸만 밀려도 시연에서 바로 드러난다.
"""

from devdemangle.app import highlight
from devdemangle.types import Method, Span


def _span(start, end, term, matched=None, method=Method.EXACT, confidence=1.0):
    return Span(start, end, term, matched or term, method, confidence)


def test_text_without_terms_is_one_plain_chunk():
    """용어가 없으면 통짜 한 조각이다. 라벨이 없으면 하이라이트도 없다."""
    assert highlight("오늘 날씨 좋네요", []) == [("오늘 날씨 좋네요", None)]


def test_term_chunk_carries_the_method_as_label():
    """라벨은 탐지 방법이다 — 화면에서 색으로 갈린다.

    "사전에 있어서 잡았다"와 "소리로 찾았다"가 눈으로 구분되는 것이
    이 데모가 보여줘야 할 차별점이다.
    """
    chunks = highlight("GitHub 봤어요", [_span(0, 6, "GitHub")])

    assert chunks == [("GitHub", "exact"), (" 봤어요", None)]


def test_chunks_rebuild_the_original_text():
    """조각을 이으면 원문이 그대로 나온다 — 글자가 새거나 사라지면 안 된다."""
    text = "GitHub에서 repository 만들었어?"
    spans = [_span(0, 6, "GitHub"), _span(9, 19, "repository")]

    assert "".join(c for c, _ in highlight(text, spans)) == text


def test_handles_term_at_the_very_start_and_end():
    """맨 앞·맨 뒤 용어에서 빈 조각을 만들지 않는다."""
    chunks = highlight("Docker", [_span(0, 6, "Docker")])

    assert chunks == [("Docker", "exact")]


def test_adjacent_spans_do_not_produce_empty_chunks():
    """맞닿은 용어 사이에 빈 조각이 끼면 화면에 빈 칸이 생긴다."""
    chunks = highlight("ABCD", [_span(0, 2, "AB"), _span(2, 4, "CD")])

    assert chunks == [("AB", "exact"), ("CD", "exact")]
    assert all(text for text, _ in chunks)


def test_fuzzy_and_regex_get_their_own_labels():
    """세 방법이 각각 다른 라벨을 받는다."""
    text = "React userId 라다씨"
    spans = [
        _span(0, 5, "React"),
        _span(6, 12, "userId", method=Method.REGEX, confidence=0.8),
        _span(13, 16, "lodash", matched="라다씨", method=Method.FUZZY, confidence=1.0),
    ]

    assert [label for _, label in highlight(text, spans)] == [
        "exact", None, "regex", None, "fuzzy",
    ]


def test_spans_out_of_order_are_still_placed_correctly():
    """정렬을 부르는 쪽에 기대지 않는다."""
    text = "GitHub과 Docker"
    spans = [_span(9, 15, "Docker"), _span(0, 6, "GitHub")]

    assert "".join(c for c, _ in highlight(text, spans)) == text
    assert [label for _, label in highlight(text, spans)] == ["exact", None, "exact"]


from devdemangle.app import view
from devdemangle.pipeline import PipelineResult


class _Translator:
    """넘어온 문장을 기록하고 정해둔 답을 준다."""

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.seen: list[str] = []

    def translate(self, text: str) -> str:
        self.seen.append(text)
        return self._reply


def _result(**kw):
    base = dict(raw="러데쉬 썼어요", corrected="lodash 썼어요",
                spans=[_span(0, 6, "lodash", "러데쉬")], translated="I used lodash.", lost=[])
    return PipelineResult(**(base | kw))


def test_view_shows_what_speech_recognition_wrote():
    assert view(_result(), _Translator("x"))[0] == "러데쉬 썼어요"


def test_view_translates_the_corrected_text_without_masking():
    """보호 없는 번역은 **가리지 않은** 보정 문장을 그대로 넘겨 얻는다.

    같은 모델·같은 문장이라 차이가 보호 여부 하나로 고정된다.
    원문(raw)을 넘기면 STT 오류까지 섞여 비교가 성립하지 않는다.
    """
    tr = _Translator("I used it.")
    unprotected = view(_result(), tr)[2]
    assert tr.seen == ["lodash 썼어요"]
    assert unprotected == "I used it."


def test_view_puts_protected_translation_in_its_own_box():
    assert view(_result(), _Translator("x"))[3] == "I used lodash."


def test_view_without_translator_says_so_in_both_boxes():
    """번역기를 안 올린 실행에서도 화면이 비지 않는다."""
    _, _, unprotected, protected, _ = view(_result(translated=None, lost=None), None)
    assert "번역 없이" in unprotected
    assert "번역 없이" in protected


def test_view_warns_about_terms_the_translation_swallowed():
    _, _, _, protected, _ = view(_result(translated="I used it.", lost=["lodash"]), _Translator("x"))
    assert "lodash" in protected and "⚠️" in protected


from devdemangle.app import pick_source


def test_pick_source_prefers_typed_text():
    """둘 다 들어 있으면 손으로 친 쪽을 쓴다 — 방금 친 것이 방금 의도한 것이다."""
    assert pick_source("a.wav", "  --no-cache 줬어  ") == ("text", "--no-cache 줬어")


def test_pick_source_falls_back_to_audio():
    assert pick_source("a.wav", "") == ("audio", "a.wav")


def test_pick_source_ignores_whitespace_only_text():
    """공백만 남은 입력칸 때문에 음성이 무시되면 안 된다."""
    assert pick_source("a.wav", "   \n ") == ("audio", "a.wav")


def test_pick_source_reports_nothing_to_do():
    assert pick_source(None, "") == ("none", "")
