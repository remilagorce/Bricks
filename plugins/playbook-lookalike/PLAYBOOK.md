# Playbook: lookalike

A playbook is NOT a brick. Bricks are primitives that never call each other;
a playbook is a recipe the orchestrator (the workspace session) follows,
chaining bricks through the table. This file documents the composition.

## The motion

```
1. IMPORT      any source → companies rows tagged segment='seed'
               (crm-import-* brick, CSV, or dictated list)
2. ENRICH      every relevant enrich-company-* brick, scoped
   SEEDS       WHERE segment='seed' — runtime discovery: bricks
               installed tomorrow join this pass automatically
3. ANALYZE     compare enriched columns across seeds → shared traits
               + the discriminating signal(s) ("they are all hiring
               a manager") — confirmed by the user
4. SOURCE      the right find-* brick(s) for the confirmed pattern
   CANDIDATES  (find-crm-lookalike, find-fullenrich with filters,
               find-directory-scrape…)
5. FILTER      re-run ONLY the discriminating enrichment brick(s) on
               the candidates, cheapest first, then keep the rows
               matching the signal
```

## Dependencies

By design: none that are hardcoded. The playbook discovers installed bricks
at runtime and degrades gracefully — with only enrich-website installed the
analysis uses pitch/language/size; when enrich-company-hiring ships, hiring
joins the analysis with zero changes here. The only true dependency is the
core contract (segment column, statuses, db.py).
