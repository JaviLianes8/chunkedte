"""The complete 1.0.0 promise of every public name: signature, result and failure types."""

from __future__ import annotations

import array
import dataclasses
import inspect
import pickle
from collections.abc import Callable
from typing import Any

import pytest

import chunkedte
from chunkedte import ChunkedError, Decoder, Encoder, LimitError, Limits, decode, encode, is_chunked

BYTES = "'bytes | bytearray | memoryview'"
SIGNATURES = {
    "decode": f"(data: {BYTES}, *, limits: 'Limits | None' = None) -> 'bytes'",
    "encode": f"(data: {BYTES}, *, chunk_size: 'int' = 8192, "
    "trailers: 'Trailers | None' = None) -> 'bytes'",
    "is_chunked": "(transfer_encoding: 'str | None', content_length: 'str | None' = None, "
    "*, request: 'bool' = True) -> 'bool'",
    "Decoder": "(limits: 'Limits | None' = None) -> 'None'",
    "Encoder": "() -> 'None'",
}
METHODS = {
    (Decoder, "feed"): f"(self, data: {BYTES}) -> 'list[bytes]'",
    (Encoder, "write"): f"(self, data: {BYTES}) -> 'bytes'",
    (Encoder, "finish"): "(self, trailers: 'Trailers | None' = None) -> 'bytes'",
}
LIMITS = [
    ("max_line_size", 4096),
    ("max_extensions_size", 16384),
    ("max_chunk_size", 2**63 - 1),
    ("max_body_size", None),
    ("max_trailer_size", 16384),
]


@pytest.mark.parametrize("name", sorted(SIGNATURES))
def test_signatures_are_pinned(name: str) -> None:
    assert str(inspect.signature(getattr(chunkedte, name))) == SIGNATURES[name]


@pytest.mark.parametrize(("owner", "name"), sorted(METHODS, key=str))
def test_method_signatures_are_pinned(owner: type, name: str) -> None:
    assert str(inspect.signature(getattr(owner, name))) == METHODS[(owner, name)]


def test_limits_is_a_frozen_dataclass_with_pinned_fields_that_pickles() -> None:
    assert [(f.name, f.default) for f in dataclasses.fields(Limits)] == LIMITS
    limits = Limits(max_body_size=5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        limits.max_body_size = 6  # type: ignore[misc]
    assert pickle.loads(pickle.dumps(limits)) == limits
    assert hash(limits) == hash(Limits(max_body_size=5))


def test_functions_and_methods_report_the_package_and_pickles_name_only_it() -> None:
    for function in (decode, encode, is_chunked, Decoder.feed, Encoder.write, Encoder.finish):
        assert function.__module__ == "chunkedte", function
    error = pickle.loads(pickle.dumps(LimitError("body exceeds max_body_size")))
    assert (type(error), str(error)) == (LimitError, "body exceeds max_body_size")
    assert b"chunkedte._" not in pickle.dumps(ChunkedError("x")) + pickle.dumps(Limits())


def test_every_public_name_method_and_property_has_an_example() -> None:
    members = [getattr(chunkedte, name) for name in chunkedte.__all__]
    members += [Decoder.feed, Decoder.is_complete, Decoder.trailers, Decoder.unused_data]
    members += [Encoder.write, Encoder.finish]
    for member in members:
        assert ">>> " in (inspect.getdoc(member) or ""), member


@pytest.mark.parametrize("data", ["text", 5, None, array.array("B", b"0"), [48]])
def test_only_bytes_like_data_is_accepted(data: object) -> None:
    calls: list[Callable[[Any], object]] = [decode, encode, Decoder().feed, Encoder().write]
    for call in calls:
        with pytest.raises(TypeError, match="expected a bytes-like object"):
            call(data)


def test_bytes_bytearray_and_memoryview_are_all_accepted() -> None:
    message = b"1\r\na\r\n0\r\n\r\n"
    for kind in (bytes, bytearray, memoryview):
        assert decode(kind(message)) == b"a"
        assert Decoder().feed(kind(message)) == [b"a"]
        assert encode(kind(b"a")) == message
        assert Encoder().write(kind(b"a")) == b"1\r\na\r\n"


@pytest.mark.parametrize("limits", [5, {}, "Limits()", dataclasses.replace])
def test_decoder_refuses_anything_but_limits(limits: object) -> None:
    with pytest.raises(TypeError, match="limits must be a Limits"):
        Decoder(limits)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="limits must be a Limits"):
        decode(b"0\r\n\r\n", limits=limits)  # type: ignore[arg-type]


@pytest.mark.parametrize(("te", "cl"), [(b"chunked", None), ("chunked", 5), (5, None), (None, 5)])
def test_is_chunked_refuses_field_values_that_are_not_str(te: object, cl: object) -> None:
    with pytest.raises(TypeError, match="field values must be str or None"):
        is_chunked(te, cl)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "trailers",
    [["ab"], [("a", "b", "c")], [("a",)], [5], "ab", b"ab", "", b"", bytearray(), memoryview(b"")],
)
def test_trailers_must_be_a_mapping_or_pairs(trailers: object) -> None:
    with pytest.raises(TypeError, match="mapping or"):
        encode(b"", trailers=trailers)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="mapping or"):
        Encoder().finish(trailers)  # type: ignore[arg-type]


def test_trailer_pairs_may_be_tuples_lists_or_a_generator_and_keep_their_order() -> None:
    expected = b"0\r\nB: 2\r\nA: 1\r\n\r\n"
    # Lists are accepted at run time although the annotation only names tuples.
    assert encode(b"", trailers=[["B", "2"], ("A", "1")]) == expected  # type: ignore[list-item]
    assert encode(b"", trailers=(pair for pair in [("B", "2"), ("A", "1")])) == expected
    assert encode(b"", trailers={"B": "2", "A": "1"}) == expected


def test_a_refused_trailer_leaves_the_encoder_open() -> None:
    encoder = Encoder()
    with pytest.raises(ChunkedError, match="cannot be sent as a trailer"):
        encoder.finish({"Content-Length": "5"})
    assert encoder.write(b"a") == b"1\r\na\r\n"
    assert encoder.finish() == b"0\r\n\r\n"
    with pytest.raises(ChunkedError, match="finish called twice"):
        encoder.finish()
    with pytest.raises(ChunkedError, match="write after finish"):
        encoder.write(b"a")


def test_the_package_top_holds_only_the_public_names() -> None:
    public = sorted(name for name in dir(chunkedte) if not name.startswith("_"))
    assert public == sorted(chunkedte.__all__)
