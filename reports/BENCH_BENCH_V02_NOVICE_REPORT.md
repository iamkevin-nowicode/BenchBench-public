# Bench-bench v0.2

## What We Learned from a 52-Week AI Coaching Benchmark

**A plain-language report for readers who have never seen a benchmark before**  
**Run date:** 15 August 2026  
**Run size:** 4 models × 10 public seeds × 52 simulated weeks = 40 episodes

> **The short answer:** Four AI models were asked to coach a fictional father through one simulated year of training, work, childcare, sleep disruption, money decisions, and missed sessions. The run found clear differences in training-load and volume planning, but it did not produce one clean overall winner—and it did not demonstrate that a model could infer Dave’s hidden personal traits.

## Executive summary

If you only read one section, read this one.

Bench-bench is a controlled test of whether an AI system can make a long sequence of connected decisions while the world keeps interrupting the plan. It is closer to managing a year than answering a question once.

### The main result

Among the three models whose results counted on every seed:

| Model | Counted mean final 1RM | Seed standard deviation | Counted seeds | Plain-language interpretation |
|---|---:|---:|---:|---|
| Grok 4.6 | **101.19 kg** | 1.66 kg | 10/10 | Eligible; tied with Muse within uncertainty |
| Muse Spark 1.2 | **101.03 kg** | 2.68 kg | 10/10 | Eligible; tied with Grok within uncertainty |
| GPT-5.6 Sol | **96.41 kg** | 1.47 kg | 10/10 | Eligible; lower than the other counted models in this run |
| Claude Opus 5 | **102.00 kg raw** | 2.42 kg | 7/10 | Highest raw average, but not an eligible leaderboard result |

Claude Opus 5 had the highest raw average, but three of its ten episodes exceeded the benchmark’s pain limit. A model with only 70% of its seeds counted does not receive a counted leaderboard mean. Its 102.00 kg remains visible as a diagnostic, not as a valid ranking entry.

Grok 4.6 and Muse Spark 1.2 were effectively tied. Their average difference was only 0.17 kg, and the uncertainty around that difference included zero. GPT-5.6 Sol was the clearest lower result: it finished about 4.78 kg below Grok and 4.62 kg below Muse on average.

### What the run says about AI planning

- The models were not equally good at choosing training loads and weekly volume.
- The top of the leaderboard is not cleanly separated. The evidence supports a Grok/Muse tie, not a confident claim that one is better.
- The benchmark caught a meaningful failure mode: a model can pursue a higher raw score while accumulating too many pain days, which voids the result.
- The benchmark did not test episode-specific adaptation strongly enough. A free-search oracle found only about 0.0115 kg of extra value from knowing each episode’s hidden traits in advance.
- The defensible claim is therefore narrow: Bench-bench measures long-horizon programming and configuration under disruption. It should not be cited as evidence of adaptive reasoning, general intelligence, or real-world coaching safety.

### What happened to the earlier run

The v0.1 pilot exposed important problems in the benchmark itself. Most importantly, Kimi K3 suffered **702 transport failures**, and four of its ten episodes contained no successful model decisions. Its old 90.48 kg leaderboard entry was retracted. In v0.2, Kimi was excluded rather than silently treated as a normal competitor, and transport failures were tracked separately from model-output errors.

That history is part of the result. A credible benchmark should show where its own measurement failed.

## 1. What is a benchmark?

A benchmark is a standardized test for a system. Every participant receives the same kind of task, follows the same rules, and is scored using the same procedure. The purpose is not to create a perfect picture of intelligence. The purpose is to make comparisons fair enough that differences in results mean something.

A simple analogy is a driving test. Two drivers do not take the same road on the same day, but they can still be compared if they follow the same course, the same traffic rules, and the same scoring rubric. Bench-bench does something similar for AI systems, except the course lasts 52 simulated weeks.

### Terms used in this report

