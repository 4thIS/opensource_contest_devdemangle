"""조사 경계 완화 규칙의 오탐을 실측한다 (PR #5 §2 배정 작업).

규칙 (2026-08-13 팀 합의):
  ① 시작 경계는 그대로 엄격하게 — 매치 시작 == 토큰 시작
  ② 끝 경계만 완화하되, 남는 꼬리가 조사 목록에 있을 때만
  ③ 문장부호는 매칭 전에 떼어낸다

측정 대상은 risk1 실험의 실측 전사문 42건(21문장 × hotwords 유/무)이다.
정답지는 audio/manifest.yaml의 terms 필드.

  실행: python experiments/particle_boundary.py
"""

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from devdemangle.glossary import load_glossary  # noqa: E402

# 팀 합의 목록. 닫힌 집합이라 목록으로 관리한다 (임의 접미사 허용 아님).
PARTICLES = [
    "은", "는", "이", "가", "을", "를", "의", "에", "에서", "으로", "로",
    "와", "과", "랑", "이랑", "도", "만", "까지", "부터", "에게", "한테",
    "보다", "처럼", "마다",
]
# 긴 것부터 봐야 "에서"가 "에"로 잘리지 않는다.
PARTICLES.sort(key=len, reverse=True)

PUNCT = ".,?!…·:;\"'()[]"
TOKEN_RE = re.compile(r"\S+")

RAW_LOG = Path(__file__).parent / "results" / "risk1.md"
MANIFEST = Path(__file__).parent / "audio" / "manifest.yaml"


def strip_punct(token: str) -> tuple[str, str]:
    """문장부호를 뒤에서 떼어낸다. (본체, 떼어낸 꼬리)"""
    body = token.rstrip(PUNCT)
    return body, token[len(body) :]


def match_token(token: str, aliases: dict[str, str]) -> tuple[str, str, str] | None:
    """토큰 하나가 alias + 조사(선택) 형태인지 본다.

    반환: (매칭된 alias, canonical, 남은 꼬리) 또는 None
    """
    body, _punct = strip_punct(token)
    low = body.lower()

    # 시작 경계는 엄격 — 토큰 처음부터 alias가 시작해야 한다.
    for alias, canonical in aliases.items():
        if not low.startswith(alias.lower()):
            continue
        tail = body[len(alias) :]
        if tail == "":
            return alias, canonical, ""
        if tail in PARTICLES:
            return alias, canonical, tail
    return None


def load_transcripts() -> list[tuple[str, str, str]]:
    """risk1.md 원시 로그에서 (조건, seed, 전사문)을 뽑는다."""
    text = RAW_LOG.read_text(encoding="utf-8")
    rows, condition = [], "?"
    for line in text.splitlines():
        if "hotwords" in line and ("없음" in line or "없이" in line):
            condition = "hotwords 없음"
        elif "hotwords" in line and ("있음" in line or "적용" in line):
            condition = "hotwords 있음"
        m = re.search(r"\[(OK  |MISS)\]\s+(seed_\d+)\.wav:\s*(.+?)\s*$", line)
        if m:
            rows.append((condition, m.group(2), m.group(3)))
    return rows


def main() -> int:
    glossary = load_glossary()
    aliases: dict[str, str] = {}
    for term in glossary:
        for alias in term.aliases:
            aliases[alias] = term.canonical
        aliases[term.canonical] = term.canonical
    # 긴 alias 우선 (겹침 길이 1순위와 같은 원칙)
    aliases = dict(sorted(aliases.items(), key=lambda kv: -len(kv[0])))

    truth = {
        e["file"].replace(".wav", ""): set(e["terms"])
        for e in yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    }

    transcripts = load_transcripts()
    if not transcripts:
        print("전사문을 못 찾았다. risk1.md 원시 로그 형식을 확인할 것.")
        return 1

    gained_right, gained_wrong, unchanged = [], [], 0

    for condition, seed, line in transcripts:
        expected = truth.get(seed, set())
        for token in TOKEN_RE.findall(line):
            hit = match_token(token, aliases)
            if hit is None:
                continue
            alias, canonical, tail = hit
            if tail == "":
                unchanged += 1  # 조사 없이도 기존 규칙이 잡던 것
                continue
            row = (condition, seed, token, f"{alias}+{tail}", canonical)
            (gained_right if canonical in expected else gained_wrong).append(row)

    total_gained = len(gained_right) + len(gained_wrong)
    print(f"표본: 전사문 {len(transcripts)}건 (21문장 x 2조건)")
    print(f"기존 규칙으로 이미 잡히던 것: {unchanged}건\n")
    print(f"조사 규칙으로 새로 잡히는 것: {total_gained}건")
    print(f"  - 정답  : {len(gained_right)}건")
    print(f"  - 오탐  : {len(gained_wrong)}건")
    if total_gained:
        rate = len(gained_wrong) / total_gained * 100
        print(f"  - 오탐률: {rate:.1f}%")

    print("\n[정답으로 새로 잡히는 것]")
    for c, s, tok, split, canon in gained_right:
        print(f"  {s} ({c}): {tok!r} = {split} -> {canon}")

    print("\n[오탐]")
    if not gained_wrong:
        print("  없음")
    for c, s, tok, split, canon in gained_wrong:
        print(f"  {s} ({c}): {tok!r} = {split} -> {canon}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
