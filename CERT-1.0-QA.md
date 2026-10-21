# chunkedte 1.0.0 QA rounds 1 to 4

QA round 1 of item 19 in `CERT-1.0-REPORT.md`, against 5a8e4e2, fixed in 099ef17: each
finding, its fix and the test that pins it. Tests named without a file are in
`tests/test_contract_edges.py`.

| Finding | Fix | Pinned by |
| --- | --- | --- |
| a-F1, c-F3 `feed` "first byte" wording; error class depends on the split | `take_line` checks the length before a bare LF; `feed` docstring and GUIDE say a grammar error comes when the line is complete | `test_contract_edges::test_the_error_class_does_not_depend_on_how_the_input_is_split` (20,000 seeded inputs, 3 splits) |
| a-F2 `__module__` rewrite broke `inspect.getsource` | classes keep their module; `Limits` and the errors pickle through `chunkedte._restore`; doctest reaches the classes through `__test__` | `test_the_source_of_every_public_name_can_be_shown`, `test_pickles_of_limits_and_errors_name_only_the_package` |
| a-F3 tab not escaped in CLI trailers | docs: bytes 0x80 to 0xFF are escaped, a tab stays a tab | `test_cli::test_decode_writes_a_tab_in_a_trailer_raw_and_escapes_bytes_above_0x7f` |
| a-F4 README CLI transcript | real output: stdout, stderr and `od -c` of `encode` | `test_docs::test_the_command_line_example_prints_what_the_readme_shows` (parses the transcript) |
| a-F5 exit codes | `--chunk-size` below 1 is a usage error (2); README and GUIDE list 0, 1 and 2 | `test_cli::test_a_chunk_size_that_is_not_a_positive_int_is_a_usage_error` |
| a-F6 non-ASCII name called "not latin-1" | reported as not a token | `test_a_non_ascii_trailer_name_is_not_a_token` |
| a-F7 `request` read by truth | `TypeError` for a non-`bool` | `test_is_chunked_takes_only_a_bool_request`, `test_upgrade` |
| a-F8 undated CHANGELOG sections | 0.2.0 dated 2026-10-19 (PyPI upload); 0.1.0 dated 2026-10-11 (merge) and marked as never on PyPI | docs |
| b-F1 empty Transfer-Encoding list | `False` for a response, `ChunkedError` still for a request | `test_framing::test_a_response_field_without_codings_is_read_to_close`, `test_upgrade` |
| b-F2 conditionals accepted as trailers | `If-Match`, `If-None-Match`, `If-Modified-Since`, `If-Unmodified-Since`, `If-Range` refused; docs say the list is fixed | `test_conditional_request_fields_are_refused_as_trailers` |
| c-F1 messages echoed trailer values | messages name the field, the bad byte in hex and its offset, never the value or line | `test_error_messages_never_echo_a_trailer_value`, `test_a_bad_trailer_value_names_the_field_byte_and_offset` |
| c-F2 strided or released `memoryview` | strided views copied to bytes; released ones raise `ValueError` like `encode` | `test_wide_and_strided_memoryviews_are_read_as_their_bytes`, `test_a_released_memoryview_raises_value_error_everywhere` |
| c-F4 huge `--chunk-size` crashed | `encode` reads at most 64 KiB at a time and fills each chunk; `MemoryError` becomes a `chunkedte:` message | `test_cli::test_a_huge_chunk_size_reads_in_bounded_blocks`, `test_encode_fills_each_chunk_from_short_reads` |
| e-F1, e-F2 wide-item `memoryview` | contracts added | X8 and X27 killed by the `memoryview` test above |
| e-F3 empty `str`/`bytes` trailers | contract added | E9 killed by `test_contract_api::test_trailers_must_be_a_mapping_or_pairs` |
| e-F4 `--trailer` split | contract added | X7 killed by `test_cli::test_encode_splits_a_trailer_argument_on_the_first_colon` |
| e-F5 huge name in a value error | contract added (encoder and decoder) | X17 killed by `test_messages` (`value, huge name` cases) |
| e-F6 CLI reads past the end | contract added | X22 killed by `test_cli::test_decode_stops_reading_once_the_message_is_complete` |
| e-F7 method `__module__` unpinned | contract added | X21 killed by `test_the_package_doctests_include_the_methods` (14 found on `chunkedte`) |

