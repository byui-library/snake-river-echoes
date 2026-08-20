from pathlib import Path

import pytest

from srebook.core import ingest


def make_tifs(tmp_path: Path, names):
    for n in names:
        (tmp_path / n).write_bytes(b"")
    return tmp_path


def test_sheets_are_ordered_naturally_not_lexically(tmp_path):
    """_2 must precede _10. Lexical sort is the classic scan-ordering bug."""
    folder = make_tifs(tmp_path, ["p_1.tif", "p_2.tif", "p_10.tif", "p_11.tif"])

    assert [p.name for p in ingest.find_sheets(folder)] == [
        "p_1.tif", "p_2.tif", "p_10.tif", "p_11.tif",
    ]


def test_finds_tif_and_tiff_case_insensitively(tmp_path):
    folder = make_tifs(tmp_path, ["a_1.tif", "b_2.TIF", "c_3.tiff", "d_4.TIFF"])

    assert len(ingest.find_sheets(folder)) == 4


def test_ignores_non_tiff_files(tmp_path):
    folder = make_tifs(tmp_path, ["a_1.tif", "notes.txt", "thumb.jpg"])

    assert [p.name for p in ingest.find_sheets(folder)] == ["a_1.tif"]


def test_folder_with_no_tiffs_returns_empty(tmp_path):
    assert ingest.find_sheets(make_tifs(tmp_path, ["readme.md"])) == []


def test_missing_folder_raises_a_readable_error(tmp_path):
    with pytest.raises(ingest.IngestError) as e:
        ingest.find_sheets(tmp_path / "nope")

    assert "does not exist" in str(e.value)


def test_metadata_guessed_from_sre_filenames(tmp_path):
    folder = make_tifs(tmp_path, ["SRE_1971_Vol1_No1_01.tif", "SRE_1971_Vol1_No1_02.tif"])

    meta = ingest.guess_metadata(ingest.find_sheets(folder))

    assert (meta.year, meta.volume, meta.issue) == (1971, 1, 1)


def test_metadata_guess_handles_multi_digit_volume_and_issue(tmp_path):
    folder = make_tifs(tmp_path, ["SRE_1984_Vol14_No23_01.tif"])

    meta = ingest.guess_metadata(ingest.find_sheets(folder))

    assert (meta.year, meta.volume, meta.issue) == (1984, 14, 23)


def test_metadata_guess_leaves_fields_none_when_names_do_not_match(tmp_path):
    """Other archives will not use this naming convention. Guess nothing rather
    than guess wrong -- the operator fills it in."""
    folder = make_tifs(tmp_path, ["scan001.tif", "scan002.tif"])

    meta = ingest.guess_metadata(ingest.find_sheets(folder))

    assert (meta.year, meta.volume, meta.issue) == (None, None, None)


def test_metadata_guess_ignores_a_year_like_number_in_a_page_position(tmp_path):
    """A bare 4-digit run is only a year if it is a plausible one."""
    folder = make_tifs(tmp_path, ["img_9999_01.tif"])

    meta = ingest.guess_metadata(ingest.find_sheets(folder))

    assert meta.year is None
