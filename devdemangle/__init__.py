"""DevDemangle - 음성인식·번역이 뭉갠 개발 용어를 되돌린다."""

from devdemangle.glossary import Glossary, GlossaryError
from devdemangle.types import Match, Method, Span, Term

__all__ = ["Glossary", "GlossaryError", "Match", "Method", "Span", "Term"]
__version__ = "0.1.0"
