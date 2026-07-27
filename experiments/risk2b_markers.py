"""리스크 2b: 표식(marker) 변형별 생존율 재측정.

risk2_placeholder.py에서 방식 2(⟦0⟧)가 0%였던 원인이
"기호를 썼기 때문"인지 "토크나이저 어휘에 없는 기호를 썼기 때문"인지 가른다.

두 계열을 비교한다:
  A. 감싸기(wrap)  — 용어를 그대로 두고 앞뒤에 표식만 붙인다. 복원이 단순하다
  B. 치환(placeholder) — 용어를 다른 토큰으로 바꿔 번역 후 되돌린다

생존율 외에 부작용 두 가지를 같이 잰다:
  - 잔여 표식: 복원 후에도 표식 문자가 출력에 남는가
  - 대문자화: 용어가 아닌 단어가 ALL-CAPS로 바뀌는가 (방식 3에서 관찰됨)
"""

import re

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

MODEL = "Helsinki-NLP/opus-mt-ko-en"

# risk2_placeholder.py와 동일한 케이스 (결과를 직접 비교하기 위해)
CASES = [
    ("lodash debounce 써서 처리했어요", ["lodash", "debounce"]),
    ("React useState 훅을 사용합니다", ["React", "useState"]),
    ("npm install 먼저 실행하세요", ["npm install"]),
    ("git commit 하고 push 해주세요", ["git commit", "push"]),
    ("Vue 컴포넌트를 다시 만들어야 해요", ["Vue"]),
    ("kubectl apply 로 배포합니다", ["kubectl apply"]),
    ("REST API 응답이 느려요", ["REST API"]),
    ("Docker 컨테이너를 재시작했습니다", ["Docker"]),
    ("TypeScript 타입 에러가 났어요", ["TypeScript"]),
    ("PostgreSQL 쿼리를 최적화해야 합니다", ["PostgreSQL"]),
]

# 인덱스 기반 생성 — 고정 리스트를 쓰면 용어가 6개 넘을 때 IndexError가 난다
NUM = ["ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"]


def load():
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL)
    if torch.cuda.is_available():
        model = model.to("cuda")
    return tok, model


def translate(tok, model, text: str) -> str:
    inputs = tok(text, return_tensors="pt").to(model.device)
    outputs = model.generate(**inputs, max_new_tokens=128)
    return tok.decode(outputs[0], skip_special_tokens=True)


# --- 계열 A: 감싸기 (용어는 그대로) ---
def make_wrap(open_s: str, close_s: str):
    def fn(tok, model, text, terms):
        marked = text
        for t in terms:
            marked = marked.replace(t, f"{open_s}{t}{close_s}")
        out = translate(tok, model, marked)
        restored = out
        for t in terms:
            restored = restored.replace(f"{open_s}{t}{close_s}", t)
        survived = [t for t in terms if t in restored]
        return marked, restored, survived

    return fn


# --- 계열 B: 치환 (용어를 플레이스홀더로) ---
def make_placeholder(fmt):
    def fn(tok, model, text, terms):
        marked = text
        for i, t in enumerate(terms):
            marked = marked.replace(t, fmt(i))
        out = translate(tok, model, marked)
        restored = out
        survived = []
        for i, t in enumerate(terms):
            if fmt(i) in out:
                survived.append(t)
                restored = restored.replace(fmt(i), t)
        return marked, restored, survived

    return fn


def raw(tok, model, text, terms):
    out = translate(tok, model, text)
    return text, out, [t for t in terms if t in out]


STRATEGIES = [
    # (라벨, 계열, 함수, 잔여물로 볼 문자)
    ("1_raw 아무것도 안 함", "-", raw, ""),
    ("2_bracket ⟦0⟧", "B", make_placeholder(lambda i: f"⟦{i}⟧"), "⟦⟧"),
    ("3_word TERMZERO", "B", make_placeholder(lambda i: f"TERM{NUM[i]}"), ""),
    ('4_wrap_quote "lodash"', "A", make_wrap('"', '"'), '"'),
    ("5_wrap_under __lodash__", "A", make_wrap("__", "__"), "_"),
    ("6_wrap_star *lodash*", "A", make_wrap("*", "*"), "*"),
    ("7_ph_under __TERMZERO__", "B", make_placeholder(lambda i: f"__TERM{NUM[i]}__"), "_"),
    ('8_ph_quote "TERMZERO"', "B", make_placeholder(lambda i: f'"TERM{NUM[i]}"'), '"'),
    ("9_ph_title Termzero", "B", make_placeholder(lambda i: f"Term{NUM[i].capitalize()}"), ""),
]


def count_shouty(text: str, terms: list[str]) -> int:
    """용어에 속하지 않는데 ALL-CAPS로 나온 단어 수 (대문자화 부작용 지표)."""
    term_words = {w.lower() for t in terms for w in t.split()}
    return sum(
        1
        for w in re.findall(r"[A-Za-z]{2,}", text)
        if w.isupper() and w.lower() not in term_words
    )


def count_residue(text: str, chars: str) -> int:
    """복원 후에도 남은 표식 문자 수."""
    return sum(text.count(c) for c in chars) if chars else 0


def diagnose_markers(tok):
    """표식이 토크나이저에서 어떻게 쪼개지는지 — 생존율 차이의 원인 진단."""
    print("=" * 70)
    print("토크나이저 진단 — 표식이 어떤 토큰으로 쪼개지는가")
    print("=" * 70)
    samples = [
        "lodash",
        "⟦0⟧",
        '"lodash"',
        "__lodash__",
        "*lodash*",
        "TERMZERO",
        "__TERMZERO__",
        '"TERMZERO"',
        "Termzero",
    ]
    unk = tok.unk_token
    for s in samples:
        pieces = tok.tokenize(s)
        mark = "  ← UNK 포함!" if unk in pieces else ""
        print(f"  {s:<16} → {pieces}{mark}")
    print()


def main():
    tok, model = load()
    print(f"모델: {MODEL} / device: {model.device}\n")

    diagnose_markers(tok)

    summary = []
    for label, family, fn, residue_chars in STRATEGIES:
        total = kept = shouty = residue = 0
        print(f"=== {label}  [{family}] ===")
        for text, terms in CASES:
            marked, restored, survived = fn(tok, model, text, terms)
            total += len(terms)
            kept += len(survived)
            shouty += count_shouty(restored, terms)
            residue += count_residue(restored, residue_chars)
            missing = set(terms) - set(survived)
            flag = "OK " if not missing else "MISS"
            print(f"  [{flag}] {restored}")
            if missing:
                print(f"         놓친 용어: {sorted(missing)}")
        rate = kept / total * 100
        print(f"  >>> 생존율 {kept}/{total} = {rate:.1f}% / 잔여표식 {residue} / 대문자화 {shouty}\n")
        summary.append((label, family, rate, residue, shouty))

    print("=" * 70)
    print(f"{'방식':<26}{'계열':<5}{'생존율':>8}{'잔여표식':>10}{'대문자화':>10}")
    print("=" * 70)
    for label, family, rate, residue, shouty in sorted(summary, key=lambda r: -r[2]):
        print(f"{label:<26}{family:<5}{rate:>7.1f}%{residue:>10}{shouty:>10}")


if __name__ == "__main__":
    main()
