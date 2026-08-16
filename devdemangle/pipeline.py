"""STT와 용어 보정을 잇는다."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from devdemangle.correct import correct, default_glossary
from devdemangle.glossary import Glossary
from devdemangle.hotwords import build as build_hotwords
from devdemangle.types import Span


class STT(Protocol):
    """음성 파일을 텍스트로 바꾸는 것. 구현체는 devdemangle.stt.WhisperSTT."""

    def transcribe(self, audio: str | Path, hotwords: str | None = None) -> str: ...


@dataclass
class PipelineResult:
    raw: str
    corrected: str
    spans: list[Span]


def run(
    audio_path: Path,
    stt: STT | None = None,
    glossary: Glossary | None = None,
) -> PipelineResult:
    """음성 → 전사 → 용어 보정.

    hotwords는 용어집에서 만들어 전사할 때 넘긴다 — 같은 용어집이 인식 힌트와
    보정 기준을 겸하므로 둘이 어긋나지 않는다.

    stt를 생략하면 WhisperSTT를 만든다. 생성 시점에 모델을 올리므로(GPU 필요)
    필요할 때까지 미룬다 — 테스트는 가짜를 주입해 이 경로를 타지 않는다.
    """
    terms = glossary if glossary is not None else default_glossary()
    hotwords = build_hotwords(terms)

    if stt is None:
        from devdemangle.stt import WhisperSTT

        stt = WhisperSTT()

    raw = stt.transcribe(audio_path, hotwords=hotwords)
    result = correct(raw, glossary)
    return PipelineResult(raw=raw, corrected=result.text, spans=result.spans)
