# Enrich

Fills columns on existing rows, one disposable AI agent per row, rows in
parallel.

- One execution path: `runner.py` (the loop) → `agent.py` (the brain).
- Preview first: 10 rows computed and shown, nothing written.
- After your GO: the whole table, with `pending/running/done/failed`
  statuses as the checkpoint — re-running resumes where it stopped.

Say: *"enrichis la ville du siège de chaque entreprise"*.
