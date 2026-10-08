"""Literal published behavior and generated invariants for deterministic text."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pdf2mp3 import clean_text, normalize_lang, sanitize_for_tts, split_into_chunks
from pdf2mp3.pdf2mp3 import preview


@pytest.mark.parametrize(
    "value",
    [None, "", "pt", "pt-br", "ptbr", "pt_br", "portuguese", "português", "portugues", " PT-BR "],
)
def test_portuguese_aliases(value):
    assert normalize_lang(value) == "pt-br"


@pytest.mark.parametrize("value", ["en", "en-us", "english", " EN-US "])
def test_english_aliases(value):
    assert normalize_lang(value) == "en"


@pytest.mark.parametrize("value", ["fr", "pt-pt", "de", "   "])
def test_unsupported_language_is_rejected(value):
    with pytest.raises(ValueError, match="Invalid language"):
        normalize_lang(value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        (" \t\r\n ", ""),
        ("multi-\nline\r text", "multiline text"),
        ("hello\nworld", "hello world"),
        ("  hello  \tworld\n\n\nnext", "hello world\n\nnext"),
        ("First.\nSecond", "First.\nSecond"),
        ("First!\nSecond", "First!\nSecond"),
        ("First?\nSecond", "First?\nSecond"),
        ("First…\nSecond", "First…\nSecond"),
        ("First:\nSecond", "First:\nSecond"),
        ("First;\nSecond", "First;\nSecond"),
        ("First)\nSecond", "First)\nSecond"),
        ("First”\nSecond", "First”\nSecond"),
        ("one\n\n\ntwo", "one\n\ntwo"),
    ],
)
def test_cleaning_characterization(raw, expected):
    assert clean_text(raw) == expected


def test_repeated_short_headers_are_removed_at_five():
    assert clean_text("Heading.\n\n" * 5 + "Body sentence.") == "Body sentence."
    assert clean_text("Heading.\n\n" * 4 + "Body sentence.").count("Heading.") == 4
    six = "One two three four five six."
    seven = "One two three four five six seven."
    assert clean_text((six + "\n\n") * 5) == ""
    assert clean_text((seven + "\n\n") * 5).count(seven) == 5


@pytest.mark.parametrize(
    ("text", "size", "expected"),
    [
        ("", 10, []),
        (" \n\t", 10, []),
        ("abcdefgh", 3, ["abc", "def", "gh"]),
        ("one. two.", 9, ["one. two."]),
        ("one. two.", 8, ["one.", "two."]),
        ("one. abcdefghi", 5, ["one.", "abcde", "fghi"]),
        ("one. two. three.", 10, ["one. two.", "three."]),
        ("one\n\ntwo", 20, ["one \n\n two"]),
        ("abc   def", 3, ["abc", "def"]),
        ("á😀文", 1, ["á", "😀", "文"]),
    ],
)
def test_chunk_characterization(text, size, expected):
    assert split_into_chunks(text, size) == expected


def test_literal_paragraph_marker_is_not_lost():
    assert split_into_chunks("Use <PARA_BREAK> literally.", 100) == ["Use <PARA_BREAK> literally."]


@pytest.mark.parametrize("size", [0, -3])
def test_chunk_api_rejects_nonpositive_limits(size):
    with pytest.raises(ValueError, match="positive"):
        split_into_chunks("synthetic", size)


@settings(derandomize=True)
@given(
    st.text(alphabet="abcXYZé漢😀.!? \n\t", max_size=400), st.integers(min_value=1, max_value=100)
)
def test_chunks_preserve_nonwhitespace_content_and_size(text, size):
    chunks = split_into_chunks(text, size)
    assert all(chunk and len(chunk) <= size for chunk in chunks)
    assert "".join("".join(chunks).split()) == "".join(text.split())


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("“Olá” & hi’\u00a0a\u200bb", '"Olá"  and  hi\' ab'),
        ("<tag> intact", "<tag> intact"),
        ("a&&b", "a and  and b"),
    ],
)
def test_sanitation_characterization(raw, expected):
    assert sanitize_for_tts(raw) == expected


@pytest.mark.parametrize(
    ("text", "size", "expected"),
    [
        ("short", 10, "short"),
        ("abcdef", 3, "abc…"),
        ("abc", 3, "abc…"),
        ("a\nb", 4, "a b"),
        ("", 3, ""),
    ],
)
def test_preview_characterization(text, size, expected):
    assert preview(text, size) == expected


def test_sentences_on_one_line_remain_on_one_line():
    assert clean_text("One. Two. Three.") == "One. Two. Three."


def test_long_sentence_can_be_followed_by_another_chunk():
    assert split_into_chunks("abcdefg. h.", 5) == ["abcde", "fg.", "h."]