The seven mutants of lens e were re-applied one at a time to a copy of 099ef17 and each
was killed by the test named.

## Round 2

Round 2 ran against 276f0e7. Lens c confirmed F1 to F4 fixed and reported N1; lens e
confirmed its 7 round 1 mutants killed, ran 40 new mutants (N01 to N40) on the changed
code and reported the 11 survivors as G1 to G7. All are fixed in e644142. N1 and G1 are
behaviour bugs: their tests failed on 276f0e7 first, and both changes are in the
CHANGELOG. G2 to G7 were missing contracts: the tests pass on 276f0e7 and kill the named
mutants. Each named mutant was re-applied alone to the tree at e644142 and was killed by
the test named.

| Finding | Fix | Pinned by (mutants killed) |
| --- | --- | --- |
| c-N1 a `--trailer` without a colon (a likely credential typo) was echoed | the message is `--trailer needs NAME:VALUE (no colon found)`, without the argument | `test_messages::test_a_trailer_argument_without_a_colon_is_never_echoed` (3 shapes, fails on 276f0e7) |
| e-G1 `MemoryError` printed `chunkedte: ` and nothing: an exception is always true, so the name fallback was dead | `str(error) or type(error).__name__` | `test_messages::test_running_out_of_memory_names_the_error_and_exits_1` (encode, decode; fails on 276f0e7; N15, N16) |
| e-G2 pickles of errors could drop `__notes__` and attributes | contract added | `test_pickles_keep_notes_and_attributes_of_errors` (N06) |
| e-G3 pickles of a `ChunkedError` subclass | contract added | `test_pickles_keep_the_type_of_subclasses` (N08) |
| e-G4 pickles of a `Limits` subclass | contract added | `test_pickles_keep_the_type_of_subclasses` (N11) |
| e-G5 huge non-integer `--chunk-size` message | exact quoted message and stderr under 400 characters | `test_messages::test_a_huge_non_integer_chunk_size_is_quoted_briefly` (N13, N14) |
| e-G6 malformed trailer name messages | exact message per branch (no colon, empty name, bad byte at offset 3 and at 0) | `test_messages::test_a_malformed_trailer_field_line_gets_its_exact_message` (N31, N32, N33) |
| e-G7 offset of a non-latin-1 trailer value | exact message with offset 2 | `test_messages::test_a_non_latin_1_trailer_value_names_the_character_offset` (N37) |

Tests named without a file are in `tests/test_contract_edges.py`. Gates at e644142: 490
passed. Lenses c and e confirmed every round 2 fix in round 3.

## Round 3

Round 3 ran against 8061556. Lens c confirmed N1 fixed and reported N2; lens e confirmed
its 11 round 2 mutants killed, ran 24 new mutants (R01 to R24) on the changed code and
reported 6 non-equivalent survivors as F1 to F4 (R10, R12 and R19 are equivalent). All
are fixed in 4b6b48c. N2 is a behaviour bug: its tests failed on 8061556 first (10
cases), and the change is in the CHANGELOG. F1 to F4 were missing contracts: the tests
pass on 8061556 and kill the named mutants. Each named mutant was re-applied alone to the
fixed tree and was killed by the test named.

