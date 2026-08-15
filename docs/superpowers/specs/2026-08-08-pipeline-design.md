# 파이프라인 관통 설계 (M2)

**작성** 2026-08-08 · **대상 브랜치** `feature/pipeline` (base: `feature/term-correction`)

## 목표

음성 파일 하나가 **보정된 텍스트**까지 한 번에 도는 경로를 만든다. 명령 한 줄로 실행되고, 결과를 눈으로 확인할 수 있어야 한다.

```
WAV ──▶ STT(hotwords) ──▶ 전사 원문 ──▶ correct() ──▶ 보정 텍스트
```

번역은 이 설계의 범위가 아니다 (M3).

## 왜 지금 이 모양인가

### hotwords는 검증된 기여다

`experiments/results/risk1.md`: 용어 인식률 **34.8% → 73.9% (+39.1%p)**, 악화된 용어 0개. 그래서 STT 계층은 hotwords를 **항상** 켠 상태를 기본값으로 한다. 끄는 건 비교 실험용 옵션이다.

### hotwords 선별기는 만들지 않는다

risk1 결론에 "토큰 예산 224 안에서 선별"이라는 문구가 있지만, 현재 `terms.yaml`의 canonical은 **21개**다. 전부 넣어도 예산에 한참 못 미친다. 선별기는 용어집이 커진 뒤의 문제이므로 지금 만들면 쓰이지 않는 코드가 된다. 용어집이 예산을 넘기는 시점에 만든다.

### STT는 주입 가능한 인터페이스로 둔다

이유는 테스트다. faster-whisper는 모델 가중치 다운로드와 (실질적으로) GPU를 요구한다. 이걸 파이프라인에 직접 박으면 **모델 없는 환경에서 테스트가 한 줄도 못 돈다.** 팀원 PC에 GPU가 없을 수 있고, 대회 심사자가 코드를 받아 테스트를 돌려볼 수도 있다.

## 구조

| 모듈 | 책임 | 의존 |
|---|---|---|
| `devdemangle/stt.py` | 음성 → 텍스트. faster-whisper를 감싼다 | faster-whisper (지연 import) |
| `devdemangle/pipeline.py` | STT와 correct를 잇는다 | stt, correct, glossary |
| `devdemangle/demo.py` | CLI 진입점 | pipeline |
| `devdemangle/correct.py` | (기존) alias → canonical | — |

### `stt.py`

```python
class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> str: ...

def hotwords_from(terms: list[Term]) -> str:
    """canonical들을 공백으로 이어 붙인다. risk1 실험과 같은 형식."""

class WhisperTranscriber:
    def __init__(self, model_size: str = "large-v3",
                 compute_type: str = "float16",
                 hotwords: str | None = None) -> None: ...
    def transcribe(self, audio_path: Path) -> str: ...
```

- `setup_cuda_dlls()`를 **faster_whisper import 전에** 호출한다. 기존 `devdemangle/_cuda.py`를 그대로 쓰며, 순서를 어기면 CUDA DLL을 못 찾는다 (risk1 스크립트가 같은 제약을 명시).
- 모델 로드는 `__init__`이 아니라 **첫 `transcribe()` 호출 때** 한다. 객체를 만드는 것만으로 수 GB를 내려받으면 테스트가 무거워진다.
- 전사 파라미터는 risk1과 동일하게 고정: `language="ko"`, `vad_filter=True`. 실험 조건과 프로덕션 조건이 달라지면 risk1 수치를 보고서에 인용할 근거가 사라진다.

### `pipeline.py`

```python
@dataclass
class PipelineResult:
    raw: str              # STT가 뱉은 원문
    corrected: str        # 보정 후
    matches: list[Match]  # 무엇을 무엇으로 고쳤는지

def run(audio_path: Path,
        transcriber: Transcriber | None = None,
        terms: list[Term] | None = None) -> PipelineResult: ...
```

`transcriber`를 생략하면 기본 용어집으로 hotwords를 만든 `WhisperTranscriber`를 쓴다. 테스트는 가짜 transcriber를 넣는다.

`raw`를 결과에 남기는 이유: 데모와 발표에서 **"STT가 이렇게 뭉갰고, 우리가 이렇게 되돌렸다"** 를 보여주는 게 이 프로젝트의 핵심 서사다. 보정 후만 남기면 그 대비가 사라진다.

### `demo.py`

```bash
uv run --extra cuda python -m devdemangle.demo experiments/audio/seed_01.wav
```

출력:

```
[전사] 깃허브에 새 레포지토리 만들었어?
[보정] GitHub에 새 repository 만들었어?
[변경] 깃허브 → GitHub, 레포지토리 → repository
```

`--model`, `--compute` 플래그는 risk1 스크립트와 같은 이름·기본값을 쓴다 (VRAM 부족 시 조정). `--no-hotwords`는 비교용으로 둔다.

## 테스트

| 대상 | 방법 | 모델 필요 |
|---|---|---|
| `hotwords_from()` | 용어집 → 문자열 형식 검증 | ❌ |
| `pipeline.run()` | 가짜 transcriber 주입, 보정 결과 검증 | ❌ |
| `PipelineResult.raw` 보존 | 가짜 transcriber가 준 원문이 그대로 남는지 | ❌ |
| `WhisperTranscriber` | **자동 테스트 없음** — 실음성 수동 확인 | ✅ |

`WhisperTranscriber`를 단위 테스트하지 않는 건 의도적이다. 감싸고 있는 게 faster-whisper 호출 한 번뿐이라, 모킹해서 테스트하면 "내가 부른 함수를 내가 불렀는지" 확인하는 동어반복이 된다. 실제 검증은 데모 명령을 실음성으로 돌려서 한다.

## 검증 (DoD)

- [ ] `uv run pytest` 통과 — **모델·GPU·음성 파일 없이**
- [ ] `uv run --extra cuda python -m devdemangle.demo <녹음.wav>` 실행 시 전사·보정·변경 3줄 출력
- [ ] 출력의 보정 텍스트에 용어가 canonical 형태로 들어 있음

## 전제와 미해결

- **음성 파일은 저장소에 없고 앞으로도 넣지 않는다.** `.gitignore`가 오디오를 최후 방어선으로 막고 있다(딥페이크 악용 위험). 데모 검증용 녹음은 로컬에만 둔다.
- 이 브랜치의 base가 `feature/term-correction`이다. 그 브랜치가 아직 `origin/main`에 병합되지 않아, M1에서 통합 순서를 정해야 한다 — **`feature/term-correction`을 먼저 병합한 뒤 이 브랜치를 올린다.**
- 번역 연동(M3)은 `pyproject.toml`의 `translate` extra가 `transformers`+`torch` 기반이다. 작업지시서 T-01에는 Argos Translate라고 적었으나 실제 저장소는 OPUS-MT(transformers) 방향으로 잡혀 있다. **M3 착수 전에 어느 쪽인지 확정해야 한다** — 둘 다 라이선스 문제는 없다(MIT / Apache-2.0 계열).
