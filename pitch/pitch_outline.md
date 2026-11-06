# ThaiNowcast — 3-minute pitch

**0:00–0:20 The gap.** Thailand learns its GDP 48 days after the quarter ends. For 4½ months a
year the single most important number about the economy is unknown. Banks, the Fiscal Policy
Office and investors fill the gap with guesses. We fill it with a number that updates every time
a statistic is published.

**0:20–0:50 What it is.** A pipeline that stores every Thai indicator with the day it became
public, rebuilds what was knowable on any date, and runs six nowcasting models from bridge
equations to a mixed-frequency factor model to gradient boosting, against a benchmark that is
hard to beat. Show the dashboard: today's nowcast of the current quarter, the 80% band, and the
bars that say *which releases moved it* (Google searches for travel, vehicle registrations,
private consumption).

**0:50–1:30 Why it is credible.** Three things nobody else in the room does: (1) a unit test that
fails if any model ever sees a number published after its nowcast date; (2) evaluation at the
moments that matter — end of month 1, 2, 3 and the day before the release — split into pre-COVID,
COVID and post-COVID, with significance tests; (3) each alternative data family switched on one at
a time, so we can say which ones pay for themselves and which ones add noise (some do).

**1:30–2:10 What we found (synthetic run / real run).** Accuracy improves monotonically as the
quarter's data arrive. The value of indicators is concentrated in turning points: in calm years
the AR benchmark is nearly as good; in 2020 it is off by more than twice as much. Adding noisy
alternative data to a linear model can hurt; the factor model absorbs short series the linear
models must discard. Intervals built from past errors cover about 80% of outcomes, as designed.
*(Replace with the real-data numbers from paper/tables once data/raw is populated.)*

**2:10–2:40 What it takes to go live.** One `make all`. The data shopping list is written
(docs/data_sources.md), fetch scripts exist, and the first-release GDP vintages are a
two-afternoon job. Partners who matter: BOT API access, NESDC press-release archive.

**2:40–3:00 Ask.** Data access and a pilot user who publishes a weekly Thai nowcast. The code is
open; the paper is drafted; the dashboard is live.

## Slides (8)

1. Title + one-line claim
2. The 48-day gap (timeline graphic from fig_release_calendar)
3. Architecture: registry → information sets → models → evaluation → dashboard
4. Live dashboard screenshot: nowcast, band, news bars
5. Backtest: RMSFE by origin (fig_rmsfe_gdp_yoy) — "it learns as data arrive"
6. Regimes: where the value is (tab_regime_gdp_yoy)
7. Ablation: which alternative data pay (fig_ablation)
8. Path to real data + ask

## Likely questions

- *Why not just use the BOT's forecast?* It is quarterly and discretionary; ours updates with
  every release and shows its reasoning.
- *Is 46 quarters enough?* For significance, barely; the monthly CPI track has 141 and the
  machinery is the same.
- *Revisions?* The scoring layer accepts first-release vintages; collecting them is on the plan.
- *Why does adding data hurt?* Short, noisy series shorten the training window of linear models
  or add regressors without signal; that is why the ablation exists and why the DFM is in the race.
