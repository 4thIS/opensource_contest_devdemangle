"""음성 파일 하나를 전사·보정해서 보여주는 데모 CLI."""

import argparse
import sys
from pathlib import Path

from devdemangle.pipeline import PipelineResult, run


def format_result(result: PipelineResult) -> str:
    # spans는 지킨 것까지 담는다. 여기서는 실제로 바뀐 것만 보여준다 —
    # "userId → userId"는 변경이 아니다.
    replaced = [s for s in result.spans if s.matched != s.term]
    if replaced:
        changes = ", ".join(f"{s.matched} → {s.term}" for s in replaced)
    else:
        changes = "없음"
    return f"[전사] {result.raw}\n[보정] {result.corrected}\n[변경] {changes}"


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
    args = parser.parse_args(argv)

    if not args.audio.exists():
        print(f"파일이 없습니다: {args.audio}", file=sys.stderr)
        return 1

    from devdemangle.stt import WhisperSTT

    stt = WhisperSTT(model_size=args.model, device=args.device, compute_type=args.compute)
    if args.no_hotwords:
        stt = _WithoutHotwords(stt)

    print(format_result(run(args.audio, stt=stt)))
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