| Term | Plain-language meaning |
|---|---|
| **Model** | The AI system being tested, such as Grok 4.6 or Muse Spark 1.2. |
| **Episode** | One complete simulated year for one model on one seed. |
| **Seed** | A fixed starting point that determines the hidden disruption pattern. Using the same seed lets models face comparable circumstances. |
| **Policy** | The model’s ongoing way of choosing training and life allocations. |
| **Raw score** | The final simulated bench press result, kept even when an episode violates a rule. |
| **Counted score** | A raw score from an episode that satisfies the benchmark’s validity rules and may enter the aggregate leaderboard. |
| **Repair** | A second chance after the model’s action fails validation. |
| **Automatic fallback** | A safe action substituted after the model’s action and its repair attempt do not produce a valid action. |
| **Transport failure** | A request could not reach or complete at the provider. This is an infrastructure event, not a model decision. |
| **Standard deviation** | A compact description of how much a model’s scores vary from seed to seed. |
| **Confidence interval** | A range describing uncertainty around a measured difference. If it includes zero, the run does not clearly separate the models on that comparison. |

The distinction between a counted score and a raw score is essential. A model should not be rewarded for a high result if it achieved that result by repeatedly violating the rules that define a valid episode.

## 2. What Bench-bench asks the model to do

The model is told to act as Dave’s coach for one year. It repeatedly receives an observation about Dave’s current situation and submits a structured weekly plan. The model must decide both what training to schedule and how to allocate scarce time, money, childcare, chores, partner coverage, and sleep protection.

### Who is Dave?

Dave is a fictional 38-year-old parent. He trained casually in his twenties, has not lifted seriously in years, and returns without a meaningful recent training base. He begins at an estimated 84 kg bench press and 84 kg body mass. The benchmark treats his trajectory as new-training progression, not the recovery of an old peak.

### What makes the task difficult?

- The model never sees Dave’s true underlying capacity, fatigue, or upcoming disruption schedule.
- The weekly estimated 1RM is noisy, so a single observation can be misleading.
- Planned sessions are not guaranteed to happen. Time, equipment, adherence, and cancellations can remove training that looked good on paper.
- Training competes with a finite weekly time ledger. The nominal pool is 900 minutes, but 180 minutes are fixed household obligations, leaving 720 discretionary minutes.
- The model can make an action invalid by overspending, violating a field rule, or prescribing an unsafe structure. It receives one repair opportunity; after that, a safe fallback can be used.
- The final score is not the noisy weekly estimate. It is based on three hidden standardized tests at weeks 44, 48, and 52 after a fixed three-day taper.

### What is scored?

The score is the average of those three hidden test results. This reduces the chance that one unusually good or bad final attempt decides the year.

More than 14 pain days voids the episode’s score. Household strain is also a hard constraint in the current configuration. Sleep debt is reported as a diagnostic and also affects the simulated recovery and readiness mechanics.

The model is told the objective and the scoring rules. That is intentional. A fair benchmark should not depend on hiding the basic rubric; it should depend on whether the model can make good decisions under the rubric’s actual constraints.

## 3. How the current run was conducted

| Item | Current v0.2 setting |
|---|---|
| Models | Claude Opus 5; GPT-5.6 Sol; Muse Spark 1.2; Grok 4.6 |
| Seeds | 400–409, ten public leaderboard seeds |
| Horizon | 52 simulated weeks per episode |
| Scoring tests | Hidden tests at weeks 44, 48, and 52; average after a fixed three-day taper |
| Validity rule | Pain days must be 14 or fewer; all expected seeds must count before an aggregate is reportable |
| Weekly budget | 900 minutes total, including a fixed 180-minute household reserve; 720 discretionary minutes remain |
| Artifact trail | 40 incremental transcripts, per-file hashes, an archive manifest, and a verification report |

### Why use seeds?

A seed is a reproducible recipe for the simulated world’s disruptions: the kinds of weeks that become harder, when sessions are lost, and how hidden state evolves. The models should not be judged on one lucky story. Running ten shared seeds lets us ask whether a difference repeats across different simulated lives.

### What was checked before looking at scores?

The analysis followed this order:

1. All 40 transcripts had to be present and complete for 52 weeks.
2. Every transcript had to carry the current engine and prompt hashes.
3. Endpoints had to be sanitized and credentials absent.
4. Transport failures had to be separate from rejected model outputs.
5. Every validation rejection had to match a documented constraint.
6. No episode could be dominated by a fallback-only year.
7. Only then were scores aggregated.

All seven checks passed for the current run. There were no transport failures, zero undocumented validation failures, and no episode with zero successful model decisions.

## 4. The results

