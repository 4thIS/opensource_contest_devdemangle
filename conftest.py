"""저장소 루트를 import 경로에 올린다 — `eval` 패키지를 테스트에서 쓰기 위해서다.

`devdemangle`은 설치되지만 `eval`은 배포물이 아니라 측정 도구라 설치되지 않는다.
pytest가 이 파일이 있는 디렉터리를 sys.path에 넣어주므로 `from eval.benchmark import ...`가 선다.
"""
