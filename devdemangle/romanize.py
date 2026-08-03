"""한글을 소리 비교용 로마자로 바꾼다 — 퍼지 보정의 전처리.

"라다시"와 "lodash"는 문자로 보면 공통점이 없다. 소리로 비교하려면 한쪽을 로마자로
바꿔 편집거리를 재야 한다. 표기 정확도는 목표가 아니다 — phonetic_key가 남은 차이를
정규화한다.

범위: 모음이 보존되는 음차(레디스·라다시·디바운스)를 안전망으로 잡는다. 자음이 뭉친
원어(Rust·nginx·npm)는 소리 유사도가 낮아 못 잡으며, 그런 용어는 용어집 등록(alias)으로
커버한다. 퍼지는 "용어집이 주력, 퍼지는 안전망"의 안전망 역할이다.
"""

import re

# 유니코드 한글 음절 = 0xAC00 + (초성 * 21 * 28) + (중성 * 28) + 종성
_HANGUL_BASE = 0xAC00
_MEDIAL_COUNT = 21
_FINAL_COUNT = 28

# 초성 19 — ㄹ은 음절 첫머리에서 r (종성 ㄹ은 l, 아래 JONGSUNG 참고)
CHOSUNG = [
    "g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s",
    "ss", "", "j", "jj", "ch", "k", "t", "p", "h",
]

# 중성 21 — 으 = eu (phonetic_key가 이 삽입 모음을 제거한다)
JUNGSUNG = [
    "a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa",
    "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i",
]

# 종성 28 — 첫 원소는 받침 없음. 길이가 27이면 ㅎ받침("좋")에서 IndexError로 터진다.
JONGSUNG = [
    "", "k", "k", "k", "n", "n", "n", "t", "l", "k",
    "m", "l", "l", "l", "p", "l", "m", "p", "p", "t",
    "t", "ng", "t", "t", "k", "t", "p", "t",
]

# 유니코드 한글 음절은 초성 19 × 중성 21 × 종성 28. 표가 어긋나면 로딩 시 바로 잡는다.
assert len(CHOSUNG) == 19 and len(JUNGSUNG) == 21 and len(JONGSUNG) == 28


def romanize(text: str) -> str:
    """한글을 로마자로 바꾼다. 한글이 아닌 문자는 그대로 통과한다.

    >>> romanize("라다시")
    'radasi'
    >>> romanize("redis")   # 비-한글은 그대로
    'redis'
    """
    out = []
    for ch in text:
        code = ord(ch) - _HANGUL_BASE
        if 0 <= code < len(CHOSUNG) * _MEDIAL_COUNT * _FINAL_COUNT:
            cho = code // (_MEDIAL_COUNT * _FINAL_COUNT)
            jung = (code % (_MEDIAL_COUNT * _FINAL_COUNT)) // _FINAL_COUNT
            jong = code % _FINAL_COUNT
            out.append(CHOSUNG[cho] + JUNGSUNG[jung] + JONGSUNG[jong])
        else:
            out.append(ch)
    return "".join(out)


_REPEAT = re.compile(r"(.)\1+")


def phonetic_key(text: str) -> str:
    """소리 비교용 정규화 키. 한글·영어에 같은 파이프라인을 태운다.

    한글 음차와 영어 원어를 같은 키로 수렴시켜 편집거리를 가깝게 만든다.

    >>> phonetic_key("레디스") == phonetic_key("redis")   # 둘 다 "ledis"
    True

    정규화 3단계 (기술근거 §7, 각 단계 실측 검증):
      ① r → l 통일    — 한국어는 r/l을 구분하지 않는다
      ② "eu"(으) 제거 — 음차가 원어에 없는 삽입 모음을 넣는다
      ③ 연속 중복 축약 — 원어/음차의 중복 표기 차이를 없앤다
    (②를 ③보다 먼저 둬서, eu 제거로 생긴 중복도 축약되게 한다.)
    """
    s = romanize(text).lower()
    s = s.replace("r", "l")   # ①
    s = s.replace("eu", "")   # ②
    s = _REPEAT.sub(r"\1", s)  # ③
    return s
