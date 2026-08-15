"""음성 파일 하나를 전사·보정해서 보여주는 데모 CLI."""

import argparse
import sys
from pathlib import Path

from devdemangle.pipeline import PipelineResult, run


def format_result(result: PipelineResult) -> str:
    if result.matches:
        changes = ", ".join(f"{m.original} → {m.canonical}" for m in result.matches)
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
    parser.add_argument("--compute", default="float16", help="정밀도 (VRAM 부족 시 int8_float16)")
    parser.add_argument("--no-hotwords", action="store_true", help="hotwords 없이 전사 (비교용)")
    args = parser.parse_args(argv)

    if not args.audio.exists():
        print(f"파일이 없습니다: {args.audio}", file=sys.stderr)
        return 1

    from devdemangle.glossary import load_glossary
    from devdemangle.hotwords import build as build_hotwords
    from devdemangle.stt import WhisperTranscriber

    hotwords = None if args.no_hotwords else build_hotwords(load_glossary())
    transcriber = WhisperTranscriber(
        model_size=args.model, compute_type=args.compute, hotwords=hotwords
    )
    print(format_result(run(args.audio, transcriber=transcriber)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
