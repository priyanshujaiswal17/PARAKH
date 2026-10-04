"""Pydantic schemas for Label Reader.

All data structures are frozen per SPEC section 8.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class DateString(BaseModel):
    kind: Literal["mfg", "packed", "expiry", "best_before", "use_by", "use_within", "other"]
    text: str  # exactly as printed, e.g. "BB 9 months from MFG"


class NutritionValues(BaseModel):
    energy_kcal: float | None = None
    protein_g: float | None = None
    carbohydrate_g: float | None = None
    total_sugar_g: float | None = None
    added_sugar_g: float | None = None
    total_fat_g: float | None = None
    saturated_fat_g: float | None = None
    trans_fat_g: float | None = None
    fibre_g: float | None = None
    sodium_mg: float | None = None
    cholesterol_mg: float | None = None


class Nutrition(BaseModel):
    basis: Literal["per_100g", "per_100ml", "per_serving", "unknown"] = "unknown"
    serving_size_text: str | None = None
    values: NutritionValues = Field(default_factory=NutritionValues)

    @field_validator("values", mode="before")
    @classmethod
    def _default_values(cls, v: Any) -> Any:
        return v if v is not None else NutritionValues()


class ExtractResult(BaseModel):
    label_readable: bool = True
    is_food_label: bool = True  # False if uploaded image is a bill, receipt, invoice, prescription, or non-food item
    non_food_reason: str | None = None
    is_medicine: bool = False
    is_supplement: bool = False  # protein powder, vitamins, nutraceutical
    product_name: str | None = None
    brand: str | None = None
    net_quantity: str | None = None
    raw_transcription: str = ""  # every readable word, [unclear] where illegible
    ingredients: list[str] = Field(default_factory=list)  # top-level items in label order
    allergen_statement: list[str] = Field(default_factory=list)  # as printed
    may_contain: list[str] = Field(default_factory=list)  # "may contain traces of..."
    veg_mark: Literal["veg", "non_veg", "unknown"] = "unknown"
    fssai_license: str | None = None
    claims: list[str] = Field(default_factory=list)  # "No added sugar", etc.
    nutrition: Nutrition = Field(default_factory=Nutrition)
    date_strings: list[DateString] = Field(default_factory=list)
    storage_text: str | None = None
    country_or_importer_note: str | None = None

    @field_validator("nutrition", mode="before")
    @classmethod
    def _default_nutrition(cls, v: Any) -> Any:
        return v if v is not None else Nutrition()

    @field_validator("ingredients", "allergen_statement", "may_contain", "claims", mode="before")
    @classmethod
    def _default_lists(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, str):
            return [v.strip()] if v.strip() else []
        return v

    @field_validator("date_strings", mode="before")
    @classmethod
    def _default_date_strings(cls, v: Any) -> Any:
        if v is None:
            return []
        return v


class VerifiedItem(BaseModel):
    text: str
    status: Literal["verified", "unverified"]
    match_score: float


class IngredientRating(BaseModel):
    name: str
    verified: bool = True
    level: Literal["good", "neutral", "watch", "limit", "not_rated"]
    reason: str  # 15 words max
    source: Literal["table", "general_knowledge", "none"]
    ins_number: str | None = None


class NutritionFlag(BaseModel):
    nutrient: str  # "sugar", "salt", "saturated_fat", "total_fat"
    level: Literal["low", "medium", "high"]
    value: float
    unit: str
    threshold_note: str


class ExpiryResult(BaseModel):
    status: Literal["expired", "expires_soon", "ok", "not_found", "unreadable"]
    expiry_date: date | None = None
    days_left: int | None = None
    explanation: str  # plain sentence built by code


class Summary(BaseModel):
    what_it_is: str = ""
    good_things: list[str] = Field(default_factory=list)  # 0 to 4 items
    watch_out: list[str] = Field(default_factory=list)  # 0 to 4 items
    suits: list[str] = Field(default_factory=list)  # 0 to 4 items
    avoid_or_ask_doctor: list[str] = Field(default_factory=list)  # 0 to 4 items
    overall_note: str = ""

    @field_validator("good_things", "watch_out", "suits", "avoid_or_ask_doctor", mode="before")
    @classmethod
    def _default_summary_lists(cls, v: Any) -> Any:
        return v if v is not None else []


class QAAnswer(BaseModel):
    question: str
    answer: str
    source: Literal["label", "general", "both", "cannot_tell"]
    evidence: list[str] = Field(default_factory=list)  # exact label quotes
    downgraded: bool = False

    @field_validator("evidence", mode="before")
    @classmethod
    def _default_evidence(cls, v: Any) -> Any:
        return v if v is not None else []


class AnalysisResult(BaseModel):
    refused: bool = False
    refusal_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    extract: ExtractResult | None = None
    verified_ingredients: list[VerifiedItem] = Field(default_factory=list)
    verified_allergens: list[VerifiedItem] = Field(default_factory=list)
    ratings: list[IngredientRating] = Field(default_factory=list)
    nutrition_flags: list[NutritionFlag] = Field(default_factory=list)
    expiry: ExpiryResult | None = None
    summary: Summary | None = None
    qa: QAAnswer | None = None
    language: Literal["English", "Hinglish"] = "English"
    backend_used: str = ""
    model_used: str = ""
    seconds_taken: float = 0.0

    @field_validator("warnings", "verified_ingredients", "verified_allergens", "ratings", "nutrition_flags", mode="before")
    @classmethod
    def _default_result_lists(cls, v: Any) -> Any:
        return v if v is not None else []


def flatten_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Inlines $defs/$ref in a JSON schema for backends that reject them."""
    schema_copy = deepcopy(schema)
    defs = schema_copy.pop("$defs", {})

    def _resolve_ref(obj: Any) -> Any:
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                if ref.startswith("#/$defs/"):
                    def_name = ref.split("/")[-1]
                    if def_name in defs:
                        resolved = deepcopy(defs[def_name])
                        return _resolve_ref(resolved)
                return obj
            return {k: _resolve_ref(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_resolve_ref(item) for item in obj]
        return obj

    return _resolve_ref(schema_copy)
