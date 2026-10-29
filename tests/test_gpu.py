import hashlib
import zipfile

import pytest

from core import gpu


def test_picks_the_fastest_gpu_mode():
    assert gpu.pick_compute_type({"float32", "float16", "int8_float16", "int8"}) == "int8_float16"
    assert gpu.pick_compute_type({"float32", "float16"}) == "float16"
    assert gpu.pick_compute_type(["int8", "float32"]) == "int8"


def test_float32_only_cards_are_skipped_because_the_cpu_is_faster():
    assert gpu.pick_compute_type({"float32"}) is None
    assert gpu.pick_compute_type(set()) is None


def test_libs_ready_needs_every_dll(tmp_path):
    assert not gpu.libs_ready(tmp_path)
    for dll in gpu.REQUIRED_DLLS[:-1]:
        (tmp_path / dll).write_bytes(b"x")
    assert not gpu.libs_ready(tmp_path)
    (tmp_path / gpu.REQUIRED_DLLS[-1]).write_bytes(b"x")
    assert gpu.libs_ready(tmp_path)


def test_activate_libs_refuses_when_nothing_is_downloaded(tmp_path):
    assert gpu.activate_libs(tmp_path) is False


def test_extract_keeps_only_dlls_from_bin_folders(tmp_path):
    wheel = tmp_path / "w.zip"
    with zipfile.ZipFile(wheel, "w") as z:
        z.writestr("nvidia/cublas/bin/cublas64_12.dll", b"dll")
        z.writestr("nvidia/cublas/bin/__init__.py", b"py")
        z.writestr("nvidia/cublas/include/cublas.h", b"h")
        z.writestr("nvidia_cublas_cu12-1.dist-info/METADATA", b"m")
    out = tmp_path / "libs"
    out.mkdir()
    gpu._extract_dlls(wheel, out)
    assert [p.name for p in out.iterdir()] == ["cublas64_12.dll"]
    assert (out / "cublas64_12.dll").read_bytes() == b"dll"


class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, n: int) -> bytes:
        chunk = self._data[self._pos : self._pos + n]
        self._pos += n
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _wheel_for(data: bytes, sha: str | None = None, size: int | None = None) -> gpu._Wheel:
    return gpu._Wheel(
        "Test", "https://example.invalid/w.whl", size or len(data), sha or hashlib.sha256(data).hexdigest()
    )


def test_download_accepts_a_matching_file(tmp_path, monkeypatch):
    data = b"a" * 3_000_000
    monkeypatch.setattr(gpu.urllib.request, "urlopen", lambda *a, **k: _FakeResponse(data))
    seen = []
    gpu._download_wheel(_wheel_for(data), tmp_path / "w", seen.append)
    assert (tmp_path / "w").read_bytes() == data
    assert seen[-1] == "Downloading Test... 100%"


def test_download_rejects_a_wrong_checksum(tmp_path, monkeypatch):
    data = b"a" * 1000
    monkeypatch.setattr(gpu.urllib.request, "urlopen", lambda *a, **k: _FakeResponse(data))
    with pytest.raises(OSError, match="checksum"):
        gpu._download_wheel(_wheel_for(data, sha="0" * 64), tmp_path / "w", None)


def test_download_rejects_a_cut_short_file(tmp_path, monkeypatch):
    data = b"a" * 1000
    monkeypatch.setattr(gpu.urllib.request, "urlopen", lambda *a, **k: _FakeResponse(data))
    with pytest.raises(OSError, match="incomplete"):
        gpu._download_wheel(_wheel_for(data, size=2000), tmp_path / "w", None)


def test_pinned_wheels_look_sane():
    for wheel in gpu._WHEELS:
        assert wheel.url.startswith("https://files.pythonhosted.org/")
        assert len(wheel.sha256) == 64
        assert wheel.size > 100_000_000


def test_cpu_is_used_when_the_switch_is_off(monkeypatch):
    monkeypatch.setattr(gpu, "status", lambda: pytest.fail("must not probe the GPU when off"))
    assert gpu.pick_device(False) == ("cpu", "int8")


def test_gpu_is_used_only_when_ready_and_fast(monkeypatch):
    ready = gpu.GpuStatus(1, "RTX", True, "float16")
    monkeypatch.setattr(gpu, "status", lambda: ready)
    assert gpu.pick_device(True) == ("cuda", "float16")
    for bad in (
        gpu.GpuStatus(0, None, True, "float16"),  # no card
        gpu.GpuStatus(1, "RTX", False, None),  # libraries not downloaded
        gpu.GpuStatus(1, "Old", True, None),  # card too old
    ):
        monkeypatch.setattr(gpu, "status", lambda bad=bad: bad)
        assert gpu.pick_device(True) == ("cpu", "int8")
