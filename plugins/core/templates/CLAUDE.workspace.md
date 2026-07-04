# Bricks workspace

You are working inside a Bricks workspace: one isolated client context.
Everything you need to know about this client lives in `context/`. Read
`context/offer.md` and `context/icp.md` before any sourcing, enrichment or
writing task.

## Golden rules

1. Data flows through the database, never through the conversation. All reads
   and writes go through `python3 tools/db.py …`. Report receipts (counts),
   never dump rows into the chat — 3 sample names maximum when illustrating.
2. Statuses are the law: mark `running` before working on a cell, write the
   result and its final status immediately after each row. Select work with
   `WHERE <col>_status = 'pending' AND status != 'disqualified'`.
3. Nothing ever leaves this machine without a human: messages are written with
   status `draft` and are never sent.
4. Context drift: if the user mentions a company or an offer that contradicts
   `context/offer.md`, STOP and ask whether they want a new workspace or a
   context update.
5. Paid actions (FullEnrich enrichment/export) require announcing the volume
   and getting explicit confirmation first.

## This workspace

- Client / project: TODO (filled by workspace-init)
- Database: `bricks.db` — inspect with `python3 tools/db.py show`
