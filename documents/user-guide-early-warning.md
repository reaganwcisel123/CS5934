# Using the Early Warning tab

A short guide for clinic staff. No statistics background needed.

## What this tab is for

It estimates how much of certain reportable illnesses Virginia is likely to see
over the **next four weeks**, and roughly what supplies that implies — so you can
order before you need it rather than after.

## The most important thing on the page

The county numbers are **allocated, not measured.**

The state health data behind this tab is reported for Virginia as a whole. There
is no county-level count to show you. So the tab takes the statewide forecast and
divides it up by how many people live in each county.

That means a county number tells you **roughly how much of the state's expected
load your area represents.** It is not a count of sick people near you. If ten
neighbours have the same illness this week, that will not appear here.

You will see an "allocated, not observed" tag on every county figure. That tag is
the point, not fine print.

## Reading the statewide list

Each row is one illness:

- **The number on the right** is the expected statewide case count over the next
  four weeks.
- **The range underneath** (for example `32.9 – 55.0`) is the realistic span. Plan
  against the range, not the single number.
- **The bar** shows that range visually. **A wider bar means less certain.** A
  narrow bar is a confident forecast; a wide one is a rough guess.

### Two labels to watch for

**"no forecast"** — there is not enough reporting history for this illness. It
does **not** mean the illness is rare or absent. It means we do not know. Treat it
as a blank, never as an all-clear.

**"13w stale"** — the most recent report for this illness is 13 weeks old. Older
reporting means a less trustworthy forecast. A large stale number should prompt a
phone call to your health district rather than a purchase order.

## Reading your county

Pick your county from the dropdown. For each illness you get the allocated case
range and a supply table:

| Item | Units to hold |
|---|---|
| Pertussis PCR swab | 4 – 9 |

Those are **planning ranges**, matched to the forecast range. The low number is a
reasonable floor and the high number a reasonable ceiling.

Two things about those quantities:

- They come from a **written mapping a person can read and argue with**
  (`data/reference/condition_supply_map.yml`), not from the model. Each entry says
  why an illness implies an item.
- They are **not a purchase order and not a clinical protocol.** They do not know
  your patient mix, your storage, your referral patterns, or your budget.

## If your county is nonmetro

If your county is nonmetro-adjacent (RUCC 4–6), **treat these numbers as a floor.**

Splitting by population assumes illness follows headcount. It does not account for
how hard care is to reach. Our own analysis found nonmetro counties come out about
1.5 percentage points below what their access burden implies — the largest gap of
any group, larger than the most rural counties. So the figures likely understate
what you will actually see.

## What this tab will not do

- It will not tell you an outbreak is happening near you.
- It will not tell you which patients are affected.
- It will not tell you anything about a specific person.
- It cannot see illnesses outside the eleven it tracks.

## The short version

This is a planning aid. It informs a decision; it does not make one. Your
judgement about your own community beats the model, and you are expected to
override it. If a number looks wrong for your area, it may well be — see the
model card for where the forecast is weakest.
