"""Gradio 데모 — 말하거나 문장을 넣으면 용어를 지켜서 자막과 번역을 보여준다.

    uv run --extra demo --extra cuda --extra translate python -m devdemangle.app

**gradio는 최상위에서 import하지 않는다.** 화면을 만드는 순수 함수들은 gradio 없이
테스트하고, UI 조립은 `main()` 안에서만 gradio를 가져간다. `stt`·`translate`
서브패키지와 같은 방식이다 — 코어를 떼어 쓰는 사람에게 UI 라이브러리를 지우지 않는다.

화면이 보여줘야 하는 것은 넷이다.

    ① 들어온 문장 — 음성이면 받아쓴 결과            raw
    ② 이대로 번역하면 (가리지 않음)                 비교 대상
    ③ 무엇을 지켰나 — 어디를 어떻게 찾았는지          spans 하이라이트
    ④ 그 용어가 번역에서도 살아남았나                translated

**②가 있어야 ④가 뭘 했는지 보인다.** 지켜낸 결과만 띄우면 "번역기 하나 더"로 보인다.
둘은 같은 번역기에 같은 문장을 넣고 **용어를 가렸는지만** 다르다.

**입력은 음성과 글자 둘 다 받는다.** 명령행 플래그처럼 소리로 받기 애매한 것을
넣어볼 수 있어야 하고, 코어가 문자열만으로 돈다는 것도 그 자리에서 보인다.
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


NO_TRANSLATOR = "(번역 없이 실행 중입니다)"


def pick_source(audio_path, text: str | None) -> tuple[str, str]:
    """음성과 글자 중 무엇으로 돌릴지 고른다.

    **손으로 친 쪽이 우선이다.** 앞 시연의 음성이 입력칸에 남아 있어도, 방금 친 문장이
    방금 의도한 것이다. 공백만 남은 칸은 비어 있는 것으로 본다 — 그것 때문에
    음성이 무시되면 이유를 찾기 어렵다.
    """
    typed = (text or "").strip()
    if typed:
        return "text", typed
    if audio_path:
        return "audio", audio_path
    return "none", ""


def view(result, translator):
    """파이프라인 결과를 화면 네 칸과 표 하나로 펼친다.

    **보호 없는 번역을 같이 낸다.** 화면에 지켜낸 결과만 띄우면 무엇을 지켰는지가
    안 보인다 — 비교 대상이 있어야 보호 계층이 한 일이 드러난다.

    비교가 성립하려면 **같은 모델에 같은 문장**을 넣어야 한다. 그래서 `raw`가 아니라
    보정된 문장(`corrected`)을 가리지 않고 그대로 넘긴다. 원문을 넘기면 STT 오류까지
    섞여서, 차이가 보호 때문인지 전사 때문인지 갈라낼 수 없다.

    UI 조립과 떼어 둔 이유는 gradio 없이 테스트하기 위해서다.
    """
    if translator is None:
        unprotected = protected = NO_TRANSLATOR
    else:
        unprotected = translator.translate(result.corrected)
        protected = result.translated or NO_TRANSLATOR
        if result.lost:
            protected += f"\n\n⚠️ 번역이 삼킨 용어: {', '.join(result.lost)}"

    return (
        result.raw,
        highlight(result.corrected, result.spans),
        unprotected,
        protected,
        term_rows(result.spans),
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="DevDemangle 데모 — 음성에서 개발 용어를 지킨다")
    parser.add_argument("--model", default="large-v3", help="Whisper 모델 (기본 large-v3)")
    parser.add_argument("--device", default="cuda", help="추론 장치 (기본 cuda)")
    parser.add_argument("--compute", default="float16", help="정밀도 (VRAM 부족 시 int8_float16)")
    parser.add_argument("--no-translate", action="store_true", help="번역 없이 보정만")
    parser.add_argument(
        "--no-hotwords",
        action="store_true",
        help="hotwords 없이 전사한다. 시연에서 보정 효과를 보이려면 이 옵션을 쓴다",
    )
    parser.add_argument("--share", action="store_true", help="공개 링크 생성")
    args = parser.parse_args(argv)

    try:
        import gradio as gr
    except ImportError:
        print("데모에는 gradio가 필요합니다: uv sync --extra demo", file=sys.stderr)
        return 1

    from devdemangle.correct import default_glossary
    from devdemangle.hotwords import WithoutHotwords
    from devdemangle.pipeline import run, run_text
    from devdemangle.stt import WhisperSTT

    glossary = default_glossary()
    print(f"용어 {len(glossary)}개 로딩 완료. 모델을 올립니다...", flush=True)

    stt = WhisperSTT(model_size=args.model, device=args.device, compute_type=args.compute)
    if args.no_hotwords:
        stt = WithoutHotwords(stt)
    translator = None
    if not args.no_translate:
        from devdemangle.translate.opusmt import OpusMTTranslator

        translator = OpusMTTranslator()
    print("준비 끝.", flush=True)

    def analyze(audio_path, typed):
        kind, source = pick_source(audio_path, typed)
        if kind == "none":
            return "말하거나 파일을 올리거나, 아래 칸에 문장을 넣으세요.", [], "", "", []

        try:
            if kind == "text":
                result = run_text(source, glossary, translator)
            else:
                result = run(source, stt=stt, glossary=glossary, translator=translator)
        except Exception as exc:  # 시연 중에 스택 대신 읽을 수 있는 말이 뜨게 한다
            return f"처리하지 못했습니다: {exc}", [], "", "", []

        return view(result, translator)

    # 녹화 화면(1280×960)에 한 번에 담기게 좌우로 나눈다. 세로로 쌓으면 표가 잘리고,
    # 잘린 채로 찍으면 "②와 ④를 나란히 본다"는 이 화면의 목적이 사라진다.
    with gr.Blocks(title="DevDemangle") as demo:
        gr.Markdown(
            "## DevDemangle &nbsp;&nbsp;<sub>음성인식과 번역이 뭉갠 개발 용어를 되돌립니다</sub>\n"
            "**②와 ④를 나란히 보십시오.** 같은 번역기에 같은 문장을 넣고 **용어를 가렸는지만** 다릅니다."
        )

        with gr.Row():
            with gr.Column(scale=2):
                audio = gr.Audio(
                    sources=["microphone", "upload"], type="filepath",
                    label="말하거나 파일을 올리세요",
                )
                typed = gr.Textbox(
                    label="또는 문장을 직접 — 음성 없이 코어만 돌립니다",
                    placeholder="빌드할 때 --no-cache 붙여서 돌려보세요",
                    lines=2,
                )
                go = gr.Button("분석", variant="primary")

            with gr.Column(scale=3):
                raw = gr.Textbox(label="① 들어온 문장 — 음성이면 받아쓴 결과", lines=2, interactive=False)
                plain = gr.Textbox(label="② 이대로 번역하면 — 보호 없음", lines=2, interactive=False)
                marked = gr.HighlightedText(
                    label="③ 보정 결과 — 색칠된 곳이 지켜낸 용어", combine_adjacent=False,
                )
                translated = gr.Textbox(label="④ 번역 — 용어 보호 적용", lines=2, interactive=False)

        table = gr.Dataframe(
            headers=["표준형", "말한 그대로", "찾은 방법", "신뢰도"],
            label="찾은 용어",
            interactive=False,
            row_count=(2, "dynamic"),
        )

        # 순서는 view()가 돌려주는 순서와 같아야 한다 — 어긋나면 칸이 뒤바뀐다.
        outputs = [raw, marked, plain, translated, table]
        inputs = [audio, typed]
        go.click(analyze, inputs=inputs, outputs=outputs)
        audio.stop_recording(analyze, inputs=inputs, outputs=outputs)
        typed.submit(analyze, inputs=inputs, outputs=outputs)

    # css는 gradio 6부터 launch()로 넘긴다. 폭을 묶어야 좌우 두 열이 벌어지지 않는다.
    demo.launch(share=args.share, css=".gradio-container{max-width:1240px !important}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
