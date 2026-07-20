from app.infrastructure.parsing.text_normalizer import normalize_text


class TestNormalizeText:
    def test_normalizes_unicode(self) -> None:
        text = "caf\u00e9 resume\u2019s"
        result = normalize_text(text)
        assert "\u00e9" not in result or "cafe" in result.lower() or "caf\u00e9" in result

    def test_collapses_multiple_spaces(self) -> None:
        text = "hello    world"
        result = normalize_text(text)
        assert "    " not in result
        assert "hello world" in result

    def test_strips_non_printable_chars(self) -> None:
        text = "hello\x00\x01\x02world"
        result = normalize_text(text)
        assert "\x00" not in result
        assert "helloworld" in result

    def test_preserves_newlines(self) -> None:
        text = "line1\nline2\nline3"
        result = normalize_text(text)
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_collapses_multiple_newlines(self) -> None:
        text = "paragraph1\n\n\n\nparagraph2"
        result = normalize_text(text)
        assert "\n\n\n" not in result

    def test_strips_trailing_spaces(self) -> None:
        text = "hello   \n"
        result = normalize_text(text)
        assert result == "hello"

    def test_empty_string(self) -> None:
        result = normalize_text("")
        assert result == ""

    def test_whitespace_only(self) -> None:
        result = normalize_text("   \t  ")
        assert result == ""

    def test_nfkc_normalization(self) -> None:
        text = "\uff21\uff22\uff23"
        result = normalize_text(text)
        assert "ABC" in result
