"""Response Assembly envelope.

The orchestrator collects each plan step's AgentOutput and hands them to the
Assembly agent, which packages them into typed UI blocks. The frontend
dispatches on `kind` — blocks are *suggestions*, not commands; the UI can
ignore or reorder.

Adding a new block kind is a four-line change: define the model, add it to
the union, and the frontend grows a new component. No runner changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

from app.schemas.intent import Intent


class _BaseBlock(BaseModel, frozen=True):
    title: str | None = None
    note: str | None = None


class NarrativeBlock(_BaseBlock, frozen=True):
    kind: Literal["narrative"] = "narrative"
    text: str


class CalloutBlock(_BaseBlock, frozen=True):
    """Short banner — e.g. 'RBI cut repo 25bp last week — affects bond funds'."""
    kind: Literal["callout"] = "callout"
    text: str
    tone: Literal["info", "watch", "important"] = "info"


class TableBlock(_BaseBlock, frozen=True):
    kind: Literal["table"] = "table"
    columns: list[str]
    rows: list[list[Any]]


class ChartBlock(_BaseBlock, frozen=True):
    """Time-series or bar data the frontend renders. Backend ships data + a
    hint about chart shape; frontend picks the library."""
    kind: Literal["chart"] = "chart"
    shape: Literal["line", "bar", "area"] = "line"
    x_label: str | None = None
    y_label: str | None = None
    series: list[dict[str, Any]]  # [{"name": ..., "points": [{"x":..., "y":...}, ...]}]


class ListBlock(_BaseBlock, frozen=True):
    """Bulleted items. Items may carry a url so the UI can render anchors."""
    kind: Literal["list"] = "list"
    items: list[dict[str, Any]]


class VideoBlock(_BaseBlock, frozen=True):
    kind: Literal["video"] = "video"
    items: list[dict[str, Any]]  # [{"title": ..., "url": ..., "channel": ...}]


class CitationsBlock(_BaseBlock, frozen=True):
    kind: Literal["citations"] = "citations"
    sources: list[str]


Block = Annotated[
    Union[NarrativeBlock, CalloutBlock, TableBlock, ChartBlock, ListBlock,
            VideoBlock, CitationsBlock],
    Field(discriminator="kind"),
]


class ResponseEnvelope(BaseModel, frozen=True):
    """The shape the UI consumes. Blocks render in order."""
    intent: Intent
    query: str
    blocks: list[Block] = Field(default_factory=list)
    disclaimer: str = (
        "This is educational information based on public data, not financial advice."
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    debug: dict[str, Any] = Field(default_factory=dict)
