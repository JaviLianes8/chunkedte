# chunkedte 1.0.0 author mutation table

The author round of item 18 in `CERT-1.0-REPORT.md`: each mutant applied alone, the test
that killed it. M36 was first caught by an exit status 1 test; since QA round 1 a
`--chunk-size` of 0 is a usage error, caught by
`test_cli::test_a_chunk_size_that_is_not_a_positive_int_is_a_usage_error[0]`.

| Id | Module | Mutation | Caught by |
| --- | --- | --- | --- |
| M1 | `_lines.py` | bare LF at the start of the buffer not checked | `test_strict::test_a_bare_lf_as_the_first_byte_of_a_line_is_rejected` |
| M2 | `_lines.py` | unfinished line allowed one byte more | `test_docs::test_each_guide_example_prints_what_its_comments_show[3]` |
| M3 | `_lines.py` | a line exactly at the limit refused | `test_limits::test_a_size_line_at_the_limit_passes_and_one_byte_more_fails` |
| M4 | `_lines.py` | bare CR inside a line accepted | `test_strict::test_a_bare_cr_in_a_size_line_is_rejected` |
| M5 | `_decode.py` | bytes after chunk data checked only once two arrived | `test_strict::test_a_wrong_byte_after_chunk_data_fails_without_waiting_for_more` |
| M6 | `_decode.py` | leading zeros counted toward the 16 digit cap | `test_limits::test_leading_zeros_do_not_count_towards_the_size_cap` |
| M7 | `_decode.py` | `max_chunk_size` itself refused | `test_limits::test_chunk_size_is_capped` |
| M8 | `_decode.py` | body cap checked per chunk, not in total | `test_limits::test_body_size_is_capped_when_the_size_line_arrives` |
| M9 | `_decode.py` | extension bytes counted per line, not per message | `test_limits::test_extension_bytes_are_bounded_across_the_whole_message` |
| M10 | `_decode.py` | trailer budget without the line's CRLF | `test_limits::test_trailer_section_is_capped_including_crlfs` |
| M11 | `_decode.py` | `unused_data` returned before completion | `test_decode::test_unused_data_is_empty_before_completion` |
| M12 | `_decode.py` | a failed decoder not poisoned | `test_decode::test_a_failed_decoder_keeps_failing` |
| M13 | `_decode.py` | one byte too many taken from chunk data | the 300 s per-test timeout (the decoder loops forever) |
| M14 | `_decode.py` | a size of 1 read as the last chunk | doctest `Decoder.unused_data` |
| M15 | `_grammar.py` | `~` dropped from `tchar` | `test_oracle_llhttp::test_valid_messages_without_bws_decode_identically` |
| M16 | `_grammar.py` | `"` allowed as `qdtext` | `test_fuzz::test_mutated_messages_get_the_same_verdict[0]` |
| M17 | `_grammar.py` | tab dropped from BWS | `test_fuzz::test_mutated_messages_get_the_same_verdict[1]` |
| M18 | `_grammar.py` | obs-fold detected for a space only, not a tab | `test_upgrade` first; now `test_strict::test_obs_fold_in_trailers_is_rejected_with_a_clear_message[\tb]` |
| M19 | `_grammar.py` | `Host` allowed as a trailer | `test_encode::test_framing_and_routing_fields_are_refused_as_trailers[Host]` |
| M20 | `_grammar.py` | edge whitespace in a trailer value allowed | `test_encode::test_trailer_values_must_be_clean_field_values[ lead]` |
| M21 | `_grammar.py` | trailer values trimmed of spaces but not tabs | `test_decode::test_trailers_are_kept_in_order_with_trimmed_values` |
| M22 | `_grammar.py` | obs-text not allowed after a backslash | `test_upgrade` first; now `test_strict::test_quoted_pairs_escape_obs_text_and_whitespace` |
| M23 | `_encode.py` | chunk size written in decimal | doctest `Encoder.write` |
| M24 | `_encode.py` | empty piece written as a zero-size chunk | doctest `Encoder` |
| M25 | `_encode.py` | pieces of `chunk_size + 1` bytes | doctest `encode` |
| M26 | `_encode.py` | `finish` does not close the encoder | `test_contract_api::test_a_refused_trailer_leaves_the_encoder_open` |
| M27 | `_framing.py` | chunked applied twice allowed | `test_docs::test_each_example_prints_what_its_comments_show[4]` |
| M28 | `_framing.py` | request and response rules swapped | doctest `is_chunked` |
| M29 | `_framing.py` | Transfer-Encoding with Content-Length allowed | doctest `is_chunked` |
| M30 | `_framing.py` | coding names compared with case | `test_docs::test_each_guide_example_prints_what_its_comments_show[5]` |
| M31 | `_framing.py` | parameters on chunked allowed | `test_docs::test_each_guide_example_prints_what_its_comments_show[5]` |
| M32 | `_limits.py` | `-1` accepted as a bound | `test_limits::test_negative_limits_are_refused[max_line_size]` |
| M33 | `_errors.py` | a 64 character quote marked as cut | `test_messages::test_a_cut_quote_is_marked_and_a_short_one_is_not` |
| M34 | `_oneshot.py` | `decode` ignores bytes after the message | doctest `decode` |
| M35 | `_cli.py` | `decode` ignores bytes in a later block | `test_cli::test_decode_notices_bytes_after_the_end_in_a_later_block` |
| M36 | `_cli.py` | `--chunk-size 0` accepted | `test_cli::test_encode_reports_bad_options_before_any_output` |
| M37 | `_encode.py` | a two-character string taken as a pair | `test_contract_api::test_trailers_must_be_a_mapping_or_pairs` |
| M38 | `_errors.py` | only `str` refused as data | `test_contract_api::test_only_bytes_like_data_is_accepted[5]` |
| M39 | `_decode.py` | `limits` type not checked | `test_contract_api::test_decoder_refuses_anything_but_limits[5]` |
| M40 | `_cli.py` | trailer bytes printed without escaping | `test_cli::test_decode_escapes_trailer_bytes_for_an_ascii_terminal` |
