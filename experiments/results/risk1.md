# 리스크 1 결과 — hotwords 효과 (최종)

> ✅ **3인 녹음 완료. 최종 판정.** 판정 기준·정의: `team_docs/10_리스크.md` §2

| | |
|---|---|
| 실행일 | 2026-07-27 |
| 모델 | faster-whisper large-v3 (float16, CUDA) |
| 표본 | seed_01~21 (21개 문장) / 용어 20개(고유) |
| **화자** | **3명** — 김도현(seed_01~07·21) / 박효민(seed_08~14) / 이명재(seed_15~20) |
| 스크립트 | `experiments/risk1_hotwords.py` |
| 원시 로그 | §5 (스크립트 콘솔 출력 원문) |

---

## 1. 판정 — ✅ 효과 있음

| 조건 | 용어 인식률 |
|------|-------------|
| hotwords 없음 | 8/23 = **34.8%** |
| hotwords 있음 | 17/23 = **73.9%** |
| **차이** | **+39.1%p** |

판정 기준 +5%p를 크게 상회한다. **`hotwords.py`를 구현한다** (토큰 예산 224 안에서 용어 선별).

> 용어 등장 횟수가 23인 것은 seed_19(React+TypeScript)와 seed_01(GitHub+repository)이 2개씩,
> Docker·TypeScript·README가 서로 다른 문장에 두 번씩 나오기 때문이다. 고유 용어는 20개.

## 2. 용어별 변화 (없음 → 있음)

**개선 8 / 악화 0 / 변화없음 12.** 악화가 하나도 없다 — hotwords가 역효과를 낸 용어는 없었다.

| 개선된 용어 (8) | 없음 → 있음 |
|---|---|
| Docker | 0/2 → 2/2 |
| FastAPI | 0/1 → 1/1 |
| GitHub | 0/1 → 1/1 |
| README | 0/2 → 1/2 (seed_21만, §3-3) |
| VS Code | 0/1 → 1/1 |
| git commit | 0/1 → 1/1 |
| localhost | 0/1 → 1/1 |
| pull request | 0/1 → 1/1 |

"변화없음 12" 중 대부분(JSON·npm install·CSS·SQL·REST API·console.log·AWS)은 **hotwords 없이도
원래 잘 잡히던 것들**이다. 약어·흔한 형태라 STT가 처음부터 맞혔다.

## 3. 관찰

### 3-1. hotwords 없이 STT가 얼마나 뭉개는가 (문제의식의 실물 증거)

| 용어 | hotwords 없이 뱉은 것 |
|------|----------------------|
| GitHub | **"기터벳"** |
| git commit | **"Git 커뮤니타"** |
| README | **"리듬"** |
| FastAPI | **"베스트 API"** |
| Python | **"파일선"** |
| Docker | **"닷컬"** / "도커" |
| TypeScript | **"타입스트리트"** |

발표에서 "왜 개발 용어 보호가 필요한가"를 보여주는 실물 자료. 원본 로그(§5)를 지우지 말 것.

### 3-2. ⭐ hotwords로도 못 살린 것 — 한계 (정직하게 기록)

3개 용어가 hotwords 있음에서도 실패했다. **이게 hotwords가 만능이 아니라는 근거이자,
2주차 보정(correct.py)이 왜 필요한가의 근거다.**

| 용어 | 실패 원인 | 누가 처리하나 |
|------|-----------|---------------|
| **Python "파일선"** | 발음이 표준형과 너무 멀어 hotwords 편향이 못 걸림 | correct.py 퍼지 매칭 |
| **React / TypeScript "타입스트리트"** | seed_19 — **한 문장에 용어 2개가 몰리면 약해진다**(§3-4) | hotwords 개선 + 보정 |
| **repository "리포지토리"** | STT는 정확히 발음을 옮겼다. 표준형 영단어만 정답으로 쳐서 MISS | correct.py 음차 alias |
| **Vue "뷰"** | 짧은 음차. hotwords 있음에서도 "뷰"로 남음 | correct.py |

> `repository`·`Vue`는 STT 실패가 아니다. "리포지토리"·"뷰"로 **정확히 전사됐는데** 우리가
> 표준형만 정답으로 세어서 MISS다. 이건 hotwords의 한계가 아니라 **보정 단계의 몫**이다.
> → hotwords(인식)와 correct(사후 보정)가 왜 둘 다 필요한지를 보여주는 실측 근거.

### 3-3. README — 문맥이 hotwords 효과를 좌우한다

같은 용어 `README`가 두 문장에서 갈렸다.

| 문장 | hotwords 있음 |
|------|--------------|
| seed_06 `README 수정해 뒀어요` | ❌ "리듬이 수정되었습니다" |
| seed_21 `readme 파일 수정해 뒀어요` | ✅ "README 파일 수정해 뒀어요" |

**문장 맨 앞에 홀로 선 짧은 용어는 Whisper가 붙잡을 앵커가 없어 hotwords도 못 건다.** 뒤에
분류어("파일")가 오면 그 자리에 hotwords가 표준형을 밀어넣는다. (파일럿에서 발견, 최종에서 재확인.)

**실용 함의:** 짧은 용어는 뒤에 분류어(파일·서버·명령어·컴포넌트)를 붙인 문장이 인식에 유리하다.

### 3-4. 조합 문장(용어 2개)이 더 어렵다

seed_19 `React 랑 TypeScript 같이 쓰고 있어요`는 **hotwords 있음에서도 둘 다 실패**했다
("타입 스트릿"). 반면 각각 단독으로 나온 TypeScript(seed_08)는 hotwords 없이도 잡혔다.
**한 문장에 용어가 몰리면 hotwords 예산이 분산되거나 문맥이 흐려진다**는 신호. 3주차
`hotwords.py`에서 용어 선별 전략을 짤 때 고려한다.

