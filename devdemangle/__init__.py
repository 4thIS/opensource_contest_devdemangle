"""DevDemangle - 음성인식·번역이 뭉갠 개발 용어를 되돌린다."""

from devdemangle.correct import CorrectionResult, correct
from devdemangle.detect import detect, resolve_overlaps
from devdemangle.fuzzy import fuzzy_detect
from devdemangle.glossary import Glossary, GlossaryError
from devdemangle.pipeline import PipelineResult, run
from devdemangle.types import Match, Method, Span, Term

__all__ = [
    "CorrectionResult",
    "Glossary",
    "GlossaryError",
    "Match",
    "Method",
    "PipelineResult",
    "Span",
    "Term",
    "correct",
    "detect",
    "fuzzy_detect",
    "resolve_overlaps",
    "run",
]
__version__ = "0.1.0"
