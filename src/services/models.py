# models.py  (overwrite whole file)
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Any, Dict


@dataclass
class TeamModel:
    id: int
    name: str
    short_name: Optional[str] = None
    tla: Optional[str] = None
    crest_url: Optional[str] = None
    venue: Optional[str] = None
    founded: Optional[int] = None
    last_updated: Optional[datetime] = None

    # ----------  NEW: easy JSON export  ----------
    def dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.last_updated:
            d["last_updated"] = self.last_updated.isoformat()
        return d


@dataclass
class CompetitionModel:
    code: str
    name: str
    area: Optional[str] = None
    season_start: Optional[datetime] = None
    season_end: Optional[datetime] = None

    def dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for dt_field in ("season_start", "season_end"):
            val = d.get(dt_field)
            if val:
                d[dt_field] = val.isoformat()
        return d


@dataclass
class MatchScore:
    home: Optional[int] = None
    away: Optional[int] = None


@dataclass
class MatchModel:
    id: int
    utc_date: datetime
    status: str
    competition: str
    home_team: TeamModel
    away_team: TeamModel
    score: MatchScore
    stage: Optional[str] = None
    group: Optional[str] = None
    last_updated: Optional[datetime] = None

    # ----------  NEW: JSON-friendly export  ----------
    def dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # convert datetime fields
        d["utc_date"] = self.utc_date.isoformat()
        if self.last_updated:
            d["last_updated"] = self.last_updated.isoformat()
        # convert nested dataclasses
        d["home_team"] = self.home_team.dict()
        d["away_team"] = self.away_team.dict()
        d["score"] = asdict(self.score)
        return d