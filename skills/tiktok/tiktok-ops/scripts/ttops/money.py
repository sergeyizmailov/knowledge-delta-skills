"""Budget validation against TikTok's per-currency verification ratios.

The 100x-budget guard. TikTok's minimum budget is not a dollar figure: it is
``base_range x verification_ratio(currency)``, and several currencies accept no
decimal places at all. A USD-shaped template landing on a JPY or IDR account is
wrong by two orders of magnitude, in the direction that spends.

Source: TikTok doc 1737585839634433 "Budget verification ratio and value range
for each currency", and 1739381246298114 "Budget". Fetched 2026-09-14.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal, ROUND_DOWN

_HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_HERE, "currencies.json")) as _fh:
    CURRENCIES = json.load(_fh)

# Base daily budget ranges, before the currency ratio is applied.
# NOTE: TikTok's own pages disagree on the standard campaign floor — the Budget
# guide says 20, the per-currency table says the base range starts at 50. The
# per-currency table is the one the verification logic is described against, so
# we use 50 and surface the conflict rather than silently picking the lower one.
BASE_CAMPAIGN_MIN = Decimal("50")
BASE_ADGROUP_MIN = Decimal("20")
BASE_STORE_MIN = Decimal("10")  # PRODUCT_SALES + STORE/SHOWCASE product source
BASE_MAX = Decimal("10000000")

CAMPAIGN_MIN_CONFLICT = (
    "TikTok's Budget guide states a 20-unit campaign minimum while its per-currency "
    "table states a base range starting at 50. ttops enforces 50 to avoid rejection. "
    "If a live call proves 20 is accepted for this account, record it in .notes/."
)


class BudgetError(ValueError):
    pass


def currency_info(currency: str):
    code = (currency or "").upper()
    if code not in CURRENCIES:
        raise BudgetError(
            f"Unknown currency {code!r}. ttops knows {len(CURRENCIES)} TikTok currencies; "
            "if this account really uses it, re-check TikTok doc 1737585839634433 "
            "and add the ratio/precision to currencies.json rather than guessing."
        )
    return CURRENCIES[code]


def decimals_for(currency: str) -> int:
    """0 for the nine integer-only currencies (CLP, HUF, IDR, ISK, JPY, KRW, PYG, TWD, VND), else 2."""
    return 0 if Decimal(str(currency_info(currency)["precision"])) >= 1 else 2


def bounds(currency: str, level: str, store_product_source: bool = False):
    """Return (min, max) allowed budget in MAJOR units for this account currency."""
    if level not in ("campaign", "adgroup"):
        raise BudgetError(f"level must be 'campaign' or 'adgroup', got {level!r}")
    ratio = Decimal(str(currency_info(currency)["ratio"]))
    if store_product_source:
        base_min = BASE_STORE_MIN
    else:
        base_min = BASE_CAMPAIGN_MIN if level == "campaign" else BASE_ADGROUP_MIN
    return (base_min * ratio, BASE_MAX * ratio)


def quantize(amount, currency: str) -> Decimal:
    """Round DOWN to the currency's allowed precision. Down, never up: rounding a
    budget up is spending money the operator did not authorise."""
    places = decimals_for(currency)
    exp = Decimal(1) if places == 0 else Decimal("0.01")
    return Decimal(str(amount)).quantize(exp, rounding=ROUND_DOWN)


def validate(amount, currency: str, level: str, *, store_product_source=False):
    """Validate a budget in major units. Returns the quantized Decimal.

    Raises BudgetError with an actionable message naming the currency and the
    allowed range in major units — never a bare 'invalid budget'.
    """
    value = Decimal(str(amount))
    if value <= 0:
        raise BudgetError(f"Budget must be positive, got {value}")

    places = decimals_for(currency)
    if places == 0 and value != value.to_integral_value():
        raise BudgetError(
            f"{currency} accepts whole units only (precision 1). "
            f"{value} has decimals — did a USD template land on a {currency} account?"
        )

    low, high = bounds(currency, level, store_product_source)
    if value < low:
        raise BudgetError(
            f"{level} budget {value} {currency} is below TikTok's minimum {low} {currency} "
            f"(base {'10' if store_product_source else (BASE_CAMPAIGN_MIN if level=='campaign' else BASE_ADGROUP_MIN)} "
            f"x verification ratio {currency_info(currency)['ratio']:g} for {currency}). "
            + (CAMPAIGN_MIN_CONFLICT if level == "campaign" and not store_product_source else "")
        )
    if value >= high:
        raise BudgetError(
            f"{level} budget {value} {currency} is at or above TikTok's maximum {high} {currency}. "
            "Refusing — a budget this size is almost always a units error."
        )
    return quantize(value, currency)


def min_increase_floor(current_spend, currency: str) -> Decimal:
    """TikTok requires an updated budget to be at least 105% of current spend.

    Not 100%. A decrease below this line is rejected, which surfaces as an
    unexplained error if you do not know the rule.
    """
    floor = Decimal(str(current_spend)) * Decimal("1.05")
    places = decimals_for(currency)
    exp = Decimal(1) if places == 0 else Decimal("0.01")
    # Round UP here: the floor must not be understated.
    from decimal import ROUND_UP
    return floor.quantize(exp, rounding=ROUND_UP)


def check_update(new_budget, current_spend, currency: str, level: str,
                 *, store_product_source=False):
    """Validate a budget *update*: range rules plus the 105%-of-spend floor."""
    value = validate(new_budget, currency, level, store_product_source=store_product_source)
    floor = min_increase_floor(current_spend, currency)
    if value < floor:
        raise BudgetError(
            f"New {level} budget {value} {currency} is below 105% of current spend "
            f"({current_spend} {currency} -> floor {floor} {currency}). TikTok rejects this. "
            "Either raise the budget above the floor or pause instead of cutting."
        )
    return value


def describe(amount, currency: str) -> str:
    """Human-facing budget string. Always major units, always names the currency —
    this is the string an operator confirms before spend is authorised."""
    places = decimals_for(currency)
    value = quantize(amount, currency)
    return f"{value:,.{places}f} {currency}"
