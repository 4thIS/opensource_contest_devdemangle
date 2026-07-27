"""리스크 2: 플레이스홀더가 OPUS-MT 번역을 통과하는지 측정한다.

3가지 방식을 시험해서 처음으로 통과하는 걸 채택한다.
"""

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

MODEL = "Helsinki-NLP/opus-mt-ko-en"

# 보정이 끝난 상태의 문장 (용어가 이미 표준형으로 복원됨)
# 각 항목: (문장, 보호해야 할 용어 목록)
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


# --- 방식 1: 아무것도 안 하기 (용어를 그대로 두고 번역) ---
def strategy_raw(tok, model, text, terms):
    out = translate(tok, model, text)
    survived = [t for t in terms if t in out]
    return out, survived


# --- 방식 2: 특수문자 표식 ---
def strategy_bracket(tok, model, text, terms):
    marked = text
    for i, t in enumerate(terms):
        marked = marked.replace(t, f"⟦{i}⟧")
    out = translate(tok, model, marked)
    restored = out
    survived = []
    for i, t in enumerate(terms):
        if f"⟦{i}⟧" in out:
            survived.append(t)
            restored = restored.replace(f"⟦{i}⟧", t)
    return restored, survived


# --- 방식 3: 모델이 익숙한 형태의 표식 ---
WORDS = ["TERMZERO", "TERMONE", "TERMTWO", "TERMTHREE", "TERMFOUR"]


def strategy_word(tok, model, text, terms):
    marked = text
    for i, t in enumerate(terms):
        marked = marked.replace(t, WORDS[i])
    out = translate(tok, model, marked)
    restored = out
    survived = []
    for i, t in enumerate(terms):
        if WORDS[i] in out:
            survived.append(t)
            restored = restored.replace(WORDS[i], t)
    return restored, survived


STRATEGIES = [
    ("1_raw (아무것도 안 함)", strategy_raw),
    ("2_bracket (특수문자)", strategy_bracket),
    ("3_word (TERMZERO)", strategy_word),
]


def main():
    tok, model = load()
    print(f"모델: {MODEL} / device: {model.device}\n")

    for name, fn in STRATEGIES:
        total = 0
        kept = 0
        print(f"=== {name} ===")
        for text, terms in CASES:
            out, survived = fn(tok, model, text, terms)
            total += len(terms)
            kept += len(survived)
            missing = set(terms) - set(survived)
            flag = "OK " if not missing else "MISS"
            print(f"  [{flag}] {out}")
            if missing:
                print(f"         놓친 용어: {sorted(missing)}")
        rate = kept / total * 100
        print(f"  >>> 생존율: {kept}/{total} = {rate:.1f}%\n")


if __name__ == "__main__":
    main()
