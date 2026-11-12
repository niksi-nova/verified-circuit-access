import pytest

from vca.outputs.braille import available, translate

pytestmark = pytest.mark.skipif(not available(), reason="Liblouis is unavailable")


def test_ueb_grade_one_letters_and_numbers():
    result = translate("abc 12")
    assert result["pages"][0].splitlines()[1] == "⠁⠃⠉⠀⠼⠁⠃"
    assert result["brf"].splitlines()[1] == "ABC #AB"


def test_word_wraps_at_40_cells():
    result = translate("a" * 39 + " bb")
    assert result["brf"].splitlines()[1:] == ["A" * 39, "BB"]


def test_header_counts_towards_25_lines_per_page():
    result = translate("\n".join(["a"] * 25))
    assert [len(page.splitlines()) for page in result["pages"]] == [25, 2]
    assert result["brf"].count("\f") == 1
    assert result["pages"][0].splitlines()[0] == result["pages"][1].splitlines()[0]
