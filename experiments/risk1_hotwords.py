"""리스크 1: hotwords가 한국어 발화 속 영어 개발 용어 인식을 개선하는지 측정한다.

hotwords 없음 / 있음 두 조건에서 같은 오디오를 전사하고, 표준형 용어가 얼마나
살아남는지 비교한다. 차이가 +5%p 이상이면 hotwords.py를 만든다.
판정 기준(+5%p)은 측정 전에 확정했다. 결과: `experiments/results/risk1.md`

용법:
    uv run --extra cuda python experiments/risk1_hotwords.py
    uv run --extra cuda python experiments/risk1_hotwords.py --model medium   # VRAM 부족 시
    uv run --extra cuda python experiments/risk1_hotwords.py \
        --manifest experiments/audio/manifest_문장끝.yaml                     # 2차 정답지
"""

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from devdemangle._cuda import setup_cuda_dlls  # noqa: E402

setup_cuda_dlls()  # faster_whisper import 전에 반드시 호출

from faster_whisper import WhisperModel  # noqa: E402

AUDIO_DIR = Path(__file__).parent / "audio"
MANIFEST = AUDIO_DIR / "manifest.yaml"


def load_manifest(path: Path = MANIFEST):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def transcribe(model, path: Path, hotwords: str | None) -> str:
    segments, _ = model.transcribe(
        str(path),
        language="ko",
        hotwords=hotwords,
        vad_filter=True,
    )
    return " ".join(s.text for s in segments).strip()


def found_terms(text: str, terms: list[str]) -> list[str]:
    """전사 결과에 표준형 용어가 그대로 들어 있는 것 (대소문자 무시)."""
    low = text.lower()
    return [t for t in terms if t.lower() in low]


def run_condition(model, entries, label: str, hotwords: str | None):
    """한 조건(hotwords 유무)으로 전체를 전사하고 결과를 모은다."""
    total = hits = 0
    rows = []  # (file, speaker, terms, found, text)
    print(f"=== {label} ===")
    for e in entries:
        path = AUDIO_DIR / e["file"]
        if not path.exists():
            print(f"  [건너뜀] {e['file']} 없음")
            continue
        text = transcribe(model, path, hotwords)
        got = found_terms(text, e["terms"])
        total += len(e["terms"])
        hits += len(got)
        mark = "OK  " if len(got) == len(e["terms"]) else "MISS"
        print(f"  [{mark}] {e['file']}: {text}")
        if len(got) != len(e["terms"]):
            print(f"          놓침: {sorted(set(e['terms']) - set(got))}")
        rows.append((e["file"], e.get("speaker", "?"), e["terms"], got, text))
    rate = hits / total * 100 if total else 0.0
    print(f"  >>> 용어 인식률: {hits}/{total} = {rate:.1f}%\n")
    return {"label": label, "hits": hits, "total": total, "rate": rate, "rows": rows}


def per_speaker_diff(off, on):
    """화자별로 hotwords 없음→있음 인식률을 집계한다 (편향 대응 근거).

    '3명이 나눠 녹음했다'를 사람 기억이 아니라 실행 로그로 증명한다.
    """
    def collect(res):
        d = {}
        for _file, spk, terms, got, _text in res["rows"]:
            d.setdefault(spk, {"total": 0, "hit": 0})
            d[spk]["total"] += len(terms)
            d[spk]["hit"] += len(got)
        return d

    a, b = collect(off), collect(on)
    print("=== 화자별 인식률 (없음 → 있음) ===")
    for spk in sorted(a):
        o = a[spk]["hit"] / a[spk]["total"] * 100 if a[spk]["total"] else 0
        n = b[spk]["hit"] / b[spk]["total"] * 100 if b[spk]["total"] else 0
        print(
            f"  화자 {spk}: {a[spk]['hit']}/{a[spk]['total']} = {o:.1f}%"
            f"  →  {b[spk]['hit']}/{b[spk]['total']} = {n:.1f}%  ({n - o:+.1f}%p)"
        )
    print(f"  화자 수: {len(a)}명\n")


