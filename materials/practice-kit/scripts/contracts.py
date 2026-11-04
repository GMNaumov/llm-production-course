import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def valid_box(self):
        if self.bbox:
            a, b, c, d = self.bbox
            if not (0 <= a < c <= 1 and 0 <= b < d <= 1):
                raise ValueError("bbox")
        return self


class StatusField(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    state: Literal["read", "missing", "unreadable", "conflict"]
    value: Literal["draft", "approved"] | None
    source: Source | None

    @model_validator(mode="after")
    def evidence(self):
        if self.state == "read" and (self.value is None or self.source is None):
            raise ValueError("read requires value and source")
        if self.state != "read" and self.value is not None:
            raise ValueError("unknown is not a value")
        return self


def route(field, evidence_verified=False, calibrated_signal=None, threshold=None):
    """Автоприёмка возможна только после независимой проверки источника и калибровки."""
    if field.state != "read" or not field.source or evidence_verified is not True:
        return "review"
    if (
        type(calibrated_signal) not in (int, float)
        or type(threshold) not in (int, float)
        or not math.isfinite(calibrated_signal)
        or not math.isfinite(threshold)
        or not 0 <= calibrated_signal <= 1
        or not 0 <= threshold <= 1
    ):
        return "review"
    return "auto" if calibrated_signal >= threshold else "review"
