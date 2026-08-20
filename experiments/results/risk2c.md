# 리스크 2c 결과 — 번역 보호 관통

실행일: 2026-08-20
모델: `Helsinki-NLP/opus-mt-ko-en` (transformers, device=cpu)
표본: risk1 §5 「hotwords 있음」 전사문 21개 → 용어가 잡힌 15문장 / **보호 대상 22건**
스크립트: `experiments/risk2c_protect_e2e.py`
(원시 출력은 `.gitignore` 방침대로 저장소에 넣지 않는다 — 아래 「재현」으로 그대로 다시 나온다)

## 무엇이 risk2와 다른가

risk2·risk2b는 **어떤 플레이스홀더를 쓸지 고르려고** 잰 것이다(문장 10개·용어 13개, 용어 목록을
손으로 넘김). 여기서는 고른 방식을 모듈(`devdemangle/translate/protect.py`)로 만든 뒤,
**용어를 코드가 스스로 찾아** 1주차 실측 전사문에 적용한다.

## 결과

| | 살아남은 용어 |
|---|---|
| **보호 O** | **22/22 = 100.0%** |
| 보호 X (그냥 번역) | 14/22 = 63.6% |

플레이스홀더 유실 **0건**. risk2에서 잰 100% 생존이 모듈로 옮긴 뒤에도 유지된다.

## 🔴 설계 결함을 하나 찾았다 — 보호 대상을 잘못 고르고 있었다

처음엔 `correct()`가 돌려주는 `spans`를 보호 대상으로 넘겼다. **틀렸다.**

`spans`는 **바꾼 것**만 담는다. 이미 표준형인 용어는 바꿀 게 없어서 안 담긴다. 그런데 번역이
망가뜨리는 건 *바뀐 용어*가 아니라 *문장에 있는 용어 전부*다.

```
"Docker 컨테이너 재시작할게."
  correct().spans        →  []            ← 보호 대상 0건
  detect()가 본 용어      →  ['Docker']
```

이대로 두면 **STT가 잘 알아들은 문장일수록 번역에서 더 망가진다.** hotwords가 잘 들은 덕에
이미 표준형으로 나온 용어가 통째로 무방비가 되기 때문이다.

보호 대상을 `detect()` 결과로 바꾸니 대상이 **5건 → 22건**으로 늘었다. 아래 사례 대부분이
이 구간에서 나온다.

## 보호 없이 번역했을 때 실제로 나온 것

| 용어 | 보호 X | 보호 O |
|---|---|---|
| `repository` | **recipe** | repository |
| `React` | **the real thing** | React |
| `FastAPI` | **pastAPI** | FastAPI |
| `pull request` | **full request** | pull request |
| `REST API` | **REST APl** (소문자 L) | REST API |
| `README` | **ReADME** | README |
| `git commit` | **Git company** | git commit |
| `console.log` | **통째로 사라짐** | console.log |

risk2에서 본 양상이 그대로 재현된다 — 모델이 개발 용어를 번역 대상으로 오인해 소리 나는 대로
다시 쓰거나, 아예 문장에서 지운다.

## ⚠️ 정직하게 — 문장 품질이 늘 좋아지는 건 아니다

**용어 생존율은 올라가지만 문장이 더 어색해지는 경우가 있다.** 15문장 중 3건이 그랬다.

```
Python으로 작성했어.
  보호X : It was written in Python.     ← 이쪽이 자연스럽다
  보호O : It's a Python.

SQL 문을 수정해야 합니다.
  보호X : You need to modify the SQL door.
  보호O : SQL You must correct the door.   ← 어순이 무너졌다
```

플레이스홀더가 문장에서 명사 자리를 차지하면서 모델이 원래와 다른 구조를 고르기 때문이다.
**"번역 품질이 좋아진다"고 쓰면 안 된다.** 이 모듈이 보장하는 건 *용어가 원형으로 살아남는 것*
하나이고, 그게 이 프로젝트가 풀려는 문제다.

<sub>risk2에서 "번역 품질도 방식 1보다 나았다"고 적었던 것은 용어가 통째로 빠져 문장이 붕괴하던
케이스와 비교한 것이라 층위가 다르다. 붕괴는 막지만, 매끄러움까지 보장하지는 않는다.</sub>

## 재현

```bash
uv sync --extra translate --extra dev
uv run python experiments/risk2c_protect_e2e.py
```

STT는 돌리지 않는다. 이 실험이 재는 건 번역 구간이라 전사문을 스크립트에 고정해 뒀다.
