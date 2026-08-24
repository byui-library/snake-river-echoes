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


def make_multipage(path, pages=5):
    from PIL import Image
    frames = [Image.new("L", (60, 80), 255 - i * 10) for i in range(pages)]
    frames[0].save(path, save_all=True, append_images=frames[1:], compression="tiff_lzw")
    return path


def test_a_multipage_tiff_is_refused_rather_than_silently_truncated(tmp_path):
    """One TIFF holding a whole issue read as a single sheet, and the other 21
    pages vanished with no warning. Losing pages quietly is the worst thing this
    program could do."""
    make_multipage(tmp_path / "whole_issue.tif", pages=22)

    with pytest.raises(ingest.IngestError) as e:
        ingest.find_sheets(tmp_path)

    message = str(e.value)
    assert "whole_issue.tif" in message
    assert "22" in message


def test_the_refusal_says_what_to_do_about_it(tmp_path):
    make_multipage(tmp_path / "issue.tif", pages=4)

    with pytest.raises(ingest.IngestError) as e:
        ingest.find_sheets(tmp_path)

    assert "one page per file" in str(e.value).lower()


def test_ordinary_single_page_scans_are_unaffected(tmp_path):
    from PIL import Image
    for n in range(1, 4):
        Image.new("L", (60, 80), 255).save(tmp_path / f"p_{n:02d}.tif")

    assert len(ingest.find_sheets(tmp_path)) == 3


def test_a_file_that_cannot_be_opened_does_not_stop_the_check(tmp_path):
    """A corrupt file is prepare's problem to report, not ingest's."""
    (tmp_path / "broken.tif").write_bytes(b"not a tiff at all")

    assert [p.name for p in ingest.find_sheets(tmp_path)] == ["broken.tif"]


def test_apple_double_metadata_files_are_not_sheets(tmp_path):
    """A Mac writing to a network share leaves a "._name" file beside every
    real one. They are resource forks, not images, and the operator saw
    "43 sheets found" for a 21-page issue followed by a read error."""
    from PIL import Image
    for n in range(1, 4):
        Image.new("L", (60, 80), 255).save(tmp_path / f"SRE_Vol4_No1_{n:02d}.TIF")
        (tmp_path / f"._SRE_Vol4_No1_{n:02d}.TIF").write_bytes(b"\x00\x05\x16\x07AppleDouble")

    sheets = ingest.find_sheets(tmp_path)

    assert [p.name for p in sheets] == ["SRE_Vol4_No1_01.TIF", "SRE_Vol4_No1_02.TIF",
                                        "SRE_Vol4_No1_03.TIF"]


def test_other_hidden_files_are_ignored_too(tmp_path):
    from PIL import Image
    Image.new("L", (60, 80), 255).save(tmp_path / "page_01.tif")
    (tmp_path / ".hidden.tif").write_bytes(b"")

    assert [p.name for p in ingest.find_sheets(tmp_path)] == ["page_01.tif"]


def test_a_file_genuinely_named_with_an_underscore_is_kept(tmp_path):
    """Only the "._" prefix is AppleDouble. A leading underscore is not."""
    from PIL import Image
    Image.new("L", (60, 80), 255).save(tmp_path / "_draft_01.tif")

    assert [p.name for p in ingest.find_sheets(tmp_path)] == ["_draft_01.tif"]


def test_apple_double_files_do_not_trip_the_multipage_check(tmp_path):
    """They cannot be opened as images, and must not be mistaken for a problem
    with the scans themselves."""
    from PIL import Image
    Image.new("L", (60, 80), 255).save(tmp_path / "p_01.tif")
    (tmp_path / "._p_01.tif").write_bytes(b"\x00\x05\x16\x07not an image")

    assert len(ingest.find_sheets(tmp_path)) == 1


def test_volume_and_issue_are_read_even_without_a_year(tmp_path):
    """Volume 4's scans are named SRE_Vol4_No1_01.TIF, with no year in the
    name. The operator saw Volume, Issue and Year all blank, when two of the
    three were sitting in the file name."""
    folder = make_tifs(tmp_path, ["SRE_Vol4_No1_01.TIF", "SRE_Vol4_No1_02.TIF"])

    meta = ingest.guess_metadata(ingest.find_sheets(folder))

    assert (meta.volume, meta.issue) == (4, 1)
    assert meta.year is None


def test_a_year_is_still_read_when_it_is_there(tmp_path):
    folder = make_tifs(tmp_path, ["SRE_1971_Vol1_No2_01.tif"])

    meta = ingest.guess_metadata(ingest.find_sheets(folder))

    assert (meta.year, meta.volume, meta.issue) == (1971, 1, 2)


def test_a_year_after_the_issue_number_is_read(tmp_path):
    folder = make_tifs(tmp_path, ["SRE_Vol2_No3_1973_01.tif"])

    meta = ingest.guess_metadata(ingest.find_sheets(folder))

    assert (meta.year, meta.volume, meta.issue) == (1973, 2, 3)
