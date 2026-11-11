import pytest

from briefkit.common.envelope import Envelope


def test_envelope_serializes_all_four_fields():
    env = Envelope(data={"bars": []}, source="yahoo", as_of="2026-11-10")
    assert env.to_dict() == {
        "data": {"bars": []},
        "source": "yahoo",
        "as_of": "2026-11-10",
        "warnings": [],
    }


def test_envelope_keeps_warnings():
    env = Envelope(data=1, source="s", as_of="2026-11-10", warnings=["short history"])
    assert env.to_dict()["warnings"] == ["short history"]


@pytest.mark.parametrize("as_of", [None, ""])
def test_envelope_rejects_missing_as_of(as_of):
    with pytest.raises(ValueError, match="as_of"):
        Envelope(data=1, source="s", as_of=as_of)


def test_envelope_rejects_missing_source():
    with pytest.raises(ValueError, match="source"):
        Envelope(data=1, source="", as_of="2026-11-10")
