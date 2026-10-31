"""Input contracts for the manual graph editor."""

import calendar
from urllib.parse import urlparse
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class HistoricalDate(BaseModel):
    # Negative years represent BCE; there is no year zero in the editor API.
    year: int
    precision: Literal["year", "month", "day"] = "year"
    month: Optional[int] = None
    day: Optional[int] = None
    approximate: bool = False

    @model_validator(mode="after")
    def valid_parts(self):
        if self.year == 0:
            raise ValueError("year zero is not supported")
        if self.precision == "year" and (self.month is not None or self.day is not None):
            raise ValueError("year precision cannot include month or day")
        if self.precision in ("month", "day") and not self.month:
            raise ValueError("month is required for this precision")
        if self.precision == "month" and self.day is not None:
            raise ValueError("month precision cannot include day")
        if self.precision == "day" and not self.day:
            raise ValueError("day is required for day precision")
        if self.month is not None and not 1 <= self.month <= 12:
            raise ValueError("month must be between 1 and 12")
        if self.day is not None:
            # Calendar precision for BCE dates is handled as a historical estimate.
            max_day = calendar.monthrange(abs(self.year), self.month)[1]
            if not 1 <= self.day <= max_day:
                raise ValueError("invalid day for month")
        return self


class Period(BaseModel):
    start: Optional[HistoricalDate] = None
    end: Optional[HistoricalDate] = None

    @model_validator(mode="after")
    def valid_order(self):
        if self.start and self.end and date_bounds(self.start)[0] > date_bounds(self.end)[1]:
            raise ValueError("period start must be before period end")
        return self


def date_bounds(value: HistoricalDate):
    if value.precision == "year":
        return (value.year, 1, 1), (value.year, 12, 31)
    if value.precision == "month":
        return (value.year, value.month, 1), (
            value.year, value.month, calendar.monthrange(abs(value.year), value.month)[1]
        )
    point = (value.year, value.month, value.day)
    return point, point


def definitely_overlap(first: Period, second: Period) -> bool:
    """Only assert overlap when uncertain boundaries still guarantee it."""
    first_start = date_bounds(first.start)[1] if first.start else None
    first_end = date_bounds(first.end)[0] if first.end else None
    second_start = date_bounds(second.start)[1] if second.start else None
    second_end = date_bounds(second.end)[0] if second.end else None
    if not all((first_start, first_end, second_start, second_end)):
        return False
    if any(point.approximate for point in (first.start, first.end, second.start, second.end)):
        return False
    return first_start <= second_end and second_start <= first_end


def possibly_overlap(first: Period, second: Period) -> bool:
    """Accept coarse dates only when they do not place people in different eras."""
    if not all((first.start, first.end, second.start, second.end)):
        return False
    if any(point.approximate for point in (first.start, first.end, second.start, second.end)):
        return False
    return (date_bounds(first.start)[0] <= date_bounds(second.end)[1] and
            date_bounds(second.start)[0] <= date_bounds(first.end)[1])


def clean_label(value):
    if not value.strip():
        raise ValueError("name or title cannot be blank")
    return value.strip()


class LocationInput(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    city: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        return clean_label(value)

    @field_validator("lat")
    @classmethod
    def valid_lat(cls, value):
        if value is not None and not (-90 <= value <= 90):
            raise ValueError("lat must be between -90 and 90")
        return value

    @field_validator("lng")
    @classmethod
    def valid_lng(cls, value):
        if value is not None and not (-180 <= value <= 180):
            raise ValueError("lng must be between -180 and 180")
        return value


class PersonInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    aliases: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    country: Optional[str] = None
    city_born: Optional[str] = None
    image_url: Optional[str] = None
    wikidata_id: Optional[str] = None
    birth: Optional[HistoricalDate] = None
    death: Optional[HistoricalDate] = None

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        return clean_label(value)

    @model_validator(mode="after")
    def valid_life(self):
        if self.birth and self.death and date_bounds(self.birth)[0] > date_bounds(self.death)[1]:
            raise ValueError("death must not precede birth")
        return self


class SourceInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: Optional[str] = None
    citation: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    accessed_at: Optional[str] = None
    location: Optional[LocationInput] = None

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value):
        return clean_label(value)

    @field_validator("url")
    @classmethod
    def web_url(cls, value):
        if value:
            parsed = urlparse(value)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError("source URL must be an HTTP(S) URL")
        return value

    @model_validator(mode="after")
    def requires_reference(self):
        if not ((self.url or "").strip() or (self.citation or "").strip()):
            raise ValueError("a URL or bibliographic citation is required")
        return self


class OrganizationInput(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    kind: Literal["team", "government", "institution", "other"] = "other"
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        return clean_label(value)


class WorkInput(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    kind: Literal["film", "music", "book", "artwork", "project", "other"] = "other"
    period: Period = Field(default_factory=Period)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        return clean_label(value)


class EventInput(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    kind: Literal[
        "sports.match", "arts.performance", "politics.treaty_signing",
        "politics.meeting", "personal.meeting", "other"
    ] = "other"
    period: Period = Field(default_factory=Period)
    place: Optional[str] = None
    location: Optional[LocationInput] = None
    source_id: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    participants: List["EventParticipantInput"] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        return clean_label(value)

    @model_validator(mode="after")
    def sync_place_and_location(self):
        if self.location and not self.place:
            self.place = self.location.name
        elif self.place and not self.location:
            self.location = LocationInput(name=self.place)
        return self


class FactInput(BaseModel):
    type_id: str
    subject_id: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    role: Optional[str] = None
    side: Optional[str] = None
    period: Period = Field(default_factory=Period)
    status: Literal["draft", "verified"] = "draft"
    note: Optional[str] = None
    location: Optional[LocationInput] = None

    @field_validator("role", "side")
    @classmethod
    def normalized_tags(cls, value):
        return value.strip().casefold() if value else None


class EventParticipantInput(FactInput):
    # The event is created in the same transaction, so its ID is assigned later.
    object_id: str = Field(default="_pending_", min_length=1)


class FactBatchInput(BaseModel):
    facts: List[FactInput] = Field(min_length=1, max_length=30)


class RevisionPatch(BaseModel):
    revision: int = Field(ge=1)
    changes: Dict[str, Any] = Field(default_factory=dict)


EventInput.model_rebuild()
