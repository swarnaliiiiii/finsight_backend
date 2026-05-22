"""mftool: Indian mutual fund NAVs sourced from AMFI. No API key."""
from __future__ import annotations

import asyncio
from datetime import date, datetime

from app.sources.base import FundInfo, FundSource


class MftoolSource(FundSource):
    name = "mftool"
    countries = {"IN"}

    def __init__(self) -> None:
        self._mf = None

    def _get_client(self):
        if self._mf is None:
            from mftool import Mftool  # type: ignore
            self._mf = Mftool()
        return self._mf

    async def search(self, query: str) -> list[FundInfo]:
        return await asyncio.to_thread(self._search_sync, query)

    def _search_sync(self, query: str) -> list[FundInfo]:
        try:
            mf = self._get_client()
            matches = mf.get_available_schemes(query) or {}
        except Exception:
            return []
        results: list[FundInfo] = []
        for code, name in list(matches.items())[:20]:
            try:
                nav_data = mf.get_scheme_quote(code) or {}
                nav_value = float(nav_data.get("nav", 0) or 0)
                as_of = self._parse_date(nav_data.get("last_updated"))
                results.append(FundInfo(
                    scheme_code=str(code),
                    scheme_name=name,
                    nav=nav_value,
                    as_of=as_of,
                    fund_house=nav_data.get("fund_house"),
                ))
            except Exception:
                continue
        return results

    async def get_nav(self, scheme_code: str) -> FundInfo | None:
        return await asyncio.to_thread(self._get_nav_sync, scheme_code)

    def _get_nav_sync(self, scheme_code: str) -> FundInfo | None:
        try:
            mf = self._get_client()
            data = mf.get_scheme_quote(scheme_code) or {}
            details = mf.get_scheme_details(scheme_code) or {}
            return FundInfo(
                scheme_code=scheme_code,
                scheme_name=data.get("scheme_name", ""),
                nav=float(data.get("nav", 0) or 0),
                as_of=self._parse_date(data.get("last_updated")),
                category=details.get("scheme_category"),
                fund_house=data.get("fund_house"),
            )
        except Exception:
            return None

    @staticmethod
    def _parse_date(value: str | None) -> date:
        if not value:
            return date.today()
        for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return date.today()
