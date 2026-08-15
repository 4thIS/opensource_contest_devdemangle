"""음성 → 텍스트. faster-whisper를 감싼다."""

from pathlib import Path

from devdemangle._cuda import setup_cuda_dlls


class WhisperTranscriber:
    """faster-whisper 래퍼. 모델은 첫 transcribe() 호출 때 로드한다."""

    def __init__(
        self,
        model_size: str = "large-v3",
        compute_type: str = "float16",
        hotwords: str | None = None,
    ) -> None:
        self.model_size = model_size
        self.compute_type = compute_type
        self.hotwords = hotwords
        self._model = None

    def _load(self):
        if self._model is None:
            setup_cuda_dlls()  # faster_whisper import 전에 반드시 호출
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self.model_size, compute_type=self.compute_type)
        return self._model

    def transcribe(self, audio_path: Path) -> str:
        """risk1 실험과 같은 조건으로 전사한다 (language=ko, vad_filter=True)."""
        model = self._load()
        segments, _ = model.transcribe(
            str(audio_path),
            language="ko",
            hotwords=self.hotwords,
            vad_filter=True,
        )
        return " ".join(s.text for s in segments).strip()
