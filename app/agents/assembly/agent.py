"""Deterministic assembler.

Reads `input.upstream['__agent_outputs__']` (a dict[str, AgentOutput] keyed by
agent name) and stitches their content into typed UI blocks. Also surfaces
scenario context as a callout when relevant.

No LLM call in this version. A later step may add an LLM-driven 'polish'
mode for plans that benefit from a rewritten lead paragraph, but it stays
opt-in — most plans should ship deterministically packaged.
"""
from __future__ import annotations

from typing import Any

from app.schemas import (AgentInput, AgentOutput, CalloutBlock, ChartBlock,
                          CitationsBlock, CurrentScenario, Document, ListBlock,
                          NarrativeBlock, ResponseEnvelope, TableBlock,
                          VideoBlock)
from app.schemas.assembly import Block

_AGENT_OUTPUTS_KEY = "__agent_outputs__"


async def run(input: AgentInput) -> AgentOutput:
    upstream_outputs: dict[str, AgentOutput] = (
        input.upstream.get(_AGENT_OUTPUTS_KEY) or {})
    blocks: list[Block] = []
    citations: list[str] = []

    callout = _scenario_callout(input.scenario)
    if callout is not None:
        blocks.append(callout)

    # Block per upstream agent. Order: insertion order of the dict (which
    # equals plan order, since runner appends in step order).
    for name, out in upstream_outputs.items():
        if name == "assembly":
            continue
        blocks.extend(_blocks_for_agent(name, out))
        citations.extend(out.citations)

    # Retrieved documents (from search.* layer calls) become Video/List blocks.
    doc_blocks, doc_urls = _blocks_for_documents(input.documents)
    blocks.extend(doc_blocks)
    citations.extend(doc_urls)

    if citations:
        blocks.append(CitationsBlock(sources=_dedupe(citations)))

    envelope = ResponseEnvelope(
        intent=input.intent,
        query=input.query,
        blocks=blocks,
    )
    return AgentOutput(
        narrative=None,
        structured={"envelope": envelope.model_dump(mode="json")},
        citations=citations,
    )


# --- helpers --------------------------------------------------------------

def _scenario_callout(scenario: CurrentScenario | None) -> CalloutBlock | None:
    if scenario is None:
        return None
    if scenario.active_events:
        ev = scenario.active_events[0]
        return CalloutBlock(
            title="Current scenario",
            text=f"{ev.type.value.replace('_', ' ').title()}: {ev.headline}",
            tone="watch",
        )
    if scenario.policy_state and scenario.policy_state.policy_rate is not None:
        ps = scenario.policy_state
        return CalloutBlock(
            title="Policy backdrop",
            text=(f"{ps.authority} policy rate at "
                   f"{ps.policy_rate}{'%' if ps.policy_rate_unit == 'percent' else ''}."),
            tone="info",
        )
    return None


def _blocks_for_agent(name: str, output: AgentOutput) -> list[Block]:
    blocks: list[Block] = []
    if output.narrative:
        blocks.append(NarrativeBlock(
            title=_title_for_agent(name),
            text=output.narrative,
        ))

    structured = output.structured or {}

    # Education agent: render the affecting-entities as a list block.
    explanation = structured.get("explanation")
    if isinstance(explanation, dict):
        entities = explanation.get("affecting_entities") or []
        if entities:
            items: list[dict[str, Any]] = []
            for e in entities:
                line = {
                    "label": e.get("name"),
                    "description": e.get("description"),
                }
                if e.get("current_value"):
                    line["value"] = e.get("current_value")
                items.append(line)
            blocks.append(ListBlock(
                title="What affects this",
                items=items,
            ))

    # Recommender output: candidates as a table (if/when wired into a plan).
    candidates = structured.get("candidates")
    if isinstance(candidates, list) and candidates:
        columns = ["Name", "Category", "3y Return", "Expense Ratio", "AUM (Cr)"]
        rows = [[
            c.get("name"),
            c.get("category"),
            c.get("returns_3y"),
            c.get("expense_ratio"),
            c.get("aum_crore"),
        ] for c in candidates]
        blocks.append(TableBlock(
            title="Candidates",
            columns=columns,
            rows=rows,
        ))

    # Personalization agent: render projection range as a 3-point bar chart
    # (p10/p50/p90) and the allocation plan as a table.
    proj_range = structured.get("projection_range")
    if isinstance(proj_range, dict) and proj_range.get("p50"):
        blocks.append(ChartBlock(
            title="Where the range lands",
            shape="bar",
            x_label="Outcome percentile",
            y_label="Final value",
            series=[{
                "name": "final_value",
                "points": [
                    {"x": "p10 (low)", "y": proj_range["p10"]},
                    {"x": "p50 (mid)", "y": proj_range["p50"]},
                    {"x": "p90 (high)", "y": proj_range["p90"]},
                ],
            }],
            note=(f"Based on {proj_range['n_simulations']} simulations with "
                   f"mean {proj_range['annual_return_mean']:.0%} and "
                   f"stdev {proj_range['annual_return_stdev']:.0%}."),
        ))

    point = structured.get("projection")
    if isinstance(point, dict) and point.get("final_value"):
        blocks.append(TableBlock(
            title="Point projection (illustrative)",
            columns=["Metric", "Value"],
            rows=[
                ["Monthly", point.get("monthly_amount")],
                ["Months", point.get("months")],
                ["Invested total", point.get("invested_total")],
                ["Final value", point.get("final_value")],
                ["Growth multiple", point.get("growth_multiple")],
                ["Assumed annual return",
                 f"{point.get('annual_return_assumed', 0):.0%}"],
            ],
        ))

    allocation = structured.get("allocation")
    if isinstance(allocation, dict) and allocation.get("slices"):
        blocks.append(TableBlock(
            title="Suggested allocation",
            columns=["Bucket", "Percent", "Why"],
            rows=[[s["bucket"], s["pct"], s["rationale"]]
                   for s in allocation["slices"]],
            note=f"Method: {allocation.get('method', '')}",
        ))

    return blocks


def _title_for_agent(name: str) -> str | None:
    return {
        "education": "Explanation",
        "recommendation": "Why this stands out",
        "scenario_policy": "Policy & scenario read",
        "personalization": "For your situation",
        "not_implemented": None,
    }.get(name)


def _dedupe(xs: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in xs:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _blocks_for_documents(docs: list[Document]) -> tuple[list[Block], list[str]]:
    """Split retrieved docs into a VideoBlock (kind=='video') and a ListBlock
    (everything else with a URL). Returns (blocks, urls_for_citations)."""
    if not docs:
        return [], []
    videos = [d for d in docs if d.kind == "video"]
    articles = [d for d in docs if d.kind != "video"]
    blocks: list[Block] = []
    if videos:
        blocks.append(VideoBlock(
            title="Watch / listen",
            items=[{"title": d.title, "url": d.url,
                     "channel": d.snippet.split("]", 1)[0].lstrip("[")
                                if d.snippet.startswith("[") else None}
                    for d in videos if d.url],
        ))
    if articles:
        blocks.append(ListBlock(
            title="Further reading",
            items=[{"label": d.title, "description": d.snippet, "url": d.url}
                    for d in articles if d.url],
        ))
    urls = [d.url for d in docs if d.url]
    return blocks, urls
