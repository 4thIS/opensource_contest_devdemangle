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


def test_run_lowers_threshold_to_catch_weaker_sounds():
    """임계값을 내리면 기본값에서 놓치던 것을 잡는다.

    "닷커"는 별칭 "도커"와 0.727이라 기본값 0.78에 못 미친다.
    """
    fake = FakeSTT("닷커 컨테이너")
    glossary = Glossary([Term(canonical="Docker", aliases=("도커",))])

    result = run(Path("dummy.wav"), stt=fake, glossary=glossary, threshold=0.70)

    assert result.corrected == "Docker 컨테이너"


def test_run_raises_threshold_to_be_stricter():
    """임계값을 올리면 기본값에서 잡히던 것도 버린다.

    용어집을 늘리면 안전 구간이 움직인다 — 그때 파이프라인을 타는 경로에서도
    새 값을 쓸 수 있어야 한다. "더커"는 0.909라 기본값에서는 잡힌다.
    """
    fake = FakeSTT("더커 컨테이너")
    glossary = Glossary([Term(canonical="Docker", aliases=("도커",))])

    result = run(Path("dummy.wav"), stt=fake, glossary=glossary, threshold=0.95)

    assert result.corrected == "더커 컨테이너"


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


class FakeTranslator:
    """받은 문장을 기록하고 정해둔 답을 돌려준다."""

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.seen: list[str] = []

    def translate(self, text: str) -> str:
        self.seen.append(text)
        return self._reply


def test_run_without_translator_leaves_translation_empty():
    """번역은 선택이다 — 안 넘기면 STT·보정만 돌고 끝난다."""
    result = run(Path("dummy.wav"), stt=FakeSTT("깃허브 봤어요"))
    assert result.translated is None


def test_run_translates_with_terms_protected():
    """번역기에는 용어가 아니라 플레이스홀더가 가야 한다."""
    fake = FakeSTT("깃허브 봤어요")
    tr = FakeTranslator("I saw TERMZERO.")
    result = run(Path("dummy.wav"), stt=fake, translator=tr)

    assert tr.seen == ["TERMZERO 봤어요"]   # 보정된 텍스트를 가려서 넘겼다
    assert result.translated == "I saw GitHub."


def test_run_reports_terms_lost_in_translation():
    fake = FakeSTT("깃허브 봤어요")
    tr = FakeTranslator("I saw it.")  # 플레이스홀더가 사라졌다
    result = run(Path("dummy.wav"), stt=fake, translator=tr)
    assert result.lost == ["GitHub"]


def test_run_translates_using_glossary_fixed_translation():
    """용어집의 고정 번역어가 번역 경로까지 이어진다."""
    fake = FakeSTT("의존성 주입으로 풀었어요")
    glossary = Glossary([Term(canonical="의존성 주입", translations={"en": "dependency injection"})])
    tr = FakeTranslator("I solved it with TERMZERO.")
    result = run(Path("dummy.wav"), stt=fake, glossary=glossary, translator=tr)
    assert result.translated == "I solved it with dependency injection."