---

## 4. 다음 행동

- [x] 3인 녹음 완료, 최종 판정: 효과 있음 (+39.1%p)
- [ ] `hotwords.py` 구현 (3주차, 토큰 예산 224 내 용어 선별 — 조합 문장 §3-4 고려)
- [ ] 리스크 문서(10) §2 판정 결과 반영 (미판정 → 확정)
- [ ] 요구사항(02) `S-STT-05` 확정 (조건부 → 필수)
- [ ] 품질·평가(05) 3단계 비교표 ② 단계 유지 확정
- [ ] `data/terms.yaml` alias 갱신 — 실측 음차를 반영 (박효민 2주차 수집이 이어받음):
      "기터벳"(GitHub) · "베스트 API"(FastAPI) · "파일선"(Python) · "닷컬"(Docker) ·
      "타입스트리트"(TypeScript) 등은 추측이 아니라 **실제로 나온** 변형이다

---

## 5. 원본 실행 로그 (보존)

```
매니페스트 21개 중 녹음 존재 21개

용어 20개를 hotwords로 사용:
  AWS CSS Docker FastAPI GitHub JSON Python README REST API React SQL TypeScript VS Code Vue console.log git commit localhost npm install pull request repository

=== hotwords 없음 ===
  [MISS] seed_01.wav: 기터벳의 리포지토리 만들었어?
          놓침: ['GitHub', 'repository']
  [OK  ] seed_02.wav: JSON 파일은 그대로인가?
  [MISS] seed_03.wav: 뷰 컴포넌트를 다시 만들어야 해요
          놓침: ['Vue']
  [OK  ] seed_04.wav: npm install부터 진행해야지
  [MISS] seed_05.wav: Git 커뮤니타가 걸렸어요.
          놓침: ['git commit']
  [MISS] seed_06.wav: 리듬이 수정되었습니다.
          놓침: ['README']
  [MISS] seed_07.wav: 도커 컨테이너 재시작할게.
          놓침: ['Docker']
  [OK  ] seed_08.wav: TypeScript 문법 에러라는데?
  [OK  ] seed_09.wav: sql 문을 수정해야 합니다
  [OK  ] seed_10.wav: console.log를 한번 확인해 볼게요.
  [OK  ] seed_11.wav: CSS 파일 새로 만들었어요.
  [OK  ] seed_12.wav: REST API 응답이 드려요.
  [MISS] seed_13.wav: 풀 리퀘스트 새로 올렸어요
          놓침: ['pull request']
  [MISS] seed_14.wav: 로컬 호스트로 들어가면 돼요.
          놓침: ['localhost']
  [OK  ] seed_15.wav: AWS 한번 배워보라고요
  [MISS] seed_16.wav: vs 코드로 작업중이요
          놓침: ['VS Code']
  [MISS] seed_17.wav: 베스트 API 서버 열었어.
          놓침: ['FastAPI']
  [MISS] seed_18.wav: 파일선으로 작성했어
          놓침: ['Python']
  [MISS] seed_19.wav: 리액트랑 타입스트리트 같이 쓰고 있어요.
          놓침: ['React', 'TypeScript']
  [MISS] seed_20.wav: 닷컬 배포했어요.
          놓침: ['Docker']
  [MISS] seed_21.wav: 리듬이 파일 수정해 뒀어요.
          놓침: ['README']
  >>> 용어 인식률: 8/23 = 34.8%

=== hotwords 있음 ===
  [MISS] seed_01.wav: GitHub에서의 리포지터리 만들었어.
          놓침: ['repository']
  [OK  ] seed_02.wav: JSON 파일은 그대로인가?
  [MISS] seed_03.wav: 뷰 컴포넌트를 다시 만들어야 해요.
          놓침: ['Vue']
  [OK  ] seed_04.wav: npm install부터 진행해야지.
  [OK  ] seed_05.wav: git commit 하고 알렸어요.
  [MISS] seed_06.wav: 리듬이 수정되었습니다.
          놓침: ['README']
  [OK  ] seed_07.wav: Docker 컨테이너 재시작할게.
  [OK  ] seed_08.wav: TypeScript 문법 에러라는데?
  [OK  ] seed_09.wav: SQL 문을 수정해야 합니다.
  [OK  ] seed_10.wav: console.log 한번 확인해 볼게요.
  [OK  ] seed_11.wav: CSS 파일 새로 만들었어요.
  [OK  ] seed_12.wav: REST API 응답이 드려요.
  [OK  ] seed_13.wav: pull request 새로 올렸어요.
  [OK  ] seed_14.wav: localhost 로 들어가면 돼요.
  [OK  ] seed_15.wav: AWS 한번 배워보라고요.
  [OK  ] seed_16.wav: VS Code로 작업 중이요.
  [OK  ] seed_17.wav: FastAPI 서버 열었어.
  [MISS] seed_18.wav: 파일선으로 작성했어.
          놓침: ['Python']
  [MISS] seed_19.wav: 리액트랑 타입 스트릿을 같이 쓰고 있어요.
          놓침: ['React', 'TypeScript']
  [OK  ] seed_20.wav: Docker를 배포했어요.
  [OK  ] seed_21.wav: README 파일 수정해 뒀어요.
  >>> 용어 인식률: 17/23 = 73.9%
```

차이: +39.1%p / 화자: 3명 (김도현·박효민·이명재)
