# Phase 0 transcript metrics

These definitions are the canonical vocabulary for runner transcripts,
supervisor logs, analyzers, and leaderboard reports. They are deliberately
separate because a transport retry is not a model-format failure, and a
repair prompt is not the same thing as a rejected output.

## Decision-level vocabulary

One decision is one weekly action request or one reactive interrupt request.

- **Rejected model output**: one model-call attempt that returned output but
  failed parsing, schema validation, or simulator validation. A transport
  failure is never a rejected model output.
- **Rejected-output decision**: a decision with at least one rejected model
  output. This is the numerator used by `repair_rate`.
- **Repair attempt**: a validation-error retry actually sent after a rejected
  model output. The legacy `repair_calls` field means this count.
- **Successful repair**: a repair attempt followed by a valid model response
  for the same decision.
- **Transport failure**: one provider/network/API attempt that failed before a
  model output was available, including timeout, HTTP 429, and other request
  failures. These are reported separately and never enter `repair_rate`.
- **Automatic fallback**: a runner- or simulator-generated fallback action
  used because no valid model action was available. It is reported separately
  from both repairs and transport failures.
- **Transformed session**: a planned session changed by a simulator rule after
  validation. The transformation must be surfaced in the weekly outcome and
  counted.

## Aggregate rules

- `repair_rate` is `rejected_output_decisions / decisions`.
- `rejected_model_outputs`, `repair_attempts`, `successful_repairs`,
  `transport_failures`, and `automatic_fallbacks` are all retained as separate
  counters.
- Missing or mismatched provenance invalidates an episode for aggregate use.
- A completed pilot episode with retried transport failures remains scoreable,
  but the transport audit marks it operationally contaminated; an incomplete
  episode or a transport-induced fallback is not silently treated as clean.
- Raw scores remain available for diagnostics, but only eligible episodes enter
  counted aggregates.
- Public leaderboard generation reads an explicit run root recursively and
  sorts transcript paths relative to that root. It must not discover archived
  or unrelated runs implicitly.
