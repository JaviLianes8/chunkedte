"""The decoder against two independent Python readings run live: h11 and http.client.

h11 is the sans-I/O HTTP/1.1 library behind httpcore and httpx; http.client is the
standard library client. Both are more lenient than RFC 9112, so they serve as oracles for
what a valid message means and for the reading of the bytes both sides accept.
"""

from __future__ import annotations

import io
import random
import re
from http.client import HTTPResponse
from typing import Any

import pytest
from generators import SEEDS, Reading, mutate, reading, valid_message
from reference import Rejected, parse

HEAD = b"POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\n"


def _h11(h11: Any, case: bytes) -> Reading | None:
    connection = h11.Connection(h11.SERVER)
    connection.receive_data(HEAD + case)
    body = b""
    try:
        while True:
            event = connection.next_event()
            if isinstance(event, h11.Data):
                body += event.data
            elif isinstance(event, h11.EndOfMessage):
                trailers = [(n.decode(), v.decode("latin-1")) for n, v in event.headers.raw_items()]
                return body, trailers, len(case) - len(connection.trailing_data[0])
            elif event is h11.NEED_DATA or event is h11.PAUSED:
                return None
    except h11.RemoteProtocolError:
        return None


class _Socket:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def makefile(self, mode: str) -> io.BufferedReader:
        return io.BufferedReader(io.BytesIO(self._data))


def _http_client(case: bytes) -> bytes:
    head = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
    response = HTTPResponse(_Socket(head + case))  # type: ignore[arg-type]
    response.begin()
    return response.read()


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_h11_reads_every_message_both_accept_the_same_way(seed: int) -> None:
    h11 = pytest.importorskip("h11")
    rng = random.Random(seed)
    pool = [*SEEDS, *(valid_message(rng) for _ in range(20))]
    seen = {"both": 0, "neither": 0, "bws": 0, "lenient": 0}
    for _ in range(8000):
        case = mutate(rng, rng.choice(pool))
        ours, theirs = reading(case), _h11(h11, case)
        if ours is not None and theirs is not None:
            assert ours == theirs, case
            seen["both"] += 1
        elif ours is None and theirs is None:
            seen["neither"] += 1
        elif ours is not None:
            # h11 refuses BWS between the size and ";", which RFC 9112 allows.
            assert re.search(rb"(?:^|\r\n)[0-9A-Fa-f]+[ \t]+;", case), case
            seen["bws"] += 1
        else:
            # h11 is lenient (unchecked extensions, bare LF, obs-fold): the hand-written
            # reading of the RFC grammar refuses these messages as well.
            with pytest.raises(Rejected):
                parse(case)
            seen["lenient"] += 1
    assert min(seen.values()) > 5, seen


def test_h11_and_this_decoder_agree_on_valid_messages_without_bws() -> None:
    h11 = pytest.importorskip("h11")
    rng = random.Random(7230)
    for _ in range(3000):
        case = valid_message(rng)
        ours = reading(case)
        assert ours is not None and ours == _h11(h11, case), case


def test_http_client_reads_the_same_body_from_valid_messages() -> None:
    rng = random.Random(2616)
    for _ in range(3000):
        case = valid_message(rng)
        ours = reading(case)
        assert ours is not None
        assert _http_client(case) == ours[0], case
