"""Optional NVIDIA GPU acceleration for the Whisper model.

faster-whisper runs on the CPU out of the box. On an NVIDIA graphics card it
can run several times faster, but only with NVIDIA's CUDA 12 libraries (cuBLAS
and cuDNN, about 1 GB), which are too big to ship inside the installer. So this
is opt-in: the user switches it on in Settings, the libraries are downloaded
once from PyPI (where NVIDIA publishes them) into the app's data folder, and
from the next launch the model loads on the GPU.

It is deliberately conservative. The GPU is used only when the card supports
a fast number format (float16 or int8); a card that offers only float32 (older
than about 2016) is slower than this app's CPU path, so it is skipped. Any
failure, at load or mid-transcription, falls back to the CPU (see
Transcriber), so a driver problem can never leave the app unable to dictate.

AMD and Intel graphics are not supported: the engine (CTranslate2) is CUDA
only.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

LIBS_DIR = Path.home() / "AppData" / "Local" / "VoxScribe" / "gpu"
APPROX_DOWNLOAD_MB = 1080

# The DLLs CTranslate2 loads for CUDA 12 on Windows. Checked before the GPU is
# offered, so a half-finished download is never mistaken for a working setup.
REQUIRED_DLLS = ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll")

# Fastest first. "float32" alone is not worth it (see module docstring).
_FAST_COMPUTE_TYPES = ("int8_float16", "float16", "int8")


@dataclass(frozen=True)
class _Wheel:
    name: str
    url: str
    size: int
    sha256: str


# Pinned PyPI wheels for CUDA 12.4, which run on any NVIDIA driver from the
# 12.4 generation (2024) onward. Their SHA-256 is checked before anything is
# unpacked, so a file swapped or corrupted on the way is never loaded.
_WHEELS = (
    _Wheel(
        "cuBLAS",
        "https://files.pythonhosted.org/packages/e2/2a/4f27ca96232e8b5269074a72e03b4e0d43aa68c9b965058b1684d07c6ff8/"
        "nvidia_cublas_cu12-12.4.5.8-py3-none-win_amd64.whl",
        396_895_858,
        "5a796786da89203a0657eda402bcdcec6180254a8ac22d72213abc42069522dc",
    ),
    _Wheel(
        "cuDNN",
        "https://files.pythonhosted.org/packages/3f/d0/f90ee6956a628f9f04bf467932c0a25e5a7e706a684b896593c06c82f460/"
        "nvidia_cudnn_cu12-9.1.0.70-py3-none-win_amd64.whl",
        679_925_892,
        "6278562929433d68365a07a4a1546c237ba2849852c0d4b2262a486e805b977a",
    ),
)

_dll_dir_handles: list = []


@dataclass(frozen=True)
class GpuStatus:
    gpu_count: int
    name: str | None
    libs_ready: bool
    compute_type: str | None  # the fast mode the card supports, or None

    @property
    def usable(self) -> bool:
        return self.gpu_count > 0 and self.libs_ready and self.compute_type is not None


def libs_ready(libs_dir: Path = LIBS_DIR) -> bool:
    return all((libs_dir / dll).is_file() for dll in REQUIRED_DLLS)


def activate_libs(libs_dir: Path = LIBS_DIR) -> bool:
    """Makes the downloaded DLLs visible to this process. False if not downloaded."""
    if not libs_ready(libs_dir):
        return False
    if hasattr(os, "add_dll_directory"):
        _dll_dir_handles.append(os.add_dll_directory(str(libs_dir)))
    os.environ["PATH"] = str(libs_dir) + os.pathsep + os.environ.get("PATH", "")
    return True


def pick_compute_type(supported: set[str] | list[str]) -> str | None:
    """The fastest GPU mode this card offers, or None when it only does float32."""
    for kind in _FAST_COMPUTE_TYPES:
        if kind in supported:
            return kind
    return None


def nvidia_gpu_count() -> int:
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except Exception:  # noqa: BLE001 -- no driver, or a broken CUDA install: no GPU
        return 0


def nvidia_gpu_name() -> str | None:
    """Card name for the Settings label; None when it cannot be read."""
    try:
        out = subprocess.run(  # noqa: S603 -- fixed command
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    first = out.stdout.strip().splitlines()[:1]
    return first[0].strip() if out.returncode == 0 and first else None


def _supported_gpu_types() -> set[str]:
    try:
        import ctranslate2

        return set(ctranslate2.get_supported_compute_types("cuda"))
    except Exception:  # noqa: BLE001
        return set()


def status() -> GpuStatus:
    """What Settings shows. Loads the libraries first when they are present, so
    the card's supported modes can be read."""
    count = nvidia_gpu_count()
    ready = libs_ready()
    compute_type = None
    if count > 0 and ready and activate_libs():
        compute_type = pick_compute_type(_supported_gpu_types())
    return GpuStatus(count, nvidia_gpu_name() if count > 0 else None, ready, compute_type)


def pick_device(use_gpu: bool) -> tuple[str, str]:
    """(device, compute_type) for WhisperModel: the GPU when the user turned it
    on and it is usable, else the CPU settings this app has always used."""
    if use_gpu:
        current = status()
        if current.usable:
            return "cuda", current.compute_type  # type: ignore[return-value]
    return "cpu", "int8"


def _download_wheel(wheel: _Wheel, dest: Path, progress: Callable[[str], None] | None) -> None:
    """Streams one wheel to `dest` (never held in memory) and checks it."""
    request = urllib.request.Request(wheel.url, headers={"User-Agent": "VoxScribe"})
    digest = hashlib.sha256()
    received = 0
    with urllib.request.urlopen(request, timeout=30) as response, dest.open("wb") as out:  # noqa: S310 -- fixed pythonhosted URL
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
            digest.update(chunk)
            received += len(chunk)
            if progress:
                progress(f"Downloading {wheel.name}... {received * 100 // wheel.size}%")
    if received != wheel.size:
        raise OSError(f"The {wheel.name} download was incomplete. Try again.")
    if digest.hexdigest() != wheel.sha256:
        raise OSError(f"The {wheel.name} download did not match its checksum. Try again.")


def _extract_dlls(wheel_path: Path, libs_dir: Path) -> None:
    """Copies only the .dll files out of a wheel, flat into `libs_dir`."""
    with zipfile.ZipFile(wheel_path) as archive:
        for info in archive.infolist():
            name = info.filename
            if name.lower().endswith(".dll") and "/bin/" in name:
                target = libs_dir / Path(name).name
                with archive.open(info) as src, target.open("wb") as dst:
                    while chunk := src.read(1024 * 1024):
                        dst.write(chunk)


def download_libs(progress: Callable[[str], None] | None = None) -> None:
    """Fetches NVIDIA's cuBLAS and cuDNN (about 1 GB) into LIBS_DIR. Raises
    OSError when the network is unavailable (including when offline mode is on),
    the download is cut short or fails its checksum."""
    LIBS_DIR.mkdir(parents=True, exist_ok=True)
    for wheel in _WHEELS:
        with tempfile.TemporaryDirectory(prefix="voxscribe-gpu-") as tmp:
            path = Path(tmp) / "wheel.zip"
            _download_wheel(wheel, path, progress)
            if progress:
                progress(f"Unpacking {wheel.name}...")
            _extract_dlls(path, LIBS_DIR)
    if not libs_ready():
        raise OSError("The GPU libraries are incomplete. Try again.")
