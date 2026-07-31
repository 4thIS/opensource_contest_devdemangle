# DevDemangle

음성인식·번역이 뭉갠 개발 용어를 되돌리는 Python 라이브러리.

STT와 기계번역은 `lodash debounce`를 "라다시 디바운스"로, `Vue`를 "뷰"로 바꿔버린다.
DevDemangle은 용어집 기반 탐지·보정으로 이런 개발 용어를 표준형으로 복원한다.

```
"라다시 디바운스 써서 처리했어요"  →  "lodash debounce 써서 처리했어요"
```

## 상태

개발 중 (2026 오픈소스 개발자대회 출품 준비).

## 사용 모델

이 프로젝트는 아래 모델을 실행 시 다운로드해 사용한다. 가중치는 저장소에 포함하지 않는다.

- **Whisper** (OpenAI) — MIT License / 구현: faster-whisper (MIT)
- **OPUS-MT** (Helsinki-NLP/opus-mt-ko-en) — CC-BY 4.0
  > Tiedemann, J., & Thottingal, S. (2020). OPUS-MT — Building open translation
  > services for the World. Proc. of the 22nd EAMT, Lisbon, Portugal.

## 라이선스

이 저장소의 코드는 **MIT License**다 ([LICENSE](LICENSE)).

모델 가중치는 저장소에 포함하지 않고 **실행 시 다운로드**한다. OPUS-MT 가중치는 CC-BY 4.0으로
출처 표기 의무가 있으나(위 "사용 모델" 참고), 저장소에 번들하지 않으므로 그 조건이 코드 배포물에
얽히지 않는다 — 코드 라이선스는 MIT로 유지된다.
