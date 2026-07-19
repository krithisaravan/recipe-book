"""
Page — Quote a Cake
One flow: pick a recipe and a target size, get back both the scaled
shopping/prep list and a suggested price — instead of splitting scaling
and pricing across two separate pages that both needed the same inputs.
"""
import sys
from pathlib import Path
from dataclasses import dataclass
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from db import (
    init_db, get_recipes, get_recipe_ingredients, get_packaging,
    upsert_product, get_recipe_quote_counts, record_recipe_quote,
    get_setting_json, set_setting_json,
)
from scaling import ScaleTarget, BaselineRecipe, scale_product, Ingredient
from shared import apply_page_style, render_footer, PALETTE

init_db()

st.set_page_config(page_title="Quote a Cake · My Recipe Book", page_icon="🧁", layout="wide")
apply_page_style("3_Quote_a_Cake.py")

st.markdown(f"""
<style>
  .baseline-note {{
    background: {PALETTE['bg_secondary']}; border-left: 3px solid {PALETTE['terracotta']};
    border-radius: 0 8px 8px 0; padding: 0.55rem 0.9rem;
    font-size: 0.85rem; color: {PALETTE['text']}; margin: 0.4rem 0 0.2rem;
  }}
  /* Group the left-column inputs into distinct cards instead of one long
     hr-separated list, so Recipe / Size / Packaging read as separate
     decisions rather than one undifferentiated form. Scoped to wrappers
     that live inside a Streamlit column — :has(.card-title) alone still
     matched the page's own outer wrapper too (it "has" a card-title
     somewhere in its whole subtree), which is what was drawing a border
     down the entire page. Only content inside our controls_col column
     should ever get this treatment. */
  div[data-testid="stColumn"] div[data-testid="stVerticalBlockBorderWrapper"] {{
    border: 1px solid {PALETTE['border']} !important;
    border-radius: 12px !important;
    background: transparent !important;
    margin-bottom: 1.25rem !important;
    padding: 0.4rem 0.2rem !important;
  }}
  div[data-testid="stColumn"] div[data-testid="stVerticalBlockBorderWrapper"]
    div[data-testid="stVerticalBlockBorderWrapper"] {{
    border: none !important;
    margin-bottom: 0 !important;
  }}
  .card-title {{
    font-family: 'Sorts Mill Goudy', serif;
    font-size: 1.02rem; color: {PALETTE['text']};
    margin-bottom: 0.2rem;
  }}
</style>
""", unsafe_allow_html=True)


def display_qty(qty: float, unit: str) -> str:
    if unit in ("grams", "mils"):
        return f"{qty:.1f}"
    return f"{qty:.2f}"


@dataclass
class ScaledLine:
    """Mirrors the fields scale_product() returns per ingredient (name, qty,
    unit, weight_g, line_cost) — used for the manual scale-factor override
    path, so the display code below works identically either way."""
    name: str
    qty: float
    unit: str
    weight_g: float
    line_cost: float


def baseline_note(r: dict) -> str:
    shape = "round" if r["base_shape"] == "round" else "rect"
    base_cakes = r.get("base_num_cakes", 1.0)
    suffix = f" × {base_cakes:g} cake(s)" if base_cakes != 1.0 else ""
    return (f"Baseline: {r['base_layers']}-layer {r['base_size_in']:.0f}\" "
            f"{shape} @ {r['base_height_in']}\" high{suffix}")


