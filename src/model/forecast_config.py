"""Configuration for the notifiable-disease forecast (US-049 / US-050).

Separate from model/config.py so the county/patient risk models and the
surveillance forecast stay independently tunable.
"""

from __future__ import annotations

RANDOM_STATE = 42

# Weeks ahead to forecast. Four gives a clinic time to order and receive stock
# without extrapolating past what 237 weeks of history supports.
HORIZON_WEEKS = 4

LAG_WEEKS = [1, 2, 3, 4, 8]
ROLLING_WINDOWS = [4, 8]
SEASONAL_LAG_WEEKS = 52

# Below this many reported weeks a series returns "insufficient history" rather
# than a low-confidence number. Two years, so the 52-week seasonal lag is usable.
MIN_HISTORY_WEEKS = 104

# Conditions forecast by default. Chosen from observed Virginia volume and
# reporting continuity (2022 W1 - 2026 W28), filtered to those a rural clinic can
# actually stock for. Counts are reported weeks out of 237.
FORECAST_CONDITIONS = [
    "Chlamydia trachomatis infection",                     # 229 wks, ~682/wk
    "Gonorrhea",                                           # 230 wks, ~227/wk
    "Campylobacteriosis",                                  # 226 wks, ~32/wk
    "Salmonellosis (excluding Salmonella Typhi infection and Salmonella Paratyphi infection)",
    "Shiga toxin-producing Escherichia coli (STEC)",       # 206 wks, ~7/wk
    "Shigellosis",                                         # 222 wks, ~6/wk
    "Cryptosporidiosis",                                   # 218 wks, ~5/wk
    "Giardiasis",                                          # 217 wks, ~4/wk
    "Pertussis",                                           # 150 wks, ~7/wk
    "Legionellosis",                                       # 155 wks, ~3/wk
    "Tuberculosis",                                        # 175 wks, ~3/wk
]

# How a state-level forecast becomes county numbers. NNDSS has no county
# dimension, so every county figure is allocated, never observed. This string is
# carried through the API and rendered on the dashboard.
ALLOCATION_METHOD = "population_share_of_state"
ALLOCATION_DISCLOSURE = (
    "Allocated from Virginia state-level NNDSS surveillance by county population "
    "share. Not an observed county case count."
)

TARGET_COLUMN = "cases"
