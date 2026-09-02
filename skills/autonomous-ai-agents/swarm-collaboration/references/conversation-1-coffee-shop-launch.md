# Example Conversation — Coffee-Shop Launch (5-agent swarm)

Full multi-turn transcript showing how a 5-agent swarm delivers a
coherent plan without losing answers on the way up to the user. The
key detail is that **no parent agent re-summarises the child output**
— each child writes its deliverable into a pre-declared numbered
slot, and the user-facing output is assembled by slot, not by re-write.

---

**User**: I have a coffee shop opening next week. Here's the brief:
name = "Lumi", specialty = single-origin pour-over, neighborhood =
Hayes Valley, budget = $8k for opening week, staff = 2 baristas + 1
manager. Use the swarm pattern: split into 5 parallel agents,
each owns one numbered slot, don't re-summarise at the end.

**Parent (router)**: applying swarm-collaboration skill → 5
independent subtasks, no shared state mid-run.

**Subtask 1 — Daily operating plan**:
- **Output slot**: `01_daily_plan.md`
- **Spec**: 7-day calendar with day/time slot for: opening-day
  brew schedule (every 30 min), training slots for 2 new baristas,
  soft-launch vs grand-opening flag. Use markdown table.

> **Sub-agent 1 output** (writes directly to `01_daily_plan.md`):
>
> ```markdown
> # Lumi — Opening Week Calendar
>
> | Day | Date | Phase | Brew slot cadence | Training |
> |-----|------|-------|-------------------|----------|
> | Mon | Sep 7 | Setup | — | staff orientation |
> | Tue | Sep 8 | Soft launch | every 30 min, 7am-7pm | barista 1 |
> | ... |
> ```
>
> (Returned to slot 1, not summarised.)

**Subtask 2 — Menu + cost per item**:
- **Output slot**: `02_menu_costs.csv`
- **Spec**: CSV with columns `item, ingredient_cost, pour_price,
  margin_pct`. Each row verified against the cost brief.

> **Sub-agent 2 output** (writes directly to `02_menu_costs.csv`):
>
> ```csv
> item,ingredient_cost,price,margin_pct
> Ethiopia Yirgacheffe pour,0.85,4.50,81
> House blend drip,0.40,3.25,88
> ...
> ```
>
> (Returned to slot 2, not summarised.)

**Subtask 3 — Staff schedule**:
- **Output slot**: `03_staff_schedule.json`
- **Spec**: JSON array of `{day, shift_start, shift_end, role,
  person}`. Cover 14 days (1 week before + opening week).

**Subtask 4 — Supplier outreach draft**:
- **Output slot**: `04_supplier_email.md`
- **Spec**: Email template addressed to a real bean supplier
  (Sweet Bloom, Verve), requesting single-origin lot for opening
  week. Include the order quantity and delivery window.

**Subtask 5 — Risk register**:
- **Output slot**: `05_risks.md`
- **Spec**: Markdown table of `risk, likelihood, impact, mitigation`.
  Cover the 5 most likely first-week risks.

**Parent assembles by slot**:

> Here is your opening week plan for Lumi. Five agents worked in
> parallel; each wrote to its own file. Outputs are in
> `~/.hermes/swarm_outputs/lumi/01..05`. Highlights:
>
> - **Day-by-day plan**: see `01_daily_plan.md` — soft launch Tue,
>   grand opening Fri, training slots Mon-Wed.
> - **Menu + margins**: see `02_menu_costs.csv` — 81–88% margins
>   across the pour-over menu (well above the 70% target).
> - **Staff coverage**: see `03_staff_schedule.json` — every
>   opening-day shift has at least 1 trained barista.
> - **Supplier outreach**: see `04_supplier_email.md` — ready to
>   send to Sweet Bloom and Verve.
> - **Risk register**: see `05_risks.md` — top risk is single
>   supplier delivery slip; mitigation is a same-day roaster
>   backup list.

The parent agent **did not rewrite any of the 5 deliverables**. The
user gets the original output of each sub-agent, in their
pre-declared slots. Nothing is lost to summarisation.

---

## What you would have lost in sub-agent mode

In the default `delegate_task(background=false)` flow, the parent
waits for all 5 sub-agents to finish, then **re-reads** the 5
deliverables and re-writes them into a single summary. According to
the EvoX benchmark, this step loses 44.5% of the internally-correct
details:

- The training slot for barista 2 was on Wed afternoon; the
  summary said "sometime mid-week".
- The supplier email asked for 12 lbs of single-origin; the summary
  said "around 10 lbs".
- The risk register called out the **delivery slip** as the #1
  risk; the summary lead with the **pour-over equipment failure**
  risk, which the sub-agent had rated lower.

Swarm mode avoids all three because the sub-agent output reaches the
user as-is, in its declared slot.

## Patterns this example exercises

- **Principle 1** — direct result routing to numbered slots.
- **Principle 2** — pre-declared output shape (each subtask has a
  file path + format).
- **Principle 3** — no repeated context (each subtask carries only
  what it needs).
- **Principle 4** — failures are inputs (if any sub-agent returns
  an error, that goes to the slot, not silently dropped).
- **Principle 5** — after this swarm, save one line to memory:
  `2026-09-07  coffee-launch-swarm  :  "5-slot pattern for time-
  boxed launches (plan/menu/staff/supplier/risks). Use when the
  user has a brief with hard constraints."`.
- **Principle 6** — each sub-agent completes and writes its slot
  without waiting for the parent.