"""Provider interfaces (replaceable data sources).

Each provider returns provenance-bearing data. Providers are read via the
database layer (already-ingested snapshots) so we never hit live external
services per dashboard request.

Historical note: these interfaces document the contracts; concrete providers
are the DB-backed repositories plus (isolated) demo/mock providers flagged
is_demo=True.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class Provider(ABC):
    name: str = "base"

    @abstractmethod
    def health(self) -> dict:
        ...


class LocationDataProvider(Provider):
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[dict]:
        ...

    @abstractmethod
    def get(self, location_id: str) -> Optional[dict]:
        ...


class BusinessDataProvider(Provider):
    @abstractmethod
    def nearby(self, lat: float, lon: float, radius_km: float, category: Optional[str] = None) -> list[dict]:
        ...


class PopulationDataProvider(Provider):
    @abstractmethod
    def for_location(self, location_id: str) -> Optional[dict]:
        ...


class MarketPriceDataProvider(Provider):
    @abstractmethod
    def latest(self, category: Optional[str] = None) -> list[dict]:
        ...


class WeatherDataProvider(Provider):
    @abstractmethod
    def latest(self, location_id: str) -> Optional[dict]:
        ...


class GovernmentSchemeProvider(Provider):
    @abstractmethod
    def active(self) -> list[dict]:
        ...
