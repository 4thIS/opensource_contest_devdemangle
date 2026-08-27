# 사용 예제

이 문서의 코드는 전부 실행해서 출력을 확인한 것이다. 그대로 복사해 돌려도 같은 결과가 나온다.

---

## 1. 문자열 하나 보정하기

가장 기본. 용어집을 안 넘기면 `data/terms.yaml`을 쓴다.

```python
from devdemangle import correct

result = correct("파이썬 스크립트 짰어요")

result.text
# 'Python 스크립트 짰어요'
```

`CorrectionResult`는 필드가 둘이다.

```python
result.text     # 보정된 문장
result.spans    # 찾은 용어 목록
```

---

## 2. 무엇을 어떻게 찾았는지 보기

`Span` 하나가 용어 하나다.

```python
from devdemangle import correct

for s in correct("깃허브에서 기터브 봤어요").spans:
    print(s.term, s.matched, s.method, round(s.confidence, 3))

# GitHub  깃허브   Method.EXACT  1.0
# GitHub  기터브   Method.FUZZY  0.923
```

| 필드 | 뜻 |
|---|---|
| `term` | 표준형 — 결과 텍스트에 들어간 것 |
| `matched` | 입력에 실제로 있던 글자 |
| `method` | `EXACT`(등록 용어) / `REGEX`(식별자 모양) / `FUZZY`(소리 유사도) |
| `confidence` | `FUZZY`만 실제로 잰 값. `EXACT`는 항상 1.0, `REGEX`는 0.8 고정 |

> ⚠️ **`confidence`는 같은 `method` 안에서만 비교할 수 있다.** `REGEX`의 0.8은 잰 값이 아니라
> "exact보다는 못 믿는다"는 자리표시자다. 퍼지 0.85가 regex 0.8보다 믿을 만하다는 뜻이 아니다.

---

## 3. 좌표 — `Span`과 `Match`는 기준이 다르다

```python
from devdemangle import correct, detect
from devdemangle.correct import default_glossary

text = "깃허브에서 봤어요"

# Span — 보정된 텍스트 기준
r = correct(text)
r.text                                  # 'GitHub에서 봤어요'
s = r.spans[0]
r.text[s.start:s.end]                   # 'GitHub'

# Match — 입력 텍스트 기준
m = detect(text, default_glossary())[0]
text[m.start:m.end]                     # '깃허브'
```

앞 용어가 길어지면 뒤 용어의 위치가 밀린다. **하이라이트를 그릴 때는 `Span`을 쓴다.**

---

## 4. 지킨 것도 결과에 담긴다

이미 표준형으로 적힌 용어는 텍스트가 안 바뀌지만 **결과에서 사라지지는 않는다.**

```python
from devdemangle import correct

r = correct("Python 스크립트랑 REST API 썼어요")

r.text
# 'Python 스크립트랑 REST API 썼어요'      그대로

[(s.matched, s.term) for s in r.spans]
# [('Python', 'Python'), ('REST API', 'REST API')]
```

번역과 하이라이트가 망가뜨리는 것은 *바뀐 용어*가 아니라 *문장에 있는 용어 전부*다.
그래서 `spans`는 "바꾼 것"이 아니라 **"지킨 것"** 목록이다.

바뀐 것만 필요하면 거른다.

```python
changed = [s for s in r.spans if s.matched != s.term]
```

---

## 5. 자체 용어집

```python
from devdemangle import Glossary, Term, correct

glossary = Glossary([
    Term(canonical="Kubernetes", aliases=("쿠버네티스", "쿠버 네티스")),
    Term(canonical="Redis", aliases=("레디스",)),
])

correct("레디스 캐시 붙였어요", glossary).text
# 'Redis 캐시 붙였어요'
```

파일에서 읽을 수도 있다.

```python
glossary = Glossary.from_yaml("my_terms.yaml")
```

```yaml
version: 1
terms:
  - canonical: Kubernetes
    aliases: [쿠버네티스, 쿠버 네티스]
  - canonical: 의존성 주입
    aliases: [디펜던시 인젝션]
    translations: { en: dependency injection }
```

로딩할 때 검증한다. 규칙 위반은 첫 건에서 멈추지 않고 **전부 모아 한 번에** 알려준다.

```python
from devdemangle import GlossaryError

try:
    Glossary.from_yaml("broken.yaml")
except GlossaryError as e:
    print(e)   # 파일 경로 + 검증 실패 N건 + 항목별 사유
```

---

## 6. 소리 유사도 임계값 조절

```python
from devdemangle import correct

correct("기터브에서 봤어요").text
# 'GitHub에서 봤어요'            기본값 0.78 — 유사도 0.923으로 통과

correct("기터브에서 봤어요", threshold=0.99).text
# '기터브에서 봤어요'             임계값 미달로 보정하지 않음
```

