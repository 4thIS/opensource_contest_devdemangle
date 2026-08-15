"""용어집 로딩 — YAML을 읽어 Term 목록으로 만든다.

이 프로젝트엔 DB가 없다. 용어집이 데이터 전부이며 성능을 좌우한다.
"""

from collections.abc import Iterable, Iterator
from pathlib import Path

import yaml

from devdemangle.types import Term

SCHEMA_VERSION = 1


class GlossaryError(ValueError):
    """용어집 로딩·검증 실패.

    ValueError를 상속하므로 `except ValueError`로도 잡힌다.
    검증 실패는 첫 건에서 멈추지 않고 전부 모아 한 번에 보고한다.
    """


class Glossary:
    """용어집. 검증된 진입점은 from_yaml이다.

    __init__은 입력을 신뢰한다. 파일 없이 용어집을 만들기 위한 통로다.
    대소문자만 다른 canonical을 직접 넣으면 조회에서는 마지막 것만 남지만
    len·canonicals는 둘 다 센다. from_yaml은 규칙 7이 이를 거부한다.
    """

    def __init__(self, terms: Iterable[Term]) -> None:
        self._terms = tuple(terms)
        # 조회는 대소문자를 무시한다. 저장은 원문 그대로다 — canonical이 공식 표기이자 출력 형태다.
        self._by_canonical = {t.canonical.lower(): t for t in self._terms}

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Glossary":
        """용어집을 읽는다.

        규칙 위반은 첫 건에서 멈추지 않고 전부 모아 GlossaryError 하나로 보고한다.
        파일이 없으면 FileNotFoundError가 그대로 올라간다.
        """
        text = Path(path).read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise GlossaryError(f"{path}: YAML 문법 오류\n{exc}") from exc

        raws, errors = _validate(data)
        if errors:
            lines = "\n".join(f"  - {e}" for e in errors)
            raise GlossaryError(f"{path}: 검증 실패 ({len(errors)}건)\n{lines}")

        return cls(
            Term(
                canonical=raw["canonical"],
                aliases=tuple(raw.get("aliases") or ()),
                translations=dict(raw.get("translations") or {}),
            )
            for raw in raws
        )

    def __iter__(self) -> Iterator[Term]:
        return iter(self._terms)

    def __len__(self) -> int:
        return len(self._terms)

    def get(self, canonical: str) -> Term | None:
        return self._by_canonical.get(canonical.lower())

    def translation_for(self, canonical: str, lang: str) -> str:
        """고정 번역어를 돌려준다. 없으면 원문 유지가 기본값이다.

        대부분의 개발 용어는 번역하면 안 되므로, 예외만 용어집에 적는다.
        """
        term = self.get(canonical)
        if term is None:
            return canonical
        return term.translations.get(lang, term.canonical)

    @property
    def canonicals(self) -> list[str]:
        return [t.canonical for t in self._terms]


ALLOWED_KEYS = frozenset({"canonical", "aliases", "translations"})


def _validate(data: object) -> tuple[list[dict], list[str]]:
    """용어집 원본을 검사한다.

    Returns:
        (검사를 통과한 항목들, 오류 메시지 목록). 오류가 있으면 항목은 쓰지 않는다.
    """
    errors: list[str] = []

    # 규칙 1
    if not isinstance(data, dict):
        return [], ["최상위가 매핑이 아닙니다 (version·terms 키가 필요합니다)"]

    # 규칙 2
    if "version" not in data:
        errors.append("version 키가 없습니다")
    elif data["version"] != SCHEMA_VERSION:
        errors.append(f"version이 {data['version']}입니다 (지원: {SCHEMA_VERSION})")

    # 규칙 3
    raw_terms = data.get("terms")
    if raw_terms is None:
        errors.append("terms 키가 없습니다")
        return [], errors
    if not isinstance(raw_terms, list):
        errors.append(f"terms가 리스트가 아닙니다 ({type(raw_terms).__name__})")
        return [], errors

    ok: list[dict] = []
    canonical_owner: dict[str, int] = {}   # 소문자 canonical -> 항목 번호
    alias_owner: dict[str, int] = {}       # 소문자 alias -> 항목 번호

    for i, raw in enumerate(raw_terms):
        where = f"terms[{i}]"

        if not isinstance(raw, dict):
            errors.append(f"{where}: 매핑이 아닙니다 ({type(raw).__name__})")
            continue

        # 규칙 10 — 오타로 별칭이 조용히 사라지는 것을 막는다
        unknown = sorted(set(raw) - ALLOWED_KEYS)
        if unknown:
            allowed = ", ".join(sorted(ALLOWED_KEYS))
            errors.append(f"{where}: 알 수 없는 키 {unknown} (허용: {allowed})")

        # 규칙 4
        canonical = raw.get("canonical")
        canonical_valid = isinstance(canonical, str) and bool(canonical.strip())
        if canonical is None:
            errors.append(f"{where}: canonical 키가 없습니다")
        elif not canonical_valid:
            errors.append(f"{where}: canonical이 비어 있거나 문자열이 아닙니다")

        # 규칙 7 — 대소문자 무시 (canonical이 유효할 때만 등록 가능)
        if canonical_valid:
            key = canonical.lower()
            if key in canonical_owner:
                errors.append(
                    f"{where}: canonical 중복 '{canonical}' "
                    f"(terms[{canonical_owner[key]}]와 같습니다)"
                )
            else:
                canonical_owner[key] = i

        # 규칙 5
        aliases = raw.get("aliases")
        if aliases is not None:
            if not isinstance(aliases, list):
                errors.append(f"{where}: aliases가 리스트가 아닙니다 ({type(aliases).__name__})")
                aliases = None
            elif any(not isinstance(a, str) or not a.strip() for a in aliases):
                errors.append(f"{where}: aliases에 비어 있거나 문자열이 아닌 원소가 있습니다")
                aliases = None

        # 규칙 6
        translations = raw.get("translations")
        if translations is not None:
            if not isinstance(translations, dict):
                errors.append(
                    f"{where}: translations가 매핑이 아닙니다 ({type(translations).__name__})"
                )
            elif any(
                not isinstance(k, str) or not isinstance(v, str)
                for k, v in translations.items()
            ):
                errors.append(f"{where}: translations의 키·값은 문자열이어야 합니다")

        # 규칙 9 — 같은 alias가 두 용어에 있으면 보정 대상이 모호해진다
        for alias in aliases or ():
            akey = alias.lower()
            if akey in alias_owner:
                errors.append(
                    f"{where}: alias '{alias}'가 terms[{alias_owner[akey]}]에도 있습니다"
                )
            else:
                alias_owner[akey] = i

        if canonical_valid:
            ok.append(raw)

    # 규칙 8 — 항목을 다 본 뒤에야 전체 canonical 집합을 알 수 있다
    for i, raw in enumerate(raw_terms):
        if not isinstance(raw, dict):
            continue
        own = raw.get("canonical")
        own_key = own.lower() if isinstance(own, str) else None
        aliases = raw.get("aliases")
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            akey = alias.lower()
            if akey in canonical_owner and akey != own_key:
                errors.append(
                    f"terms[{i}]: alias '{alias}'가 "
                    f"terms[{canonical_owner[akey]}]의 canonical과 충돌합니다"
                )

    return ok, errors
