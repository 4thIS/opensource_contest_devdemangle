"""번역 어댑터 — 보정된 한국어를 용어 보호하며 영어로.

`protect`는 순수 로직이라 여기서 바로 올린다. 번역기 구현체(OpusMTTranslator)는
transformers·torch를 끌고 오므로 여기서 import하지 않는다 — `import devdemangle`만으로
무거운 라이브러리가 딸려오면 코어를 떼어 쓸 수 없다. 쓸 때 직접 가져간다:

    from devdemangle.translate.opusmt import OpusMTTranslator
"""

from devdemangle.translate.protect import (
    TranslationResult,
    Translator,
    translate_protected,
)

__all__ = ["TranslationResult", "Translator", "translate_protected"]
