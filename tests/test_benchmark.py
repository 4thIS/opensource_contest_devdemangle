"""평가 하니스의 셈법.

수치가 보고서로 나가므로 **세는 방식 자체를 테스트한다.** 하니스가 조용히 잘못 세면
숫자는 그럴듯하게 나오고 아무도 눈치채지 못한다.
"""

from eval.benchmark import score


def test_restored_term_counts_as_hit():
    """기대한 용어가 결과에 있으면 맞힌 것이다."""
    o = score(expected_text="Docker 씁니다", expected_terms=["Docker"],
              got_text="Docker 씁니다", got_terms=["Docker"])
    assert (o.tp, o.fp, o.fn) == (1, 0, 0)
    assert o.text_ok


def test_missed_term_counts_as_miss():
    """기대했는데 못 찾았으면 재현율을 깎는다."""
    o = score(expected_text="Kotlin 씁니다", expected_terms=["Kotlin"],
              got_text="코트를 씁니다", got_terms=[])
    assert (o.tp, o.fp, o.fn) == (0, 0, 1)
    assert o.missing == ["Kotlin"]
    assert not o.text_ok


def test_unexpected_term_counts_as_false_positive():
    """기대하지 않은 것을 찾았으면 정밀도를 깎는다. 오탐 픽스처가 이 경로로 잡힌다."""
    o = score(expected_text="압축 비율을 높이면", expected_terms=[],
              got_text="압축 Vue을 높이면", got_terms=["Vue"])
    assert (o.tp, o.fp, o.fn) == (0, 1, 0)
    assert o.extra == ["Vue"]


def test_same_term_twice_is_counted_twice():
    """한 문장에 같은 용어가 두 번 나오면 두 번 센다 — 집합으로 접으면 놓침이 숨는다."""
    o = score(expected_text="Docker에서 Docker로", expected_terms=["Docker", "Docker"],
              got_text="Docker에서 Docker로", got_terms=["Docker"])
    assert (o.tp, o.fn) == (1, 1)


from eval.benchmark import Outcome, aggregate


def _o(text_ok=True, tp=0, fp=0, fn=0):
    return Outcome(text_ok=text_ok, tp=tp, fp=fp, fn=fn)


def test_recall_is_found_over_expected():
    m = aggregate([_o(tp=3, fn=1), _o(tp=1, fn=1)])
    assert m.recall == 0.6667


def test_precision_is_correct_over_everything_found():
    m = aggregate([_o(tp=3, fp=1)])
    assert m.precision == 0.75


def test_precision_is_none_when_nothing_was_found():
    """아무것도 안 찾았으면 정밀도는 계산할 수 없다. 1.0으로 채우면 만점처럼 보인다."""
    m = aggregate([_o(), _o()])
    assert m.precision is None


def test_sentence_accuracy_is_exact_text_match_ratio():
    m = aggregate([_o(text_ok=True), _o(text_ok=True), _o(text_ok=False), _o(text_ok=False)])
    assert m.sentence_accuracy == 0.5


def test_false_positive_rate_counts_sentences_that_were_touched():
    """오탐률은 용어 단위가 아니라 문장 단위다 — 한 문장에서 둘 틀려도 오탐 문장은 하나다."""
    m = aggregate([_o(text_ok=False, fp=2), _o(text_ok=True), _o(text_ok=True), _o(text_ok=True)])
    assert m.false_positive_rate == 0.25


from eval.benchmark import classify, survived


def test_changed_text_is_a_restoration_case():
    assert classify({"broken": "도커 씁니다", "expected": "Docker 씁니다", "terms": ["Docker"]}) == "복원"


def test_unchanged_text_without_terms_is_a_false_positive_case():
    assert classify({"broken": "비율이 올라가요", "expected": "비율이 올라가요", "terms": []}) == "오탐"


def test_unchanged_text_with_terms_is_a_protection_case():
    """텍스트가 안 바뀌어도 terms가 있으면 '감지는 됐어야 한다'는 뜻이다."""
    assert classify({"broken": "Redis 씁니다", "expected": "Redis 씁니다", "terms": ["Redis"]}) == "보호"


def test_survived_counts_terms_still_present_in_the_text():
    assert survived("GitHub의 repository 만들었어?", ["GitHub", "repository"]) == 2


def test_survived_does_not_count_a_mangled_term():
    assert survived("기터벳의 리포지토리 만들었어?", ["GitHub", "repository"]) == 0


def test_survived_ignores_case():
    """전사가 'sql'로 뱉어도 SQL은 살아남은 것이다 — 대소문자는 깨짐이 아니다."""
    assert survived("sql 문을 수정해야 합니다", ["SQL"]) == 1


from eval.benchmark import run_stages
from devdemangle.glossary import Glossary
from devdemangle.types import Term

_G = Glossary([Term(canonical="Docker", aliases=("도커",))])
_RECORDS = [
    # off = 힌트 없이 전사(깨짐) / on = 힌트 켜고 전사(살아남음)
    {"off": "도커 씁니다", "on": "Docker 씁니다", "terms": ["Docker"]},
    {"off": "도커 올려요", "on": "도커 올려요", "terms": ["Docker"]},
]


def test_run_stages_reports_all_four_conditions():
    """힌트와 보정은 **서로 독립인 두 축**이다. 넷을 다 내야 표가 오해를 안 만든다.

    셋만 내면 "힌트 위에 보정을 얹은 값"으로 읽히는데, 실제로는 힌트를 뺀 값이었다.
    """
    stages = run_stages(_RECORDS, _G, threshold=0.78)
    assert set(stages) == {
        ("힌트 없음", "보정 없음"),
        ("힌트 적용", "보정 없음"),
        ("힌트 없음", "보정 적용"),
        ("힌트 적용", "보정 적용"),
    }


def test_run_stages_counts_hotwords_axis():
    stages = run_stages(_RECORDS, _G, threshold=0.78)
    assert stages[("힌트 없음", "보정 없음")] == (0, 2)   # 둘 다 "도커"로 깨짐
    assert stages[("힌트 적용", "보정 없음")] == (1, 2)   # 하나만 살아남음


def test_run_stages_counts_correction_axis():
    """보정은 힌트가 있든 없든 걸린다 — 축이 독립이라는 것이 표의 전제다."""
    stages = run_stages(_RECORDS, _G, threshold=0.78)
    assert stages[("힌트 없음", "보정 적용")] == (2, 2)
    assert stages[("힌트 적용", "보정 적용")] == (2, 2)


from eval.benchmark import brief_table


def test_brief_table_is_short_enough_for_a_screen():
    """시연에서 터미널을 찍는다. 스크롤이 생기면 표가 화면 밖으로 나간다."""
    lines = brief_table(_RECORDS, _G, threshold=0.78).splitlines()
    assert len(lines) <= 10


def test_brief_table_shows_all_four_conditions():
    text = brief_table(_RECORDS, _G, threshold=0.78)
    for cell in ("0.0%", "50.0%", "100.0%"):
        assert cell in text
    assert "힌트 없음" in text and "힌트 적용" in text
    assert "보정 없음" in text and "보정 적용" in text


def test_brief_table_states_where_the_glossary_came_from():
    """숫자만 보이면 처음 보는 음성에서도 이만큼 나온다는 뜻으로 읽힌다."""
    assert "용어집" in brief_table(_RECORDS, _G, threshold=0.78)


def test_brief_table_has_no_markdown_pipes():
    """터미널에 띄울 것이라 표 기호가 없어야 읽힌다."""
    assert "|" not in brief_table(_RECORDS, _G, threshold=0.78)
