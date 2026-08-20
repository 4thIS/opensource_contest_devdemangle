"""번역 보호 관통 측정 — 보정된 문장을 실제로 번역해 용어가 살아남는지 센다.

risk2·risk2b는 플레이스홀더 방식을 고르려고 잰 것이고(문장 10개·용어 13개),
여기서는 **고른 방식을 모듈로 만든 뒤** 1주차 실측 전사문으로 다시 잰다.
바뀐 점은 둘이다.

- 용어를 문자열이 아니라 `correct()`가 준 **위치(Span)** 로 가린다
- 보호 없이 번역한 결과를 같이 찍어 **무엇이 달라지는지** 남긴다

실행: uv run python experiments/risk2c_protect_e2e.py   (--extra translate 필요)
"""

import sys

from devdemangle.correct import correct, default_glossary
from devdemangle.translate.opusmt import OpusMTTranslator
from devdemangle.translate.protect import spans_for_protection, translate_protected

# risk1 §5의 「hotwords 있음」 전사문. STT를 다시 돌리지 않으려고 텍스트로 고정한다
# (이 실험이 재는 건 번역 구간이지 전사 구간이 아니다).
TRANSCRIPTS = [
    "GitHub에서의 리포지터리 만들었어.",
    "JSON 파일은 그대로인가?",
    "뷰 컴포넌트를 다시 만들어야 해요.",
    "npm install부터 진행해야지.",
    "git commit 하고 알렸어요.",
    "리듬이 수정되었습니다.",
    "Docker 컨테이너 재시작할게.",
    "TypeScript 문법 에러라는데?",
    "SQL 문을 수정해야 합니다.",
    "console.log 한번 확인해 볼게요.",
    "CSS 파일 새로 만들었어요.",
    "REST API 응답이 드려요.",
    "pull request 새로 올렸어요.",
    "localhost 로 들어가면 돼요.",
    "AWS 한번 배워보라고요.",
    "VS Code로 작업 중이요.",
    "FastAPI 서버 열었어.",
    "파일선으로 작성했어.",
    "리액트랑 타입 스트릿을 같이 쓰고 있어요.",
    "Docker를 배포했어요.",
    "README 파일 수정해 뒀어요.",
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    glossary = default_glossary()
    translator = OpusMTTranslator()

    protected_total = 0
    lost_total = 0
    survived_naive = 0
    differed = 0

    for text in TRANSCRIPTS:
        corrected = correct(text, glossary)
        # 보호 대상은 "바뀐 것"이 아니라 "있는 것" 전부다 (spans_for_protection 참고).
        guard = spans_for_protection(corrected.text, glossary)
        if not guard:
            continue

        result = translate_protected(corrected.text, guard, translator)
        naive = translator.translate(corrected.text)

        protected_total += len(result.protected)
        lost_total += len(result.lost)

        # 보호 없이 번역했을 때 용어가 원형 그대로 남았는지 (대소문자까지 일치)
        survived_naive += sum(1 for t in result.protected if t in naive)
        if naive != result.text:
            differed += 1

        print(f"보정  : {corrected.text}")
        print(f"보호X : {naive}")
        print(f"보호O : {result.text}")
        if result.lost:
            print(f"  !! 유실: {result.lost}")
        print()

    kept = protected_total - lost_total
    print("=" * 60)
    print(f"보호 대상 용어      : {protected_total}")
    print(f"보호 O — 살아남음   : {kept}/{protected_total} = {kept/protected_total:.1%}")
    print(f"보호 X — 살아남음   : {survived_naive}/{protected_total} = {survived_naive/protected_total:.1%}")
    print(f"두 결과가 다른 문장 : {differed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
