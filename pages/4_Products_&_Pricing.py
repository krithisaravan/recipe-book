"""
Page — Saved Products
A catalog of standard offerings (fixed size + packaging combos) for quick
reference. This is a secondary, tucked-away page — actually calculating a
price for an order happens on Quote a Cake, which doesn't require a saved
product at all. Reached from Quote a Cake and the Dashboard, not the main
top nav.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from db import (
    init_db, get_recipes, get_recipe_ingredients,
    get_packaging, get_products, upsert_product, delete_product,
)
from scaling import ScaleTarget, BaselineRecipe, scale_product, Ingredient
from shared import apply_page_style, render_footer, FAVICON_PATH

init_db()

st.set_page_config(page_title="Saved Products · My Recipe Book", page_icon=FAVICON_PATH, layout="wide")
apply_page_style("4_Products_&_Pricing.py")

st.markdown("<h1 style='text-align:center; font-style:italic;'>Saved Products</h1>", unsafe_allow_html=True)
st.caption(
    "Your catalog of standard sizes and packaging combos, for quick reference. "
    "To actually price an order, use **Quote a Cake**, which works straight from "
    "a recipe and doesn't need a saved product first."
)
st.page_link("pages/3_Quote_a_Cake.py", label="Go to Quote a Cake →")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

recipes   = get_recipes()
packaging = get_packaging()

if not recipes:
    st.warning("No recipes yet. Head to **Add a Recipe** first.")
    st.stop()

all_products_manage = get_products()

st.markdown("### Products")

if all_products_manage:
    manage_rows = [{
        "Product":   p["name"],
        "Recipe":    p["recipe_name"],
        "Size":      f"{p['cake_size_in']:.0f}\" {'rnd' if p['cake_shape']=='round' else 'rct'}",
        "Layers":    p["num_layers"],
        "Cakes":     p["num_cakes"],
        "Packaging": p["packaging_name"] or "—",
    } for p in all_products_manage]
    st.dataframe(pd.DataFrame(manage_rows), use_container_width=True, hide_index=True)
else:
    st.info(
        "No products saved yet. You can save one here, or from the "
        "\"Save this size as a standard product\" section on Quote a Cake."
    )

st.markdown('<hr class="divider">', unsafe_allow_html=True)

edit_options = ["— add new —"] + [p["name"] for p in all_products_manage]
edit_choice  = st.selectbox("Edit an existing product, or add a new one",
                            edit_options, key="prod_edit_select")

editing_prod = None
if edit_choice != "— add new —":
    editing_prod = next(p for p in all_products_manage if p["name"] == edit_choice)

with st.form("product_form", clear_on_submit=True):
    st.markdown(f"#### {'Edit' if editing_prod else 'Add'} product")

    c1, c2 = st.columns(2)
    with c1:
        prod_name = st.text_input(
            "Product name",
            value=editing_prod["name"] if editing_prod else "",
            placeholder='e.g. 8" double layer',
        )
        prod_recipe_names = [r["name"] for r in recipes]
        default_recipe_idx = 0
        if editing_prod and editing_prod["recipe_name"] in prod_recipe_names:
            default_recipe_idx = prod_recipe_names.index(editing_prod["recipe_name"])
        prod_recipe_name = st.selectbox("Recipe", prod_recipe_names,
                                         index=default_recipe_idx)
        prod_recipe = next(r for r in recipes if r["name"] == prod_recipe_name)

    with c2:
        pkg_options   = ["None"] + [p["name"] for p in packaging]
        default_pkg   = (editing_prod["packaging_name"]
                         if editing_prod and editing_prod.get("packaging_name")
                         else "None")
        if default_pkg not in pkg_options:
            default_pkg = "None"
        prod_pkg_name = st.selectbox("Packaging (optional)", pkg_options,
                                      index=pkg_options.index(default_pkg))
        if len(pkg_options) == 1:
            st.caption("No packaging on file yet — add items on **Manage Costs**.")
        prod_pkg = next((p for p in packaging if p["name"] == prod_pkg_name), None)

    st.markdown("**Cake dimensions**")
    c3, c4, c5 = st.columns(3)
    with c3:
        prod_shape = st.selectbox(
            "Shape", ["round", "rect"],
            format_func=lambda x: "Round" if x == "round" else "Rectangular",
            index=["round", "rect"].index(editing_prod["cake_shape"])
                  if editing_prod else 0,
        )
    with c4:
        prod_size = st.number_input(
            "Size / length (in)", min_value=4.0, max_value=24.0,
            step=0.5, format="%.1f",
            value=float(editing_prod["cake_size_in"]) if editing_prod else 8.0,
        )
    with c5:
        prod_width = st.number_input(
            "Width (in, rect only)", min_value=0.0, max_value=24.0,
            step=0.5, format="%.1f",
            value=float(editing_prod["rect_width_in"]) if editing_prod else 0.0,
            help="Leave 0 for round cakes.",
        )

    c6, c7, c8 = st.columns(3)
    with c6:
        prod_height = st.number_input(
            "Layer height (in)", min_value=0.5, max_value=4.0,
            step=0.05, format="%.2f",
            value=float(editing_prod["cake_height_in"]) if editing_prod
                  else float(prod_recipe["base_height_in"]),
        )
    with c7:
        prod_layers = st.number_input(
            "Layers per cake", min_value=1, max_value=12, step=1,
            value=int(editing_prod["num_layers"]) if editing_prod else 2,
        )
    with c8:
        prod_cakes = st.number_input(
            "Number of cakes", min_value=0.5, max_value=20.0,
            step=0.5, format="%.1f",
            value=float(editing_prod["num_cakes"]) if editing_prod else 1.0,
        )

    save_prod = st.form_submit_button("Save product")

if save_prod:
    if not prod_name.strip():
        st.error("Please enter a product name.")
    elif prod_shape == "rect" and prod_width <= 0:
        st.error("Please enter a width for rectangular cakes.")
    else:
        upsert_product(
            recipe_id=prod_recipe["id"],
            name=prod_name.strip(),
            cake_size_in=prod_size,
            cake_shape=prod_shape,
            cake_height_in=prod_height,
            num_layers=prod_layers,
            num_cakes=prod_cakes,
            adjustment_pct=0.0,
            rect_width_in=prod_width,
            packaging_id=prod_pkg["id"] if prod_pkg else None,
            product_id=editing_prod["id"] if editing_prod else None,
        )
        st.success(f"{'Updated' if editing_prod else 'Added'} **{prod_name}**.")
        st.rerun()

if all_products_manage:
    with st.expander("Remove a product"):
        del_name = st.selectbox("Choose product to remove",
                                 [p["name"] for p in all_products_manage],
                                 key="del_prod_select")
        if st.button("Remove", key="del_prod_btn", type="secondary"):
            row = next(p for p in all_products_manage if p["name"] == del_name)
            delete_product(row["id"])
            st.success(f"Removed **{del_name}**.")
            st.rerun()

render_footer("4_Products_&_Pricing.py")