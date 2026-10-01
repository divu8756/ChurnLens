"""Offer catalogue (app/config/offers.yaml) and model pricing (app/config/pricing.yaml),
validated with Pydantic. Errors name the YAML line of the offending entry."""

from pathlib import Path
from typing import Annotated, Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.config import CONFIG_DIR

OFFERS_FILE = CONFIG_DIR / "offers.yaml"
PRICING_FILE = CONFIG_DIR / "pricing.yaml"
Rate = Annotated[float, Field(ge=0, le=1)]


class CatalogueError(ValueError):
    """The YAML file is invalid; the message says where and why."""


class ColumnInRule(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    column: str = Field(min_length=1)
    in_: list[str | int | float | bool] = Field(alias="in", min_length=1)


class ColumnRangeRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: str = Field(min_length=1)
    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def _bounds(self) -> Self:
        if self.min is None and self.max is None:
            raise ValueError("a range rule needs min, max or both")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min must not be greater than max")
        return self


class RiskBandRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risk_band: list[Literal["High", "Medium", "Low"]] = Field(min_length=1)


Rule = RiskBandRule | ColumnInRule | ColumnRangeRule


class OfferSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    cost: float = Field(ge=0)
    cost_basis: Literal["per_accepted", "per_targeted"] = "per_accepted"
    assumed_acceptance_rate: Rate
    assumed_save_rate: Rate = 0.5
    eligible_segments: list[Rule] = Field(default_factory=list)


class ModelPrice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_per_1m: float = Field(ge=0)
    output_per_1m: float = Field(ge=0)


class Pricing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = ""
    currency: str = "USD"
    default: ModelPrice = ModelPrice(input_per_1m=0, output_per_1m=0)
    models: dict[str, ModelPrice] = Field(default_factory=dict)

    def price(self, model: str) -> ModelPrice:
        return self.models.get(model, self.default)


def _compose(path: Path) -> tuple[Any, yaml.Node | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogueError(f"{path.name}: cannot be read ({exc.strerror}).") from None
    try:
        return yaml.safe_load(text), yaml.compose(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" line {mark.line + 1}" if mark else ""
        problem = getattr(exc, "problem", None) or str(exc)
        raise CatalogueError(f"{path.name}{where}: invalid YAML ({problem}).") from None


def _problems(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'value'}: {e['msg']}"
                     for e in exc.errors())


def load_catalogue(path: Path = OFFERS_FILE) -> list[OfferSpec]:
    data, node = _compose(path)
    if not isinstance(data, list) or not isinstance(node, yaml.SequenceNode):
        raise CatalogueError(f"{path.name}: must be a list of offers.")
    offers: list[OfferSpec] = []
    for item, item_node in zip(data, node.value, strict=True):
        line = item_node.start_mark.line + 1
        try:
            offers.append(OfferSpec.model_validate(item))
        except ValidationError as exc:
            raise CatalogueError(f"{path.name} line {line}: {_problems(exc)}.") from None
    names = [o.name.casefold() for o in offers]
    duplicates = sorted({o.name for o in offers if names.count(o.name.casefold()) > 1})
    if duplicates:
        raise CatalogueError(f"{path.name}: duplicate offer names: {', '.join(duplicates)}.")
    return offers


def load_pricing(path: Path = PRICING_FILE) -> Pricing:
    data, _ = _compose(path)
    try:
        return Pricing.model_validate(data or {})
    except ValidationError as exc:
        raise CatalogueError(f"{path.name}: {_problems(exc)}.") from None
