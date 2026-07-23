"""Tests for workspace invite code generation and normalisation."""

import re

from backend.app.controllers.workspaces import (
    generate_invite_code,
    normalize_invite_code,
)

_FORMAT = re.compile(r"^BOLO-[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$")


def test_generated_code_matches_format():
    for _ in range(50):
        assert _FORMAT.match(generate_invite_code())


def test_generated_code_is_short():
    assert len(generate_invite_code()) == 14


def test_ambiguous_letters_are_excluded():
    # I/L/O/U are omitted from the random body so a code survives being read
    # aloud or hand-copied. (The fixed BOLO prefix is exempt — it's a word.)
    bodies = "".join(generate_invite_code()[5:] for _ in range(200))
    assert not set("ILOU") & set(bodies)


def test_codes_are_unique_enough():
    assert len({generate_invite_code() for _ in range(200)}) == 200


def test_normalize_is_case_insensitive():
    assert normalize_invite_code("bolo-k7m2-9xq4") == "BOLO-K7M2-9XQ4"


def test_normalize_strips_whitespace_and_regroups():
    assert normalize_invite_code("  BOLOK7M29XQ4 ") == "BOLO-K7M2-9XQ4"
    assert normalize_invite_code("BOLO K7M2 9XQ4") == "BOLO-K7M2-9XQ4"
    assert normalize_invite_code("BOLO--K7M2--9XQ4\n") == "BOLO-K7M2-9XQ4"


def test_normalize_round_trips_a_generated_code():
    code = generate_invite_code()
    assert normalize_invite_code(code.lower()) == code


def test_legacy_uuid_token_is_left_alone():
    # Pre-existing invites hold lowercase UUIDs, where hyphens are significant.
    uuid_token = "a0000000-0000-4000-8000-000000000000"
    assert normalize_invite_code(uuid_token) == uuid_token
    assert normalize_invite_code(f"  {uuid_token}  ") == uuid_token


def test_normalize_handles_empty_input():
    assert normalize_invite_code("") == ""
    assert normalize_invite_code(None) == ""
