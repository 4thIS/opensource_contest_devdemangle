"""_cuda 헬퍼 테스트.

아래 두 테스트는 nvidia pip 패키지(`--extra cuda`)가 깔려 있어야 의미가 있다.
없으면 건너뛴다 — 모델도 GPU도 없는 환경에서 `pytest`가 초록불이어야
코드를 받은 사람이 바로 돌려볼 수 있다.
"""

import pytest

pytest.importorskip("nvidia", reason="--extra cuda 없이 실행 중 (nvidia pip 패키지 없음)")


def test_setup_cuda_dlls_returns_paths():
    from devdemangle._cuda import setup_cuda_dlls

    dirs = setup_cuda_dlls()
    assert isinstance(dirs, list)
    # nvidia 패키지가 깔려 있으면 최소 1개는 나와야 한다
    assert len(dirs) > 0, "nvidia-cublas-cu12가 설치되지 않았습니다"


def test_setup_cuda_dlls_modifies_path():
    import os

    from devdemangle._cuda import setup_cuda_dlls

    dirs = setup_cuda_dlls()
    assert dirs[0] in os.environ["PATH"]
