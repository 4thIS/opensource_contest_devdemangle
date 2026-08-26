"""번역 보호 — 용어를 가리고 번역한 뒤 되돌린다.

기계번역은 개발 용어를 번역 대상으로 오인한다. `debounce`를 `devounce`로,
`TypeScript`를 `Type Type Type`으로 만들고, 심하면 문장이 통째로 무너진다.
그래서 번역기에 넘기기 전에 용어를 플레이스홀더로 가리고, 나온 뒤에 되돌린다.

**플레이스홀더는 대문자 글자만 쓴다.** 이건 취향이 아니라 실측 결과다
(`experiments/results/risk2.md`·`risk2b.md`):

    TERMZERO      13/13 살아남음
    "TERMZERO"     0/13
    __TERMZERO__   0/13
    Termzero       2/13
    ⟦0⟧            0/13

같은 플레이스홀더인데 따옴표나 밑줄을 덧붙이면 100%p가 날아간다. 숫자도 위험하다 —
`⟦0⟧`는 남은 숫자만 번역돼 `zero`라는 영어 단어로 나왔다. 그래서 글자만 남긴다.

번역기는 주입받는다. 이 모듈은 transformers를 import하지 않는다 — 코어가 번역
라이브러리를 모르게 하려는 것이고, 덕분에 이 로직은 모델 없이 테스트된다.
"""

from dataclasses import dataclass
from typing import Protocol

from devdemangle.glossary import Glossary
from devdemangle.types import Span

PLACEHOLDER_PREFIX = "TERM"

# 0~9를 영어 단어로. 자리올림해 두 자리 이상을 만든다(10 → TERMONEZERO).
# 아라비아 숫자를 쓰지 않는 이유는 위 docstring 참고 — 숫자는 번역돼 버린다.
_DIGIT_WORDS = (
    "ZERO", "ONE", "TWO", "THREE", "FOUR",
    "FIVE", "SIX", "SEVEN", "EIGHT", "NINE",
)


class Translator(Protocol):
    """한국어 문장 하나를 영어로. 구현체는 devdemangle.translate.opusmt.OpusMTTranslator."""

    def translate(self, text: str) -> str: ...


@dataclass
class TranslationResult:
    text: str
    protected: list[str]  # 가렸던 용어 (입력 순서)
    lost: list[str]       # 번역이 삼켜서 되돌리지 못한 것


def placeholder_for(index: int) -> str:
    """index번째 용어에 쓸 플레이스홀더.

    실험에서 쓴 이름(TERMZERO·TERMONE·TERMTWO)을 그대로 이어간다. 열 개를 넘으면
    자릿수를 이어 붙인다 — TERMONEZERO처럼. 글자만 남기려고 숫자 대신 단어를 쓴다.
    """
    if index < 0:
        raise ValueError(f"index는 0 이상이어야 한다: {index}")
    digits = "".join(_DIGIT_WORDS[int(d)] for d in str(index))
    return PLACEHOLDER_PREFIX + digits


def _check(text: str, spans: list[Span]) -> None:
    """가리기 전에 좌표를 검사한다.

    Span은 **보정된 텍스트** 기준이라 다른 텍스트에 그대로 쓰면 엉뚱한 자리를 자른다.
    조용히 잘못 자르느니 여기서 멈추는 게 낫다.
    """
    for s in spans:
        if s.start < 0 or s.end > len(text) or s.start >= s.end:
            raise ValueError(
                f"Span이 텍스트 범위를 벗어난다: [{s.start}:{s.end}] (len={len(text)})"
            )
    ordered = sorted(spans, key=lambda s: s.start)
    for a, b in zip(ordered, ordered[1:]):
        if a.end > b.start:
            raise ValueError(
                f"Span이 겹친다: [{a.start}:{a.end}] · [{b.start}:{b.end}]"
            )


