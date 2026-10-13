import importlib.resources

import chunkedte

# The public API. Add every exported name here as the library grows; this list is the
# contract and the test below fails if the module and this list disagree.
PUBLIC_API: list[str] = [
    "ChunkedError",
    "Decoder",
    "Encoder",
    "LimitError",
    "Limits",
    "decode",
    "encode",
    "is_chunked",
]


def test_all_lists_exactly_the_public_api() -> None:
    assert sorted(chunkedte.__all__) == sorted(PUBLIC_API)


def test_every_exported_name_resolves() -> None:
    for name in chunkedte.__all__:
        assert hasattr(chunkedte, name)


def test_version_is_a_three_part_string() -> None:
    parts = chunkedte.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_the_package_ships_type_information() -> None:
    assert importlib.resources.files("chunkedte").joinpath("py.typed").is_file()


def test_errors_are_value_errors_and_limit_errors_are_chunked_errors() -> None:
    assert issubclass(chunkedte.ChunkedError, ValueError)
    assert issubclass(chunkedte.LimitError, chunkedte.ChunkedError)
