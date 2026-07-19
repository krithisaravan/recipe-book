"""
scaling.py — recipe scaling math for the baker app

All volume calculations use cubic inches internally.
Scaling factor = target total volume / baseline total volume × (1 + adjustment).
"""

import math
from dataclasses import dataclass


# ── Cake geometry ─────────────────────────────────────────────────────────────

def round_layer_volume(diameter_in: float, height_in: float) -> float:
    """Cubic inches for one round cake layer."""
    return math.pi * (diameter_in / 2) ** 2 * height_in


def rect_layer_volume(length_in: float, width_in: float, height_in: float) -> float:
    """Cubic inches for one rectangular cake layer."""
    return length_in * width_in * height_in


# Standard sheet pan dimensions (length × width, inches)
SHEET_PAN_SIZES: dict[str, tuple[float, float]] = {
    "quarter": (13.0, 9.0),
    "half":    (18.0, 13.0),
}


# ── Scaling core ──────────────────────────────────────────────────────────────

@dataclass
class ScaleTarget:
    """Everything needed to describe one product size."""
    shape: str            # "round" | "rect"
    size_in: float        # diameter for round; length for rect
    width_in: float       # ignored for round; width for rect
    height_in: float      # layer height
    num_layers: int       # layers per cake
    num_cakes: float      # can be fractional (e.g. 3.5)
    adjustment_pct: float = 0.0   # e.g. 0.05 for +5%


@dataclass
class BaselineRecipe:
    """Describes what the baseline recipe produces."""
    num_layers: int
    size_in: float
    height_in: float
    shape: str = "round"
    num_cakes: float = 1.0   # how many cakes the baseline recipe itself yields


def target_volume(t: ScaleTarget) -> float:
    """Total batter volume the target requires for ONE cake (before num_cakes)."""
    if t.shape == "round":
        layer_vol = round_layer_volume(t.size_in, t.height_in)
    else:
        layer_vol = rect_layer_volume(t.size_in, t.width_in, t.height_in)
    return layer_vol * t.num_layers


def baseline_volume(b: BaselineRecipe) -> float:
    """Total batter volume for ONE cake of the baseline recipe (before num_cakes)."""
    if b.shape == "round":
        layer_vol = round_layer_volume(b.size_in, b.height_in)
    else:
        layer_vol = rect_layer_volume(b.size_in, b.size_in, b.height_in)
    return layer_vol * b.num_layers


def scale_factor(target: ScaleTarget, baseline: BaselineRecipe) -> float:
    """
    Multiplier to apply to every baseline ingredient quantity.

    = (target_volume / baseline_volume) * (target.num_cakes / baseline.num_cakes) * (1 + adjustment)

    The num_cakes ratio matters whenever the baseline recipe itself was written
    to yield more than one cake (e.g. "this batch makes batter for 3 cakes") —
    scaling must normalize against that, not just multiply target cakes in directly.
    """
    vol_ratio = target_volume(target) / baseline_volume(baseline)
    cake_ratio = target.num_cakes / baseline.num_cakes
    return vol_ratio * cake_ratio * (1 + target.adjustment_pct)


# ── Ingredient scaling ────────────────────────────────────────────────────────

@dataclass
class Ingredient:
    name: str
    base_qty: float
    unit: str
    weight_g: float   # grams equivalent of base_qty (used for cost calc)
    cost_per_g: float = 0.0


@dataclass
class ScaledIngredient:
    name: str
    unit: str
    qty: float
    weight_g: float
    cost_per_g: float
    line_cost: float


def scale_ingredients(
    ingredients: list[Ingredient],
    factor: float,
) -> list[ScaledIngredient]:
    """Return scaled quantities and costs for all ingredients."""
    result = []
    for ing in ingredients:
        qty     = round(ing.base_qty * factor, 3)
        wt      = round(ing.weight_g * factor, 3)
        cost    = round(wt * ing.cost_per_g, 4)
        result.append(ScaledIngredient(
            name=ing.name,
            unit=ing.unit,
            qty=qty,
            weight_g=wt,
            cost_per_g=ing.cost_per_g,
            line_cost=cost,
        ))
    return result


def total_ingredient_cost(scaled: list[ScaledIngredient]) -> float:
    return round(sum(s.line_cost for s in scaled), 4)


# ── Convenience: scale a full product ────────────────────────────────────────

def scale_product(
    ingredients: list[Ingredient],
    target: ScaleTarget,
    baseline: BaselineRecipe,
) -> tuple[list[ScaledIngredient], float, float]:
    """
    Returns (scaled_ingredients, scale_factor, total_ingredient_cost).
    """
    f      = scale_factor(target, baseline)
    scaled = scale_ingredients(ingredients, f)
    cost   = total_ingredient_cost(scaled)
    return scaled, f, cost