# Bench-bench Current Artifact Verification

- Engine/config hash: `sha256:d5585a5bb69088a0cb7b3f4f78b70dc79a3caa59a3fcbbc00a9fcebde6d3add1`
- Overall: **PASS**

| Check | Result |
|---|:---:|
| adversarial_search_reproduces | PASS |
| all_json_reports_have_hash | PASS |
| all_markdown_reports_have_hash | PASS |
| authoritative_leaderboard_not_generated_before_live_run | PASS |
| baseline_gate_reproduces | PASS |
| card_adversarial_numbers_match | PASS |
| card_and_manifest_have_hash | PASS |
| card_baseline_numbers_match | PASS |
| card_counted_baseline_numbers_match | PASS |
| card_diagnostic_numbers_match | PASS |
| card_gate_numbers_match | PASS |
| card_public_status_matches | PASS |
| private_seed_git_history_clear | PASS |
| private_seed_values_not_materialized | PASS |
| public_leaderboard_pending | PASS |
| public_transcript_count | PASS |
| stale_run_directories_removed | PASS |
| transcripts_have_current_hash | PASS |
| twelve_week_diagnostic_reproduces | PASS |

This verification reruns the deterministic calibration gate, the 12-week diagnostic, and the adversarial search; confirms that the public leaderboard is still pending its live run; and checks every numeric validation value printed in BENCHMARK_CARD.md. It makes no model or network calls.
