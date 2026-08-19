# DevDemangle

음성인식·번역이 뭉갠 개발 용어를 되돌리는 Python 라이브러리.

STT와 기계번역은 `lodash debounce`를 "라다시 디바운스"로, `Vue`를 "뷰"로 바꿔버린다.
DevDemangle은 용어집 기반 탐지·보정으로 이런 개발 용어를 표준형으로 복원한다.

```
"라다시 디바운스 써서 처리했어요"  →  "lodash debounce 써서 처리했어요"
```

## 사용법

```bash
git clone https://github.com/4thIS/opensource_contest_devdemangle.git
cd opensource_contest_devdemangle
uv sync
```

```python
from devdemangle import correct

result = correct("파이썬 스크립트 짰어요")
print(result.text)   # "Python 스크립트 짰어요"
print(result.spans)  # [Span(start=0, end=6, term='Python', matched='파이썬', ...)]
```

`spans`의 `start`·`end`는 **보정된 텍스트** 기준이다. 앞 용어가 길어지면 뒤 위치가 밀리기 때문이다 — 입력 기준 좌표가 필요하면 `detect()`가 돌려주는 `Match`를 쓴다.

용어집은 `data/terms.yaml`을 쓴다. 자체 용어집으로 보정하려면 `Glossary`로 불러와 두 번째 인자로 넘긴다.

```python
from devdemangle import Glossary, correct

glossary = Glossary.from_yaml("my_terms.yaml")
result = correct("깃허브에서 봤어요", glossary)   # "GitHub에서 봤어요"
```

> **알려진 한계** — 오탐을 최소화하려고 경계를 좁게 잡았다.
>
> - **앞에 다른 글자가 붙으면 안 잡는다** (`"우리깃허브"`). 한국어에서 용어 앞에 오는 것은 조사가 아니라 다른 단어라, 시작 경계는 완화하지 않는다.
> - **어미는 떼지 않는다** (`"깃허브다"`). 조사는 닫힌 집합이라 목록으로 관리할 수 있지만 어미는 그렇지 않다.
> - 용어집에 **없는** 변형(`Vue` ← `"뷰"` 류)은 이 모듈의 스코프가 아니다 — 소리 유사도 기반 보정이 따로 맡는다.

## 상태

개발 중 (2026 오픈소스 개발자대회 출품 준비). 용어집 기반 탐지(`detect`)·보정(`correct`)과 STT 연동(`pipeline`)까지 구현 완료. 번역 연동은 다음 단계.

실측 — 1주차 코퍼스에서 STT가 놓친 전사문 13개(용어 14건)에 보정을 적용해 **13/14 복원**. 남은 1건은 용어집에 없는 별칭(`Vue` ← "뷰")이라 소리 유사도 보정의 몫이다.

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
