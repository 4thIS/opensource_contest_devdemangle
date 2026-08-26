"""Gradio 데모 — 마이크로 말하면 용어를 지켜서 자막과 번역을 보여준다.

    uv run --extra demo --extra cuda python -m devdemangle.app

**gradio는 최상위에서 import하지 않는다.** `highlight()`는 순수 함수라 gradio 없이
테스트하고, UI 조립은 `main()` 안에서만 gradio를 가져간다. `stt`·`translate`
서브패키지와 같은 방식이다 — 코어를 떼어 쓰는 사람에게 UI 라이브러리를 지우지 않는다.

화면이 보여줘야 하는 것은 셋이다.

    마이크에서 들어온 말이 어떻게 전사됐나          raw
    무엇을 지켰나 — 어디를 어떻게 찾았는지           spans 하이라이트
    그 용어가 번역에서도 살아남았나                 translated

가운데가 핵심이다. 보정된 문장만 보여주면 "번역기 하나 더"로 보이고,
**어디를 우리가 지켰는지가 눈에 보여야** 차별점이 전달된다.
"""

from devdemangle.types import Span

# 화면에서 색으로 갈릴 라벨. gradio의 HighlightedText가 라벨별로 색을 배정한다.
# 값은 Method의 문자열 그대로다 — 라벨을 따로 만들면 코드와 화면이 어긋난다.
LABELS = {
    "exact": "용어집에 등록된 표기·별칭",
    "regex": "모양으로 찾은 미등록 식별자 (보정하지 않음)",
    "fuzzy": "용어집에 없는 발음 변형 — 소리로 찾음",
}


def highlight(text: str, spans: list[Span]) -> list[tuple[str, str | None]]:
    """보정된 문장을 (조각, 라벨) 목록으로 자른다.

    라벨이 `None`인 조각은 하이라이트되지 않는다. 용어 조각의 라벨은 **탐지 방법**이라,
    화면에서 "사전에 있어서 잡았다"와 "소리로 찾았다"가 색으로 갈린다.

    ⚠️ `Span`의 좌표는 **결과 텍스트 기준**이다. 입력 기준인 `Match`를 넣으면
    앞 용어가 길어진 만큼 뒤 조각이 밀려 엉뚱한 글자를 덮는다.

    빈 조각은 만들지 않는다. 용어가 문장 맨 앞에 있거나 두 용어가 맞닿으면
    사이가 0글자인데, 그대로 넣으면 화면에 빈 칸이 생긴다.
    """
    chunks: list[tuple[str, str | None]] = []
    cursor = 0

    for span in sorted(spans, key=lambda s: s.start):
        if span.start > cursor:
            chunks.append((text[cursor:span.start], None))
        chunks.append((text[span.start:span.end], str(span.method)))
        cursor = span.end

    if cursor < len(text):
        chunks.append((text[cursor:], None))

    return chunks


def term_rows(spans: list[Span]) -> list[list[str]]:
    """찾은 용어를 표로. 무엇을 어떻게 찾았고 얼마나 믿는지."""
    return [
        [
            span.term,
            span.matched,
            LABELS.get(str(span.method), str(span.method)),
            f"{span.confidence:.3f}" if span.method == "fuzzy" else "—",
        ]
        for span in spans
    ]


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="DevDemangle 데모 — 음성에서 개발 용어를 지킨다")
    parser.add_argument("--model", default="large-v3", help="Whisper 모델 (기본 large-v3)")
    parser.add_argument("--device", default="cuda", help="추론 장치 (기본 cuda)")
    parser.add_argument("--compute", default="float16", help="정밀도 (VRAM 부족 시 int8_float16)")
    parser.add_argument("--no-translate", action="store_true", help="번역 없이 보정만")
    parser.add_argument("--share", action="store_true", help="공개 링크 생성")
    args = parser.parse_args(argv)

    try:
        import gradio as gr
    except ImportError:
        print("데모에는 gradio가 필요합니다: uv sync --extra demo", file=sys.stderr)
        return 1

    from devdemangle.correct import default_glossary
    from devdemangle.pipeline import run
    from devdemangle.stt import WhisperSTT

    glossary = default_glossary()
    print(f"용어 {len(glossary)}개 로딩 완료. 모델을 올립니다...", flush=True)

    stt = WhisperSTT(model_size=args.model, device=args.device, compute_type=args.compute)
    translator = None
    if not args.no_translate:
        from devdemangle.translate.opusmt import OpusMTTranslator

        translator = OpusMTTranslator()
    print("준비 끝.", flush=True)

    def analyze(audio_path):
        if not audio_path:
            return "", [], "", []

        result = run(audio_path, stt=stt, glossary=glossary, translator=translator)
        translated = result.translated or "(번역 없이 실행 중입니다)"
        if result.lost:
            translated += f"\n\n⚠️ 번역이 삼킨 용어: {', '.join(result.lost)}"

        return result.raw, highlight(result.corrected, result.spans), translated, term_rows(result.spans)

    with gr.Blocks(title="DevDemangle") as demo:
        gr.Markdown(
            "# DevDemangle\n"
            "음성인식과 번역이 뭉갠 개발 용어를 되돌립니다. "
            "**색이 칠해진 부분이 지켜낸 용어**이고, 색은 어떻게 찾았는지에 따라 갈립니다."
        )

        audio = gr.Audio(sources=["microphone", "upload"], type="filepath", label="말하거나 파일을 올리세요")
        go = gr.Button("분석", variant="primary")

        raw = gr.Textbox(label="① 음성인식이 받아쓴 그대로", lines=2, interactive=False)
        marked = gr.HighlightedText(label="② 보정 결과 — 색칠된 곳이 지켜낸 용어", combine_adjacent=False)
        translated = gr.Textbox(label="③ 번역 (용어 보호 적용)", lines=3, interactive=False)
        table = gr.Dataframe(
            headers=["표준형", "말한 그대로", "찾은 방법", "신뢰도"],
            label="찾은 용어",
            interactive=False,
        )

        go.click(analyze, inputs=audio, outputs=[raw, marked, translated, table])
        audio.stop_recording(analyze, inputs=audio, outputs=[raw, marked, translated, table])

    demo.launch(share=args.share)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
