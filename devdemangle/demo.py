"""음성 파일 하나를 전사·보정해서 보여주는 데모 CLI."""

from devdemangle.pipeline import PipelineResult


def format_result(result: PipelineResult) -> str:
    if result.matches:
        changes = ", ".join(f"{m.original} → {m.canonical}" for m in result.matches)
    else:
        changes = "없음"
    return f"[전사] {result.raw}\n[보정] {result.corrected}\n[변경] {changes}"
