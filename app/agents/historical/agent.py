"""Historical Behavior agent."""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from app.config import settings
from app.schemas import AgentInput, AgentOutput, HistoricalReport

_DISCLAIMER = (
    "Past performance does not guarantee future returns. "
    "This is educational information, not financial advice.")


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.3,
    )


_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are FinSight, a beginner-friendly financial educator. Frame the "
     "historical numbers below in 4-6 sentences. Be concrete about what "
     "happened (return, drawdown), set context for why the era mattered, "
     "and gently note what a beginner might take away — without ever "
     "telling them what to buy or sell. End with the exact line: "
     "'Past performance does not guarantee future returns.'"),
    ("user",
     "Era: {era_label} ({start} to {end})\n"
     "Era context: {era_summary}\n\n"
     "Instrument: {instrument_label} ({ticker})\n"
     "Period return: {period_return}\n"
     "Max drawdown:  {max_dd}\n"
     "Annualized volatility (window): {vol}\n"
     "Notes: {notes}\n\n"
     "Write the framing.")
])


async def run(input: AgentInput) -> AgentOutput:
    report: HistoricalReport | None = input.upstream.get("historical_report")

    if report is None:
        return AgentOutput(
            narrative=("We couldn't match your question to one of our "
                        "tracked historical eras. Try mentioning a specific "
                        "year (e.g. '2008') or event (COVID, taper, GFC)."),
            disclaimer=_DISCLAIMER,
        )

    perf = report.performance
    if perf is None or perf.period_return_pct is None:
        return AgentOutput(
            narrative=(f"For {report.instrument_label} during "
                        f"{report.era.label}, we don't have enough price "
                        "data on file to compute a window return. Try a "
                        "broader instrument (NIFTY 50, S&P 500)."),
            structured=_structured(report),
            disclaimer=_DISCLAIMER,
        )

    try:
        chain = _PROMPT | _llm()
        response = await chain.ainvoke({
            "era_label": report.era.label,
            "start": report.era.start_date.isoformat(),
            "end": report.era.end_date.isoformat(),
            "era_summary": report.era.summary or "(no extra context)",
            "instrument_label": report.instrument_label,
            "ticker": report.ticker,
            "period_return": f"{perf.period_return_pct:+.2f}%",
            "max_dd": (f"{perf.max_drawdown_pct:.2f}%"
                        if perf.max_drawdown_pct is not None else "n/a"),
            "vol": (f"{perf.annualized_volatility_pct:.2f}%"
                     if perf.annualized_volatility_pct is not None else "n/a"),
            "notes": "; ".join(perf.notes) or "(none)",
        })
        narrative = (response.content if hasattr(response, "content")
                      else str(response))
    except Exception as exc:
        narrative = _fallback_narrative(report)
        return AgentOutput(
            narrative=narrative,
            structured=_structured(report, error=str(exc)[:200]),
            disclaimer=_DISCLAIMER,
        )

    return AgentOutput(
        narrative=narrative,
        structured=_structured(report),
        disclaimer=_DISCLAIMER,
    )


def _structured(report: HistoricalReport, error: str | None = None) -> dict:
    out = {"historical_report": report.model_dump(mode="json")}
    if error is not None:
        out["llm_error"] = error
    return out


def _fallback_narrative(report: HistoricalReport) -> str:
    perf = report.performance
    if perf is None or perf.period_return_pct is None:
        return (f"During {report.era.label}, we couldn't compute window "
                 "stats for the requested instrument. "
                 "Past performance does not guarantee future returns.")
    dd = (f", with a peak-to-trough drawdown of {perf.max_drawdown_pct:.1f}%"
           if perf.max_drawdown_pct is not None else "")
    return (f"During {report.era.label}, {report.instrument_label} "
            f"returned {perf.period_return_pct:+.1f}%{dd}. "
            f"Era context: {report.era.summary} "
            "Past performance does not guarantee future returns.")
