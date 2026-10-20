"""Differential fuzz: the decoder against an independent reading of the grammar."""

from __future__ import annotations

import itertools
import random

import pytest
from generators import SEEDS, mutate
from reference import Rejected, Result, parse

from chunkedte import ChunkedError, Decoder, encode


def _decoder_result(message: bytes, cuts: list[int]) -> Result | None:
    decoder = Decoder()
    pieces: list[bytes] = []
    bounds = [0, *sorted(cuts), len(message)]
    try:
        for start, end in itertools.pairwise(bounds):
            pieces.extend(decoder.feed(message[start:end]))
    except ChunkedError:
        return None
    if not decoder.is_complete:
        return None
    return b"".join(pieces), decoder.trailers, decoder.unused_data


def _reference_result(message: bytes) -> Result | None:
    try:
        return parse(message)
    except Rejected:
        return None


def _cases(count: int) -> list[bytes]:
    rng = random.Random(9112)
    return [mutate(rng, rng.choice(SEEDS)) for _ in range(count)]


def test_every_seed_is_valid_for_both_readings() -> None:
    for seed in SEEDS:
        assert _reference_result(seed) is not None, seed
        assert _decoder_result(seed, []) == _reference_result(seed), seed


@pytest.mark.parametrize("block", range(8))
def test_mutated_messages_get_the_same_verdict(block: int) -> None:
    cases = _cases(8 * 500)[block * 500 : (block + 1) * 500]
    rng = random.Random(block)
    accepted = 0
    for message in cases:
        expected = _reference_result(message)
        cuts = [rng.randint(0, len(message)) for _ in range(rng.randint(0, 4))]
        assert _decoder_result(message, cuts) == expected, message
        accepted += expected is not None
    # The corpus must exercise both sides, or the comparison proves little.
    assert 0 < accepted < len(cases)


def test_every_split_point_gives_the_same_result() -> None:
    message = SEEDS[1] + b"rest"
    expected = _reference_result(message)
    for first in range(len(message) + 1):
        for second in range(first, len(message) + 1, 5):
            assert _decoder_result(message, [first, second]) == expected


def test_random_bodies_round_trip_through_encode_and_both_readings() -> None:
    rng = random.Random(7230)
    for _ in range(200):
        body = rng.randbytes(rng.randint(0, 300))
        message = encode(body, chunk_size=rng.randint(1, 64), trailers={"T": "v"})
        expected = (body, [("T", "v")], b"")
        assert _reference_result(message) == expected
        assert _decoder_result(message, [rng.randint(0, len(message))]) == expected
