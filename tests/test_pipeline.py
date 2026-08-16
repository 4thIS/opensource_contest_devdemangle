from pathlib import Path

from devdemangle.glossary import Glossary
from devdemangle.pipeline import PipelineResult, run
from devdemangle.types import Term


class FakeSTT:
    """미리 정한 문자열을 뱉는 가짜 STT. 모델·GPU·음성 파일이 필요 없다."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[tuple[Path, str | None]] = []

    def transcribe(self, audio, hotwords: str | None = None) -> str:
        self.calls.append((audio, hotwords))
        return self._text


def test_run_corrects_transcribed_text():
    fake = FakeSTT("깃허브 레포지토리 만들었어?")
    result = run(Path("dummy.wav"), stt=fake)
    assert result.corrected == "GitHub repository 만들었어?"


def test_run_keeps_raw_transcription():
    """보정 전 원문을 남긴다 — 데모에서 '이렇게 뭉갰다'를 보여주는 근거다."""
    fake = FakeSTT("깃허브 레포지토리 만들었어?")
    result = run(Path("dummy.wav"), stt=fake)
    assert result.raw == "깃허브 레포지토리 만들었어?"


def test_run_reports_spans():
    fake = FakeSTT("깃허브 레포지토리 만들었어?")
    result = run(Path("dummy.wav"), stt=fake)
    assert [(s.matched, s.term) for s in result.spans] == [
        ("깃허브", "GitHub"),
        ("레포지토리", "repository"),
    ]


def test_run_passes_audio_path_to_stt():
    fake = FakeSTT("안녕하세요")
    run(Path("sample.wav"), stt=fake)
    assert fake.calls[0][0] == Path("sample.wav")


def test_run_passes_hotwords_built_from_glossary():
    """같은 용어집이 인식 힌트와 보정 기준을 겸한다 — 둘이 어긋나면 실험이 무의미해진다."""
    fake = FakeSTT("도커 씁니다")
    glossary = Glossary([Term(canonical="Docker", aliases=("도커",))])
    run(Path("dummy.wav"), stt=fake, glossary=glossary)
    assert fake.calls[0][1] == "Docker"


def test_run_accepts_custom_glossary():
    fake = FakeSTT("도커 씁니다")
    glossary = Glossary([Term(canonical="Docker", aliases=("도커",))])
    result = run(Path("dummy.wav"), stt=fake, glossary=glossary)
    assert result.corrected == "Docker 씁니다"


def test_run_with_no_matches_returns_text_unchanged():
    fake = FakeSTT("오늘 날씨 좋네요")
    result = run(Path("dummy.wav"), stt=fake)
    assert result.corrected == "오늘 날씨 좋네요"
    assert result.spans == []


def test_pipeline_result_is_a_dataclass_with_three_fields():
    fake = FakeSTT("깃허브")
    result = run(Path("dummy.wav"), stt=fake)
    assert isinstance(result, PipelineResult)
    assert result.raw and result.corrected and result.spans
