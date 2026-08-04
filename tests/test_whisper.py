"""WhisperSTT 어댑터 테스트.

어댑터는 얇다 — 로직이 없다. 그래서 두 가지만 본다:
  ① 계약: faster-whisper를 올바른 인자로 부르는가 (mock, 빠름, GPU 불필요)
  ② 스모크: 실제 tiny 모델로 터지지 않고 str을 내놓는가 (GPU 필요, 느림)
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _install_fake_faster_whisper(monkeypatch, segments):
    """faster_whisper.WhisperModel을 가짜로 갈아끼운다.

    실제 모델·GPU 없이 어댑터가 넘기는 인자를 관찰하기 위해서다.
    반환된 MagicMock으로 호출 인자를 검증한다.
    """
    fake_model = MagicMock()
    fake_model.transcribe.return_value = (iter(segments), object())  # (segments, info)
    fake_ctor = MagicMock(return_value=fake_model)
    fake_module = SimpleNamespace(WhisperModel=fake_ctor)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    return fake_ctor, fake_model


def test_transcribe_joins_segment_texts(monkeypatch):
    """전사 결과 세그먼트들을 이어붙여 하나의 문자열로 돌려준다."""
    segs = [SimpleNamespace(text="lodash "), SimpleNamespace(text="써서")]
    _install_fake_faster_whisper(monkeypatch, segs)

    from devdemangle.stt.whisper import WhisperSTT

    stt = WhisperSTT()
    result = stt.transcribe("audio.wav")

    assert result == "lodash 써서"


def test_transcribe_passes_hotwords_and_korean_vad(monkeypatch):
    """hotwords·language='ko'·vad_filter가 실제로 faster-whisper로 넘어간다."""
    _, fake_model = _install_fake_faster_whisper(monkeypatch, [])

    from devdemangle.stt.whisper import WhisperSTT

    WhisperSTT().transcribe("audio.wav", hotwords="lodash React")

    _, kwargs = fake_model.transcribe.call_args
    assert kwargs["hotwords"] == "lodash React"
    assert kwargs["language"] == "ko"
    assert kwargs["vad_filter"] is True


def test_model_loaded_once_with_configured_options(monkeypatch):
    """모델은 __init__에서 지정 옵션으로 한 번만 로딩된다 (large-v3는 무거워 재사용)."""
    fake_ctor, fake_model = _install_fake_faster_whisper(monkeypatch, [])

    from devdemangle.stt.whisper import WhisperSTT

    stt = WhisperSTT(model_size="large-v3", device="cuda", compute_type="float16")
    stt.transcribe("a.wav")
    stt.transcribe("b.wav")

    fake_ctor.assert_called_once_with("large-v3", device="cuda", compute_type="float16")
    assert fake_model.transcribe.call_count == 2


# --- 스모크: 실제 모델로 진짜 도는지 (GPU 필요, mock 없음) ---


def _cuda_available() -> bool:
    """GPU가 없으면 스모크를 건너뛴다 (CI·CPU 환경)."""
    try:
        from devdemangle._cuda import setup_cuda_dlls

        setup_cuda_dlls()
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _write_silence_wav(path, seconds=3, rate=16000):
    """무음 WAV를 만든다 (16kHz 모노 16bit) — stdlib wave만 사용."""
    import wave

    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)      # 16bit
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * rate * seconds)


@pytest.mark.skipif(not _cuda_available(), reason="CUDA GPU 없음 — 스모크 생략")
def test_smoke_real_tiny_model_returns_str(tmp_path):
    """실제 tiny 모델 + 무음 3초 WAV로 어댑터가 터지지 않고 str을 낸다.

    mock이 못 잡는 것: setup_cuda_dlls 순서, 실제 transcribe 경로가 진짜 도는지.
    tiny를 쓰는 이유는 large-v3(3GB)가 아니라 빠르게 경로만 태우기 위해서다.
    """
    from devdemangle.stt.whisper import WhisperSTT

    wav = tmp_path / "silence.wav"
    _write_silence_wav(wav)

    stt = WhisperSTT(model_size="tiny")
    result = stt.transcribe(wav)

    assert isinstance(result, str)