def cake_sketch_svg(shape: str, size_in: float, width_in: float, height_in: float,
                     num_layers: int, num_cakes: float) -> str:
    """A small hand-sketched side view of the cake, redrawn live as she adjusts
    shape, size, and layers. Purely decorative — proportions are stretched to
    stay legible and pleasant, not dimensionally exact."""
    ink, cream = PALETTE["brown"], PALETTE["white"]
    pink = PALETTE["pink"]

    canvas_w, canvas_h = 260, 190
    cx = canvas_w / 2

    # How many ghost cakes will actually be drawn behind the main one —
    # decided up front so the whole scene (main cake included) can be
    # sized to leave them real room, rather than sizing the main cake at
    # full scale first and then fighting over whatever margin is left.
    extra = min(6, round(num_cakes) - 1) if num_cakes and num_cakes > 1 else 0
    group_scale = max(0.55, 1.0 - 0.09 * extra) if extra else 1.0

    body_w = max(70.0, min(210.0, size_in * 11)) * group_scale
    layer_h = max(14.0, min(34.0, height_in * 20))
    layers_drawn = max(1, min(int(num_layers), 8))
    body_h = max(50.0, min(148.0, layer_h * layers_drawn)) * group_scale
    top_ry = 11
    base_y = 160
    top_y = base_y - body_h

    def draw(offset_x: float = 0.0, opacity: float = 1.0, scale: float = 1.0) -> str:
        bw = body_w * scale
        bh = body_h * scale
        local_top_y = base_y - bh
        left  = cx + offset_x - bw / 2
        right = cx + offset_x + bw / 2
        layer_h_actual = bh / layers_drawn
        seam_ry = max(4.0, min(top_ry, layer_h_actual * 0.35)) * scale
        arc_ry = max(3.0, min(9.0, layer_h_actual * 0.28)) * scale

        parts = []

        if shape == "round":
            # One single body shape — no internal per-layer rects. Splitting
            # the body into stacked pieces was the actual bug: each piece
            # kept its own straight edge, and no matter how a curve was
            # layered on top, that straight line was still there underneath
            # it. With one plain body, there's nothing for the seam curves
            # to conflict with.
            # The body's bottom edge curves the same way the seams do — this
            # time it's baked into the filled shape itself (not a decorative
            # line drawn near a separate flat edge), so there's no gap of
            # background color showing between the curve and the fill.
            parts.append(
                f'<path d="M {left:.1f} {local_top_y:.1f} L {left:.1f} {base_y:.1f} '
                f'A {bw/2:.1f} {arc_ry:.1f} 0 0 0 {right:.1f} {base_y:.1f} '
                f'L {right:.1f} {local_top_y:.1f} Z" '
                f'fill="{cream}" stroke="{ink}" stroke-width="2" opacity="{opacity}"/>'
            )
            parts.append(
                f'<ellipse cx="{cx+offset_x:.1f}" cy="{local_top_y:.1f}" rx="{bw/2:.1f}" '
                f'ry="{seam_ry:.1f}" fill="{pink}" stroke="{ink}" '
                f'stroke-width="1.6" opacity="{opacity}"/>'
            )
            for i in range(1, layers_drawn):
                y = base_y - layer_h_actual * i
                arc = (f'M {left:.1f} {y:.1f} A {bw/2:.1f} {arc_ry:.1f} 0 0 0 '
                       f'{right:.1f} {y:.1f}')
                # A dark outline drawn first, then the pink line on top of
                # it — reads as one outlined curved seam, not two lines.
                parts.append(
                    f'<path d="{arc}" fill="none" stroke="{ink}" '
                    f'stroke-width="4" stroke-linecap="round" opacity="{opacity}"/>'
                )
                parts.append(
                    f'<path d="{arc}" fill="none" stroke="{pink}" '
                    f'stroke-width="2" stroke-linecap="round" opacity="{opacity}"/>'
                )
        else:
            depth = max(8.0, min(26.0, width_in * 2.2)) * scale
            band_h = max(4.0, min(8.0, layer_h_actual * 0.3))
            parts.append(
                f'<rect x="{left:.1f}" y="{local_top_y:.1f}" width="{bw:.1f}" '
                f'height="{bh:.1f}" '
                f'fill="{cream}" stroke="{ink}" stroke-width="2" opacity="{opacity}"/>'
            )
            parts.append(
                f'<polygon points="{left:.1f},{local_top_y:.1f} {right:.1f},{local_top_y:.1f} '
                f'{right-depth*0.4:.1f},{local_top_y-depth*0.5:.1f} {left-depth*0.4:.1f},{local_top_y-depth*0.5:.1f}" '
                f'fill="{pink}" stroke="{ink}" stroke-width="2" opacity="{opacity}"/>'
            )
            for i in range(1, layers_drawn):
                y = base_y - layer_h_actual * i
                parts.append(
                    f'<rect x="{left:.1f}" y="{y-band_h/2:.1f}" width="{bw:.1f}" '
                    f'height="{band_h:.1f}" fill="{pink}" stroke="{ink}" '
                    f'stroke-width="1.6" opacity="{opacity}"/>'
                )

        return "".join(parts)

    svg_body = ""
    if extra:
        # Ghost cakes fan out symmetrically behind the main one — alternating
        # left/right in pairs — instead of trailing off to one side only.
        # All cakes here (main and ghosts) are the same size, since the
        # whole scene was already scaled down above to leave genuine room —
        # shrinking just the ghosts while keeping the main cake at full size
        # made them read as background clutter rather than "more cakes."
        ghosts = []
        for i in range(extra):
            side = -1 if i % 2 == 0 else 1
            pair_index = i // 2 + 1
            ghosts.append((pair_index, side))
        max_offset = max(0.0, cx - 6 - body_w / 2)
        max_pair_index = (extra + 1) // 2
        step = body_w * 0.55
        if max_pair_index > 0:
            step = min(step, max_offset / max_pair_index)
        for pair_index, side in sorted(ghosts, key=lambda g: -g[0]):
            ghost_opacity = max(0.16, 0.42 - 0.07 * (pair_index - 1))
            svg_body += draw(offset_x=side * step * pair_index, opacity=ghost_opacity)
    svg_body += draw()

    return (
        f'<svg viewBox="0 0 {canvas_w} {canvas_h}" width="100%" height="170" '
        f'xmlns="http://www.w3.org/2000/svg">{svg_body}</svg>'
    )


