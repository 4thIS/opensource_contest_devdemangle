from pathlib import Path

from devdemangle.glossary import Term
from devdemangle.pipeline import PipelineResult, run


class FakeTranscriber:
    """미리 정한 문자열을 뱉는 가짜 STT. 모델·GPU·음성 파일이 필요 없다."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[Path] = []

    def transcribe(self, audio_path: Path) -> str:
        self.calls.append(audio_path)
        return self._text


def test_run_corrects_transcribed_text():
    fake = FakeTranscriber("깃허브 레포지토리 만들었어?")
    result = run(Path("dummy.wav"), transcriber=fake)
    assert result.corrected == "GitHub repository 만들었어?"


def test_run_keeps_raw_transcription():
    """보정 전 원문을 남긴다 — 데모에서 '이렇게 뭉갰다'를 보여주는 근거다."""
    fake = FakeTranscriber("깃허브 레포지토리 만들었어?")
    result = run(Path("dummy.wav"), transcriber=fake)
    assert result.raw == "깃허브 레포지토리 만들었어?"


def test_run_reports_matches():
    fake = FakeTranscriber("깃허브 레포지토리 만들었어?")
    result = run(Path("dummy.wav"), transcriber=fake)
    assert [(m.original, m.canonical) for m in result.matches] == [
        ("깃허브", "GitHub"),
        ("레포지토리", "repository"),
    ]


def test_run_passes_audio_path_to_transcriber():
    fake = FakeTranscriber("안녕하세요")
    run(Path("sample.wav"), transcriber=fake)
    assert fake.calls == [Path("sample.wav")]


def test_run_accepts_custom_glossary():
    fake = FakeTranscriber("도커 씁니다")
    terms = [Term(canonical="Docker", aliases=["도커"])]
    result = run(Path("dummy.wav"), transcriber=fake, terms=terms)
    assert result.corrected == "Docker 씁니다"


def test_run_with_no_matches_returns_text_unchanged():
    fake = FakeTranscriber("오늘 날씨 좋네요")
    result = run(Path("dummy.wav"), transcriber=fake)
    assert result.corrected == "오늘 날씨 좋네요"
    assert result.matches == []


def test_pipeline_result_is_a_dataclass_with_three_fields():
    fake = FakeTranscriber("깃허브")
    result = run(Path("dummy.wav"), transcriber=fake)
    assert isinstance(result, PipelineResult)
    assert result.raw and result.corrected and result.matches
