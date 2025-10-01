"""
Unit tests for language normalization in pdf2mp3.

These tests validate the behavior of normalize_lang:
- Correct normalization of English and Portuguese inputs.
- Proper handling of unsupported languages.
"""

import pytest
from pdf2mp3 import normalize_lang


def test_normalize_lang_valid_en():
    """
    Ensure that English inputs are normalized to 'en'.
    """
    assert normalize_lang("en") == "en"
    assert normalize_lang("english") == "en"
    assert normalize_lang("EN-US") == "en"


def test_normalize_lang_valid_pt():
    """
    Ensure that Portuguese inputs are normalized to 'pt-br'.
    """
    assert normalize_lang("pt") == "pt-br"
    assert normalize_lang("português") == "pt-br"
    assert normalize_lang("PT-BR") == "pt-br"


def test_normalize_lang_invalid():
    """
    Ensure that unsupported language codes raise ValueError.
    """
    with pytest.raises(ValueError):
        normalize_lang("fr")