The table below is the main result. A dash would mean that the benchmark intentionally does not publish a counted mean because not all ten seeds were valid. In this run, only Opus required that treatment.

| Model | Mean final 1RM | Seed SD | Range | Counted seeds | How to read it |
|---|---:|---:|---:|---:|---|
| **Grok 4.6** | **101.19 kg** | 1.66 kg | 98.26–104.19 | 10/10 | Eligible; tied with Muse within uncertainty. |
| **Muse Spark 1.2** | **101.03 kg** | 2.68 kg | 97.17–104.45 | 10/10 | Eligible; tied with Grok within uncertainty. |
| **GPT-5.6 Sol** | **96.41 kg** | 1.47 kg | 93.38–97.76 | 10/10 | Eligible; lower than the other counted models in this run. |
| **Claude Opus 5** | **102.00 kg raw** | 2.42 kg | 98.51–106.28 | 7/10 | Raw leader, but not eligible: three episodes exceeded 14 pain days. |

“1RM” means one-repetition maximum: the heaviest weight the simulated lifter could lift once under the standardized test. The unit is kilograms.

### Is there a winner?

Not cleanly.

Grok 4.6 and Muse Spark 1.2 are separated by only 0.17 kg on average. Their paired 95% interval runs from −1.37 kg to +1.70 kg. In plain language: this run does not justify saying one is better than the other.

GPT-5.6 Sol is the clearest lower result. It is about 4.78 kg below Grok 4.6 and 4.62 kg below Muse Spark 1.2 on average. Those differences were positive on nearly every shared seed.

Claude Opus 5 is a special case. Its raw average is highest, but the pain rule is part of the test, not an optional side metric. The correct conclusion is not “Opus wins.” The correct conclusion is “Opus produced the highest raw scores but failed the episode-validity rule on three seeds.”

### The scripted-expert reference

Bench-bench also includes a hand-written `scripted-expert` policy. It is a reference point, not another model and not a theoretical maximum. The current visual reference is 102.89 kg on burned development seeds. It helps answer “how does a model compare with a known, coherent strategy?” It does not mean that no legal policy may ever score higher.

### Pairwise comparisons

| Comparison | Average difference | Two-sided 95% paired interval | Wins / losses / ties |
|---|---:|---:|---:|
| Grok 4.6 − GPT-5.6 Sol | +4.78 kg | +3.21 to +6.36 | 10 / 0 / 0 |
| Muse Spark 1.2 − GPT-5.6 Sol | +4.62 kg | +2.60 to +6.63 | 9 / 0 / 1 |
| Opus 5 − GPT-5.6 Sol | +5.59 kg | +3.62 to +7.56 | 10 / 0 / 0 |
| Opus 5 − Muse Spark 1.2 | +0.97 kg | −1.16 to +3.11 | 6 / 4 / 0 |
| Opus 5 − Grok 4.6 | +0.81 kg | −0.88 to +2.50 | 5 / 5 / 0 |
| Grok 4.6 − Muse Spark 1.2 | +0.17 kg | −1.37 to +1.70 | 5 / 5 / 0 |

The Opus comparisons are diagnostic raw-score comparisons because three Opus episodes were voided. They are not valid counted leaderboard comparisons.

## 5. The ten seed results, shown directly

An average can hide important variation. This table shows the raw final score on every public seed. The seed numbers are not model ratings; they are different simulated years. Look for repeated patterns rather than one unusually high or low row.

| Seed | Opus 5 | Grok 4.6 | Muse Spark 1.2 | GPT-5.6 Sol |
|---:|---:|---:|---:|---:|
| 400 | 102.34 | 101.11 | 102.03 | 95.42 |
| 401 | 106.28 | 101.00 | 103.77 | 97.49 |
| 402 | 99.95* | 100.19 | 101.00 | 93.38 |
| 403 | 98.51* | 99.67 | 97.17 | 96.48 |
| 404 | 100.96 | 102.49 | 104.45 | 96.71 |
| 405 | 101.92 | 100.85 | 101.78 | 97.23 |
| 406 | 105.34 | 102.54 | 98.12 | 94.62 |
| 407 | 100.01 | 101.62 | 100.38 | 97.76 |
| 408 | 103.14* | 104.19 | 103.93 | 97.37 |
| 409 | 101.55 | 98.26 | 97.64 | 97.64 |

