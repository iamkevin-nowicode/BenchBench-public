# Bench-bench Current Artifact Verification

- Engine/config hash: `sha256:fdbd829339622163df8a27d64fe6467e353c1b2bd8ff289b25e36783e8d2e9a1`
- Overall: **FAIL**

| Check | Result |
|---|:---:|
| adversarial_search_reproduces | PASS |
| all_json_reports_have_hash | PASS |
| all_markdown_reports_have_hash | PASS |
| authoritative_leaderboard_not_generated_before_live_run | FAIL |
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
| stale_run_directories_removed | FAIL |
| transcripts_have_current_hash | PASS |
| twelve_week_diagnostic_reproduces | PASS |

This verification reruns the deterministic calibration gate, the 12-week diagnostic, and the adversarial search; confirms that the public leaderboard is still pending its live run; and checks every numeric validation value printed in BENCHMARK_CARD.md. It makes no model or network calls.
