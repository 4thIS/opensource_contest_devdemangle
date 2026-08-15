"""음성 → 텍스트. faster-whisper를 감싼다."""

from devdemangle.glossary import Term


def hotwords_from(terms: list[Term]) -> str:
    """표준형만 공백으로 이어 붙인다. risk1 실험과 같은 형식이다.

    alias는 넣지 않는다 — hotwords는 "이런 단어가 나올 것"이라고 STT에
    알려주는 힌트라, 깨진 형태를 넣으면 오히려 그쪽으로 인식된다.
    """
    return " ".join(t.canonical for t in terms)
