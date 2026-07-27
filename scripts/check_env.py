"""개발 환경 검증 - 팀원 전원이 개발 시작 전 이 스크립트를 통과해야 한다.

마지막 줄에 "[OK] 환경 정상 - GPU 추론 가능"이 뜨면 통과.
막히면 실행·운영 문서의 "흔한 문제" 표를 볼 것.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from devdemangle._cuda import setup_cuda_dlls  # noqa: E402

print("CUDA DLL 경로:", len(setup_cuda_dlls()), "개 등록")  # 반드시 import 전에

import ctranslate2  # noqa: E402
import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

print("CUDA 장치 수:", ctranslate2.get_cuda_device_count())
assert ctranslate2.get_cuda_device_count() > 0, "GPU가 안 잡힙니다"

model = WhisperModel("tiny", device="cuda", compute_type="float16")
segments, info = model.transcribe(np.zeros(16000 * 3, dtype=np.float32), language="ko")
list(segments)  # 3초 무음으로 추론 경로를 태워 DLL 문제를 드러냄

print("[OK] 환경 정상 - GPU 추론 가능")
