"""Instrument starter agent.

Handles the "How do I start an X" / "I want to begin investing in Y" family
for any actionable instrument (SIP, mutual fund, ETF, gold ETF, FD, bond,
NCD, stock).

Gates on profile completeness:

  - If the profile is missing key fields (age, amount, horizon, risk),
    return an intro narrative + a FormBlock the UI renders inline.
    The user fills the form; the frontend resubmits POST /api/ask with the
    captured fields + intent=instrument_starter, and this agent re-runs
    with a complete profile.

  - If the profile is complete, return a focused intro narrative. The
    plan's other steps (projection.sip_fv, monte_carlo, allocation,
    recommender.consensus, search.term_resources, sentiment) populate the
    rest of the envelope via Assembly.

Inputs (AgentInput):
  - user.age, user.amount, user.horizon_years, user.risk_tolerance
  - scenario               : CurrentScenario | None
  - upstream['explanation']: Explanation | None (from education layer)
  - upstream['instrument_type_resolved']: InstrumentType | None
"""
from __future__ import annotations

from app.schemas import (AgentInput, AgentOutput, Explanation, FormBlock,
                          InstrumentType, RiskLevel)

_DISCLAIMER = (
    "Educational guidance based on public data and rule-of-thumb math. "
    "Not financial advice — talk to a registered adviser before committing money."
)


# Per-instrument copy & form tweaks ------------------------------------------

_LUMP_SUM_INSTRUMENTS = {
    InstrumentType.FD, InstrumentType.BOND, InstrumentType.NCD,
    InstrumentType.STOCK,
}


def _instrument_meta(inst: InstrumentType | None, country: str) -> dict:
    currency = "₹" if country == "IN" else "$" if country == "US" else "£"
    base = {"currency": currency}
    if inst == InstrumentType.SIP:
        return {**base, "label": "SIP", "what": "Systematic Investment Plan",
                "amount_label": f"Monthly SIP amount ({currency})",
                "amount_placeholder": "e.g. 5000",
                "amount_min": 500,
                "intro": ("Starting a SIP is one of the simplest ways to "
                           "invest — you commit a fixed amount every month "
                           "into a mutual fund. Rupee-cost averaging smooths "
                           "out market swings over time.")}
    if inst == InstrumentType.MUTUAL_FUND:
        return {**base, "label": "mutual fund",
                "what": "diversified, professionally managed pool of investments",
                "amount_label": f"Monthly investment ({currency})",
                "amount_placeholder": "e.g. 5000",
                "amount_min": 500,
                "intro": ("Mutual funds pool your money with thousands of "
                           "others and a fund manager invests it across many "
                           "stocks or bonds. Beginners almost always start "
                           "with an index fund or a flexi-cap fund.")}
    if inst == InstrumentType.ETF:
        return {**base, "label": "ETF",
                "what": "Exchange-Traded Fund",
                "amount_label": f"Amount per buy ({currency})",
                "amount_placeholder": "e.g. 5000",
                "amount_min": 100,
                "intro": ("An ETF is a basket of stocks (or gold, silver, "
                           "bonds) that trades like a single share. Gold "
                           "ETFs and broad-market index ETFs (Nifty 50, "
                           "S&P 500) are the most common beginner choices.")}
    if inst == InstrumentType.FD:
        return {**base, "label": "FD",
                "what": "Fixed Deposit",
                "amount_label": f"Lump sum to deposit ({currency})",
                "amount_placeholder": "e.g. 100000",
                "amount_min": 1000,
                "intro": ("Fixed Deposits lock your money for a tenure at a "
                           "guaranteed interest rate. The safest option for "
                           "money you can't afford to risk.")}
    if inst == InstrumentType.BOND:
        return {**base, "label": "bond",
                "what": "fixed-income debt security",
                "amount_label": f"Lump sum ({currency})",
                "amount_placeholder": "e.g. 50000",
                "amount_min": 1000,
                "intro": ("Bonds lend money to the government or a company "
                           "in exchange for fixed interest payments. G-Secs "
                           "(Government Securities) are the lowest-risk INR "
                           "fixed-income option.")}
    if inst == InstrumentType.NCD:
        return {**base, "label": "NCD",
                "what": "Non-Convertible Debenture",
                "amount_label": f"Lump sum ({currency})",
                "amount_placeholder": "e.g. 10000",
                "amount_min": 1000,
                "intro": ("NCDs are corporate debt with fixed coupons. "
                           "Higher yields than FDs/G-Secs but more credit "
                           "risk — always check the rating.")}
    if inst == InstrumentType.STOCK:
        return {**base, "label": "stocks",
                "what": "individual company shares",
                "amount_label": f"Amount per buy ({currency})",
                "amount_placeholder": "e.g. 5000",
                "amount_min": 100,
                "intro": ("Buying stocks means owning a slice of a company. "
                           "More upside than mutual funds, but also more "
                           "risk. Most beginners are better served by index "
                           "funds; if you want direct stocks, start with "
                           "well-established large-caps.")}
    return {**base, "label": "investment", "what": "investment",
            "amount_label": f"Amount ({currency})",
            "amount_placeholder": "e.g. 5000",
            "amount_min": 500,
            "intro": ("Let's set up a starter plan. We'll suggest where to "
                      "put your money, project the range of outcomes, and "
                      "list reading material.")}


def _missing_fields(input: AgentInput) -> list[str]:
    u = input.user
    missing: list[str] = []
    if u.age is None:
        missing.append("age")
    if u.amount is None or u.amount <= 0:
        missing.append("amount")
    if u.horizon_years is None or u.horizon_years <= 0:
        missing.append("horizon_years")
    if u.risk_tolerance is None:
        missing.append("risk_tolerance")
    return missing


