"""`srebook doctor` -- what the clean-machine test actually asserts against.

Without it, a packaged build that borrowed Tesseract from the host looks exactly
like one that shipped its own.
"""
import pytest

from srebook import cli
from srebook.core import ocr


def test_doctor_reports_which_tesseract_it_resolved(capsys, tmp_path, monkeypatch):
    vendor = tmp_path / "vendor" / "tesseract"
    (vendor / "tessdata").mkdir(parents=True)
    (vendor / "tesseract.exe").write_bytes(b"")
    (vendor / "tessdata" / "eng.traineddata").write_bytes(b"")
    monkeypatch.setattr(ocr, "bundle_candidates", lambda bundle=None: [tmp_path])

    code = cli.main(["doctor"])

    out = capsys.readouterr().out
    assert code == 0
    assert "bundled" in out
    assert str(vendor / "tesseract.exe") in out


def test_doctor_fails_when_tesseract_is_missing(capsys, monkeypatch):
    """A packaged build with no Tesseract must fail the check loudly, which is
    the whole point of running this in a pristine Windows."""
    monkeypatch.setattr(ocr, "find_tesseract", lambda **_kw: None)
    monkeypatch.setattr(ocr, "tesseract_source", lambda **_kw: "not found")

    code = cli.main(["doctor"])

    assert code != 0
    assert "not found" in (capsys.readouterr().out + capsys.readouterr().err).lower()


def test_doctor_says_whether_it_is_running_packaged_or_from_source(capsys):
    cli.main(["doctor"])

    assert "source" in capsys.readouterr().out.lower()


def test_doctor_reports_the_pdf_and_image_libraries(capsys):
    """If PyInstaller drops pikepdf or PIL, the app fails at build time on a
    real issue. Better to find out from a one-second check."""
    cli.main(["doctor"])

    out = capsys.readouterr().out
    assert "pikepdf" in out
    assert "Pillow" in out


def test_doctor_reports_available_languages(capsys, tmp_path, monkeypatch):
    vendor = tmp_path / "vendor" / "tesseract"
    (vendor / "tessdata").mkdir(parents=True)
    (vendor / "tesseract.exe").write_bytes(b"")
    (vendor / "tessdata" / "eng.traineddata").write_bytes(b"")
    monkeypatch.setattr(ocr, "bundle_candidates", lambda bundle=None: [tmp_path])

    cli.main(["doctor"])

    assert "eng" in capsys.readouterr().out
