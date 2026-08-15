"""Paired baseline evaluation and Phase 2 diagnostics.

The six scripted policies remain useful calibration and regression fixtures.
They are not the v0.2 release gate: that gate is the held-out policy ladder
performed after calibration. Oracle headroom remains a secondary diagnostic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import math
from statistics import fmean, stdev
from typing import Any, Iterable

from .adversarial import run_adversarial_search
from .config import SimConfig
from .engine import BenchEnvironment
from .policies import POLICY_NAMES, make_policy
from .provenance import current_prompt_hash, engine_config_hash
from .scoring import MIN_COUNTED_SEED_FRACTION, PAIN_DAYS_LIMIT, counted_score, constraint_violations


# This threshold is retained as a diagnostic for the historical six-policy
# report. It is not the v0.2 release criterion.
STABLE_ORDER_RATE_THRESHOLD = 0.65


@dataclass(frozen=True)
class EpisodeStats:
    policy: str
    seed: int
    final_1rm_kg: float
    completed_sessions: int
    missed_sessions: int
    fallback_sessions: int
    productive_weeks: int
    pain_days: int
    household_strain: float
    household_strain_peak: float
    mean_household_strain: float
    household_strain_high_weeks: int
    final_third_mean_household_strain: float
    sleep_debt: float
    total_spend_cents: int
    invalid_reason: str | None
    action_repairs: int
    fallback_actions: int
    planned_sessions: int
    transformed_sessions: int
    attempted_sessions: int
    planned_fallbacks: int
    capital_purchases: int
    constraint_violations: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["constraint_violations"] = list(self.constraint_violations)
        values["raw_final_1rm_kg"] = self.final_1rm_kg
        values["counted_final_1rm_kg"] = counted_score(
            self.final_1rm_kg,
            invalid_reason=self.invalid_reason,
            violations=self.constraint_violations,
        )
        return values


@dataclass(frozen=True)
class PolicySummary:
    policy: str
    episodes: int
    mean_final_1rm_kg: float
    seed_std_kg: float
    min_final_1rm_kg: float
    max_final_1rm_kg: float
    mean_completed_sessions: float
    mean_missed_sessions: float
    mean_fallback_sessions: float
    mean_productive_weeks: float
    mean_pain_days: float
    mean_household_strain: float
    mean_household_strain_peak: float
    mean_household_strain_high_weeks: float
    mean_final_third_household_strain: float
    mean_sleep_debt: float
    mean_action_repairs: float
    invalid_episodes: int
    mean_planned_sessions: float
    mean_transformed_sessions: float
    mean_attempted_sessions: float
    mean_planned_fallbacks: float
    mean_capital_purchases: float
    counted_episodes: int
    counted_mean_final_1rm_kg: float | None
    counted_seed_std_kg: float | None
    counted_min_final_1rm_kg: float | None
    counted_max_final_1rm_kg: float | None
    counted_seed_fraction: float
    constraint_violating_episodes: int
    constraint_violation_counts: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_episode(policy_name: str, seed: int, config: SimConfig | None = None) -> EpisodeStats:
    config = config or SimConfig.twelve_week()
    policy = make_policy(policy_name, seed, allow_home_rack=config.enable_home_rack)
    env = BenchEnvironment(seed, config)
    while not env.done:
        policy_action = policy.action(env.observation)
        env.submit_week(policy_action, reactive_responder=policy.reactive)
    result = env.final_result()
    week_records = [record for record in env.log_records if record.get("type") == "week"]
    action_repairs = sum(1 for record in week_records if record["validation"]["repair_attempted"])
    fallback_actions = sum(1 for record in week_records if record["validation"]["fallback_used"])
    planned_sessions = result.planned_sessions
    planned_fallbacks = sum(
        sum(1 for session in record["action"]["sessions"] if session["focus"] == "fallback")
        for record in week_records
    )
    capital_purchases = sum(len(record["action"]["life"]["purchases"]) for record in week_records)
    return EpisodeStats(
        policy=policy_name,
        seed=seed,
        final_1rm_kg=result.final_1rm_kg,
        completed_sessions=result.completed_sessions,
        missed_sessions=result.missed_sessions,
        fallback_sessions=result.fallback_sessions,
        productive_weeks=result.productive_weeks,
        pain_days=result.pain_days,
        household_strain=result.household_strain,
        household_strain_peak=result.household_strain_peak,
        mean_household_strain=result.mean_household_strain,
        household_strain_high_weeks=result.household_strain_high_weeks,
        final_third_mean_household_strain=result.final_third_mean_household_strain,
        sleep_debt=result.sleep_debt,
        total_spend_cents=result.total_spend_cents,
        invalid_reason=result.invalid_reason,
        action_repairs=action_repairs,
        fallback_actions=fallback_actions,
        planned_sessions=planned_sessions,
        transformed_sessions=result.transformed_sessions,
        attempted_sessions=result.attempted_sessions,
        planned_fallbacks=planned_fallbacks,
        capital_purchases=capital_purchases,
        constraint_violations=constraint_violations(
            pain_days=result.pain_days,
            household_strain_high_weeks=result.household_strain_high_weeks,
            final_third_mean_household_strain=result.final_third_mean_household_strain,
            household_strain_limit=config.household_strain_limit,
            household_strain_high_week_limit=config.household_strain_high_week_limit,
        ),
    )


def run_exploit_suite(
    seeds: Iterable[int] = range(20),
    weeks: int = 52,
    *,
    weekly_stimulus_cap: float | None = None,
) -> dict[str, Any]:
    """Backward-compatible entry point for the automated red-team search."""
    return run_adversarial_search(
        seeds=seeds,
        weeks=weeks,
        weekly_stimulus_cap=weekly_stimulus_cap,
    )


def markdown_exploit_report(report: dict[str, Any], expert_mean: float | None = None) -> str:
    comparison = report.get("comparison", {})
    reference_mean = expert_mean if expert_mean is not None else comparison.get("expert_mean_final_1rm_kg")
    thresholds = comparison.get("release_abuse_thresholds", {})
    lines = [
        "# Bench-bench Phase 4 Automated Adversarial Search",
        "",
        f"- Engine/config hash: `{engine_config_hash()}`",
        f"- Prompt hash: `{current_prompt_hash()}`",
        "Red-team candidates are generated by deterministic search over legal public WeekAction fields and evaluated on the full 52-week configuration. The widened genome includes mixed-focus weekly templates, per-week structure, boundary load ratios including zero, and ordered capital purchases.",
        "",
        "A candidate blocks release only when it beats the scripted expert and has at least one simulator-abuse signature.",
        "",
        "| Candidate | Counted mean final 1RM (kg) | Raw mean final 1RM (kg) | Seed std | Pain days | Final strain | Peak strain | High-strain weeks | Final-third strain | Violations | Beats expert | Abuse signatures | Human review | Blocks release |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|:---:|---|:---:|:---:|",
    ]
    for name in report["exploit_policies"]:
        summary = report["summaries"][name]
        candidate = report.get("candidates", {}).get(name, {})
        signatures = ", ".join(candidate.get("abuse_signatures", [])) or "none"
        mean = summary.get("mean_final_1rm_kg")
        if mean is not None:
            score = f"{mean:.2f}"
        elif summary.get("counted_episodes", summary.get("episodes", 0)):
            score = "not reportable"
        else:
            score = "invalid"
        raw_mean = summary.get("raw_mean_final_1rm_kg")
        raw_score = f"{raw_mean:.2f}" if raw_mean is not None else "—"
        violation_counts = summary.get("constraint_violation_counts", {})
        violations = ", ".join(f"{violation}: {count}" for violation, count in sorted(violation_counts.items())) or "—"
        lines.append(
            f"| {name} | {score} | {raw_score} | {summary['seed_std_kg'] if summary['seed_std_kg'] is not None else '—'} | {summary['mean_pain_days'] if summary['mean_pain_days'] is not None else '—'} | {summary['mean_household_strain'] if summary['mean_household_strain'] is not None else '—'} | {summary.get('mean_household_strain_peak', '—')} | {summary.get('mean_household_strain_high_weeks', '—')} | {summary.get('mean_final_third_household_strain', '—')} | {violations} | {'yes' if candidate.get('beats_expert') else 'no'} | {signatures} | {'yes' if candidate.get('requires_human_review') else 'no'} | {'yes' if candidate.get('release_blocked') else 'no'} |"
        )
    if reference_mean is not None:
        lines.extend(["", f"Scripted-expert reference mean: **{reference_mean:.2f} kg**.", ""])
        for name in report["exploit_policies"]:
            summary = report["summaries"][name]
            mean = summary["mean_final_1rm_kg"]
            if mean is None:
                counted = summary.get("counted_episodes", summary.get("episodes", 0))
                total = summary.get("total_episodes", counted)
                label = "not reportable" if counted else "invalid candidate"
                lines.append(f"- {name}: {label} ({counted}/{total} seeds counted)")
            else:
                lines.append(f"- {name}: {'beats expert' if mean > reference_mean else 'does not beat expert'} ({mean - reference_mean:+.2f} kg)")
    if thresholds:
        lines.extend(
            [
                "",
                "## Release-abuse thresholds",
                "",
                f"- Mean pain days: ≥{thresholds.get('mean_pain_days', 14):g}",
                f"- Mean household strain: ≥{thresholds.get('mean_household_strain', 0.95):g}",
                f"- Human review margin (not an abuse signature): ≥{comparison.get('human_review_margin_kg', 5.0):g} kg",
                "- Physical envelope: high-load/high-rep or over-loaded authored fallback sessions",
            ]
        )
    diagnostic_ranking = report.get("search", {}).get("diagnostic_ranking", [])
    if diagnostic_ranking:
        lines.extend(
            [
                "",
                "## Survivor-bias diagnostic ranking",
                "",
                "Diagnostic only: genomes are sorted by raw mean final 1RM on the search seeds. Counted means are shown only for genomes compliant on every search seed; no row here can make a comparison or release claim.",
                "",
                "| Rank | Genome | Raw mean (kg) | Counted fraction | Counted mean (kg) | All-seed eligible |",
                "|---:|---|---:|---:|---:|:---:|",
            ]
        )
        for rank, diagnostic in enumerate(diagnostic_ranking, start=1):
            raw_mean = diagnostic.get("raw_mean_final_1rm_kg")
            counted_mean = diagnostic.get("counted_mean_final_1rm_kg")
            raw_text = f"{raw_mean:.2f}" if raw_mean is not None else "—"
            counted_text = f"{counted_mean:.2f}" if counted_mean is not None else "—"
            lines.append(
                f"| {rank} | {diagnostic['name']} | {raw_text} | {diagnostic['counted_seed_fraction']:.1%} | {counted_text} | {'yes' if diagnostic['eligible_for_comparison'] else 'no'} |"
            )
        lines.append("Full genome fields and the complete ranking are in the JSON report.")
    lines.extend(
        [
            "",
            "## Patch status",
            "",
            "The search includes volume-stacking, compressed-fallback, 8×4, mixed-focus, zero-load, purchase-order, and the two independent-reviewer boundary genomes as regression seeds; candidates are still generated and ranked by the search, not by a fixed exploit-policy registry. A candidate with incomplete counted-seed coverage remains visible as a diagnostic but cannot supply a leaderboard mean.",
            "",
        ]
    )
    return "\n".join(lines)


def write_exploit_report(report: dict[str, Any], json_path: str | Path, markdown_path: str | Path, expert_mean: float | None = None) -> None:
    json_path = Path(json_path)
    markdown_path = Path(markdown_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    report = dict(report)
    comparison = dict(report.get("comparison", {}))
    if expert_mean is not None:
        comparison["expert_mean_final_1rm_kg"] = expert_mean
    comparison["exploit_wins_over_expert"] = {
        name: (
            report["summaries"][name]["mean_final_1rm_kg"] > comparison["expert_mean_final_1rm_kg"]
            if report["summaries"][name]["mean_final_1rm_kg"] is not None
            and comparison.get("expert_mean_final_1rm_kg") is not None
            else None
        )
        for name in report["exploit_policies"]
    }
    comparison["release_blocked_candidates"] = [
        name for name in report["exploit_policies"]
        if report.get("candidates", {}).get(name, {}).get("release_blocked", False)
    ]
    comparison["human_review_candidates"] = [
        name for name in report["exploit_policies"]
        if report.get("candidates", {}).get(name, {}).get("requires_human_review", False)
    ]
    report["comparison"] = comparison
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_exploit_report(report, expert_mean), encoding="utf-8")


def summarize(episodes: Iterable[EpisodeStats], policy: str) -> PolicySummary:
    all_values = list(episodes)
    values = [episode for episode in all_values if episode.invalid_reason is None]
    if not values:
        raise ValueError(f"policy {policy} has no valid episodes to summarize")
    scores = [episode.final_1rm_kg for episode in values]
    spread = stdev(scores) if len(scores) > 1 else 0.0
    counted = [
        episode
        for episode in values
        if not episode.constraint_violations
    ]
    counted_scores = [episode.final_1rm_kg for episode in counted]
    # Structural invalid episodes are expected seeds too: they must reduce the
    # coverage fraction rather than disappearing from the denominator.
    counted_fraction = len(counted) / len(all_values) if all_values else 0.0
    counted_aggregate_reportable = counted_fraction >= MIN_COUNTED_SEED_FRACTION
    violation_counts: dict[str, int] = {}
    for episode in values:
        for violation in episode.constraint_violations:
            violation_counts[violation] = violation_counts.get(violation, 0) + 1
    average = lambda field: round(fmean(getattr(episode, field) for episode in values), 4)
    return PolicySummary(
        policy=policy,
        episodes=len(values),
        mean_final_1rm_kg=round(fmean(scores), 4),
        seed_std_kg=round(spread, 4),
        min_final_1rm_kg=round(min(scores), 4),
        max_final_1rm_kg=round(max(scores), 4),
        mean_completed_sessions=average("completed_sessions"),
        mean_missed_sessions=average("missed_sessions"),
        mean_fallback_sessions=average("fallback_sessions"),
        mean_productive_weeks=average("productive_weeks"),
        mean_pain_days=average("pain_days"),
        mean_household_strain=average("household_strain"),
        mean_household_strain_peak=average("household_strain_peak"),
        mean_household_strain_high_weeks=average("household_strain_high_weeks"),
        mean_final_third_household_strain=average("final_third_mean_household_strain"),
        mean_sleep_debt=average("sleep_debt"),
        mean_action_repairs=average("action_repairs"),
        invalid_episodes=sum(episode.invalid_reason is not None for episode in all_values),
        mean_planned_sessions=average("planned_sessions"),
        mean_transformed_sessions=average("transformed_sessions"),
        mean_attempted_sessions=average("attempted_sessions"),
        mean_planned_fallbacks=average("planned_fallbacks"),
        mean_capital_purchases=average("capital_purchases"),
        counted_episodes=len(counted),
        counted_mean_final_1rm_kg=round(fmean(counted_scores), 4) if counted_scores and counted_aggregate_reportable else None,
        counted_seed_std_kg=round(stdev(counted_scores), 4) if len(counted_scores) > 1 and counted_aggregate_reportable else (0.0 if counted_scores and counted_aggregate_reportable else None),
        counted_min_final_1rm_kg=round(min(counted_scores), 4) if counted_scores and counted_aggregate_reportable else None,
        counted_max_final_1rm_kg=round(max(counted_scores), 4) if counted_scores and counted_aggregate_reportable else None,
        counted_seed_fraction=round(counted_fraction, 4),
        constraint_violating_episodes=len(values) - len(counted),
        constraint_violation_counts=violation_counts,
    )


def _pooled_std(first: PolicySummary, second: PolicySummary) -> float:
    numerator = max(0, first.episodes - 1) * first.seed_std_kg**2 + max(0, second.episodes - 1) * second.seed_std_kg**2
    denominator = max(1, first.episodes + second.episodes - 2)
    return math.sqrt(numerator / denominator)


def _pairwise_order_rate(first: list[EpisodeStats], second: list[EpisodeStats]) -> float:
    right = {episode.seed: episode.final_1rm_kg for episode in second}
    comparisons = [episode.final_1rm_kg < right[episode.seed] for episode in first if episode.seed in right]
    return fmean(comparisons) if comparisons else 0.0


def gate_metrics(
    summaries: dict[str, PolicySummary],
    episodes: dict[str, list[EpisodeStats]],
    *,
    enforce: bool = True,
) -> dict[str, Any]:
    random_summary = summaries["random"]
    expert_summary = summaries["scripted-expert"]
    pooled_std = _pooled_std(expert_summary, random_summary)
    difference = expert_summary.mean_final_1rm_kg - random_summary.mean_final_1rm_kg
    ratio = difference / pooled_std if pooled_std > 0 else float("inf")
    means = {name: summary.mean_final_1rm_kg for name, summary in summaries.items()}
    ordering = (
        means["random"] < means["reckless-maximalist"]
        and means["random"] < means["rigid-linear"]
        and max(means["reckless-maximalist"], means["rigid-linear"]) < means["skip-when-busy"]
        and means["skip-when-busy"] < means["recovery-aware"] < means["scripted-expert"]
    )
    adjacent_rates = {
        "random<reckless": _pairwise_order_rate(episodes["random"], episodes["reckless-maximalist"]),
        "random<rigid": _pairwise_order_rate(episodes["random"], episodes["rigid-linear"]),
        "rigid_or_reckless<skip": min(
            _pairwise_order_rate(episodes["rigid-linear"], episodes["skip-when-busy"]),
            _pairwise_order_rate(episodes["reckless-maximalist"], episodes["skip-when-busy"]),
        ),
        "skip<recovery": _pairwise_order_rate(episodes["skip-when-busy"], episodes["recovery-aware"]),
        "recovery<expert": _pairwise_order_rate(episodes["recovery-aware"], episodes["scripted-expert"]),
    }
    stable_ordering = min(adjacent_rates.values()) >= STABLE_ORDER_RATE_THRESHOLD
    score_order = [
        "random",
        "reckless-maximalist",
        "rigid-linear",
        "skip-when-busy",
        "recovery-aware",
        "scripted-expert",
    ]
    adjacent_sigma: dict[str, dict[str, float]] = {}
    for left, right in zip(score_order, score_order[1:]):
        pooled = _pooled_std(summaries[left], summaries[right])
        gap = summaries[right].mean_final_1rm_kg - summaries[left].mean_final_1rm_kg
        adjacent_sigma[f"{left}->{right}"] = {
            "gap_kg": round(gap, 4),
            "pooled_seed_std_kg": round(pooled, 4),
            "sigma": round(gap / pooled, 4) if pooled > 0 else float("inf"),
        }
    reckless = summaries["reckless-maximalist"]
    recovery = summaries["recovery-aware"]
    expert = summaries["scripted-expert"]
    reckless_loses_endogenously = (
        reckless.mean_final_1rm_kg < expert.mean_final_1rm_kg
        and reckless.mean_final_1rm_kg < recovery.mean_final_1rm_kg
        and reckless.mean_pain_days > expert.mean_pain_days
        and reckless.invalid_episodes == 0
    )
    return {
        "expert_minus_random_kg": round(difference, 4),
        "pooled_seed_std_kg": round(pooled_std, 4),
        "separation_ratio": round(ratio, 4),
        "ordering_pass": ordering,
        "pairwise_order_rates": {key: round(value, 4) for key, value in adjacent_rates.items()},
        "adjacent_sigma": adjacent_sigma,
        "stable_order_rate_threshold": STABLE_ORDER_RATE_THRESHOLD,
        "stable_ordering_pass": stable_ordering,
        "reckless_loses_endogenously": reckless_loses_endogenously,
        "invalid_episode_free": all(summary.invalid_episodes == 0 for summary in summaries.values()),
        "gate_enforced": enforce,
        "gate_pass": bool(ratio >= 3.0 and ordering and stable_ordering and reckless_loses_endogenously) if enforce else None,
    }


def run_rack_ablation(seeds: Iterable[int] = range(20), weeks: int = 52) -> dict[str, Any]:
    """Compare the expert with and without a usable home rack.

    The disabled run changes the policy's available decision, so it chooses
    gym sessions rather than emitting home sessions that the engine would
    reject as unequipped.
    """
    seed_list = list(seeds)
    enabled_config = SimConfig(weeks=weeks, enable_home_rack=True)
    disabled_config = SimConfig(weeks=weeks, enable_home_rack=False)
    enabled = [run_episode("scripted-expert", seed, enabled_config) for seed in seed_list]
    disabled = [run_episode("scripted-expert", seed, disabled_config) for seed in seed_list]
    enabled_summary = summarize(enabled, "scripted-expert")
    disabled_summary = summarize(disabled, "scripted-expert")
    disabled_by_seed = {episode.seed: episode.final_1rm_kg for episode in disabled}
    return {
        "policy": "scripted-expert",
        "seeds": seed_list,
        "enabled": enabled_summary.as_dict(),
        "disabled": disabled_summary.as_dict(),
        "mean_swing_kg": round(
            enabled_summary.mean_final_1rm_kg - disabled_summary.mean_final_1rm_kg,
            4,
        ),
        "paired_score_deltas_kg": {
            str(episode.seed): round(episode.final_1rm_kg - disabled_by_seed[episode.seed], 4)
            for episode in enabled
        },
    }


def run_suite(
    seeds: Iterable[int] = range(20),
    weeks: int = 12,
    *,
    ablations: bool = True,
    enforce_legacy_gate: bool = False,
) -> dict[str, Any]:
    seed_list = list(seeds)
    config = SimConfig(weeks=weeks)
    episodes: dict[str, list[EpisodeStats]] = {name: [] for name in POLICY_NAMES}
    for policy in POLICY_NAMES:
        for seed in seed_list:
            episodes[policy].append(run_episode(policy, seed, config))
    summaries = {policy: summarize(episodes[policy], policy) for policy in POLICY_NAMES}
    report: dict[str, Any] = {
        "benchmark": "Bench-bench",
        "engine_config_hash": engine_config_hash(),
        "prompt_hash": current_prompt_hash(),
        "phase": 2,
        "config": config.as_dict(),
        "seeds": seed_list,
        "policies": list(POLICY_NAMES),
        "summaries": {name: summary.as_dict() for name, summary in summaries.items()},
        "episodes": {name: [episode.as_dict() for episode in values] for name, values in episodes.items()},
        # The old six-baseline ordering is intentionally diagnostic. The
        # v0.2 release gate is the held-out oracle/policy-ladder gate and is
        # not silently substituted by this report.
        "gate": gate_metrics(
            summaries,
            episodes,
            enforce=bool(enforce_legacy_gate and weeks == 52),
        ),
        "rack_ablation": run_rack_ablation(seed_list, weeks),
    }
    if ablations:
        report["ablations"] = run_ablations(seed_list, weeks, report)
    return report


def run_ablations(seeds: list[int], weeks: int, full_report: dict[str, Any]) -> list[dict[str, Any]]:
    full_summaries = full_report["summaries"]
    definitions = {
        "no-sleep-system": {"enable_sleep_system": False},
        "no-delayed-adaptation": {"enable_delayed_adaptation": False},
        "no-event-system": {"enable_event_system": False},
    }
    results: list[dict[str, Any]] = []
    for name, overrides in definitions.items():
        config = SimConfig(weeks=weeks, **overrides)
        episode_map: dict[str, list[EpisodeStats]] = {policy: [] for policy in POLICY_NAMES}
        for policy in POLICY_NAMES:
            for seed in seeds:
                episode_map[policy].append(run_episode(policy, seed, config))
        summaries = {policy: summarize(episode_map[policy], policy) for policy in POLICY_NAMES}
        score_deltas = {
            policy: round(summaries[policy].mean_final_1rm_kg - float(full_summaries[policy]["mean_final_1rm_kg"]), 4)
            for policy in POLICY_NAMES
        }
        decision_deltas = {
            policy: {
                "planned_sessions": round(summaries[policy].mean_planned_sessions - float(full_summaries[policy]["mean_planned_sessions"]), 4),
                "planned_fallbacks": round(summaries[policy].mean_planned_fallbacks - float(full_summaries[policy]["mean_planned_fallbacks"]), 4),
                "capital_purchases": round(summaries[policy].mean_capital_purchases - float(full_summaries[policy]["mean_capital_purchases"]), 4),
            }
            for policy in POLICY_NAMES
        }
        ablation_gate = gate_metrics(summaries, episode_map, enforce=False)
        results.append(
            {
                "name": name,
                "disabled": overrides,
                "summaries": {policy: summary.as_dict() for policy, summary in summaries.items()},
                "score_delta_vs_full_kg": score_deltas,
                "decision_delta_vs_full": decision_deltas,
                "gate": ablation_gate,
                "changed_score": any(abs(value) >= 0.10 for value in score_deltas.values()),
                "changed_decisions": any(
                    abs(delta[field]) >= 0.10
                    for delta in decision_deltas.values()
                    for field in ("planned_sessions", "planned_fallbacks", "capital_purchases")
                ),
            }
        )
    return results


def markdown_report(report: dict[str, Any]) -> str:
    gate = report["gate"]
    gate_enforced = bool(gate.get("gate_enforced", report["config"]["weeks"] == 52))
    lines = [
        f"# Bench-bench Baseline Diagnostic — {report['config']['weeks']}-week config",
        "",
        "This report is generated by the paired scripted-baseline suite. The six-policy ordering and separation fields are diagnostics. The v0.2 release gate is the held-out oracle/policy-ladder evaluation and is reported separately.",
        "",
        f"- Engine/config hash: `{report.get('engine_config_hash', engine_config_hash())}`",
        f"- Prompt hash: `{report.get('prompt_hash', current_prompt_hash())}`",
        f"- Config: {report['config']['weeks']} weeks",
        f"- Seeds: {report['seeds']}",
        f"- Separation: {gate['expert_minus_random_kg']:.3f} kg / {gate['pooled_seed_std_kg']:.3f} kg = **{gate['separation_ratio']:.3f}** (required ≥ 3.0)",
        f"- Headline-score constraint: pain days ≤{PAIN_DAYS_LIMIT}; household strain is invalid at ≥{report['config'].get('household_strain_high_week_limit', 4)} weeks at or above {report['config'].get('household_strain_limit', 0.75):g} or when the final {report['config'].get('household_strain_final_window_weeks', 13)}-week mean exceeds that threshold. Raw final 1RM remains reported; peak strain and sleep debt are diagnostics.",
        f"- Counted aggregate rule: a counted mean and seed SD are reportable only when every expected seed is counted (minimum fraction {MIN_COUNTED_SEED_FRACTION:.0%}); otherwise they are shown as — and raw results remain diagnostic.",
        f"- Ordering: {'PASS' if gate['ordering_pass'] else 'FAIL'}; stable ordering: {'PASS' if gate['stable_ordering_pass'] else 'FAIL'} (paired rate ≥ {gate.get('stable_order_rate_threshold', 0.65):.0%})",
        f"- Reckless loses endogenously: {'PASS' if gate['reckless_loses_endogenously'] else 'FAIL'}",
        f"- Historical six-policy gate fields: **diagnostic only**; legacy enforcement requested: {'yes' if gate_enforced else 'no'}",
        "",
        "## Baseline results",
        "",
        "| Policy | Raw mean final 1RM (kg) | Counted mean final 1RM (kg) | Raw seed SD | Counted seed SD | Counted seeds | Counted fraction | Planned | Transformed | Attempted | Completed | Missed | Pain days | Final household strain | Peak strain | High-strain weeks | Final-third strain | Violations | Invalid episodes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for name in report["policies"]:
        summary = report["summaries"][name]
        counted_mean = summary.get("counted_mean_final_1rm_kg")
        counted_sd = summary.get("counted_seed_std_kg")
        violation_counts = summary.get("constraint_violation_counts", {})
        violations = ", ".join(f"{violation}: {count}" for violation, count in sorted(violation_counts.items())) or "—"
        lines.append(
            f"| {name} | {summary['mean_final_1rm_kg']:.2f} | {f'{counted_mean:.2f}' if counted_mean is not None else '—'} | {summary['seed_std_kg']:.2f} | {f'{counted_sd:.2f}' if counted_sd is not None else '—'} | {summary['counted_episodes']}/{summary['episodes'] + summary['invalid_episodes']} | {summary['counted_seed_fraction']:.2f} | {summary['mean_planned_sessions']:.1f} | {summary['mean_transformed_sessions']:.1f} | {summary['mean_attempted_sessions']:.1f} | {summary['mean_completed_sessions']:.1f} | {summary['mean_missed_sessions']:.1f} | {summary['mean_pain_days']:.1f} | {summary['mean_household_strain']:.3f} | {summary['mean_household_strain_peak']:.3f} | {summary['mean_household_strain_high_weeks']:.1f} | {summary['mean_final_third_household_strain']:.3f} | {violations} | {summary['invalid_episodes']} |"
        )
    lines.extend(["", "## Paired ordering rates", ""])
    for name, rate in gate["pairwise_order_rates"].items():
        lines.append(f"- {name}: {rate:.1%}")
    lines.extend(
        [
            "",
            "## Adjacent mean separation",
            "",
            "| Pair | Mean gap (kg) | Pooled seed SD | Sigma |",
            "|---|---:|---:|---:|",
        ]
    )
    for pair, values in gate.get("adjacent_sigma", {}).items():
        lines.append(
            f"| {pair} | {values['gap_kg']:.3f} | {values['pooled_seed_std_kg']:.3f} | {values['sigma']:.3f} |"
        )
    lines.extend(["", "## Ablations", "", "A mechanic is considered active when removing it changes scores or decisions in the paired suite.", ""])
    for ablation in report.get("ablations", []):
        lines.append(
            f"- **{ablation['name']}**: score movement = {'YES' if ablation['changed_score'] else 'NO'}, decision movement = {'YES' if ablation['changed_decisions'] else 'NO'}, full gate after removal = {('PASS' if ablation['gate']['gate_pass'] else 'FAIL') if ablation['gate'].get('gate_enforced', True) else 'NOT ENFORCED'}"
        )
        lines.append(f"  - score deltas (kg): {ablation['score_delta_vs_full_kg']}")
        lines.append(f"  - decision deltas: {ablation['decision_delta_vs_full']}")
    rack = report.get("rack_ablation")
    if rack:
        lines.extend(
            [
                "",
                "## Home-rack ablation",
                "",
                f"- Enabled: {rack['enabled']['mean_final_1rm_kg']:.2f} kg (seed SD {rack['enabled']['seed_std_kg']:.2f})",
                f"- Disabled: {rack['disabled']['mean_final_1rm_kg']:.2f} kg (seed SD {rack['disabled']['seed_std_kg']:.2f})",
                f"- Paired mean swing: **{rack['mean_swing_kg']:.2f} kg**",
                "",
                "The disabled run removes the rack from the policy's available choices; it does not submit unequipped home sessions.",
            ]
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The six policies are fixed scripts, not optimized searches. Raw score is the average of hidden standardized-test projections at weeks 44, 48, and 52; the counted column applies pain days ≤14 plus sustained household strain: at least four weeks at or above 0.75, or a final-third (13-week) mean above 0.75. Final strain, peak strain, sleep debt, adherence, and invalid-action counts remain visible diagnostics.",
            "The historical separation and ordering fields remain visible for calibration and regression analysis. They are not a release claim and do not replace the held-out Phase 3 gate.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: dict[str, Any], json_path: str | Path, markdown_path: str | Path) -> None:
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(markdown_path).write_text(markdown_report(report), encoding="utf-8")