**기본값 0.78은 기본 용어집 기준으로 잰 값이다.** 용어집을 바꾸면 안전 구간이 움직이므로
다시 재야 한다 — 그래서 상수로 박지 않고 인자로 열어 두었다.

---

## 7. 탐지만 따로 쓰기

보정 없이 위치만 알고 싶을 때.

```python
from devdemangle import detect, Glossary, Term

glossary = Glossary([Term(canonical="Docker", aliases=("도커",))])

detect("도커를 재시작할게", glossary)
# [Match(start=0, end=2, term='Docker', matched='도커', method=EXACT, confidence=1.0)]
```

**조사는 매치 구간 밖에 둔다.** 구간이 `"도커를"`까지 덮으면 치환할 때 조사가 같이 사라진다.

용어집에 없는 식별자는 모양으로 잡는다.

```python
detect("--no-cache 옵션 줬어", glossary)
# [Match(0, 10, '--no-cache', '--no-cache', method=REGEX, confidence=0.8)]
```

`term`과 `matched`가 같다 — 표준형을 모르기 때문이다. **이런 것은 보정하지 않고 보호만 한다.**

---

## 8. 소리 탐지만 따로 쓰기

```python
from devdemangle import fuzzy_detect, Glossary, Term

glossary = Glossary([Term(canonical="Python", aliases=("파이썬",))])

fuzzy_detect("파일선 스크립트 짰어요", glossary)
# [Match(0, 3, 'Python', '파일선', method=FUZZY, confidence=0.933)]
```

비교 대상은 **표준형이 아니라 한글 별칭**이다. `"리듬이"`는 영문 `README`와 재면 0.55지만
별칭 `"리드미"`와는 1.00이다. 한국어 음차는 한국어끼리 대야 한다.

이미 찾은 구간을 건너뛰게 할 수도 있다.

```python
found = detect(text, glossary)
found += fuzzy_detect(text, glossary, found)     # 세 번째 인자
```

---

## 9. 겹치는 후보 고르기

`detect`와 `fuzzy_detect`는 겹치는 후보를 **전부** 돌려준다. 고르는 것은 따로다.

```python
from devdemangle import detect, fuzzy_detect, resolve_overlaps

found = detect(text, glossary)
found += fuzzy_detect(text, glossary, found)
accepted = resolve_overlaps(found)
```

우선순위는 **① method ② 길이 ③ 신뢰도 ④ 위치**다.

`method`가 길이보다 앞서는 것이 중요하다. 어절을 통째로 잡는 소리 추정이 조사를 뗀 등록 용어를
밀어내면 안 되기 때문이다. `"npm install"`과 `"npm"`은 둘 다 등록 용어라 method가 같고,
그다음 길이에서 긴 쪽이 남는다.

---

## 10. 음성부터 통째로

```python
from devdemangle import run

result = run("meeting.wav")

result.raw         # STT가 뱉은 원문
result.corrected   # 보정된 문장
result.spans       # 찾은 용어
```

용어집에서 hotwords를 만들어 STT에 넘긴다. **같은 용어집이 인식 힌트와 보정 기준을 겸하므로
둘이 어긋나지 않는다.**

STT를 갈아끼울 수 있다. `transcribe(audio, hotwords=None) -> str`만 있으면 된다.

```python
class MySTT:
    def transcribe(self, audio, hotwords=None):
        return "도커 서버 다시 열어봐"

run("dummy.wav", stt=MySTT()).corrected
# 'Docker 서버 다시 열어봐'
```

테스트에서 이 방식을 쓰면 **모델도 GPU도 음성 파일도 필요 없다.**

임계값과 용어집도 넘길 수 있다.

```python
run("meeting.wav", glossary=my_glossary, threshold=0.85)
```

---

## 11. 명령줄에서 한 번 돌려보기

```bash
uv run --extra cuda python -m devdemangle.demo meeting.wav
```

```
[전사] 기터벳의 리포지토리 만들었어?
[보정] GitHub의 repository 만들었어?
[변경] 기터벳 → GitHub, 리포지토리 → repository
```

hotwords 없이 비교해 보려면 `--no-hotwords`를 붙인다.

```bash
uv run --extra cuda python -m devdemangle.demo meeting.wav --no-hotwords
```

---

## 12. 고정 번역어

대부분의 개발 용어는 번역하면 안 된다. 그래서 **원문 유지가 기본값**이고, 예외만 용어집에 적는다.

```python
glossary.translation_for("Vue", "ko")            # 'Vue'                  원문 유지
glossary.translation_for("의존성 주입", "en")     # 'dependency injection'  고정 번역어
glossary.translation_for("모르는용어", "en")      # '모르는용어'             입력 그대로
```