def per_term_diff(off, on):
    """용어별로 hotwords 없음→있음에서 인식이 어떻게 바뀌었는지 (발표·보고서용)."""
    def collect(res):
        d = {}
        for _file, _spk, terms, got, _text in res["rows"]:
            for t in terms:
                d.setdefault(t, {"total": 0, "hit": 0})
                d[t]["total"] += 1
                d[t]["hit"] += 1 if t in got else 0
        return d

    a, b = collect(off), collect(on)
    print("=== 용어별 변화 (없음 → 있음) ===")
    improved, worsened, same = [], [], []
    for t in sorted(a):
        o, n = a[t]["hit"], b[t]["hit"]
        tot = a[t]["total"]
        tag = "→"
        if n > o:
            tag, _ = "↑ 개선", improved.append(t)
        elif n < o:
            tag, _ = "↓ 악화", worsened.append(t)
        else:
            same.append(t)
        print(f"  {t:<14} {o}/{tot} → {n}/{tot}  {tag}")
    print(f"\n  개선 {len(improved)} / 악화 {len(worsened)} / 변화없음 {len(same)}")
    if worsened:
        print(f"  ⚠️ 악화된 용어: {worsened} (역효과 — 보고서에 원인 기록)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="large-v3", help="Whisper 모델 (기본 large-v3)")
    ap.add_argument(
        "--compute", default="float16", help="정밀도 (VRAM 부족 시 int8_float16)"
    )
    ap.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST,
        help="정답지 (기본 1차 manifest.yaml). 차수가 다르면 섞지 말고 파일을 바꾼다",
    )
    args = ap.parse_args()

    entries = load_manifest(args.manifest)
    present = [e for e in entries if (AUDIO_DIR / e["file"]).exists()]
    speakers = sorted({e.get("speaker", "?") for e in present})

    print(f"매니페스트 {len(entries)}개 중 녹음 존재 {len(present)}개")
    print(f"화자 {len(speakers)}명: {', '.join(speakers)}\n")
    if not present:
        print("⚠️ 녹음 파일이 하나도 없습니다. experiments/audio/에 seed_*.wav를 넣으세요.")
        print("   목록: experiments/audio/녹음목록.md")
        return

    all_terms = sorted({t for e in present for t in e["terms"]})
    hotwords_str = " ".join(all_terms)
    print(f"용어 {len(all_terms)}개를 hotwords로 사용:\n  {hotwords_str}\n")

    print(f"모델 로딩: {args.model} ({args.compute})...")
    model = WhisperModel(args.model, device="cuda", compute_type=args.compute)
    print("로딩 완료.\n")

    off = run_condition(model, present, "hotwords 없음", None)
    on = run_condition(model, present, "hotwords 있음", hotwords_str)

    per_term_diff(off, on)
    per_speaker_diff(off, on)

    diff = on["rate"] - off["rate"]
    print("\n" + "=" * 50)
    print(f"hotwords 없음: {off['rate']:.1f}%  →  있음: {on['rate']:.1f}%")
    print(f"차이: {diff:+.1f}%p")
    if diff >= 5:
        verdict = "효과 있음 → hotwords.py 구현"
    elif diff <= -5:
        verdict = "역효과 → 접근법 2로 전환 + 원인 분석"
    else:
        verdict = "효과 없음 → 접근법 2로 전환 (실험했으나 효과 없어 제외)"
    print(f"판정: {verdict}")
    print("=" * 50)
    print(f"\n녹음 파일 {len(present)}개 / 화자 {len(speakers)}명: {', '.join(speakers)}")
    print("결과를 experiments/results/risk1.md에 기록하세요 (숫자 + 화자 수 필수).")
    if len(speakers) < 2:
        print("⚠️ 화자가 1명이면 파일럿입니다. 최종 판정은 여러 명 녹음 후.")


if __name__ == "__main__":
    main()
