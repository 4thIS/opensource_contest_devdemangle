"""녹음 파일을 Whisper 규격(16kHz·모노·16bit WAV)으로 변환한다.

팀원이 m4a·mp3 등 아무 형식으로 녹음해 보내도 이걸로 규격을 맞춘다.
ffmpeg가 PATH에 있으면 그걸 쓰고, 없으면 --ffmpeg로 경로를 지정한다.

용법:
    # audio/ 안의 변환 안 된 파일을 전부 WAV로 (기본)
    uv run python experiments/convert_audio.py

    # 다른 폴더의 파일들을 audio/로 변환해 넣기
    uv run python experiments/convert_audio.py --src "C:/.../녹음"

    # 파일 하나만, 이름 지정
    uv run python experiments/convert_audio.py --src rec.m4a --name seed_01.wav

ffmpeg가 없으면:
    --ffmpeg "C:/.../ffmpeg.exe" 로 경로를 직접 준다.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

AUDIO_DIR = Path(__file__).parent / "audio"
SRC_EXTS = {".m4a", ".mp3", ".wav", ".flac", ".ogg", ".aac", ".wma", ".mp4"}


def find_ffmpeg(explicit: str | None) -> str:
    """ffmpeg 실행 경로를 찾는다. 순서: --ffmpeg → PATH."""
    if explicit:
        if Path(explicit).exists():
            return explicit
        sys.exit(f"[오류] 지정한 ffmpeg가 없습니다: {explicit}")

    found = shutil.which("ffmpeg")
    if found:
        return found

    sys.exit("[오류] ffmpeg를 찾을 수 없습니다. --ffmpeg로 ffmpeg.exe 경로를 지정하세요.")


def convert(ffmpeg: str, src: Path, dst: Path) -> None:
    """src를 16kHz·모노·16bit WAV로 변환해 dst에 쓴다."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        "-i", str(src),
        "-ar", "16000",   # 16kHz
        "-ac", "1",       # 모노
        "-c:a", "pcm_s16le",  # 16bit PCM
        str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--src",
        help="변환할 파일 또는 폴더. 생략하면 audio/ 안의 비-WAV 파일을 변환한다.",
    )
    ap.add_argument("--name", help="출력 파일명 (--src가 파일 하나일 때만). 예: seed_01.wav")
    ap.add_argument("--ffmpeg", help="ffmpeg.exe 경로 (PATH에 없을 때)")
    ap.add_argument(
        "--overwrite", action="store_true", help="이미 있는 WAV도 다시 변환한다"
    )
    args = ap.parse_args()

    ffmpeg = find_ffmpeg(args.ffmpeg)
    print(f"ffmpeg: {ffmpeg}\n")

    # 변환할 소스 목록 구성
    if args.src:
        src = Path(args.src)
        if src.is_file():
            jobs = [(src, args.name or f"{src.stem}.wav")]
        elif src.is_dir():
            jobs = [(p, f"{p.stem}.wav") for p in sorted(src.iterdir())
                    if p.suffix.lower() in SRC_EXTS]
        else:
            sys.exit(f"[오류] --src 경로가 없습니다: {src}")
    else:
        # 기본: audio/ 안의 비-WAV 파일을 변환
        jobs = [(p, f"{p.stem}.wav") for p in sorted(AUDIO_DIR.iterdir())
                if p.is_file() and p.suffix.lower() in SRC_EXTS
                and p.suffix.lower() != ".wav"]

    if not jobs:
        print("변환할 파일이 없습니다.")
        if not args.src:
            print(f"  audio 폴더({AUDIO_DIR})에 m4a/mp3 파일을 넣거나 --src로 위치를 지정하세요.")
        return

    ok = skipped = failed = 0
    for src, out_name in jobs:
        dst = AUDIO_DIR / out_name
        if dst.exists() and not args.overwrite and dst.resolve() != src.resolve():
            print(f"  [건너뜀] {out_name} 이미 있음 (--overwrite로 덮어쓰기)")
            skipped += 1
            continue
        try:
            convert(ffmpeg, src, dst)
            print(f"  [변환] {src.name}  →  {out_name}")
            ok += 1
        except subprocess.CalledProcessError as e:
            print(f"  [실패] {src.name}: {e.stderr.decode('utf-8', 'replace')[:200]}")
            failed += 1

    print(f"\n변환 {ok} / 건너뜀 {skipped} / 실패 {failed}")
    if ok:
        print(f"→ {AUDIO_DIR} 에 저장됨. 이제 risk1_hotwords.py를 돌릴 수 있습니다.")


if __name__ == "__main__":
    main()
