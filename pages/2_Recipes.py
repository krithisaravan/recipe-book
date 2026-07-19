"""
Page — Add a Recipe
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from db import (
    init_db, get_recipes, upsert_recipe, delete_recipe,
    get_ingredients, create_placeholder_ingredient,
    get_recipe_ingredients, set_recipe_ingredient, remove_recipe_ingredient,
)
from shared import apply_page_style, render_footer

init_db()

st.set_page_config(page_title="Add a Recipe · My Recipe Book", page_icon="🧁", layout="wide")
apply_page_style("2_Recipes.py")

st.markdown("""
<style>
  .recipe-card {
    background: #FFFDF8;
    border: 1.5px solid #D4B896;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    cursor: pointer;
  }
  .recipe-card.active { border-color: #2C1A0E; background: #EEC9C0; }
  .recipe-card-name { font-weight: 600; font-size: 0.95rem; color: #2C1A0E; }
  .recipe-card-sub  { font-size: 0.78rem; color: #7A5C44; margin-top: 2px; }

  .panel-header {
    font-family: 'DM Serif Display', serif;
    font-size: 1.3rem; color: #2C1A0E;
    margin-bottom: 0.25rem;
  }
  .baseline-pill {
    display: inline-block; background: #EEC9C0;
    border: 1px solid #D4A090; border-radius: 999px;
    padding: 3px 12px; font-size: 0.82rem; color: #2C1A0E;
    margin-bottom: 1rem;
  }
  .ing-row-name  { font-weight: 500; color: #2C1A0E; }
  .ing-row-qty   { color: #2C1A0E; }
  .ing-row-cost  { color: #7A5C44; font-size: 0.82rem; }

  .draft-row {
    background: #FFFDF8; border: 1px solid #D4B896;
    border-radius: 8px; padding: 0.4rem 0.75rem;
    margin-bottom: 0.35rem; font-size: 0.88rem;
    display: flex; justify-content: space-between; align-items: center;
  }
  hr.divider { border: none; border-top: 1px solid #D4B896; margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)

GRAM_UNITS = {"grams", "mils"}
UNIT_OPTS  = ["grams", "mils", "whole egg", "tsp", "tbsp", "oz", "lb"]

# ── State ──────────────────────────────────────────────────────────────────────
for key, default in [
    ("selected_recipe_id", None),
    ("recipe_panel", "view"),        # "view" | "create" | "edit"
    ("editing_ing_id", None),
    ("draft_ingredients", []),
    ("recipes_initialized", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

recipes         = get_recipes()
all_ingredients = get_ingredients()

# Auto-select first recipe on first load only
if not st.session_state.recipes_initialized:
    st.session_state.recipes_initialized = True
    if recipes:
        st.session_state.selected_recipe_id = recipes[0]["id"]
        st.session_state.recipe_panel = "view"

selected_recipe = next(
    (r for r in recipes if r["id"] == st.session_state.selected_recipe_id), None
)

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("<h1 style='text-align:center; font-style:italic;'>Recipes</h1>", unsafe_allow_html=True)
st.caption(
    "Each recipe needs a **baseline** — the size and quantity the original "
    "recipe is written for. The app scales everything else from that. "
    "Don't have a price for an ingredient yet? Add it anyway — you can "
    "price it later from **Manage Costs**."
)

col_list, col_panel = st.columns([1, 2], gap="large")


# ══════════════════════════════════════════════════════════════════════════════
# LEFT — Recipe list
# ══════════════════════════════════════════════════════════════════════════════
with col_list:
    # New recipe button at top for discoverability
    if st.button("+ New recipe", use_container_width=True, type="primary"):
        st.session_state.selected_recipe_id = None
        st.session_state.recipe_panel = "create"
        st.session_state.draft_ingredients = []
        st.rerun()

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    if not recipes:
        st.info("No recipes yet — click **+ New recipe** to create your first one.")
    else:
        for r in recipes:
            is_active  = r["id"] == st.session_state.selected_recipe_id
            card_class = "recipe-card active" if is_active else "recipe-card"
            shape_lbl  = "round" if r["base_shape"] == "round" else "rect"
            st.markdown(
                f"<div class='{card_class}'>"
                f"<div class='recipe-card-name'>{r['name']}</div>"
                f"<div class='recipe-card-sub'>"
                f"{r['base_layers']}-layer {r['base_size_in']:.0f}\" {shape_lbl}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("Open", key=f"open_{r['id']}", use_container_width=True):
                st.session_state.selected_recipe_id = r["id"]
                st.session_state.recipe_panel = "view"
                st.session_state.editing_ing_id = None
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# RIGHT — Panel (view recipe / create / edit)
# ══════════════════════════════════════════════════════════════════════════════
with col_panel:
    panel = st.session_state.recipe_panel

    # ── CREATE PANEL ──────────────────────────────────────────────────────────
    if panel == "create":
        st.markdown("<div class='panel-header'>New recipe</div>", unsafe_allow_html=True)
        st.caption("Fill in the baseline output — what does one full batch produce?")

        fk = "new"  # form key suffix so widgets remount blank each time

        new_name = st.text_input("Recipe name", placeholder="e.g. Vanilla Butter Cake",
                                  key=f"r_name_{fk}")

        c1, c2 = st.columns(2)
        with c1:
            new_layers = st.number_input("Layers per cake", min_value=1, step=1,
                                          value=1, key=f"r_layers_{fk}")
            new_size   = st.number_input("Layer size (in)", min_value=1.0, step=0.5,
                                          format="%.1f", value=6.0, key=f"r_size_{fk}")
        with c2:
            new_height = st.number_input("Layer height (in)", min_value=0.5, step=0.05,
                                          format="%.2f", value=1.30, key=f"r_height_{fk}")
            new_cakes  = st.number_input(
                "Cakes per batch", min_value=0.5, step=0.5, format="%.1f",
                value=1.0, key=f"r_cakes_{fk}",
                help="How many cakes does one full batch of this recipe produce? Usually 1.",
            )

        new_shape = st.radio("Shape", ["round", "rect"],
                              format_func=lambda x: "Round" if x == "round" else "Rectangular",
                              horizontal=True, key=f"r_shape_{fk}")
        new_notes = st.text_area("Notes (optional)", height=60,
                                  placeholder="Any notes…", key=f"r_notes_{fk}")

        # Draft ingredients
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        st.markdown("**Ingredients** *(optional — you can add these after saving)*")

        if st.session_state.draft_ingredients:
            for idx, d in enumerate(st.session_state.draft_ingredients):
                qty_str = f"{d['qty']:.0f}" if d["unit"] in GRAM_UNITS else f"{d['qty']:.2f}"
                badge = (" <span class='unknown-badge'>⚠ needs price</span>"
                         if not d.get("cost_known", True) else "")
                dc1, dc2 = st.columns([6, 1])
                with dc1:
                    st.markdown(
                        f"<div class='draft-row'><span><b>{d['name']}</b> — "
                        f"{qty_str} {d['unit']}{badge}</span></div>",
                        unsafe_allow_html=True,
                    )
                with dc2:
                    if st.button("✕", key=f"rm_draft_{idx}"):
                        st.session_state.draft_ingredients.pop(idx)
                        st.rerun()

        used_names = {d["name"] for d in st.session_state.draft_ingredients}
        available  = [i for i in all_ingredients if i["name"] not in used_names]

        # Toggle lives outside the form so switching it reruns immediately
        # and swaps the selectbox for a text input — the form itself stays
        # untouched, so nothing she's already typed gets wiped.
        new_ing_toggle = st.checkbox(
            "This ingredient isn't in my price list yet",
            key="draft_new_ing_toggle",
            help="Add it now with the name only — price it later from Manage Costs.",
        )

        if not all_ingredients and not new_ing_toggle:
            st.caption(
                "No ingredients in your cost list yet — add them on **Manage Costs**, "
                "or check the box above to add one by name now."
            )
        elif new_ing_toggle or available:
            with st.form("draft_ing_form", clear_on_submit=True):
                di1, di2, di3 = st.columns([3, 2, 2])
                with di1:
                    if new_ing_toggle:
                        d_name = st.text_input("New ingredient name", placeholder="e.g. Vanilla bean paste")
                    else:
                        d_name = st.selectbox("Ingredient", [i["name"] for i in available])
                with di2:
                    d_qty  = st.number_input("Qty", min_value=0.0, step=1.0,
                                              format="%.2f", value=0.0)
                with di3:
                    d_unit = st.selectbox("Unit", UNIT_OPTS)

                if d_unit not in GRAM_UNITS:
                    d_weight = st.number_input("Weight in grams (for costing)",
                                                min_value=0.0, step=1.0,
                                                format="%.2f", value=0.0)
                else:
                    d_weight = d_qty

                if st.form_submit_button("Add ingredient", use_container_width=True):
                    if new_ing_toggle and not d_name.strip():
                        st.error("Please enter a name for the new ingredient.")
                    elif d_qty <= 0:
                        st.error("Quantity must be greater than 0.")
                    elif d_unit not in GRAM_UNITS and d_weight <= 0:
                        st.error("Please enter the weight in grams for costing.")
                    else:
                        if new_ing_toggle:
                            new_id, _existed = create_placeholder_ingredient(d_name.strip())
                            st.session_state.draft_ingredients.append({
                                "ingredient_id": new_id,
                                "name": d_name.strip(),
                                "qty": d_qty, "unit": d_unit, "weight_g": d_weight,
                                "cost_known": False,
                            })
                        else:
                            d_ing = next(i for i in available if i["name"] == d_name)
                            st.session_state.draft_ingredients.append({
                                "ingredient_id": d_ing["id"],
                                "name": d_ing["name"],
                                "qty": d_qty, "unit": d_unit, "weight_g": d_weight,
                                "cost_known": bool(d_ing.get("cost_known", 1)),
                            })
                        st.rerun()

        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("Save recipe", type="primary", use_container_width=True):
                if not new_name.strip():
                    st.error("Please enter a recipe name.")
                else:
                    new_id = upsert_recipe(
                        name=new_name.strip(), base_layers=new_layers,
                        base_size_in=new_size, base_height_in=new_height,
                        base_shape=new_shape, base_num_cakes=new_cakes,
                        notes=new_notes.strip(),
                    )
                    for d in st.session_state.draft_ingredients:
                        set_recipe_ingredient(
                            recipe_id=new_id, ingredient_id=d["ingredient_id"],
                            base_qty=d["qty"], unit=d["unit"], weight_g=d["weight_g"],
                        )
                    unpriced_saved = sum(
                        1 for d in st.session_state.draft_ingredients
                        if not d.get("cost_known", True)
                    )
                    st.session_state.draft_ingredients = []
                    st.session_state.selected_recipe_id = new_id
                    st.session_state.recipe_panel = "view"
                    # Clear form widgets
                    for k in [f"r_name_{fk}", f"r_layers_{fk}", f"r_size_{fk}",
                               f"r_height_{fk}", f"r_cakes_{fk}",
                               f"r_shape_{fk}", f"r_notes_{fk}"]:
                        st.session_state.pop(k, None)
                    st.session_state.pop("draft_new_ing_toggle", None)
                    if unpriced_saved:
                        st.success(
                            f"Created **{new_name}** — {unpriced_saved} ingredient(s) "
                            "still need a price, add it whenever you're ready."
                        )
                    else:
                        st.success(f"Created **{new_name}**.")
                    st.rerun()
        with bc2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.recipe_panel = "view"
                st.session_state.draft_ingredients = []
                st.rerun()

    # ── VIEW / EDIT PANEL ─────────────────────────────────────────────────────
    elif selected_recipe is None:
        st.info("Select a recipe from the list, or click **+ New recipe** to create one.")

    else:
        r = selected_recipe
        shape_lbl  = "round" if r["base_shape"] == "round" else "rect"
        base_cakes = r.get("base_num_cakes", 1.0)
        cakes_sfx  = f" × {base_cakes:g} cake(s)" if base_cakes != 1.0 else ""
        recipe_ings = get_recipe_ingredients(r["id"])

        # ── Recipe header with edit toggle ────────────────────────────────────
        rh1, rh2 = st.columns([3, 1])
        with rh1:
            st.markdown(f"<div class='panel-header'>{r['name']}</div>",
                        unsafe_allow_html=True)
            st.markdown(
                f"<span class='baseline-pill'>"
                f"{r['base_layers']}-layer {r['base_size_in']:.0f}\" {shape_lbl} "
                f"@ {r['base_height_in']}\" high{cakes_sfx}"
                f"</span>",
                unsafe_allow_html=True,
            )
        with rh2:
            edit_open = (panel == "edit")
            if st.button("Edit recipe" if not edit_open else "Cancel edit",
                          use_container_width=True):
                st.session_state.recipe_panel = "view" if edit_open else "edit"
                st.rerun()

        # ── Inline edit form ──────────────────────────────────────────────────
        if panel == "edit":
            with st.form(f"edit_recipe_{r['id']}", clear_on_submit=False):
                e_name = st.text_input("Recipe name", value=r["name"])
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_layers = st.number_input("Layers per cake", min_value=1, step=1,
                                                value=int(r["base_layers"]))
                    e_size   = st.number_input("Layer size (in)", min_value=1.0,
                                                step=0.5, format="%.1f",
                                                value=float(r["base_size_in"]))
                with ec2:
                    e_height = st.number_input("Layer height (in)", min_value=0.5,
                                                step=0.05, format="%.2f",
                                                value=float(r["base_height_in"]))
                    e_cakes  = st.number_input(
                        "Cakes per batch", min_value=0.5, step=0.5, format="%.1f",
                        value=float(r.get("base_num_cakes", 1.0)),
                        help="How many cakes does one full batch produce?",
                    )
                e_shape = st.radio(
                    "Shape", ["round", "rect"],
                    format_func=lambda x: "Round" if x == "round" else "Rectangular",
                    horizontal=True,
                    index=["round", "rect"].index(r["base_shape"]),
                )
                e_notes = st.text_area("Notes (optional)", value=r["notes"] or "",
                                        height=60)
                s1, s2 = st.columns(2)
                with s1:
                    save_edit = st.form_submit_button("Save changes",
                                                       use_container_width=True)
                with s2:
                    del_clicked = st.form_submit_button("Delete recipe",
                                                         use_container_width=True,
                                                         type="secondary")

            if save_edit:
                if not e_name.strip():
                    st.error("Please enter a recipe name.")
                else:
                    upsert_recipe(
                        name=e_name.strip(), base_layers=e_layers,
                        base_size_in=e_size, base_height_in=e_height,
                        base_shape=e_shape, base_num_cakes=e_cakes,
                        notes=e_notes.strip(), recipe_id=r["id"],
                    )
                    st.session_state.recipe_panel = "view"
                    st.success("Saved.")
                    st.rerun()

            if del_clicked:
                delete_recipe(r["id"])
                st.session_state.selected_recipe_id = None
                st.session_state.recipe_panel = "view"
                st.success(f"Deleted **{r['name']}**.")
                st.rerun()

            st.markdown('<hr class="divider">', unsafe_allow_html=True)

        # ── Ingredient list ───────────────────────────────────────────────────
        st.markdown("**Ingredients**")

        unpriced_in_recipe = [x for x in recipe_ings if not x.get("cost_known", 1)]
        if unpriced_in_recipe:
            names = ", ".join(f"**{x['name']}**" for x in unpriced_in_recipe)
            st.markdown(
                f"<span class='unknown-badge'>⚠ {len(unpriced_in_recipe)} ingredient(s) "
                f"still need a price: {names}</span>",
                unsafe_allow_html=True,
            )

        if recipe_ings:
            for ing in recipe_ings:
                is_editing = st.session_state.editing_ing_id == ing["ingredient_id"]
                qty_str  = (f"{ing['base_qty']:.0f}" if ing["unit"] in GRAM_UNITS
                            else f"{ing['base_qty']:.2f}")
                unpriced = not ing.get("cost_known", 1)

                if is_editing:
                    with st.form(f"edit_ing_{ing['ingredient_id']}", clear_on_submit=False):
                        st.markdown(f"**Editing: {ing['name']}**")
                        ei1, ei2 = st.columns(2)
                        with ei1:
                            new_qty = st.number_input("Qty", min_value=0.0, step=1.0,
                                                       format="%.2f",
                                                       value=float(ing["base_qty"]))
                        with ei2:
                            unit_opts = UNIT_OPTS.copy()
                            if ing["unit"] not in unit_opts:
                                unit_opts.insert(0, ing["unit"])
                            new_unit = st.selectbox("Unit", unit_opts,
                                                     index=unit_opts.index(ing["unit"]))
                        if new_unit in GRAM_UNITS:
                            new_weight = new_qty
                            st.caption(f"Costing weight: {new_weight:.0f} g")
                        else:
                            new_weight = st.number_input(
                                "Weight in grams (for costing)",
                                min_value=0.0, step=1.0, format="%.2f",
                                value=float(ing["weight_g"]))
                        b1, b2 = st.columns(2)
                        with b1:
                            save_ing = st.form_submit_button("Save", use_container_width=True)
                        with b2:
                            cancel_ing = st.form_submit_button("Cancel",
                                                                use_container_width=True)
                    if save_ing:
                        if new_qty <= 0:
                            st.error("Quantity must be > 0.")
                        else:
                            set_recipe_ingredient(
                                recipe_id=r["id"], ingredient_id=ing["ingredient_id"],
                                base_qty=new_qty, unit=new_unit, weight_g=new_weight,
                            )
                            st.session_state.editing_ing_id = None
                            st.rerun()
                    if cancel_ing:
                        st.session_state.editing_ing_id = None
                        st.rerun()
                else:
                    ic1, ic2, ic3, ic4, ic5 = st.columns([3, 2, 1.5, 0.7, 0.7])
                    with ic1:
                        name_html = f"<span class='ing-row-name'>{ing['name']}</span>"
                        if unpriced:
                            name_html += " <span class='unknown-badge'>⚠</span>"
                        st.markdown(name_html, unsafe_allow_html=True)
                    with ic2:
                        st.markdown(f"<span class='ing-row-qty'>{qty_str} {ing['unit']}</span>",
                                    unsafe_allow_html=True)
                    with ic3:
                        cost_txt = (f"${ing['line_cost']:.4f}" if not unpriced
                                    else "no price yet")
                        st.markdown(
                            f"<span class='ing-row-cost'>{cost_txt}</span>",
                            unsafe_allow_html=True)
                    with ic4:
                        if st.button("Edit", key=f"ed_{ing['ingredient_id']}"):
                            st.session_state.editing_ing_id = ing["ingredient_id"]
                            st.rerun()
                    with ic5:
                        if st.button("✕", key=f"rm_{ing['ingredient_id']}"):
                            remove_recipe_ingredient(r["id"], ing["ingredient_id"])
                            st.rerun()

            base_cost = sum(x["line_cost"] for x in recipe_ings)
            cost_note = " (partial — some ingredients unpriced)" if unpriced_in_recipe else ""
            st.markdown(
                f"Base recipe cost: <span class='cost-badge'>${base_cost:.4f}</span>{cost_note}",
                unsafe_allow_html=True,
            )
        else:
            st.info("No ingredients yet — add the first one below.")

        # ── Add ingredient ────────────────────────────────────────────────────
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        st.markdown("**Add an ingredient**")

        ing_ids_used   = {x["ingredient_id"] for x in recipe_ings}
        available_ings = [i for i in all_ingredients if i["id"] not in ing_ids_used]

        add_new_toggle = st.checkbox(
            "This ingredient isn't in my price list yet",
            key=f"add_new_ing_toggle_{r['id']}",
            help="Add it now with the name only — price it later from Manage Costs.",
        )

        if not all_ingredients and not add_new_toggle:
            st.caption(
                "No ingredients in your cost list. Add them on **Manage Costs**, "
                "or check the box above to add one by name now."
            )
        elif not add_new_toggle and not available_ings:
            st.success("All your priced ingredients are already in this recipe.")
        else:
            with st.form("add_ing_form", clear_on_submit=True):
                ai1, ai2, ai3 = st.columns([3, 2, 2])
                with ai1:
                    if add_new_toggle:
                        a_name = st.text_input("New ingredient name", placeholder="e.g. Almond extract")
                    else:
                        a_name = st.selectbox("Ingredient",
                                               [i["name"] for i in available_ings])
                with ai2:
                    a_qty  = st.number_input("Qty", min_value=0.0, step=1.0,
                                              format="%.2f", value=0.0)
                with ai3:
                    a_unit = st.selectbox("Unit", UNIT_OPTS)

                if a_unit not in GRAM_UNITS:
                    a_weight = st.number_input(
                        "Weight in grams (for costing)",
                        min_value=0.0, step=1.0, format="%.2f", value=0.0)
                else:
                    a_weight = a_qty

                if st.form_submit_button("Add to recipe", use_container_width=True):
                    if add_new_toggle and not a_name.strip():
                        st.error("Please enter a name for the new ingredient.")
                    elif a_qty <= 0:
                        st.error("Quantity must be > 0.")
                    elif a_unit not in GRAM_UNITS and a_weight <= 0:
                        st.error("Please enter the weight in grams for costing.")
                    else:
                        if add_new_toggle:
                            new_ing_id, _existed = create_placeholder_ingredient(a_name.strip())
                            set_recipe_ingredient(
                                recipe_id=r["id"], ingredient_id=new_ing_id,
                                base_qty=a_qty, unit=a_unit, weight_g=a_weight,
                            )
                            st.success(
                                f"Added **{a_name}** — it doesn't have a price yet, "
                                "add one whenever you're ready on Manage Costs."
                            )
                        else:
                            a_ing = next(i for i in available_ings if i["name"] == a_name)
                            set_recipe_ingredient(
                                recipe_id=r["id"], ingredient_id=a_ing["id"],
                                base_qty=a_qty, unit=a_unit, weight_g=a_weight,
                            )
                            st.success(f"Added **{a_name}**.")
                        st.rerun()

render_footer("2_Recipes.py")
