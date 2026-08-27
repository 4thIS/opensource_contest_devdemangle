# DevDemangle

음성인식·번역이 뭉갠 개발 용어를 되돌리는 Python 라이브러리.

STT와 기계번역은 개발 용어를 한글 음차로 뭉갠다. DevDemangle은 용어집 기반 탐지·보정으로
이런 용어를 표준형으로 복원한다.

**아래는 실측 예시다.** 3인이 녹음한 문장을 Whisper large-v3로 전사한 결과이며,
지어낸 것이 아니라 실제로 나온 문자열이다.

```
말한 것    GitHub에 새 repository 만들었어?
전사       기터벳의 리포지토리 만들었어?          ← 용어 둘 다 깨짐
보정 후    GitHub의 repository 만들었어?
```

**코어는 오디오도 번역도 모른다.** `import devdemangle`은 `faster_whisper`·`torch`·`transformers`를
불러오지 않는다. 문자열만 있으면 코어를 그대로 쓸 수 있고, 테스트도 음성 파일 없이 돈다.

---

## 설치

Python 3.13 이상이 필요하다. 패키지 관리는 [uv](https://docs.astral.sh/uv/)를 쓴다.

```bash
git clone https://github.com/4thIS/opensource_contest_devdemangle.git
cd opensource_contest_devdemangle
uv sync
```

필요한 것만 골라 넣는다.

| 명령 | 무엇이 들어오나 |
|---|---|
| `uv sync` | 코어 + STT(faster-whisper) |
| `uv sync --extra cuda` | + GPU 추론용 CUDA 라이브러리 |
| `uv sync --extra translate` | + 번역(transformers·torch) |
| `uv sync --extra dev` | + pytest |

> ⚠️ **`faster-whisper`는 현재 선택이 아니라 필수 의존성이다.** 코어가 import하지는 않지만
> 설치는 된다. 문자열 보정만 쓸 사람에게는 불필요한 무게라, 향후 선택 의존성으로 뺄 예정이다.

### GPU로 돌리려면

STT는 CUDA에서 가장 빠르다. 환경 점검 스크립트가 있다.

```bash
uv run --extra cuda python scripts/check_env.py
```

> **Windows 주의** — CUDA DLL을 PATH에 먼저 등록한 뒤 `faster_whisper`를 import해야 한다.
> 순서가 어긋나면 추론에서 `cublas64_12.dll not found`로 터진다.
> `devdemangle.stt` 서브패키지가 이 순서를 알아서 맞춘다.

### 모델 가중치

**저장소에 포함하지 않는다.** 처음 실행할 때 자동으로 내려받는다(Whisper `large-v3` 약 3GB).
근거는 아래 [라이선스](#라이선스) 참고.

---

## 빠른 시작

```python
from devdemangle import correct

result = correct("파이썬 스크립트 짰어요")
print(result.text)   # "Python 스크립트 짰어요"
print(result.spans)  # [Span(start=0, end=6, term='Python', matched='파이썬', ...)]
```

용어집은 `data/terms.yaml`을 쓴다. 자체 용어집으로 보정하려면 `Glossary`로 불러와 넘긴다.

```python
from devdemangle import Glossary, correct

glossary = Glossary.from_yaml("my_terms.yaml")
result = correct("깃허브에서 봤어요", glossary)   # "GitHub에서 봤어요"
```

소리 유사도의 하한도 조절할 수 있다.

```python
correct("깃허브에서 봤어요", glossary, threshold=0.85)   # 더 보수적으로
```

> 기본값 `0.78`은 기본 용어집 기준으로 오탐과 정답 사이를 실측해 정한 값이다.
> **용어집을 바꾸면 그 경계도 움직이므로 다시 재야 한다** — 그래서 코드에 박지 않고 인자로 열어 두었다.

음성부터 통째로 넣으려면 `run()`을 쓴다. 자세한 예제는 **[docs/usage.md](docs/usage.md)**.

```python
from devdemangle import run

result = run("meeting.wav")
print(result.raw)        # STT가 뱉은 원문
print(result.corrected)  # 보정된 문장
```

---

## 데모 앱

```bash
uv sync --extra demo --extra cuda --extra translate
uv run python -m devdemangle.app
```

마이크로 말하거나, 파일을 올리거나, **문장을 그대로 넣을 수 있다.** 화면은 네 칸이다.

```
① 들어온 문장          음성이면 받아쓴 결과
② 이대로 번역하면       용어를 가리지 않고 그대로 번역          ← 비교 대상
③ 보정 결과            되돌린 문장. 찾은 용어에 색이 칠해진다
④ 번역                용어를 보호해서 번역
```

**②와 ④는 같은 번역기에 같은 문장을 넣고 용어를 가렸는지만 다르다.** 외부 번역
서비스를 쓰지 않는 이유가 이것이다 — 다른 모델로 비교하면 차이가 보호 때문인지
모델 때문인지 갈라낼 수 없다.

```
② It's enough for Plask to be simple.      보호 없음 — 없는 이름이 된다
④ A simple one is enough for Flask.        보호 적용
```

**문장 입력은 오디오를 거치지 않는다.** 코어가 문자열만으로 도는 것을 그 자리에서
확인할 수 있고, `--no-cache` 같은 명령행 옵션처럼 소리로 전달하기 애매한 것을 넣어볼 때 쓴다.

> **`--no-hotwords`를 붙이면** 용어집을 인식 힌트로 넘기지 않는다. 보정 단계가 혼자
> 무엇을 되돌리는지 보려면 이쪽이다. 힌트를 켜면 STT가 용어를 이미 맞게 뱉는 경우가 많아
> ①과 ③이 거의 같아진다.

---

## 어떻게 찾나

두 단계다.

1. **등록 탐지** — 용어집의 표준형·별칭을 Aho-Corasick으로 정확히 찾는다. 대소문자를 무시하고,
   뒤에 붙은 조사는 매치 구간에서 뺀다(`"도커를"` → `Docker` + `를`).
2. **소리 탐지** — 남은 자리를 한글 음차의 소리 유사도로 한 번 더 훑는다.
   `"기터브"`처럼 용어집에 **없는** 발음 변형은 여기서 잡는다.

용어집에 없는 식별자는 모양으로 찾는다 — 명령행 플래그(`--no-cache`), camelCase(`userId`),
snake_case(`user_id`). **다만 보정하지 않는다.** 표준형을 모르기 때문이고, 하이라이트와
번역 보호에 쓰라고 결과에만 실어 보낸다.

### `spans`에는 지킨 것도 담긴다

```python
result = correct("Python 스크립트랑 REST API 썼어요")
result.text     # 그대로 — 이미 표준형이라 바꿀 게 없다
result.spans    # [Python, REST API]  ← 그래도 실린다
```

번역과 하이라이트가 망가뜨리는 것은 *바뀐 용어*가 아니라 *문장에 있는 용어 전부*다.
바뀐 것만 보려면 `span.matched != span.term`으로 거른다.

`spans`의 `start`·`end`는 **보정된 텍스트** 기준이다. 앞 용어가 길어지면 뒤 위치가 밀리기 때문이다.
입력 기준 좌표가 필요하면 `detect()`가 돌려주는 `Match`를 쓴다.

---

## 알려진 한계

오탐을 최소화하려고 경계를 좁게 잡았다. **놓치는 쪽이 잘못 바꾸는 쪽보다 낫다고 판단했다** —
오탐은 사용자가 실제로 말한 글자를 지우기 때문이다(`"우리깃허브"` → `GitHub`, "우리"가 사라진다).

- **앞에 다른 글자가 붙으면 안 잡는다** (`"우리깃허브"`). 한국어에서 용어 앞에 오는 것은 조사가
  아니라 다른 단어라, 시작 경계는 완화하지 않는다. 띄어 쓴 `"우리 깃허브"`는 정상적으로 잡힌다.
- **어미는 떼지 않는다** (`"깃허브다"`, `"파이썬입니다"`). 조사는 닫힌 집합이라 목록으로 관리할 수
  있지만 어미는 그렇지 않다. 실측 표본에서 이 규칙 때문에 못 잡은 것이 문장 끝 16건 중 3건이다.
- **짧은 음차는 소리로 찾지 않는다** (`Vue` ← `"뷰"`). 두 글자짜리 소리는 일상어와 우연히 겹쳐도
  유사도가 높게 나와, 임계값으로 가려지지 않는다.
- **한 어절씩만 본다.** `"패스트 API"`처럼 STT가 용어 중간에 공백을 넣으면 놓친다. 그런 형태는
  별칭으로 등록해서 커버한다.
- **동음이의어를 문맥으로 가리지 못한다.** `"파이선"`(뱀)과 `Python`, `"제이슨"`(사람 이름)과
  `JSON`은 소리가 같거나 매우 가깝다. 소리만 보는 방식의 원리적 한계다.

---

## 상태

개발 중 (2026 오픈소스 개발자대회 출품 준비).
탐지(`detect`)·소리 유사도 탐지(`fuzzy_detect`)·보정(`correct`)·STT 연동(`pipeline`)·
번역 보호(`translate`)까지 구현 완료. 데모 앱과 평가 하니스도 저장소에 있다.

**실측** — 3인이 녹음한 음성 64문장을 STT부터 관통시켜 **용어 69건 중 65건 복원(94.2%)**.

| | 보정 없음 | 보정 적용 |
|---|---|---|
| **인식 힌트 없음** | 20.3% | **91.3%** |
| **인식 힌트 적용** | 65.2% | **94.2%** |

**가로로 읽으면 보정의 효과, 세로로 읽으면 인식 힌트의 효과다.** 계단이 아니라 두 축이다.

힌트가 보정을 만나면 기여가 **44.9%p에서 2.9%p로** 줄어든다. 보정이 힌트가 하던 일을
대부분 흡수한다는 뜻이고, 그래서 보정 계층이 필요하다.

> **용어집은 이 코퍼스의 실측 전사에서 만들었다.** 녹음에서 나온 표기를 별칭으로 등록한 뒤
> 같은 녹음으로 잰 값이므로, **처음 보는 음성에 대한 일반화 성능이 아니다.**
> 용어집 확장 전(용어 23개)으로 재면 전체가 58.0%다.

표본을 나눠 보면 이렇다. 2·3차 녹음은 용어가 문장 끝에 오거나 신규 용어를 쓰는
어려운 표본이라 1차보다 낮다.

| 표본 | 문장 | 힌트만 | 보정만 | 둘 다 |
|---|---|---|---|---|
| 1차 녹음 | 21 | 73.9% | 95.7% | 95.7% |
| 문장 끝 | 16 | 61.1% | 77.8% | 88.9% |
| 용어집 확장 | 27 | 60.7% | 96.4% | 96.4% |

**번역 보호**는 따로 잰다. 보정까지 살아남은 용어 63건 중,

| | 번역문에도 남은 용어 |
|---|---|
| 보호 없이 번역 | 41/63 = 65.1% |
| **용어를 가리고 번역** | **61/63 = 96.8%** |

못 지킨 2건 중 1건은 **번역기가 플레이스홀더 자체를 변형해** 되돌리지 못한 경우다.

> 보정 단계에서 이미 실패한 6건은 이 계산에서 뺐다. 지킬 대상이 없었던 것을
> 번역 보호의 실패로 세면 두 단계의 책임이 섞인다.

직접 재볼 수 있다. **GPU가 없어도 된다** — 실측 전사가 저장소에 들어 있다.

```bash
uv run python eval/benchmark.py --date $(date +%F)
```

---

## 공개 API

```python
from devdemangle import (
    correct, detect, fuzzy_detect, resolve_overlaps, run,
    Glossary, GlossaryError, Term, Match, Span, Method,
    CorrectionResult, PipelineResult,
)
```

| 구간 | 안정성 |
|---|---|
| `Glossary`·`GlossaryError`·`correct`·`CorrectionResult`·`Match`·`Span`·`Term`·`Method` | 공개 API. 함부로 바꾸지 않는다 |
| `detect`·`resolve_overlaps`·`fuzzy_detect`·`run`·`PipelineResult` | 공개하되 변경될 수 있다 |
| `_`로 시작하는 것 | 내부용 |

---

## 기여

버그 제보와 용어집 추가를 환영한다. **특히 "STT가 이 용어를 이렇게 깨뜨리더라"는 실측 제보가
가장 쓸모 있다** — 별칭은 규칙으로 예측할 수 없어서 실제로 나온 것을 모으는 수밖에 없다.

자세한 것은 [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 사용 모델

이 프로젝트는 아래 모델을 실행 시 다운로드해 사용한다. 가중치는 저장소에 포함하지 않는다.

- **Whisper** ([openai/whisper](https://github.com/openai/whisper)) —
  [MIT License](https://github.com/openai/whisper/blob/main/LICENSE) /
  구현: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT)
- **OPUS-MT** ([Helsinki-NLP/opus-mt-ko-en](https://huggingface.co/Helsinki-NLP/opus-mt-ko-en))
  — 라이선스 표기가 출처마다 다르다.
  - 우리가 내려받는 Hugging Face 배포본의 모델 카드 표기는
    [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)이다.
  - 원 프로젝트 [OPUS-MT](https://github.com/Helsinki-NLP/Opus-MT)는 사전학습 모델을
    [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/)으로 안내한다.
  - 어느 쪽이 맞다고 단정하지 않고 **더 엄격한 쪽(CC-BY 4.0)의 출처 표기 의무를 따른다.**
    아래가 그 표기다.

  > Tiedemann, J., & Thottingal, S. (2020).
  > [OPUS-MT — Building open translation services for the World](https://aclanthology.org/2020.eamt-1.61/).
  > *Proc. of the 22nd EAMT*, Lisbon, Portugal.

## 라이선스

이 저장소의 코드는 **MIT License**다 ([LICENSE](LICENSE)).

모델 가중치는 저장소에 포함하지 않고 **실행 시 다운로드**한다. 배포물에 가중치를 넣지 않으므로
모델 쪽 조건(Apache-2.0의 고지 유지, CC-BY 4.0의 출처 표기)이 코드 배포물에 얽히지 않는다 —
코드 라이선스는 MIT로 유지된다. 출처 표기는 위 "사용 모델"에 두었다.