\* Opus episodes 402, 403, and 408 exceeded the pain limit. Their raw scores remain visible for auditability but do not enter the counted aggregate.

### What stands out

- Grok and Muse exchange the lead repeatedly. That is what a tie looks like in a small, noisy comparison.
- GPT is lower on every seed than Grok and lower on nine of ten seeds than Muse.
- Opus has the highest raw score on several seeds, but also the only invalid episodes in the current lineup.
- The spread between seeds is large enough that a single seed should never be treated as a definitive ranking.

## 6. Reliability: did the models actually play the game?

A benchmark result is useful only if the transcript shows the model actually interacting with the environment. Operational events are therefore reported separately from score.

| Model | Rejected decisions | Repair rate | Successful repairs | Automatic fallbacks | Transport failures |
|---|---:|---:|---:|---:|---:|
| Claude Opus 5 | 112 / 704 | 15.91% | 98 | 14 | 0 |
| GPT-5.6 Sol | 23 / 704 | 3.27% | 19 | 4 | 0 |
| Grok 4.6 | 22 / 704 | 3.13% | 12 | 10 | 0 |
| Muse Spark 1.2 | 14 / 704 | 1.99% | 6 | 8 | 0 |

A rejected decision means the model returned an action that did not pass validation. The model gets one repair attempt. A fallback is counted separately when the repaired action is still unavailable or invalid. A transport failure means the provider request itself failed; there were none in v0.2.

### Other audit counts

- **40/40** transcripts were complete and matched the current engine and prompt hashes.
- **185** validation or engine rejection messages matched a known inventory constraint.
- **22** model responses were malformed JSON and were counted as format errors, not hidden model successes.
- **36** automatic fallbacks occurred in total, all on weekly turns.
- No episode had zero successful model decisions.
- No episode had more than two automatic fallback decisions.
- **3** episodes exceeded the pain limit, all Claude Opus 5.
- **0** current episodes violated the household-strain constraint.

### Cost

| Model | Episodes | Cost per episode | Total cost |
|---|---:|---:|---:|
| Claude Opus 5 | 10 | $6.1209 | $61.2044 |
| GPT-5.6 Sol | 10 | $3.1290 | $31.2905 |
| Grok 4.6 | 10 | $1.1473 | $11.4734 |
| Muse Spark 1.2 | 10 | $1.0956 | $10.9562 |
| **All models** | **40** | — | **$114.9245** |

Costs include the recorded input, cached-input, visible-output, and provider-specific reasoning/thinking tokens. No cost was treated as zero merely because a provider returned a different usage shape.

## 7. What the first run taught us

The first live run was a pilot: it tested both the models and the benchmark infrastructure. It found problems that had to be fixed before the current public run could be treated as evidence.

| Problem found in v0.1 | Why it mattered | What changed for v0.2 |
|---|---|---|
| Kimi K3 had 702 transport failures. | A score produced mostly by failed requests or safe fallback actions is not a model result. | Kimi was excluded from the new lineup; transport failures are now reported separately and excluded from counted aggregates. |
| The old report counted Kimi 10/10. | It made an unscoreable model look comparable to the others. | The old leaderboard is explicitly retracted/superseded; the corrected historical report shows Kimi at 0/10 counted. |
| Prompt/schema mismatches caused repairs. | Models were sometimes punished for constraints that were not explained consistently. | A single constraint inventory now renders the prompt and powers the conformance test. |
| Volume stacking and zero-load credit exposed engine exploits. | A policy could earn stimulus without paying the intended training cost. | The engine added rep-rate coupling, load checks, stimulus limits, and a conserved time/resource ledger. |
| Unpriced household resources distorted choices. | A model could burn a resource without paying a meaningful cost. | Household strain became a hard constraint; sleep debt remains reported and affects simulated physiology. |
| Survivor-mean bias could hide invalid episodes. | Dropping bad seeds can make a risky policy look better than it is. | All expected seeds must count before an aggregate is reportable. |

### The Kimi correction, plainly

The archived v0.1 analyzer found ten Kimi transcripts, but all ten were excluded because they contained transport failures. Four episodes had zero successful model decisions. The old headline number of 90.48 kg therefore described a mixture of transport failure and fallback behavior, not a clean Kimi performance.

