"""STT와 용어 보정을 잇고, 원하면 번역까지 잇는다."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from devdemangle.correct import correct, default_glossary
from devdemangle.glossary import Glossary
from devdemangle.hotwords import build as build_hotwords
from devdemangle.translate.protect import (
    Translator,
    spans_for_protection,
    translate_protected,
)
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
) -> PipelineResult:
    """음성 → 전사 → 용어 보정 → (선택) 번역.

    hotwords는 용어집에서 만들어 전사할 때 넘긴다 — 같은 용어집이 인식 힌트와
    보정 기준을 겸하므로 둘이 어긋나지 않는다.

    stt를 생략하면 WhisperSTT를 만든다. 생성 시점에 모델을 올리므로(GPU 필요)
    필요할 때까지 미룬다 — 테스트는 가짜를 주입해 이 경로를 타지 않는다.

    번역은 **보정 뒤에** 한다. 순서가 반대면 번역기가 뭉갠 용어를 보정해야 하는데,
    그때는 이미 무엇이 용어였는지 알 수 없다.

    보호 대상은 `result.spans`가 아니라 보정된 문장에서 **다시 찾는다.** spans는
    바꾼 것만 담고 있어서, 이미 표준형이던 용어(STT가 잘 알아들은 것)가 빠진다.
    그 상태로 번역하면 잘 인식된 문장일수록 더 망가진다 — 실측에서 REST API가
    `ReST APl`, React가 `the real thing`이 됐다.
    """
    terms = glossary if glossary is not None else default_glossary()
    hotwords = build_hotwords(terms)

    if stt is None:
        from devdemangle.stt import WhisperSTT

        stt = WhisperSTT()

    raw = stt.transcribe(audio_path, hotwords=hotwords)
    result = correct(raw, glossary)

    if translator is None:
        return PipelineResult(raw=raw, corrected=result.text, spans=result.spans)

    guard = spans_for_protection(result.text, terms)
    protected = translate_protected(result.text, guard, translator)
    return PipelineResult(
        raw=raw,
        corrected=result.text,
        spans=result.spans,
        translated=protected.text,
        lost=protected.lost,
    )