| Finding | Fix | Pinned by (mutants killed) |
| --- | --- | --- |
| c-N2 a refused trailer name was quoted, so a credential typed with a space or `=` before a colon inside it was echoed (CLI and `encode`) | the message gives the first bad character and its offset (`invalid byte 0x20 at offset 13 in a trailer field name`, `non-ASCII character U+00E9 at offset 3 ...`) or `empty trailer field name`, never the name | `test_cli_trailers::test_a_trailer_argument_with_a_colon_inside_the_secret_is_never_echoed` (3 shapes), `test_cli_trailers::test_a_bad_trailer_name_gives_the_first_bad_character_and_never_the_rest` (4 names), `test_cli_trailers::test_an_empty_trailer_name_is_named_as_such`; all fail on 8061556 |
| e-F1 the empty-message fallback was pinned only for `MemoryError` | contract added: a bare `OSError` gives exit 1 and `chunkedte: OSError` | `test_cli_trailers::test_an_error_with_an_empty_message_is_named_by_its_type` (R01) |
| e-F2 `--trailer NAME:` with an empty value | contract added: exit 0, `0\r\nX-E: \r\n\r\n` | `test_cli_trailers::test_a_trailer_argument_with_an_empty_value_sends_an_empty_field` (R13) |
| e-F3 whitespace around a `--trailer` name | contract added: `X-A : 1` and ` X-A: 1` exit 1 with the exact message | `test_cli_trailers::test_whitespace_around_a_trailer_argument_name_is_refused` (R20) |
| e-F4 trimming of the `--trailer` value | contract added: SP and HTAB trimmed at both ends, 0xA0 kept, a trailing form feed refused with the exact message | `test_cli_trailers::test_a_trailer_argument_value_loses_only_spaces_and_tabs_at_its_ends`, `test_cli_trailers::test_a_form_feed_at_the_end_of_a_trailer_argument_value_is_refused` (R21, R22, R23) |

The round 1 test `test_a_non_ascii_trailer_name_is_not_a_token` now expects the
`non-ASCII character U+.... at offset` message, and the GUIDE example of a refused name
shows the new message. Gates at 4b6b48c: 508 passed.
Lenses c and e confirmed every round 3 fix in round 4.

## Round 4

Round 4 ran against ee22527. Lens c confirmed N2 fixed and reported PASS. Lens e
confirmed its round 3 mutants (R01, R13, R20 to R23) and its round 2 mutants killed, ran
32 new mutants (Q01 to Q32) on the new `_check_name` and reported the 5 non-equivalent
survivors as E1 to E5 (Q04, Q06, Q21, Q24 and Q30 are equivalent). None is a behaviour
bug: each was a missing contract, so the code and the CHANGELOG are unchanged. All are
pinned in 3c84ffb by one parametrized test,
`test_cli_trailers::test_the_whole_trailer_name_is_checked_before_anything_else`, which
passes on ee22527. Each named mutant was re-applied alone to the tree at 3c84ffb and was
killed by that test.

| Finding | Contract added (exact message, `in a trailer field name`) | Mutant killed |
| --- | --- | --- |
| e-E1 a bad character after offset 63 | `"X" * 64 + " tail"`: `invalid byte 0x20 at offset 64`; `"X" * 70 + "\u00e9"`: `non-ASCII character U+00E9 at offset 70` | Q03 |
| e-E2 a blank name | `" "`: `invalid byte 0x20 at offset 0`; `"\t"`: `invalid byte 0x09 at offset 0` | Q07 |
| e-E3 a character outside the BMP | `"\U0001f600"`: `U+1F600 at offset 0`; `"X-\U00010000"`: `U+10000 at offset 2` | Q17 |
| e-E4 punctuation tchars before the bad byte | `X.Y Z` and `a!b c`: `0x20 at offset 3`; a name with eleven more punctuation tchars before a space: `0x20 at offset 23` | Q23 |
| e-E5 the name check runs before the forbidden list | Kelvin sign `\u212aeep-alive` (lower-cases to `keep-alive`): `non-ASCII character U+212A at offset 0`, not the forbidden message | Q32 |

Gates at 3c84ffb: 518 passed. Lens e confirmed every round 4 fix in round 5.