The corrected v0.1 report lists Kimi as **0/10 counted**. The current v0.2 report does not include Kimi in the model lineup.

### Historical v0.1 numbers

These numbers are context, not a causal before/after experiment. v0.1 used a different engine, prompt, and seed set.

The v0.1 pilot cost $127.63 in total. The current v0.2 public run cost $114.9245.

| Model | v0.1 counted mean | Counted seeds | Repair rate | Important note |
|---|---:|---:|---:|---|
| Claude Opus 5 | 100.06 kg | 10/10 | 19.20% | Valid in v0.1; not fully valid in v0.2. |
| Grok 4.5 | 99.19 kg | 10/10 | 8.42% | Not the current Grok 4.6 run. |
| Muse Spark 1.2 | 98.62 kg | 10/10 | 4.43% | Historical context only. |
| GPT-5.6 Sol | 93.86 kg | 10/10 | 2.22% | Historical context only. |
| Kimi K3 | — | 0/10 | 702 transport failures | Old 90.48 kg entry retracted. |

## 8. How the benchmark went from idea to report

The project developed in stages. Each stage changed the question from “can we make a simulation?” to “can we make a measurement that another person can inspect and reproduce?”

### Stage 1 — The idea

The starting idea was to test AI planning over a long horizon rather than through a single question. A model would need to make decisions now whose consequences appear weeks later.

### Stage 2 — The first simulator

The simulation added Dave, training sessions, family logistics, money, sleep, missed sessions, and standardized tests. This made the task feel like a year of life rather than a sequence of disconnected prompts.

The first lesson was that a realistic-looking simulation is not automatically a valid benchmark. Every mechanic needs a reason, a measurable effect, and a regression test.

### Stage 3 — Baselines and live pilots

Scripted baseline policies were used to understand the environment before trusting model results. Live runs then exposed prompt ambiguity, repair behavior, provider failures, and cases where the fallback played too much of the episode.

### Stage 4 — Attack the environment

The benchmark was deliberately attacked with volume stacking, compressed fallbacks, zero-load actions, mixed-focus weeks, boundary values, and purchase-order variants. This found strategies that were legal under the schema but violated the intended meaning of training.

The key lesson was that adversarial testing is necessary. A plausible-looking rule set can still reward the wrong behavior.

### Stage 5 — Ground and recalibrate

The engine added literature grounding, detraining checks, annual-gain guards, hidden tests, consistency drift, a constrained weekly ledger, sleep calibration, and resource costs. The goal was not to tune constants until one preferred model won. The goal was to keep the fictional athlete in a plausible range while making decisions matter.

### Stage 6 — Make the prompt honest

All enforced constraints were centralized in one inventory. The prompt is rendered from that inventory, and a conformance test checks both directions: every inventory rule appears in the prompt, and every stated constraint exists in the inventory.

This directly addressed the earlier problem where validation enforced limits that the prompt did not clearly state.

### Stage 7 — Rehearse and retain

The deterministic pipeline was run before paid calls. The live adapter smoke test exercised the actual scoring path. Transcripts were written incrementally, hashed, archived, and checked for credentials and mismatched configuration.

### Stage 8 — The current report

The current run uses four models and ten public seeds. It reports counted results, raw diagnostics, operational failures, costs, and limitations instead of hiding inconvenient records.

The final claim is narrower than the original ambition, but it is more defensible.

## 9. What this benchmark does measure

The evidence supports this focused claim:

> **Bench-bench measures long-horizon configuration and programming quality under recurring disruption.**

In practical terms, it tests whether an agent can:

- choose training loads and volumes that are neither too timid nor recklessly aggressive;
- plan around a finite time and money budget;
- continue making coherent decisions when sessions are lost and observations are noisy;
- respond to a changing weekly situation without losing the long-term objective; and
- stay within pain and household constraints across an entire year.

## 10. What it does not yet measure

- It does not provide strong evidence that a model can infer a particular episode’s hidden recovery capacity. A per-seed oracle search found only about 0.0115 kg of extra headroom over the best fixed policy.
- It does not establish general intelligence, common-sense competence, or real-world coaching safety.
- It does not prove that a model is physiologically realistic. The simulator is grounded by research and regression tests, but it remains a designed model of a fictional person.
- It does not support a causal claim that the model’s provider, architecture, or training method alone caused the ranking.
- It does not make the raw Opus average a valid leaderboard result, because three episodes violated the pain rule.

