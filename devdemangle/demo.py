"""음성 파일 하나를 전사·보정해서 보여주는 데모 CLI."""

import argparse
import sys
from pathlib import Path

from devdemangle.pipeline import PipelineResult, run


def format_result(result: PipelineResult) -> str:
    if result.spans:
        changes = ", ".join(f"{s.matched} → {s.term}" for s in result.spans)
    else:
        changes = "없음"

    lines = [
        f"[전사] {result.raw}",
        f"[보정] {result.corrected}",
        f"[변경] {changes}",
    ]
    if result.translated is not None:
        lines.append(f"[번역] {result.translated}")
    # 번역이 삼킨 용어는 숨기지 않는다 — 있을 때만 줄이 는다
    if result.lost:
        lines.append(f"[유실] {', '.join(result.lost)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    # 한국어 Windows(cp949)에서 한글 출력이 깨지는 것을 막는다.
    # 에러 메시지는 stderr로 나가므로 둘 다 바꿔야 한다.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="음성 파일을 전사하고 개발 용어를 보정한다")
    parser.add_argument("audio", type=Path, help="음성 파일 경로 (WAV)")
    parser.add_argument("--model", default="large-v3", help="Whisper 모델 (기본 large-v3)")
    parser.add_argument("--device", default="cuda", help="추론 장치 (기본 cuda)")
    parser.add_argument("--compute", default="float16", help="정밀도 (VRAM 부족 시 int8_float16)")
    parser.add_argument("--no-hotwords", action="store_true", help="hotwords 없이 전사 (비교용)")
    parser.add_argument(
        "--translate",
        action="store_true",
        help="보정 후 영어로 번역한다 (용어는 보호). uv sync --extra translate 필요",
    )
    args = parser.parse_args(argv)

    if not args.audio.exists():
        print(f"파일이 없습니다: {args.audio}", file=sys.stderr)
        return 1

    from devdemangle.stt import WhisperSTT

    stt = WhisperSTT(model_size=args.model, device=args.device, compute_type=args.compute)
    if args.no_hotwords:
        stt = _WithoutHotwords(stt)

    translator = None
    if args.translate:
        # 번역 모델은 여기서만 올린다 — 안 쓰는 실행에 수백 MB를 물리지 않는다.
        from devdemangle.translate.opusmt import OpusMTTranslator

        translator = OpusMTTranslator()

    print(format_result(run(args.audio, stt=stt, translator=translator)))
    return 0


class _WithoutHotwords:
    """hotwords를 떼고 전사한다 (비교용).

    파이프라인이 용어집에서 hotwords를 만들어 넘기므로, 끄려면 넘어온 값을
    여기서 버린다. 파이프라인에 "끄기" 분기를 두지 않기 위한 것이다.
    """

    def __init__(self, inner) -> None:
        self._inner = inner

    def transcribe(self, audio, hotwords: str | None = None) -> str:
        return self._inner.transcribe(audio, hotwords=None)


if __name__ == "__main__":
    raise SystemExit(main())