def mask(text: str, spans: list[Span]) -> tuple[str, list[tuple[str, str]]]:
    """용어 자리를 플레이스홀더로 바꾼다.

    문자열 치환(`str.replace`)을 쓰지 않는다. 같은 용어가 두 번 나오면 한 번에 둘 다
    바뀌어 서로 다른 플레이스홀더를 줄 수 없고, 용어가 아닌 곳에 우연히 같은 글자가
    있으면 거기까지 바뀐다. 위치로 자른다.

    Returns:
        (가려진 텍스트, [(플레이스홀더, 원래 용어)] 입력 순서)
    """
    _check(text, spans)

    order = sorted(range(len(spans)), key=lambda i: spans[i].start)
    mapping: list[tuple[str, str]] = [("", "")] * len(spans)

    parts: list[str] = []
    cursor = 0
    for slot, i in enumerate(order):
        s = spans[i]
        token = placeholder_for(slot)
        parts.append(text[cursor:s.start])
        parts.append(token)
        cursor = s.end
        mapping[i] = (token, s.term)
    parts.append(text[cursor:])

    return "".join(parts), mapping


def unmask(text: str, mapping: list[tuple[str, str, str]]) -> tuple[str, list[str]]:
    """플레이스홀더를 되돌린다.

    mapping의 각 항목은 (플레이스홀더, 되돌릴 값, 보고할 이름) 세 값이다. 둘이
    갈리는 건 고정 번역어가 있을 때다 — 텍스트에는 번역어를 꽂아 넣지만, 무엇을
    지켰고 무엇을 잃었는지는 항상 canonical(보고할 이름) 기준으로 알린다.

    번역이 플레이스홀더를 삼키는 경우가 있다. 되돌리지 못한 것은 숨기지 않고
    따로 알린다 — 조용히 빠지면 무엇이 사라졌는지 아무도 모른다.

    긴 플레이스홀더부터 되돌린다. TERMONE이 TERMONEZERO의 앞부분과 겹쳐서,
    짧은 것부터 하면 긴 쪽이 잘린다.
    """
    restored = text
    lost: list[str] = []

    for token, restore_value, report_value in sorted(mapping, key=lambda m: -len(m[0])):
        if token in restored:
            restored = restored.replace(token, restore_value)
        else:
            lost.append(report_value)

    # lost는 입력 순서로 돌려준다 (위에서 길이순으로 돌았다)
    order = [report_value for token, _, report_value in mapping if report_value in lost]
    return restored, order


def translate_protected(
    text: str,
    spans: list[Span],
    translator: Translator,
    glossary: Glossary | None = None,
    target_lang: str = "en",
) -> TranslationResult:
    """용어를 보호하면서 번역한다.

    Args:
        text: 번역할 문장. 보통 `correct()`가 돌려준 보정된 텍스트다.
        spans: 보호할 용어의 위치. **text 기준 좌표여야 한다** —
            `CorrectionResult.spans`가 그대로 맞는다.
        translator: 문장 하나를 번역하는 것.
        glossary: 고정 번역어 조회에 쓴다. 생략하면 모든 용어를 canonical
            그대로 복원한다 — 고정 번역어가 없을 때와 같은 동작이다.
        target_lang: `glossary.translation_for()`에 넘길 언어 코드.

    Returns:
        번역문과, 보호한 용어·잃어버린 용어. 두 목록 다 canonical 기준이다 —
        본문에는 고정 번역어가 들어가도, 무엇을 지켰는지는 항상 원래 용어 이름으로 알린다.
    """
    if not spans:
        return TranslationResult(text=translator.translate(text), protected=[], lost=[])

    masked, mapping = mask(text, spans)
    translated = translator.translate(masked)

    restore_mapping = [
        (
            token,
            glossary.translation_for(term, target_lang) if glossary is not None else term,
            term,
        )
        for token, term in mapping
    ]
    restored, lost = unmask(translated, restore_mapping)

    return TranslationResult(
        text=restored,
        protected=[term for _, term in mapping],
        lost=lost,
    )
