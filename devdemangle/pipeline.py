"""STT와 용어 보정을 잇는다."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from devdemangle.correct import Match, correct
from devdemangle.glossary import Term


class Transcriber(Protocol):
    """음성 파일을 텍스트로 바꾸는 것. 구현체는 stt.WhisperTranscriber."""

    def transcribe(self, audio_path: Path) -> str: ...


@dataclass
class PipelineResult:
    raw: str
    corrected: str
    matches: list[Match]


def run(
    audio_path: Path,
    transcriber: Transcriber | None = None,
    terms: list[Term] | None = None,
) -> PipelineResult:
    """음성 → 전사 → 용어 보정.

    transcriber를 생략하면 기본 용어집으로 hotwords를 만든 WhisperTranscriber를
    쓴다 (모델 로드가 일어나므로 테스트에서는 가짜를 주입한다).
    """
    if transcriber is None:
        from devdemangle.glossary import load_glossary
        from devdemangle.stt import WhisperTranscriber, hotwords_from

        glossary = terms if terms is not None else load_glossary()
        transcriber = WhisperTranscriber(hotwords=hotwords_from(glossary))

    raw = transcriber.transcribe(audio_path)
    result = correct(raw, terms=terms)
    return PipelineResult(raw=raw, corrected=result.text, matches=result.matches)
