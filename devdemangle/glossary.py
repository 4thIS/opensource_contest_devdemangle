"""용어집 로딩 — YAML을 읽어 Term 목록으로 만든다.

이 프로젝트엔 DB가 없다. 용어집이 데이터 전부이며 성능을 좌우한다 (설계 03 §II).
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
    def __init__(self, terms: Iterable[Term]) -> None:
        self._terms = tuple(terms)
        # 조회는 대소문자를 무시한다 (C-DET-03). 저장은 원문 그대로다.
        self._by_canonical = {t.canonical.lower(): t for t in self._terms}

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Glossary":
        text = Path(path).read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise GlossaryError(f"{path}: YAML 문법 오류\n{exc}") from exc

        terms = [
            Term(
                canonical=raw["canonical"],
                aliases=tuple(raw.get("aliases") or ()),
                translations=dict(raw.get("translations") or {}),
            )
            for raw in data["terms"]
        ]
        return cls(terms)

    def __iter__(self) -> Iterator[Term]:
        return iter(self._terms)

    def __len__(self) -> int:
        return len(self._terms)

    def get(self, canonical: str) -> Term | None:
        return self._by_canonical.get(canonical.lower())

    def translation_for(self, canonical: str, lang: str) -> str:
        """고정 번역어를 돌려준다. 없으면 원문 유지가 기본값이다 (C-GLOS-05)."""
        term = self.get(canonical)
        if term is None:
            return canonical
        return term.translations.get(lang, term.canonical)

    @property
    def canonicals(self) -> list[str]:
        return [t.canonical for t in self._terms]