A benchmark becomes more credible when its public claim matches the part of the environment that actually separates systems. The current run shows meaningful differences in load and volume planning, but it does not show a strong episode-specific adaptation signal. That limitation tells the next version exactly what needs to improve.

## 11. Recommended next steps for v2

The next version should improve the measurement before expanding the number of models.

1. **Make hidden traits change the location of the best training choice.** A model should have to infer whether Dave responds better to more volume, more recovery, or a different exposure pattern.
2. **Make life-allocation choices vary across episodes.** If the same giveback or sleep setting wins on every seed, it is a checkbox, not a planning problem.
3. **Keep every scarce resource priced or scored.** An unpriced resource becomes a free switch that rewards the obvious answer rather than planning skill.
4. **Use held-out certification seeds.** Never tune constants on the seeds used to certify the benchmark. Report oracle headroom and a graded policy ladder before paying for another model run.
5. **Keep the all-seed validity rule.** A model that fails one part of the protocol should not receive a survivor-only average that hides the failure.
6. **Freeze the paid-run protocol in advance.** Choose the lineup, seed count, sampling policy, and pricing table before the run, then do not extend the seed set after seeing the results.

## Final takeaway

Bench-bench is most useful when read as a measurement instrument, not a beauty contest. It asks whether a model can sustain a reasonable strategy through a messy year.

The current version answers that question in a bounded way: Grok 4.6 and Muse Spark 1.2 are tied at the top among valid results, GPT-5.6 Sol is clearly lower in this run, Claude Opus 5 has the highest raw score but fails the pain constraint on three seeds, and the benchmark’s strongest remaining limitation is that it does not yet create enough value for episode-specific adaptation.

That is a narrower result than “the smartest model wins.” It is also the result the evidence can actually support.

## Appendix A. Reproducibility and audit details

This report was generated from the repository’s authoritative artifacts. No model calls were made to write it.

| Artifact | Purpose | Status |
|---|---|---|
| `reports/PUBLIC_LEADERBOARD.md` | Authoritative current public leaderboard | Generated; current hashes present |
| `reports/PUBLIC_LEADERBOARD.json` | Machine-readable current records and metrics | Used for current tables |
| `reports/PILOT_V0.1_LEADERBOARD.md` | Corrected historical v0.1 analysis | Kimi 0/10 counted; old final report superseded |
| `reports/CURRENT_VERIFICATION.md` | Reproduction and artifact checks | Overall PASS |
| `artifacts/v0.2-public-manifest.json` | Per-transcript hashes and archive metadata | 40 transcripts listed |
| `artifacts/v0.2-public-transcripts.tar.gz` | Archived public transcripts | Archive hash recorded in manifest |

### Configuration hashes

- **Engine/config:** `sha256:438c1d77d284450cd4e3da2eac9fcda83c45bfb81f7a67598c62763d96602a52`
- **Prompt:** `sha256:06d96111ac9db67e92f1a26d00f84e986ea95d13fc2acf0825b97be112ef0d27`
- **Transcript archive:** `sha256:3ad637dfec0960dfc1eef768e2fd21cdef442b565601dea3fa013dbcbe63a4b9`

## Appendix B. Questions a new reader may have

### Why not just rank the highest average?

Because a high average can be produced by invalid or risky episodes. The benchmark requires every expected seed to count before publishing an aggregate.

### Why show raw scores at all?

So reviewers can see the complete evidence, including excluded episodes, without letting invalid records decide the ranking.

### What does a 95% interval mean here?

It is a range describing uncertainty around a paired model difference under this ten-seed sample. If it includes zero, the run does not clearly separate the models on that comparison.

### Is a seed a random score?

No. It is a reproducible simulated world. Different seeds create different but repeatable life disruptions.

### Why do repairs matter?

They show whether a model can produce actions that follow the schema and mechanics. High repair rates can indicate format difficulty or prompt/schema confusion.

### What is the safest headline?

The benchmark found a clear lower tier in this run, a Grok/Muse tie at the top among valid results, and a real limitation around episode-specific adaptation.
