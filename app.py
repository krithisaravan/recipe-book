"""
Dashboard — task-first landing page. Asks "what do you want to do?"
instead of leading with entity management (Ingredients / Recipes / Products).
"""
import streamlit as st
import pandas as pd
from db import (
    init_db, get_ingredients, get_packaging, get_recipes,
    get_recipe_ingredients, get_products,
)
from shared import apply_page_style, render_footer, FAVICON_PATH

init_db()

st.set_page_config(page_title="My Recipe Book", page_icon=FAVICON_PATH, layout="wide")
apply_page_style("app.py")

ingredients = get_ingredients()
packaging   = get_packaging()
recipes     = get_recipes()
products    = get_products()

has_ingredients = len(ingredients) > 0
has_recipes     = len(recipes) > 0

st.markdown("<h1 style='text-align:center; font-style:italic;'>My Recipe Book</h1>", unsafe_allow_html=True)

# ── What do you want to do? ───────────────────────────────────────────────────
st.markdown(
    "<p style='text-align:center; color:#7A5C44; font-size:1.1rem;'>What do you want to do?</p>",
    unsafe_allow_html=True,
)

t1, t2, t3 = st.columns(3, gap="medium")

with t1:
    st.markdown(
        "<div class='task-card'>"
        "<a class='task-card-link' href='/Recipes' target='_self'></a>"
        "<div class='task-card-icon'>01</div>"
        "<div class='task-card-title'>Add a recipe</div>"
        "<div class='task-card-desc'>Enter a baseline recipe and its "
        "ingredients — even if some prices aren't in yet.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

with t2:
    if has_recipes:
        st.markdown(
            "<div class='task-card'>"
            "<a class='task-card-link' href='/Quote_a_Cake' target='_self'></a>"
            "<div class='task-card-icon'>02</div>"
            "<div class='task-card-title'>Quote a cake</div>"
            "<div class='task-card-desc'>Pick a recipe and a size — get the shopping "
            "list and the total cost, on one screen.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='task-card disabled' title='Add a recipe first'>"
            "<div class='task-card-icon'>02</div>"
            "<div class='task-card-title'>Quote a cake</div>"
            "<div class='task-card-desc'>Pick a recipe and a size — get the shopping "
            "list and the total cost, on one screen.</div>"
            "</div>",
            unsafe_allow_html=True,
        )

with t3:
    st.markdown(
        "<div class='task-card'>"
        "<a class='task-card-link' href='/Ingredients_&_Packaging' target='_self'></a>"
        "<div class='task-card-icon'>03</div>"
        "<div class='task-card-title'>Manage ingredient costs</div>"
        "<div class='task-card-desc'>Keep what you paid for ingredients and "
        "packaging current, so every quote stays accurate.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

st.markdown(
    "<div style='text-align:center; margin-top:0.9rem;'>"
    "<a href='/Products_&_Pricing' target='_self' "
    "style=\"color:#C1603A; font-size:0.88rem; text-decoration:underline; "
    "text-underline-offset:3px; font-family:'Fraunces', serif;\">"
    "Manage your saved products catalog</a></div>",
    unsafe_allow_html=True,
)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── Getting started (shown until the basics are in place) ────────────────────
if not (has_ingredients and has_recipes):
    st.markdown("### Getting started")
    st.caption("Two things to set up first — then you can quote a cake any time.")

    c1, c2 = st.columns(2)
    with c1:
        check = "✓ " if has_recipes else ""
        st.markdown(
            f"<div class='step-card'>"
            f"<div class='step-card-num'>Step 1</div>"
            f"<div class='step-card-title'>{check}Add a recipe</div>"
            f"<div class='step-card-desc'>Create a recipe and its baseline "
            f"quantities. Don't have a price for an ingredient yet? Add it "
            f"anyway — you can price it later.</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/2_Recipes.py", label="Go add a recipe →")
    with c2:
        check = "✓ " if has_ingredients else ""
        st.markdown(
            f"<div class='step-card'>"
            f"<div class='step-card-num'>Step 2</div>"
            f"<div class='step-card-title'>{check}Manage ingredient costs</div>"
            f"<div class='step-card-desc'>Add what you paid for ingredients and "
            f"packaging. Cost per gram calculates automatically.</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/1_Ingredients_&_Packaging.py", label="Go manage costs →")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

if not recipes:
    st.stop()

# ── Recipes overview ─────────────────────────────────────────────────────────
st.markdown("### Your recipes")
recipe_rows = []
for r in recipes:
    ri = get_recipe_ingredients(r["id"])
    base_cost = sum(x["line_cost"] for x in ri)
    shape_lbl = "round" if r["base_shape"] == "round" else "rect"
    recipe_rows.append({
        "Recipe":      r["name"],
        "Baseline":    f"{r['base_layers']}-layer {r['base_size_in']:.0f}\" {shape_lbl}",
        "Ingredients": len(ri),
        "Base cost":   f"${base_cost:.4f}" if ri else "—",
    })
st.dataframe(pd.DataFrame(recipe_rows), use_container_width=True, hide_index=True)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── Saved products (secondary — tucked behind an expander, not the main flow) ─
with st.expander("Saved products & margins"):
    if not products:
        st.info(
            "No saved products yet. You don't need one to quote a cake — head "
            "to **Quote a Cake** any time — but saving a standard offering here "
            "makes it faster to re-quote later."
        )
        st.page_link("pages/4_Products_&_Pricing.py", label="Manage saved products →")
    else:
        from scaling import ScaleTarget, BaselineRecipe, scale_product, Ingredient

        recipe_map   = {r["id"]: r for r in recipes}
        product_rows = []

        for p in products:
            recipe = recipe_map.get(p["recipe_id"])
            if not recipe:
                continue
            ri = get_recipe_ingredients(recipe["id"])
            if not ri:
                continue
            ingredients_obj = [
                Ingredient(x["name"], x["base_qty"], x["unit"], x["weight_g"], x["cost_per_g"])
                for x in ri
            ]
            target = ScaleTarget(
                shape=p["cake_shape"], size_in=p["cake_size_in"],
                width_in=p["rect_width_in"] or 0.0, height_in=p["cake_height_in"],
                num_layers=p["num_layers"], num_cakes=p["num_cakes"],
                adjustment_pct=0.0,
            )
            baseline = BaselineRecipe(
                num_layers=recipe["base_layers"], size_in=recipe["base_size_in"],
                height_in=recipe["base_height_in"], shape=recipe["base_shape"],
                num_cakes=recipe.get("base_num_cakes", 1.0),
            )
            _, _, ing_cost = scale_product(ingredients_obj, target, baseline)
            pkg_cost   = float(p.get("packaging_cost") or 0.0)
            total_cost = ing_cost + pkg_cost
            price_60   = total_cost / 0.4 if total_cost else 0.0

            product_rows.append({
                "Product":            p["name"],
                "Recipe":             p["recipe_name"],
                "Total cost":         total_cost,
                "Price @ 60% margin": price_60,
            })

        if product_rows:
            df = pd.DataFrame(product_rows)
            df_display = df.copy()
            df_display["Total cost"]          = df_display["Total cost"].map("${:.4f}".format)
            df_display["Price @ 60% margin"]  = df_display["Price @ 60% margin"].map("${:.2f}".format)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.page_link("pages/4_Products_&_Pricing.py", label="Manage saved products →")

render_footer("app.py")