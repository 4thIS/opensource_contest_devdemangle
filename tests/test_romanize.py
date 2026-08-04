from devdemangle.romanize import phonetic_key, romanize


def test_romanize_basic_syllables():
    """한글 음절을 초성·중성·종성 자모로 분해해 로마자로 잇는다.

    ㄹ은 음절 첫머리에서 r. 표기 정확도가 아니라 편집거리를 가깝게 하는 게 목표라 그대로 둔다.
    """
    assert romanize("라다시") == "radasi"


def test_romanize_passes_non_hangul_through():
    """한글이 아닌 문자는 그대로 둔다 — phonetic_key가 영어에도 같은 파이프라인을 태우려면."""
    assert romanize("redis") == "redis"
    assert romanize("npm install") == "npm install"


def test_final_hieut_does_not_crash():
    """종성 리스트가 27개면 ㅎ받침에서 IndexError로 터진다. 28개여야 한다.

    (실제로 27개로 만들었다가 이 테스트에서 잡은 버그다.)
    """
    assert romanize("좋다") == "jotda"


def test_romanize_final_consonant():
    """종성 ㄹ은 l, ㅇ은 ng (초성 ㄹ의 r과 다르다)."""
    assert romanize("돌") == "dol"      # ㄷ+ㅗ+ㄹ(l)
    assert romanize("강") == "gang"     # ㄱ+ㅏ+ㅇ(ng)


# --- phonetic_key: 소리 비교용 정규화 키 ---


def test_phonetic_key_korean_and_english_converge():
    """한글 음차와 영어 원어가 같은 키로 수렴해야 퍼지 매칭이 성립한다."""
    assert phonetic_key("레디스") == phonetic_key("redis")


def test_phonetic_key_known_values():
    """실제 음차↔원어 쌍에서 확인한 키 값."""
    assert phonetic_key("레디스") == "ledis"
    assert phonetic_key("redis") == "ledis"
    assert phonetic_key("라다시") == "ladasi"


def test_phonetic_key_unifies_r_and_l():
    """한국어는 r/l을 구분하지 않는다 → l로 통일."""
    assert phonetic_key("rust") == phonetic_key("lust")


def test_phonetic_key_removes_epenthetic_eu():
    """음차가 원어에 없는 '으'(eu)를 끼워넣는다 → 제거해야 원어에 가까워진다."""
    # 디바운스 → dibaunseu → (eu 제거) dibauns → (r→l 무관)
    assert "eu" not in phonetic_key("디바운스")


def test_phonetic_key_collapses_repeats():
    """연속 중복 문자를 축약한다 (bookkeeper류)."""
    assert phonetic_key("bookkeeper") == phonetic_key("bokeeper".replace("ee", "e"))
    # 직접 검증: 중복이 사라진다
    key = phonetic_key("sslli")
    assert "ss" not in key and "ll" not in key
