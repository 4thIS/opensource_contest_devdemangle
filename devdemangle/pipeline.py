"""STT와 용어 보정을 잇고, 원하면 번역까지 잇는다."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from devdemangle.correct import correct, default_glossary
from devdemangle.fuzzy import DEFAULT_THRESHOLD
from devdemangle.glossary import Glossary
from devdemangle.hotwords import build as build_hotwords
from devdemangle.translate.protect import Translator, translate_protected
from devdemangle.types import Span


class STT(Protocol):
    """음성 파일을 텍스트로 바꾸는 것. 구현체는 devdemangle.stt.WhisperSTT."""

    def transcribe(self, audio: str | Path, hotwords: str | None = None) -> str: ...


@dataclass
class PipelineResult:
    raw: str
    corrected: str
    spans: list[Span]
    translated: str | None = None  # 번역기를 안 넘기면 None
    lost: list[str] | None = None  # 번역이 삼켜 되돌리지 못한 용어


def run(
    audio_path: Path,
    stt: STT | None = None,
    glossary: Glossary | None = None,
    translator: Translator | None = None,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> PipelineResult:
    """음성 → 전사 → 용어 보정 → (선택) 번역.

    hotwords는 용어집에서 만들어 전사할 때 넘긴다 — 같은 용어집이 인식 힌트와
    보정 기준을 겸하므로 둘이 어긋나지 않는다.

    stt를 생략하면 WhisperSTT를 만든다. 생성 시점에 모델을 올리므로(GPU 필요)
    필요할 때까지 미룬다 — 테스트는 가짜를 주입해 이 경로를 타지 않는다.

    번역은 **보정 뒤에** 한다. 순서가 반대면 번역기가 뭉갠 용어를 보정해야 하는데,
    그때는 이미 무엇이 용어였는지 알 수 없다.

    보호 대상은 `result.spans`를 그대로 쓴다. spans는 바꾼 것뿐 아니라 이미 표준형이라
    지킨 용어까지 담으므로, STT가 잘 알아들은 용어도 번역에서 보호된다.

    Args:
        threshold: 소리 유사도 하한. correct()로 그대로 넘긴다 — 용어집을 바꾸면
            안전 구간이 움직이므로, 음성에서 들어오는 경로에도 통로를 둔다.
    """
    terms = glossary if glossary is not None else default_glossary()
    hotwords = build_hotwords(terms)

    if stt is None:
        from devdemangle.stt import WhisperSTT

        stt = WhisperSTT()

    raw = stt.transcribe(audio_path, hotwords=hotwords)
    result = correct(raw, glossary, threshold=threshold)

    if translator is None:
        return PipelineResult(raw=raw, corrected=result.text, spans=result.spans)

    protected = translate_protected(result.text, result.spans, translator, terms)
    return PipelineResult(
        raw=raw,
        corrected=result.text,
        spans=result.spans,
        translated=protected.text,
        lost=protected.lost,
    )