def _form_block(meta: dict, country: str) -> FormBlock:
    currency = meta["currency"]
    return FormBlock(
        title=f"Tell us a bit about you (for a {meta['label']} plan)",
        note=("We use these to project realistic outcomes and suggest funds "
               "that match your profile. None of this is stored against "
               "your real identity — it just personalises this conversation."),
        intent="instrument_starter",
        submit_label="Build my plan",
        fields=[
            {
                "name": "age",
                "label": "Your age",
                "kind": "number",
                "min": 18, "max": 80, "step": 1,
                "placeholder": "e.g. 28",
                "required": True,
            },
            {
                "name": "income_bracket",
                "label": (f"Monthly take-home income ({currency})"),
                "kind": "select",
                "required": False,
                "options": _income_options(country),
            },
            {
                "name": "amount",
                "label": meta["amount_label"],
                "kind": "number",
                "min": meta["amount_min"], "max": 10_000_000, "step": 500,
                "placeholder": meta["amount_placeholder"],
                "required": True,
            },
            {
                "name": "horizon_years",
                "label": "Investment horizon (years)",
                "kind": "number",
                "min": 1, "max": 40, "step": 1,
                "placeholder": "e.g. 10",
                "required": True,
            },
            {
                "name": "risk_tolerance",
                "label": "Comfort with ups and downs",
                "kind": "select",
                "required": True,
                "options": [
                    {"value": RiskLevel.LOW.value,
                       "label": "Low — I'd panic in a 20% drop"},
                    {"value": RiskLevel.MODERATE.value,
                       "label": "Moderate — short-term swings are fine"},
                    {"value": RiskLevel.HIGH.value,
                       "label": "High — I can stomach a -30% year"},
                    {"value": RiskLevel.VERY_HIGH.value,
                       "label": "Very high — full equity, long horizon"},
                ],
            },
            {
                "name": "goal",
                "label": "Goal (optional)",
                "kind": "text",
                "required": False,
                "placeholder": "e.g. retirement, house, kid's college",
            },
        ],
    )


def _income_options(country: str) -> list[dict]:
    if country == "IN":
        return [
            {"value": "lt_25k",  "label": "Under ₹25,000"},
            {"value": "25k_50k", "label": "₹25,000 – ₹50,000"},
            {"value": "50k_1L",  "label": "₹50,000 – ₹1,00,000"},
            {"value": "1L_2L",   "label": "₹1,00,000 – ₹2,00,000"},
            {"value": "gt_2L",   "label": "Over ₹2,00,000"},
        ]
    if country == "US":
        return [
            {"value": "lt_3k",   "label": "Under $3,000"},
            {"value": "3k_6k",   "label": "$3,000 – $6,000"},
            {"value": "6k_10k",  "label": "$6,000 – $10,000"},
            {"value": "10k_20k", "label": "$10,000 – $20,000"},
            {"value": "gt_20k",  "label": "Over $20,000"},
        ]
    return [
        {"value": "lt_2k",   "label": "Under £2,000"},
        {"value": "2k_4k",   "label": "£2,000 – £4,000"},
        {"value": "4k_8k",   "label": "£4,000 – £8,000"},
        {"value": "8k_15k",  "label": "£8,000 – £15,000"},
        {"value": "gt_15k",  "label": "Over £15,000"},
    ]


def _intro_form_narrative(meta: dict, explanation: Explanation | None) -> str:
    intro = meta["intro"]
    if explanation:
        intro += f" {explanation.plain_english}"
    return (intro + " To build you a plan with projected outcomes and picks, "
                     "fill in the four short fields below.")


def _intro_complete_narrative(input: AgentInput, meta: dict,
                                explanation: Explanation | None) -> str:
    u = input.user
    currency = meta["currency"]
    risk = u.risk_tolerance.value if u.risk_tolerance else "moderate"
    is_lump = (input.user.instrument_type or InstrumentType.SIP) in _LUMP_SUM_INSTRUMENTS
    cadence = "lump sum" if is_lump else "/month"
    base = (
        f"Here's your starter plan for a {currency}{u.amount:,.0f} {cadence} "
        f"into {meta['label']} over {u.horizon_years} years at a {risk} risk "
        "level. Below you'll find the suggested split, projected outcomes, "
        "fund picks, reading material, and what other beginners typically do."
    )
    if explanation:
        base += f" {explanation.why_it_matters}"
    return base


async def run(input: AgentInput) -> AgentOutput:
    explanation: Explanation | None = input.upstream.get("explanation")
    inst = (input.upstream.get("instrument_type_resolved")
             or input.user.instrument_type
             or InstrumentType.SIP)
    if not isinstance(inst, InstrumentType):
        try:
            inst = InstrumentType(inst)
        except Exception:
            inst = InstrumentType.SIP

    meta = _instrument_meta(inst, input.user.country)
    missing = _missing_fields(input)

    if missing:
        narrative = _intro_form_narrative(meta, explanation)
        form = _form_block(meta, input.user.country)
        return AgentOutput(
            narrative=narrative,
            structured={
                "needs_profile": True,
                "missing_fields": missing,
                "instrument": inst.value,
                "extra_blocks": [form.model_dump()],
            },
            disclaimer=_DISCLAIMER,
        )

    narrative = _intro_complete_narrative(input, meta, explanation)
    return AgentOutput(
        narrative=narrative,
        structured={"needs_profile": False, "instrument": inst.value},
        disclaimer=_DISCLAIMER,
    )
