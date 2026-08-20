"""OPUS-MT 어댑터 — 한국어 문장을 영어로.

모델은 `Helsinki-NLP/opus-mt-ko-en`이다. 대회 운영규정 별표2가 「로컬 또는 독립 서버
환경 내 직접 구동」을 요구하므로 상용 번역 API는 쓸 수 없고, 제8조③(비상업 라이선스
금지) 때문에 NLLB-200·SeamlessM4T(CC-BY-NC)도 못 쓴다. OPUS-MT는 둘 다 통과한다.

어댑터는 얇게 유지한다. 용어 보호는 protect.py의 일이고 여기서는 문장을 넣고 받기만 한다.

transformers·torch는 `__init__`에서 import한다. 모듈을 올리는 것만으로 수백 MB가
따라오면 코어를 떼어 쓸 수 없다. 설치는 `uv sync --extra translate`.
"""

DEFAULT_MODEL = "Helsinki-NLP/opus-mt-ko-en"


class OpusMTTranslator:
    """OPUS-MT로 한국어를 영어로 옮긴다.

    모델은 __init__에서 한 번 올려 재사용한다. 문장마다 다시 올리면 못 쓴다.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = "cpu") -> None:
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as e:  # pragma: no cover - 설치 안내 경로
            raise ImportError(
                "번역에는 transformers가 필요하다: uv sync --extra translate"
            ) from e

        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(device)
        self._device = device

    def translate(self, text: str) -> str:
        """한국어 한 문장을 영어로.

        빈 문자열은 모델에 넣지 않는다 — 토크나이저가 빈 입력에서 경고를 내고,
        돌려줄 것도 없다.
        """
        if not text.strip():
            return text

        batch = self._tokenizer([text], return_tensors="pt", padding=True)
        batch = {k: v.to(self._device) for k, v in batch.items()}
        # max_new_tokens를 따로 주지 않는다. 이 모델의 생성 설정에 max_length가 이미
        # 들어 있어, 둘을 같이 주면 transformers가 매 호출마다 경고를 찍는다.
        generated = self._model.generate(**batch)
        return self._tokenizer.decode(generated[0], skip_special_tokens=True)
