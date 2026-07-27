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
