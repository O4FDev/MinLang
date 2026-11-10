# Records

Dated records of past work: audits, measurement campaigns and agent-run
reports. They describe the tree as it was on their date and are not kept up to
date, so do not follow their commands or paths as current instructions; the
living documentation is the rest of `docs/`. `tools/garden.py` does not report
drift here. Add a record as `docs/records/YYYY-MM-DD-topic/` and link it from
the living document it supports. Raw per-agent logs stay in the run folder,
not here; git history keeps everything removed from this folder.

- [2026-10-19-security](2026-10-19-security/): the security audit, the review
  plan and its results. Current practice is in `docs/security-review.md`.
- [2026-10-20-perfcs](2026-10-20-perfcs/): runtime performance designs and
  matched measurements; the harness and raw data are in `experiments/perfcs/`.
- [2026-10-30-goal-run](2026-10-30-goal-run/): the 2026-10-30 performance goal
  run: final status, score history, the gap register with its repros
  (`gaps-repros/`), profile-backed causes of slowness, the cost of each
  guarantee (`tradeoffs.md`) and the plan for the next phase.