st.markdown("<h1 style='text-align:center; font-style:italic;'>Quote a Cake</h1>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:center; margin-top:-0.4rem; margin-bottom:0.6rem;'>"
    "<a href='/Products_&_Pricing' target='_self' "
    f"style=\"color:{PALETTE['terracotta']}; font-size:0.88rem; "
    "text-decoration:underline; text-underline-offset:3px; "
    "font-family:'Fraunces', serif;\">Saved products →</a></div>",
    unsafe_allow_html=True,
)

recipes = get_recipes()
if not recipes:
    st.warning("No recipes yet. Head to **Add a Recipe** to create one first.")
    st.stop()

# Most-quoted recipes float to the top of the dropdown, so the cake she
# makes every week doesn't require scrolling past one-offs to find.
quote_counts = get_recipe_quote_counts()
recipes_sorted = sorted(recipes, key=lambda r: (-quote_counts.get(r["id"], 0), r["name"]))

packaging = get_packaging()

controls_col, spacer_col, output_col = st.columns([5, 1, 9])

with controls_col:

    # ── Card: Recipe ─────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("<div class='card-title'>Recipe</div>", unsafe_allow_html=True)
        recipe_names = [r["name"] for r in recipes_sorted]
        chosen_name  = st.selectbox("Recipe", recipe_names, key="quote_recipe_select",
                                     label_visibility="collapsed")
        recipe       = next(r for r in recipes_sorted if r["name"] == chosen_name)
        recipe_ings  = get_recipe_ingredients(recipe["id"])
        st.markdown(
            f"<div class='baseline-note'>{baseline_note(recipe)}</div>",
            unsafe_allow_html=True,
        )

    if not recipe_ings:
        st.warning("This recipe has no ingredients yet. Add them on the Recipes page.")
        st.stop()

    unpriced = [x for x in recipe_ings if not x.get("cost_known", 1)]

    # Remembered per-recipe defaults from the last time this recipe was
    # quoted — falls back to the recipe's own baseline the first time.
    defaults = get_setting_json(f"quote_defaults:{recipe['id']}", {}) or {}

    # ── Card: Size & shape ──────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("<div class='card-title'>Size & shape</div>", unsafe_allow_html=True)

        shape = st.radio(
            "Shape", ["round", "rect"],
            format_func=lambda x: "Round" if x == "round" else "Rectangular",
            horizontal=True,
            index=["round", "rect"].index(defaults.get("shape", recipe["base_shape"])),
        )

        if shape == "round":
            cake_size = st.number_input(
                "Diameter (inches)", min_value=4.0, max_value=18.0, step=0.5,
                format="%.1f", value=float(defaults.get("size_in", 8.0)),
            )
            rect_width = 0.0
        else:
            c1, c2 = st.columns(2)
            with c1:
                cake_size = st.number_input(
                    "Length (inches)", min_value=4.0, max_value=24.0, step=0.5,
                    format="%.1f", value=float(defaults.get("size_in", 13.0)),
                )
            with c2:
                rect_width = st.number_input(
                    "Width (inches)", min_value=4.0, max_value=24.0, step=0.5,
                    format="%.1f", value=float(defaults.get("width_in", 9.0)),
                )

        cake_height = st.number_input(
            "Layer height (inches)", min_value=0.5, max_value=4.0, step=0.05,
            format="%.2f", value=float(defaults.get("height_in", recipe["base_height_in"])),
        )

        c3, c4 = st.columns(2)
        with c3:
            num_layers = st.number_input(
                "Layers per cake", min_value=1, max_value=12, step=1,
                value=int(defaults.get("num_layers", 2)),
            )
        with c4:
            num_cakes = st.number_input(
                "Number of cakes", min_value=0.5, max_value=20.0, step=0.5,
                format="%.1f", value=float(defaults.get("num_cakes", 1.0)),
            )

        st.markdown("<div style='margin-top:0.3rem'></div>", unsafe_allow_html=True)
        use_manual_scale = st.checkbox(
            "Type in my own scale factor instead",
            value=bool(defaults.get("use_manual_scale", False)),
            help=(
                "Skips the automatic size-based calculation above and scales "
                "every ingredient by this number instead — 2.0 means double "
                "the baseline recipe, 0.5 means half."
            ),
        )
        if use_manual_scale:
            manual_scale_factor = st.number_input(
                "Scale factor", min_value=0.05, max_value=20.0, step=0.25,
                format="%.2f", value=float(defaults.get("manual_scale_factor", 1.0)),
            )
        else:
            manual_scale_factor = float(defaults.get("manual_scale_factor", 1.0))

        st.markdown(
            f"<div style='text-align:center; margin-top:0.4rem;'>"
            f"{cake_sketch_svg(shape, cake_size, rect_width, cake_height, num_layers, num_cakes)}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Card: Packaging ──────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("<div class='card-title'>Packaging</div>", unsafe_allow_html=True)

        pkg_options = ["None"] + [p["name"] for p in packaging]
        default_pkg = defaults.get("packaging_name", "None")
        if default_pkg not in pkg_options:
            default_pkg = "None"
        pkg_choice = st.selectbox("What's it going in?", pkg_options,
                                   index=pkg_options.index(default_pkg))
        chosen_pkg = next((p for p in packaging if p["name"] == pkg_choice), None)
        if not packaging:
            st.caption("No packaging on file — add it on **Manage Costs** if you want it included.")

# ── Compute ────────────────────────────────────────────────────────────────────
target = ScaleTarget(
    shape=shape, size_in=cake_size, width_in=rect_width,
    height_in=cake_height, num_layers=num_layers, num_cakes=num_cakes,
    adjustment_pct=0.0,
)
baseline = BaselineRecipe(
    num_layers=recipe["base_layers"], size_in=recipe["base_size_in"],
    height_in=recipe["base_height_in"], shape=recipe["base_shape"],
    num_cakes=recipe.get("base_num_cakes", 1.0),
)
ingredients = [
    Ingredient(r["name"], r["base_qty"], r["unit"], r["weight_g"], r["cost_per_g"])
    for r in recipe_ings
]

if use_manual_scale:
    # Bypass the size-based geometry calculation entirely — every ingredient
    # is just the baseline amount times her own number. ScaledLine mirrors
    # the fields scale_product()'s own return values have (name, qty, unit,
    # weight_g, line_cost), so none of the display code below needs to know
    # or care which path was taken.
    factor = manual_scale_factor
    scaled = [
        ScaledLine(
            name=r["name"], qty=r["base_qty"] * factor, unit=r["unit"],
            weight_g=r["weight_g"] * factor,
            line_cost=r["weight_g"] * factor * r["cost_per_g"],
        )
        for r in recipe_ings
    ]
    ing_cost = sum(s.line_cost for s in scaled)
else:
    scaled, factor, ing_cost = scale_product(ingredients, target, baseline)

pkg_cost   = float(chosen_pkg["cost_per_item"]) if chosen_pkg else 0.0
total_cost = ing_cost + pkg_cost

# Remember this recipe's inputs for next time, and count it as quoted once
# per recipe selection (not on every widget nudge) so "most-quoted" stays
# meaningful rather than just tracking whoever was open longest.
set_setting_json(f"quote_defaults:{recipe['id']}", {
    "shape": shape, "size_in": cake_size, "width_in": rect_width,
    "height_in": cake_height, "num_layers": num_layers, "num_cakes": num_cakes,
    "packaging_name": pkg_choice,
    "use_manual_scale": use_manual_scale, "manual_scale_factor": manual_scale_factor,
})
if st.session_state.get("last_quoted_recipe_id") != recipe["id"]:
    record_recipe_quote(recipe["id"])
    st.session_state["last_quoted_recipe_id"] = recipe["id"]

# ── Output ─────────────────────────────────────────────────────────────────────
with output_col:
    shape_label = (f"{cake_size:.0f}\" round" if shape == "round"
                   else f"{cake_size:.0f}×{rect_width:.0f}\" rect")

    if unpriced:
        names = ", ".join(f"**{x['name']}**" for x in unpriced)
        st.markdown(
            f"<span class='unknown-badge'>⚠ {len(unpriced)} ingredient(s) don't have "
            f"a price yet ({names}) — the totals below are missing their cost.</span>",
            unsafe_allow_html=True,
        )

    # ── Cost breakdown ───────────────────────────────────────────────────────
    st.markdown(f"<div class='receipt-charge'>${total_cost:.2f}</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='receipt-charge-label'>total cost for this batch</div>",
        unsafe_allow_html=True,
    )

    pkg_line_label = f"Packaging ({chosen_pkg['name']})" if chosen_pkg else "Packaging (none selected)"
    st.markdown(
        "<div class='receipt-box'>"
        f"<div class='receipt-line'><span>Ingredients</span><span>${ing_cost:.2f}</span></div>"
        f"<div class='receipt-line'><span>{pkg_line_label}</span><span>${pkg_cost:.2f}</span></div>"
        f"<div class='receipt-line total'><span>Total cost</span><span>${total_cost:.2f}</span></div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Shopping / prep list ────────────────────────────────────────────────
    st.markdown("### Shopping list for this batch")
    if use_manual_scale:
        st.caption(
            f"Using your manual scale factor of ×{manual_scale_factor:.2f} — "
            "the size/shape inputs above aren't driving these quantities."
        )
    rows = [{
        "Ingredient": s.name,
        "Qty":        display_qty(s.qty, s.unit),
        "Unit":       s.unit,
        "Weight (g)": f"{s.weight_g:.1f}",
        "Line cost":  f"${s.line_cost:.4f}",
    } for s in scaled]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    total_weight = sum(s.weight_g for s in scaled)
    st.caption(f"Total batter weight: {total_weight:.1f} g")

    with st.expander("Compare with the recipe's baseline"):
        comp_rows = [{
            "Ingredient":   orig["name"],
            "Baseline qty": f"{display_qty(orig['base_qty'], orig['unit'])} {orig['unit']}",
            "Scaled qty":   f"{display_qty(sc.qty, sc.unit)} {sc.unit}",
        } for orig, sc in zip(recipe_ings, scaled)]
        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)
        base_cost = sum(r["line_cost"] for r in recipe_ings)
        st.caption(f"Baseline ingredient cost: ${base_cost:.4f}  →  This batch: ${ing_cost:.4f}")

    with st.expander("Save this size as a standard product"):
        st.caption(
            "For a size you'll quote again and again — this saves it to your "
            "product catalog so it's easy to pull up later."
        )
        save_name = st.text_input(
            "Product name", placeholder=f'e.g. {recipe["name"]} — {shape_label}',
            key="quote_save_product_name",
        )
        if st.button("Save product", key="quote_save_product_btn"):
            if not save_name.strip():
                st.error("Please enter a name for this product.")
            else:
                upsert_product(
                    recipe_id=recipe["id"], name=save_name.strip(),
                    cake_size_in=cake_size, cake_shape=shape,
                    cake_height_in=cake_height, num_layers=int(num_layers),
                    num_cakes=num_cakes, adjustment_pct=0.0,
                    rect_width_in=rect_width,
                    packaging_id=chosen_pkg["id"] if chosen_pkg else None,
                )
                st.success(f"Saved **{save_name}** to your product catalog.")
        st.page_link("pages/4_Products_&_Pricing.py", label="Manage saved products →")

    with st.expander("See a suggested price at different margins"):
        st.caption(
            "Optional — the cost above is what this batch costs you. This just "
            "adds a profit margin on top, if you want a starting point for what "
            "to charge."
        )
        margin_pct = st.slider(
            "Profit margin", min_value=10, max_value=80, value=60, step=5,
            help=(
                "How much of the final price is profit, after cost. 60% means: "
                "of every dollar you charge, 60 cents is profit and 40 cents "
                "covers cost."
            ),
        )
        margin_fraction = margin_pct / 100
        suggested_price = total_cost / (1 - margin_fraction) if margin_fraction < 1 else 0.0
        profit = suggested_price - total_cost
        st.markdown(
            "<div class='receipt-box'>"
            f"<div class='receipt-line'><span>Total cost</span><span>${total_cost:.2f}</span></div>"
            f"<div class='receipt-line'><span>Profit at {margin_pct}%</span><span>${profit:.2f}</span></div>"
            f"<div class='receipt-line total'><span>Suggested price</span><span>${suggested_price:.2f}</span></div>"
            "</div>",
            unsafe_allow_html=True,
        )

render_footer("3_Quote_a_Cake.py")
