import pytest

from rekuest_next.blok.parser import jsx
from rekuest_next.blok.validate import validate_blok


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


# --- structural ids -------------------------------------------------------


def test_node_ids_are_structural_and_stable() -> None:
    source = "<Card><CardContent><Button /><Button /></CardContent></Card>"

    assert jsx(source) == jsx(source)

    card = jsx(source)
    content = card.children[0]
    assert card.id == "Card"
    assert content.id == "Card/CardContent[0]"
    assert [child.id for child in content.children] == [
        "Card/CardContent[0]/Button[0]",
        "Card/CardContent[0]/Button[1]",
    ]


def test_explicit_id_wins_and_roots_its_children() -> None:
    card = jsx('<Card id="ot2-monitor"><Button /></Card>')

    assert card.id == "ot2-monitor"
    assert card.children[0].id == "ot2-monitor/Button[0]"
    assert not any(prop.key == "id" for prop in card.props or ())


# --- inner text -----------------------------------------------------------


def test_inner_text_is_rejected_rather_than_dropped() -> None:
    with pytest.raises(ValueError) as exc_info:
        jsx('<Badge className="x">Opentrons is getting hot!</Badge>')

    message = str(exc_info.value)
    assert "Text content is not rendered in <Badge>" in message
    assert "Opentrons is getting hot!" in message


def test_text_trailing_a_child_is_rejected() -> None:
    with pytest.raises(ValueError, match="Text content is not rendered"):
        jsx("<Card><Button />trailing</Card>")


def test_whitespace_between_children_is_allowed() -> None:
    assert jsx("<Card>\n  <Button />\n</Card>").children is not None


# --- "#" declarations -----------------------------------------------------


def test_hash_prop_is_a_plain_static_value_outside_foreach() -> None:
    prop = jsx('<Page color="#fff" />').props[0]

    assert prop.static_value == "#fff"
    assert prop.declares_value is None


def test_hash_prop_outside_foreach_declares_no_local() -> None:
    # A stray "#" used to declare a local that suppressed the unknown-reference
    # error for that name anywhere in the subtree.
    component = jsx('<Page color="#fff"><Text text="@fff" /></Page>')

    with pytest.raises(ValueError, match="Unknown non-static reference 'fff'"):
        validate_blok(component, [])


def test_foreach_let_declares_the_loop_variable() -> None:
    let_prop = next(
        prop
        for prop in jsx('<foreach items="@dep.state.xs" let="#item" />').props
        if prop.key == "let"
    )

    assert let_prop.declares_value == "item"
    assert let_prop.static_value == "item"


def test_foreach_let_must_be_a_hash_identifier() -> None:
    with pytest.raises(ValueError, match="must declare a loop variable"):
        jsx('<foreach items="@dep.state.xs" let="item" />')


def test_foreach_without_items_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing required prop"):
        validate_blok(jsx('<foreach let="#item" />'), [])


# --- validation error locations -------------------------------------------


def test_validation_error_names_the_component_and_its_id() -> None:
    component = jsx('<Card><Row><Text text="@nope.state.x" /></Row></Card>')

    with pytest.raises(ValueError) as exc_info:
        validate_blok(component, [])

    assert "prop 'text' of <Text> (Card/Row[0]/Text[0])" in str(exc_info.value)
