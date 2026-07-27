"""Windows에서 nvidia pip 패키지의 CUDA DLL을 찾게 해주는 헬퍼."""

import glob
import os


def setup_cuda_dlls() -> list[str]:
    """nvidia pip 패키지의 DLL 디렉터리를 PATH 앞에 추가한다.

    CTranslate2는 검색 플래그 없는 LoadLibrary를 쓰기 때문에
    os.add_dll_directory()를 존중하지 않는다. PATH를 직접 고쳐야 한다.
    faster_whisper를 import하기 전에 호출할 것.

    Returns:
        PATH에 추가된 디렉터리 목록. nvidia 패키지가 없으면 빈 리스트.
    """
    try:
        import nvidia
    except ImportError:
        return []

    dll_dirs = []
    for base in nvidia.__path__:
        dll_dirs += [d for d in glob.glob(os.path.join(base, "*", "bin")) if os.path.isdir(d)]

    if dll_dirs:
        os.environ["PATH"] = os.pathsep.join(dll_dirs) + os.pathsep + os.environ["PATH"]
    return dll_dirs
