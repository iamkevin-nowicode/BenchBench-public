# Initial message to send Codex

Read every Markdown file in this repository before doing any work.

Bench-bench is a serious long-horizon agent benchmark. I am the product owner and benchmark designer, and I do not write code.

You own research support, architecture, implementation, tests, scripts, documentation, debugging, reproducibility, and demonstrations. Do not ask me to manually edit source code.

Challenge assumptions that weaken validity, safety, interpretability, reproducibility, or realism.

The benchmark has three distinct tracks:

1. model-only
2. frozen-web tool use
3. open-web experimental

Frozen-web is the recommended official tool-use track. Core simulator outcomes must remain deterministic. Search results and language models may influence decisions but may never directly decide world state or score.

Begin only with `02_MILESTONE_0_ARCHITECTURE.md`. Do not implement the simulator yet.

At the end provide a plain-English summary, files changed, commands run, tests or validation performed, unresolved assumptions, decisions requiring my approval, and your recommended next milestone. Do not proceed without approval.
