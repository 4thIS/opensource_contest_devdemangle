"""faster-whisper 어댑터 — 오디오를 한국어 텍스트로.

⚠️ import 순서: `setup_cuda_dlls()`를 faster_whisper import 전에 호출해야 한다.
CTranslate2가 검색 플래그 없는 LoadLibrary를 써서, 안 그러면 추론에서
`cublas64_12.dll not found`로 터진다 (실행·운영 문서 CUDA DLL 절).

그래서 모듈 로드 때 setup_cuda_dlls()를 부르고, faster_whisper import는
__init__으로 미룬다 — 그 시점엔 PATH가 이미 고쳐져 있다.

어댑터는 얇게 유지한다. 로직을 넣으면 코어가 오디오를 알게 된다.
"""

from pathlib import Path

from devdemangle._cuda import setup_cuda_dlls

setup_cuda_dlls()  # faster_whisper가 import되기 전에 PATH를 고쳐둔다


class WhisperSTT:
    """faster-whisper로 오디오를 전사한다.

    모델은 __init__에서 한 번 로딩해 재사용한다 (large-v3는 무거워 매번 로딩하면 안 된다).
    """

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
    ) -> None:
        import faster_whisper  # setup_cuda_dlls() 이후에 import (위 주석 참고)

        self._model = faster_whisper.WhisperModel(
            model_size, device=device, compute_type=compute_type
        )

    def transcribe(self, audio: str | Path, hotwords: str | None = None) -> str:
        """오디오 파일을 한국어로 전사한다.

        Args:
            audio: 오디오 파일 경로.
            hotwords: STT에 힌트로 줄 용어 문자열. 인식 정확도를 높인다 (S-STT-05).

        Returns:
            전사 텍스트. 발화 단위 세그먼트를 공백으로 이어붙인다.
        """
        segments, _ = self._model.transcribe(
            str(audio),
            language="ko",     # S-STT-01: 한국어 전사
            hotwords=hotwords,  # S-STT-05: 용어 힌트
            vad_filter=True,    # S-STT-02: 무음 구간 제거
        )
        # 세그먼트는 제 나름의 앞뒤 공백을 달고 온다. strip 후 이어붙여 이중 공백을 막는다.
        parts = (s.text.strip() for s in segments)
        return " ".join(p for p in parts if p)
