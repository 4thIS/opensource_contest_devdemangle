"""STT에 넘길 hotwords 문자열을 만든다."""

from collections.abc import Iterable

from devdemangle.types import Term

# Whisper가 프롬프트로 받는 토큰 상한. 컨텍스트의 절반이다.
DEFAULT_BUDGET = 224

# 토크나이저를 직접 부르지 않고 근사한다. 표준형은 대부분 ASCII 기술 용어라
# 4자 ≈ 1토큰으로 잡는다. 어떤 용어를 남길지 고르는 선별 로직은 후속 작업이고,
# 지금은 용어집 순서를 그대로 따라 예산이 찰 때까지만 넣는다.
_CHARS_PER_TOKEN = 4


def _tokens(word: str) -> int:
    return max(1, -(-len(word) // _CHARS_PER_TOKEN))


def build(glossary: Iterable[Term], *, budget: int = DEFAULT_BUDGET) -> str:
    """표준형만 공백으로 이어 붙인다. risk1 실험과 같은 형식이다.

    alias는 넣지 않는다 — hotwords는 "이런 단어가 나올 것"이라고 STT에
    알려주는 힌트라, 깨진 형태를 넣으면 오히려 그쪽으로 인식된다.

    budget(토큰)을 넘기면 거기서 멈춘다. 씨앗 21개로는 걸리지 않지만
    목표인 50개가 되면 뒤쪽이 잘려 나가므로 상한을 명시해둔다.
    """
    selected: list[str] = []
    used = 0

    for term in glossary:
        cost = _tokens(term.canonical) + (1 if selected else 0)
        if used + cost > budget:
            break
        selected.append(term.canonical)
        used += cost

    return " ".join(selected)


class WithoutHotwords:
    """hotwords를 떼고 전사한다 (비교용).

    파이프라인이 용어집에서 hotwords를 만들어 넘기므로, 끄려면 넘어온 값을
    여기서 버린다. 파이프라인에 "끄기" 분기를 두지 않기 위한 것이다.

    **시연에서 이게 필요하다.** hotwords를 켜면 STT가 용어를 이미 맞게 뱉어서
    보정 단계가 무엇을 되돌렸는지 화면에 안 보인다.
    """

    def __init__(self, inner) -> None:
        self._inner = inner

    def transcribe(self, audio, hotwords: str | None = None) -> str:
        return self._inner.transcribe(audio, hotwords=None)
