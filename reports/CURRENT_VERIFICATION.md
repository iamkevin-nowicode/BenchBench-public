# Bench-bench Current Artifact Verification

- Engine/config hash: `sha256:438c1d77d284450cd4e3da2eac9fcda83c45bfb81f7a67598c62763d96602a52`
- Prompt hash: `sha256:06d96111ac9db67e92f1a26d00f84e986ea95d13fc2acf0825b97be112ef0d27`
- Overall: **PASS**

| Check | Result |
|---|:---:|
| adversarial_search_reproduces | PASS |
| all_json_reports_have_hash | PASS |
| all_markdown_reports_have_hash | PASS |
| authoritative_leaderboard_state_valid | PASS |
| baseline_gate_reproduces | PASS |
| card_adversarial_numbers_match | PASS |
| card_and_manifest_have_hash | PASS |
| card_baseline_numbers_match | PASS |
| card_counted_baseline_numbers_match | PASS |
| card_diagnostic_numbers_match | PASS |
| card_gate_numbers_match | PASS |
| card_public_status_matches | PASS |
| pilot_archive_manifest_complete | PASS |
| private_seed_git_history_clear | PASS |
| private_seed_values_not_materialized | PASS |
| public_leaderboard_pending_or_complete | PASS |
| public_transcript_count | PASS |
| stale_run_directories_removed | PASS |
| transcripts_have_current_hash | PASS |
| transcripts_have_current_prompt_hash | PASS |
| twelve_week_diagnostic_reproduces | PASS |

This verification reruns the deterministic calibration gate, the 12-week diagnostic, and the adversarial search; validates either the pre-run pending state or the complete public artifact state; and checks every numeric validation value printed in BENCHMARK_CARD.md. It makes no model or network calls.
