# chunkedte 1.0.0 QA round 1

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
