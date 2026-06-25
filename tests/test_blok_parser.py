import pytest

from rekuest_next.blok.parser import jsx


def test_jsx_parser_reports_line_column_and_source_context() -> None:
    malformed = "<Page>\n  <Header />\n  <Label>\n</Page>\n<Footer />"

    with pytest.raises(ValueError) as exc_info:
        jsx(malformed)

    message = str(exc_info.value)

    assert "Failed to parse JSX/XML at line 4, column" in message
    assert "mismatched tag" in message
    assert "2 |   <Header />" in message
    assert "3 |   <Label>" in message
    assert "4 | </Page>" in message
    assert "5 | <Footer />" in message
    assert "^" in message


def test_jsx_parser_reports_eof_with_previous_context() -> None:
    malformed = "<Page>\n  <Label>\n        "

    with pytest.raises(ValueError) as exc_info:
        jsx(malformed)

    message = str(exc_info.value)

    assert "unexpected end of input (no element found)" in message
    assert "2 |   <Label>" in message
    assert "3 |         <end of input>" in message
    assert "^" in message
