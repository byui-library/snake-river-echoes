"""How the app finds Tesseract.

A packaged build must use the Tesseract it ships with and nothing else. If it
can fall back to PATH, then a build that bundled no Tesseract at all still works
on a developer machine and fails on the first archive workstation -- the exact
failure a clean-machine test exists to catch.
"""
from pathlib import Path

import pytest

from srebook.core import ocr


@pytest.fixture
def bundle(tmp_path):
    """A pretend packaged layout with Tesseract inside it."""
    vendor = tmp_path / "vendor" / "tesseract"
    vendor.mkdir(parents=True)
    exe = vendor / "tesseract.exe"
    exe.write_bytes(b"")
    return tmp_path, exe


def test_a_packaged_build_uses_its_own_tesseract(bundle):
    root, exe = bundle

    assert ocr.find_tesseract(frozen=True, bundle=root) == str(exe)


def test_a_packaged_build_never_falls_back_to_path(tmp_path, monkeypatch):
    """The whole point. A missing bundle must fail loudly, not borrow one."""
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: r"C:\somewhere\tesseract.exe")

    assert ocr.find_tesseract(frozen=True, bundle=tmp_path) is None


def test_a_packaged_build_ignores_a_system_installation(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: None)
    monkeypatch.setattr(ocr, "_WINDOWS_TESSERACT", str(tmp_path / "system.exe"))
    (tmp_path / "system.exe").write_bytes(b"")

    assert ocr.find_tesseract(frozen=True, bundle=tmp_path) is None


def test_an_explicit_override_still_works_in_a_packaged_build(tmp_path, monkeypatch):
    """The documented escape hatch for an archive that keeps Tesseract elsewhere.
    Deliberate operator action, not an accident of PATH."""
    elsewhere = tmp_path / "chosen.exe"
    elsewhere.write_bytes(b"")
    monkeypatch.setenv("SREBOOK_TESSERACT", str(elsewhere))

    assert ocr.find_tesseract(frozen=True, bundle=tmp_path) == str(elsewhere)


def test_running_from_source_may_use_path(tmp_path, monkeypatch):
    """Developing is not deploying; a system Tesseract is fine here."""
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: r"C:\dev\tesseract.exe")

    assert ocr.find_tesseract(frozen=False, bundle=tmp_path) == r"C:\dev\tesseract.exe"


def test_the_resolved_source_is_reportable(bundle):
    """So the clean-machine test can assert WHICH tesseract ran, not merely that
    one did."""
    root, _exe = bundle

    assert ocr.tesseract_source(frozen=True, bundle=root) == "bundled"


def test_source_reports_path_when_borrowed(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: r"C:\dev\tesseract.exe")

    assert ocr.tesseract_source(frozen=False, bundle=tmp_path) == "PATH"


def test_source_reports_nothing_found(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: None)
    monkeypatch.setattr(ocr, "_WINDOWS_TESSERACT", str(tmp_path / "absent.exe"))

    assert ocr.tesseract_source(frozen=False, bundle=tmp_path) == "not found"


def test_the_missing_bundle_error_names_where_it_looked(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setattr(ocr, "find_tesseract", lambda **_kw: None)

    with pytest.raises(ocr.OcrError) as e:
        ocr.run_tesseract(Image.new("L", (10, 10)), cache_dir=tmp_path, key="k")

    assert "Tesseract" in str(e.value)


def test_a_packaged_build_looks_where_pyinstaller_actually_puts_data(tmp_path, monkeypatch):
    """PyInstaller 6 onedir puts bundled data in _internal/, not beside the exe.
    Looking beside the exe finds nothing and the app reports no Tesseract."""
    monkeypatch.setattr(ocr.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ocr.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert ocr.bundle_root() == tmp_path


def test_bundle_root_falls_back_to_the_exe_directory(tmp_path, monkeypatch):
    """onefile builds and older layouts still resolve."""
    monkeypatch.setattr(ocr.sys, "frozen", True, raising=False)
    monkeypatch.delattr(ocr.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(ocr.sys, "executable", str(tmp_path / "app.exe"))

    assert ocr.bundle_root() == tmp_path


def test_tesseract_installed_beside_the_exe_is_found(tmp_path, monkeypatch):
    """The installer lays Tesseract down next to the app rather than routing it
    through PyInstaller, which otherwise duplicates 130 MB of DLLs into
    _internal as well as vendor/."""
    exe_dir = tmp_path / "app"
    vendor = exe_dir / "vendor" / "tesseract"
    vendor.mkdir(parents=True)
    (vendor / "tesseract.exe").write_bytes(b"")
    monkeypatch.setattr(ocr.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ocr.sys, "executable", str(exe_dir / "SREBookBuilder.exe"))
    monkeypatch.setattr(ocr.sys, "_MEIPASS", str(exe_dir / "_internal"), raising=False)

    assert ocr.bundled_tesseract() == vendor / "tesseract.exe"


def test_tesseract_inside_the_pyinstaller_bundle_is_still_found(tmp_path, monkeypatch):
    """Either layout works, so the resolver does not care how it was packaged."""
    exe_dir = tmp_path / "app"
    internal = exe_dir / "_internal"
    vendor = internal / "vendor" / "tesseract"
    vendor.mkdir(parents=True)
    (vendor / "tesseract.exe").write_bytes(b"")
    monkeypatch.setattr(ocr.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ocr.sys, "executable", str(exe_dir / "SREBookBuilder.exe"))
    monkeypatch.setattr(ocr.sys, "_MEIPASS", str(internal), raising=False)

    assert ocr.bundled_tesseract() == vendor / "tesseract.exe"
