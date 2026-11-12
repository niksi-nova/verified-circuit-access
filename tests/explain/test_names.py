"""Test-only: plain-name mapping."""

from vca.explain.names import plain_name


def test_known_category_gets_plain_name():
    assert plain_name("nmos") == "N-channel transistor"
    assert plain_name("resistor") == "resistor"


def test_unknown_category_falls_back_to_raw_sentence():
    assert plain_name("made-up-thing") == "component of type made-up-thing"
