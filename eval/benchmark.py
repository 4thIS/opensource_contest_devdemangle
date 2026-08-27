"""평가 하니스 — 픽스처와 실측 전사를 관통시켜 수치를 낸다.

pytest(코드가 맞나)와 다르다. 여기는 **효과가 있나**를 잰다.

세는 방식을 이 파일에 몰아둔 이유는 그것만 따로 테스트하기 위해서다. 하니스가
조용히 잘못 세면 숫자는 그럴듯하게 나오고 보고서까지 그대로 간다.
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from devdemangle import correct
from devdemangle.correct import default_glossary
from devdemangle.fuzzy import DEFAULT_THRESHOLD


@dataclass
class Outcome:
    """픽스처 한 건의 채점 결과."""

    text_ok: bool          # 결과 문장이 기대와 정확히 같은가
    tp: int                # 기대한 용어를 찾음
    fp: int                # 기대하지 않은 것을 찾음 — 오탐
    fn: int                # 기대했는데 못 찾음 — 미탐
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)


def score(
    expected_text: str,
    expected_terms: list[str],
    got_text: str,
    got_terms: list[str],
) -> Outcome:
    """용어를 **다중집합**으로 대조한다.

    집합으로 접으면 한 문장에 같은 용어가 두 번 나올 때 하나만 찾아도 만점이 된다.
    """
    want, have = Counter(expected_terms), Counter(got_terms)
    hit = want & have

    missing = list((want - have).elements())
    extra = list((have - want).elements())

    return Outcome(
        text_ok=(expected_text == got_text),
        tp=sum(hit.values()),
        fp=len(extra),
        fn=len(missing),
        missing=missing,
        extra=extra,
    )


@dataclass
class Metrics:
    """모아서 낸 수치. 잴 수 없는 것은 `None`으로 남긴다."""

    recall: float | None
    precision: float | None
    sentence_accuracy: float | None
    false_positive_rate: float | None
    n: int


def _ratio(num: int, den: int) -> float | None:
    """분모가 0이면 `None`. 0으로 채우면 '나쁨'으로, 1로 채우면 '만점'으로 읽힌다."""
    return round(num / den, 4) if den else None


def aggregate(outcomes: list[Outcome]) -> Metrics:
    """여러 건을 하나로.

    **오탐률만 문장 단위다.** 나머지는 용어 단위다. 한 문장에서 오탐이 둘 나면
    정밀도는 두 번 깎이지만 오탐 문장은 하나다 — 보고서에는 둘 다 필요하다.
    """
    tp = sum(o.tp for o in outcomes)
    fp = sum(o.fp for o in outcomes)
    fn = sum(o.fn for o in outcomes)

    return Metrics(
        recall=_ratio(tp, tp + fn),
        precision=_ratio(tp, tp + fp),
        sentence_accuracy=_ratio(sum(o.text_ok for o in outcomes), len(outcomes)),
        false_positive_rate=_ratio(sum(not o.text_ok for o in outcomes), len(outcomes)),
        n=len(outcomes),
    )


def classify(item: dict) -> str:
    """픽스처 한 건이 무엇을 시험하는지.

    세 갈래가 `terms` 하나로 갈린다. **텍스트만으로는 오탐과 보호를 구분할 수 없다** —
    둘 다 문장이 안 바뀌기 때문이다.

        broken != expected                  →  복원
        broken == expected · terms 비었음     →  오탐
        broken == expected · terms 있음       →  보호
    """
    if item["broken"] != item["expected"]:
        return "복원"
    return "보호" if item.get("terms") else "오탐"


def survived(text: str, terms: list[str]) -> int:
    """`text`에 표준형이 그대로 살아있는 용어의 수.

    대소문자는 무시한다. 전사가 `sql`로 뱉은 것을 깨졌다고 세면 3단계 비교표의
    첫 칸이 실제보다 나쁘게 나온다 — 재려는 것은 표기 통일이 아니라 **소실**이다.
    """
    low = text.lower()
    return sum(1 for t in terms if t.lower() in low)


def brief_table(records: list[dict], glossary, threshold: float = DEFAULT_THRESHOLD) -> str:
    """시연에서 화면에 띄울 짧은 표.

    전체 보고서는 50줄이 넘어 터미널 한 화면에 안 들어간다. 촬영 중 스크롤이 생기면
    표가 화면 밖으로 나가므로, **전체 표본 2×2만** 남긴다.

    마크다운 기호를 쓰지 않는다. 터미널에서는 `|`가 읽기를 방해한다.
    """
    st = run_stages(records, glossary, threshold)
    total = sum(len(r["terms"]) for r in records)

    def cell(hot: str, fix: str) -> str:
        part, whole = st[(hot, fix)]
        return f"{part / whole * 100:.1f}%" if whole else "—"

    lines = [
        f"용어가 살아남은 비율 — 문장 {len(records)}건 · 용어 {total}회",
        "",
        f"{'':10}{'보정 없음':>10}{'보정 적용':>12}",
    ]
    for hot in ("힌트 없음", "힌트 적용"):
        lines.append(
            f"{hot:10}{cell(hot, '보정 없음'):>12}{cell(hot, '보정 적용'):>14}"
        )
    lines += ["", "용어집은 이 녹음의 실측 전사에서 구축"]
    return "\n".join(lines)


# ---------------------------------------------------------------- 실행부

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TRANSCRIPTS = Path(__file__).parent / "data" / "transcripts.json"
RESULTS_DIR = Path(__file__).parent / "results"


def load_fixtures(directory: Path) -> dict[str, list[dict]]:
    """`*.yaml`을 읽어 갈래별로 나눈다. 파일 이름이 아니라 **내용**으로 나눈다."""
    buckets: dict[str, list[dict]] = {"복원": [], "오탐": [], "보호": []}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for item in data.get("fixtures", []):
            buckets[classify(item)].append(item)
    return buckets


def run_fixtures(items: list[dict], glossary, threshold: float) -> list[tuple[dict, Outcome]]:
    scored = []
    for item in items:
        result = correct(item["broken"], glossary, threshold=threshold)
        scored.append((item, score(
            expected_text=item["expected"],
            expected_terms=item.get("terms") or [],
            got_text=result.text,
            got_terms=[s.term for s in result.spans],
        )))
    return scored


def run_stages(
    records: list[dict], glossary, threshold: float
) -> dict[tuple[str, str], tuple[int, int]]:
    """네 조건에서 용어가 몇 개나 살아남았나. 넷이 **같은 음성·같은 정답지**를 쓴다.

    **힌트(hotwords)와 보정은 서로 독립인 두 축이다.** 셋만 내면 표가 계단처럼 보여서
    "힌트 위에 보정을 얹은 값"으로 읽히는데, 그 자리에 있던 값은 힌트를 **뺀** 값이었다.
    넷을 다 내면 가로로 보정의 효과, 세로로 힌트의 효과가 각각 읽힌다.

    반환 키는 `(힌트, 보정)` 쌍이라 2×2로 그대로 펼칠 수 있다.
    """
    total = sum(len(r["terms"]) for r in records)

    def count(key: str, fix: bool) -> tuple[int, int]:
        got = 0
        for r in records:
            text = r[key]
            if fix:
                text = correct(text, glossary, threshold=threshold).text
            got += survived(text, r["terms"])
        return got, total

    return {
        ("힌트 없음", "보정 없음"): count("off", False),
        ("힌트 적용", "보정 없음"): count("on", False),
        ("힌트 없음", "보정 적용"): count("off", True),
        ("힌트 적용", "보정 적용"): count("on", True),
    }


def _pct(part: int, whole: int) -> str:
    return f"{part}/{whole} = {part / whole * 100:.1f}%" if whole else "—"


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import subprocess
    import sys

    parser = argparse.ArgumentParser(description="DevDemangle 평가 하니스")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--fixtures", type=Path, default=FIXTURE_DIR)
    parser.add_argument("--date", help="측정일 YYYY-MM-DD (추이 기록용)")
    parser.add_argument(
        "--brief",
        action="store_true",
        help="전체 표본 2×2만 화면에 띄운다. 시연 촬영용 — 파일은 쓰지 않는다",
    )
    args = parser.parse_args(argv)

    glossary = default_glossary()

    if args.brief:
        records = json.loads(TRANSCRIPTS.read_text(encoding="utf-8"))
        print(brief_table(records, glossary, args.threshold))
        return 0

    if not args.date:
        print("--date 가 필요합니다 (또는 --brief)", file=sys.stderr)
        return 1

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        commit = "(알 수 없음)"

    out = [
        f"# 측정 결과 — {args.date}",
        "",
        "| | |",
        "|---|---|",
        f"| 커밋 | `{commit}` |",
        f"| 임계값 | {args.threshold} |",
        f"| 용어집 | 용어 {len(glossary)}개 |",
        f"| 실행 | `uv run python eval/benchmark.py --date {args.date}` |",
        "",
        "## 1. 단계별 비교 — 실측 음성",
        "",
    ]

    records = json.loads(TRANSCRIPTS.read_text(encoding="utf-8"))
    sets = ["1차", "문장끝", "용어확장"]

    # 차수를 나눠서도 낸다. 차수마다 난이도가 달라서(2·3차는 문장 끝·신규 용어)
    # 전체 값만 내면 1차 표본으로 잰 기존 수치와 비교가 안 된다.
    groups = [("전체", records)] + [(s, [r for r in records if r["set"] == s]) for s in sets]

    out += [f"문장 {len(records)}건 · 용어 등장 {sum(len(r['terms']) for r in records)}회", "",
            "**힌트와 보정은 서로 독립인 두 축이다.** 가로로 읽으면 보정의 효과,",
            "세로로 읽으면 인식 힌트의 효과다. 계단이 아니다.", ""]

    for label, group in groups:
        st = run_stages(group, glossary, args.threshold)
        out += [f"### {label} — 문장 {len(group)}건", "",
                "| | 보정 없음 | 보정 적용 |", "|---|---|---|"]
        for hot in ("힌트 없음", "힌트 적용"):
            cells = " | ".join(_pct(*st[(hot, fix)]) for fix in ("보정 없음", "보정 적용"))
            out.append(f"| **{hot}** | {cells} |")
        out.append("")

    out += ["> **용어집은 이 코퍼스의 실측 전사에서 만들었다.** 녹음에서 나온 표기를",
            "> 별칭으로 등록한 뒤 같은 녹음으로 잰 값이므로, 처음 보는 음성에 대한",
            "> 일반화 성능이 아니다. 그 값은 아직 재지 않았다.", ""]

    out += ["", "## 2. 픽스처", ""]
    if not args.fixtures.is_dir():
        out += [f"⚠️ `{args.fixtures}`가 없어 건너뛰었다. 검수된 픽스처를 넣으면 이 절이 채워진다.", ""]
    else:
        buckets = load_fixtures(args.fixtures)
        out += ["| 갈래 | 건수 | 재현율 | 정밀도 | 문장 정확도 | 오탐률 |", "|---|---|---|---|---|---|"]
        failures = []
        for kind, items in buckets.items():
            if not items:
                continue
            scored = run_fixtures(items, glossary, args.threshold)
            m = aggregate([o for _, o in scored])
            fpr = _fmt(m.false_positive_rate) if kind == "오탐" else "—"
            out.append(f"| {kind} | {m.n} | {_fmt(m.recall)} | {_fmt(m.precision)} "
                       f"| {_fmt(m.sentence_accuracy)} | {fpr} |")
            failures += [(kind, i, o) for i, o in scored
                         if not o.text_ok or o.missing or o.extra]

        out += ["", f"## 3. 실패 항목 {len(failures)}건", "",
                "숫자만 남기면 고칠 수가 없다. 어긋난 것을 전부 적는다.", ""]
        for kind, item, o in failures:
            out += ["```", f"[{kind}] {item['broken']}"]
            if item["expected"] != item["broken"]:
                out.append(f"  기대  {item['expected']}")
            if o.missing:
                out.append(f"  놓침  {o.missing}")
            if o.extra:
                out.append(f"  오탐  {o.extra}")
            out.append("```")

    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{args.date}.md"
    # newline을 고정한다. Windows 기본값이면 CRLF로 써서, 돌릴 때마다 파일 전체가
    # 바뀐 것처럼 보인다 — 저장소 나머지는 LF다.
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(out))
    print(f"\n→ {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
