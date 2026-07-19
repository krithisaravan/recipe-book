"""
Page — Manage Costs (ingredients & packaging)
She enters what she paid and how much she bought; cost/g calculates automatically.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from db import (
    init_db, get_ingredients, upsert_ingredient, delete_ingredient,
    get_packaging, upsert_packaging, delete_packaging,
    UNIT_TO_GRAMS,
)
from shared import apply_page_style, render_footer

init_db()

st.set_page_config(page_title="Manage Costs · My Recipe Book", page_icon="🧁", layout="wide")
apply_page_style("1_Ingredients_&_Packaging.py")

st.markdown(
    "<style>[data-baseweb=\"tab-list\"] { justify-content: center !important; }</style>",
    unsafe_allow_html=True,
)



# ── Helpers ────────────────────────────────────────────────────────────────────

def cost_per_g(cost: float, qty: float, unit: str) -> float:
    grams_per_unit = UNIT_TO_GRAMS.get(unit, 1.0)
    grams = qty * grams_per_unit
    return cost / grams if grams else 0.0


def fmt_cpg(cpg: float) -> str:
    return f"${cpg:.5f}/g"


# ── Page header ────────────────────────────────────────────────────────────────

st.markdown("<h1 style='text-align:center; font-style:italic;'>Manage Costs</h1>", unsafe_allow_html=True)

tab_ing, tab_pkg = st.tabs(["Ingredients", "Packaging"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — INGREDIENTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_ing:

    ingredients = get_ingredients()
    unpriced_count = sum(1 for i in ingredients if not i.get("cost_known", 1))

    # ── Bulk-editable table ──────────────────────────────────────────────────
    st.markdown(
        "<div style='text-align:center;'>"
        "<h3 style='margin-bottom:0.15rem;'>Your ingredients</h3>"
        "<p style='color:#7A5C44; font-size:0.85rem; margin-bottom:0.2rem;'>"
        "Edit cells directly, paste multiple rows from a spreadsheet, or use the "
        "+ in the table's own toolbar to add a row.</p>"
        "<p style='color:#7A5C44; font-size:0.85rem; margin-bottom:0.2rem;'>"
        "To delete a row: select it on the left and click the trash icon in the "
        "table's toolbar, or clear all its cells.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if unpriced_count:
        unpriced_names = ", ".join(
            f"**{i['name']}**" for i in ingredients if not i.get("cost_known", 1)
        )
        st.markdown(
            f"<span class='unknown-badge'>⚠ needs a price: {unpriced_names}</span>",
            unsafe_allow_html=True,
        )

    if "ing_editor_version" not in st.session_state:
        st.session_state.ing_editor_version = 0

    # Prefer the last in-progress snapshot (so switching tabs or a rerun
    # doesn't discard edits she hasn't saved yet); otherwise rebuild fresh
    # from the db.
    if "ing_editor_snapshot" in st.session_state:
        editor_df = st.session_state.ing_editor_snapshot
    else:
        # qty_purchased isn't stored directly (only cost_per_g is derived from it),
        # so reconstruct an editable qty from cost and cost_per_g for display purposes.
        rows_for_editor = []
        for i in ingredients:
            grams_per_unit = UNIT_TO_GRAMS.get(i["unit"], 1.0)
            if i["cost_per_g"] > 0:
                qty = i["cost"] / (i["cost_per_g"] * grams_per_unit)
            else:
                qty = 0.0
            rows_for_editor.append({
                "id": i["id"],
                "Ingredient": i["name"],
                "Total cost paid ($)": i["cost"],
                "Qty purchased": round(qty, 3),
                "Unit": i["unit"],
                "Source": i["source"],
            })
        editor_df = pd.DataFrame(rows_for_editor) if rows_for_editor else pd.DataFrame(
            columns=["id", "Ingredient", "Total cost paid ($)", "Qty purchased", "Unit", "Source"]
        )

    edited = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key=f"ing_bulk_editor_{st.session_state.ing_editor_version}",
        column_config={
            "id": None,  # hide internal id column
            "Ingredient": st.column_config.TextColumn(required=True),
            "Total cost paid ($)": st.column_config.NumberColumn(
                format="$%.2f", min_value=0.0, required=True,
                help="What you paid for the entire quantity purchased, not per unit.",
            ),
            "Qty purchased": st.column_config.NumberColumn(
                format="%.3f", min_value=0.0, required=True,
                help="How much you bought, in the unit selected to the right.",
            ),
            "Unit": st.column_config.SelectboxColumn(
                options=list(UNIT_TO_GRAMS.keys()), required=True,
                help="Weight units only — see the converter below if you buy by count or volume.",
            ),
            "Source": st.column_config.TextColumn(),
        },
    )
    st.session_state.ing_editor_snapshot = edited

    bc1, bc2 = st.columns([1, 4])
    with bc1:
        save_bulk = st.button("Save changes", key="save_ing_bulk", type="primary",
                               use_container_width=True)

    if save_bulk:
        errors = []
        merged_names = []
        existing_ids = {i["id"] for i in ingredients}
        edited_ids = set()

        for _, row in edited.iterrows():
            name = str(row["Ingredient"]).strip() if pd.notna(row["Ingredient"]) else ""
            if not name:
                continue  # skip fully blank rows
            cost = row["Total cost paid ($)"]
            qty  = row["Qty purchased"]
            unit = row["Unit"]
            source = str(row["Source"]) if pd.notna(row["Source"]) else ""

            if pd.isna(cost) or cost <= 0:
                errors.append(f"'{name}': cost must be greater than 0")
                continue
            if pd.isna(qty) or qty <= 0:
                errors.append(f"'{name}': quantity must be greater than 0")
                continue
            if unit not in UNIT_TO_GRAMS:
                errors.append(
                    f"'{name}': unit must be one of {', '.join(UNIT_TO_GRAMS.keys())}"
                )
                continue

            row_id = row["id"] if pd.notna(row.get("id")) else None
            # upsert_ingredient always marks cost_known=1 — this is the one
            # place a placeholder ingredient (added from Recipes with no
            # price) becomes "priced," by name match if row_id isn't set.
            result_id, merged = upsert_ingredient(
                name=name, cost=float(cost), purchase_qty=float(qty),
                unit=unit, source=source,
                ingredient_id=int(row_id) if row_id else None,
            )
            # Track the ACTUAL id the row ended up as — for a merge, that's
            # the existing ingredient's id, not the (nonexistent) new one.
            # Getting this wrong would make the cleanup step below think the
            # merged-into ingredient was deleted from the table and remove it.
            edited_ids.add(int(result_id))
            if merged:
                merged_names.append(name)

        # Every existing ingredient no longer present — whether the row was
        # deleted via the grid's own backspace/delete-key shortcut or its
        # name cell got cleared — goes through a confirmation step rather
        # than deleting immediately. Nothing here is a deliberate multi-step
        # delete action the way a dedicated checkbox would be, so it doesn't
        # get to act like one.
        removed_ids = existing_ids - edited_ids
        if removed_ids:
            id_to_name = {i["id"]: i["name"] for i in ingredients}
            st.session_state.pending_ing_deletions = [
                {"id": rid, "name": id_to_name.get(rid, "?")} for rid in removed_ids
            ]

        if errors:
            st.error("Some rows weren't saved:\n\n" + "\n".join(f"- {e}" for e in errors))
        if merged_names:
            st.info(
                "Matched to an existing ingredient rather than creating a duplicate: "
                + ", ".join(f"'{n}'" for n in merged_names)
            )
        if not errors and not removed_ids:
            st.session_state.pop("ing_editor_snapshot", None)
            st.session_state.ing_editor_version += 1
            st.success("Saved.")
            st.rerun()

    # A row went missing from the grid — backspace/delete-key on a selected
    # row, or its name cell got cleared — without any deliberate delete
    # step. Hold off actually removing it from the database until she
    # confirms, rather than treating a stray keystroke as a delete command.
    if st.session_state.get("pending_ing_deletions"):
        pending = st.session_state.pending_ing_deletions
        names = ", ".join(f"**{d['name']}**" for d in pending)
        st.warning(
            f"{names} disappeared from the table above — might have been a "
            "stray keystroke rather than something you meant to delete. "
            "Delete for real, or keep them?"
        )
        pcol1, pcol2 = st.columns(2)
        with pcol1:
            if st.button("Yes, delete for real", key="confirm_delete_ing", type="primary"):
                blocked = []
                for d in pending:
                    try:
                        delete_ingredient(d["id"])
                    except Exception:
                        blocked.append(d["name"])
                st.session_state.pending_ing_deletions = []
                st.session_state.pop("ing_editor_snapshot", None)
                st.session_state.ing_editor_version += 1
                if blocked:
                    st.warning(
                        f"Couldn't remove {', '.join(blocked)} — used in a recipe. "
                        "Remove from that recipe first."
                    )
                else:
                    st.success("Deleted.")
                st.rerun()
        with pcol2:
            if st.button("No, keep them", key="cancel_delete_ing"):
                st.session_state.pending_ing_deletions = []
                # Discard the in-progress snapshot so the table re-syncs
                # fresh from the database, which brings the row back.
                st.session_state.pop("ing_editor_snapshot", None)
                st.session_state.ing_editor_version += 1
                st.rerun()

    with st.expander("Buying by count or volume instead of weight? Convert it here."):
        st.caption(
            "Enter what you bought and the weight of one unit — this adds a "
            "ready-to-save row above with the total worked out for you."
        )
        cv1, cv2, cv3, cv4 = st.columns([2, 1.4, 1.4, 1.2])
        with cv1:
            conv_name = st.text_input("Ingredient name", key="conv_name",
                                       placeholder="e.g. Eggs")
        with cv2:
            conv_count = st.number_input(
                "Number purchased", min_value=0.0, step=1.0, value=0.0,
                key="conv_count", help="e.g. 12 for a dozen eggs",
            )
        with cv3:
            conv_unit_weight = st.number_input(
                "Weight per unit (g)", min_value=0.0, step=1.0, value=0.0,
                key="conv_unit_weight", help="e.g. one large egg ≈ 50 g",
            )
        with cv4:
            conv_cost = st.number_input(
                "Total cost ($)", min_value=0.0, step=0.01, value=0.0,
                key="conv_cost",
            )

        conv_total_g = conv_count * conv_unit_weight
        if conv_total_g > 0:
            st.caption(f"= {conv_total_g:.0f} g total ({conv_total_g / 453.592:.3f} lb)")

        if st.button("Add as a new row", key="conv_add_btn"):
            if not conv_name.strip():
                st.error("Enter an ingredient name first.")
            elif conv_total_g <= 0:
                st.error("Enter both a count and a weight per unit greater than 0.")
            elif conv_cost <= 0:
                st.error("Enter the total cost.")
            else:
                new_row = pd.DataFrame([{
                    "id": None, "Remove": False, "Status": "", "Ingredient": conv_name.strip(),
                    "Total cost paid ($)": conv_cost,
                    "Qty purchased": round(conv_total_g, 2),
                    "Unit": "g", "Source": "",
                }])
                editor_df = pd.concat([editor_df, new_row], ignore_index=True)
                st.session_state.ing_editor_snapshot = editor_df
                st.session_state.ing_editor_version += 1
                st.success(
                    f"Added '{conv_name}' as {conv_total_g:.0f} g — "
                    "review it above and click Save changes when ready."
                )
                st.rerun()

    with st.expander("Prefer to add or edit one ingredient at a time?"):
        # ── Add / edit form ───────────────────────────────────────────────────
        # Editing: let her pick an existing ingredient to pre-fill the form
        edit_options = ["— add new —"] + [i["name"] for i in ingredients]
        edit_choice = st.selectbox("Edit an existing ingredient, or add a new one",
                                   edit_options, key="ing_edit_select")

        editing = None
        if edit_choice != "— add new —":
            editing = next(i for i in ingredients if i["name"] == edit_choice)

        if editing is not None and not editing.get("cost_known", 1):
            st.markdown(
                "<span class='unknown-badge'>⚠ This ingredient was added from a "
                "recipe and doesn't have a price yet — fill it in below.</span>",
                unsafe_allow_html=True,
            )

        with st.form("ing_form", clear_on_submit=True):
            st.markdown(f"#### {'Edit' if editing else 'Add'} ingredient")

            col1, col2, col3, col4 = st.columns([3, 2, 2, 3])

            with col1:
                ing_name = st.text_input(
                    "Ingredient name",
                    value=editing["name"] if editing else "",
                    placeholder="e.g. AP Flour",
                )
            with col2:
                ing_cost = st.number_input(
                    "Total cost ($)",
                    min_value=0.0, step=0.01, format="%.2f",
                    value=float(editing["cost"]) if editing else 0.0,
                )
            with col3:
                ing_qty = st.number_input(
                    "Quantity purchased",
                    min_value=0.01, step=0.5, format="%.2f",
                    value=1.0,
                    help="How much you bought, in the unit selected to the right.",
                )
            with col4:
                unit_options = list(UNIT_TO_GRAMS.keys())
                ing_unit = st.selectbox(
                    "Unit",
                    unit_options,
                    index=unit_options.index(editing["unit"]) if editing else 0,
                )

            col5, col6 = st.columns([4, 2])
            with col5:
                ing_source = st.text_input(
                    "Where you buy it (optional)",
                    value=editing["source"] if editing else "",
                    placeholder="e.g. Costco, Amazon",
                )
            with col6:
                # Live preview of cost/g
                preview_cpg = cost_per_g(ing_cost, ing_qty, ing_unit)
                st.markdown(
                    f"<br><span class='cost-badge'>= {fmt_cpg(preview_cpg)}</span>",
                    unsafe_allow_html=True,
                )

            save_ing = st.form_submit_button(
                "Save ingredient", use_container_width=False
            )

        if save_ing:
            if not ing_name.strip():
                st.error("Please enter an ingredient name.")
            elif ing_cost <= 0:
                st.error("Cost must be greater than $0.")
            else:
                _, ing_merged = upsert_ingredient(
                    name=ing_name.strip(),
                    cost=ing_cost,
                    purchase_qty=ing_qty,
                    unit=ing_unit,
                    source=ing_source.strip(),
                    ingredient_id=editing["id"] if editing else None,
                )
                if ing_merged:
                    st.info(f"'{ing_name}' already existed — updated it instead "
                            "of creating a duplicate.")
                else:
                    st.success(f"{'Updated' if editing else 'Added'} **{ing_name}**.")
                st.rerun()

        # ── Delete ────────────────────────────────────────────────────────────
        if ingredients:
            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            del_ing = st.selectbox(
                "Or remove an ingredient",
                [i["name"] for i in ingredients],
                key="del_ing_select",
            )
            if st.button("Remove", key="del_ing_btn", type="secondary"):
                row = next(i for i in ingredients if i["name"] == del_ing)
                try:
                    delete_ingredient(row["id"])
                    st.success(f"Removed **{del_ing}**.")
                    st.rerun()
                except Exception:
                    st.error(
                        f"**{del_ing}** is used in at least one recipe and can't be removed. "
                        "Delete it from those recipes first."
                    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PACKAGING
# ══════════════════════════════════════════════════════════════════════════════
with tab_pkg:

    packaging = get_packaging()

    if "pkg_editor_version" not in st.session_state:
        st.session_state.pkg_editor_version = 0

    # ── Bulk-editable table ──────────────────────────────────────────────────
    st.markdown(
        "<div style='text-align:center;'>"
        "<h3 style='margin-bottom:0.15rem;'>Your packaging</h3>"
        "<p style='color:#7A5C44; font-size:0.85rem; margin-bottom:0.2rem;'>"
        "Edit cells directly, paste multiple rows from a spreadsheet, or use the "
        "+ in the table's own toolbar to add a row.</p>"
        "<p style='color:#7A5C44; font-size:0.85rem; margin-bottom:0.2rem;'>"
        "To delete a row: select it on the left and click the trash icon in the "
        "table's toolbar, or clear all its cells.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if "pkg_editor_snapshot" in st.session_state:
        pkg_editor_df = st.session_state.pkg_editor_snapshot
    else:
        pkg_rows_for_editor = [{
            "id": p["id"],
            "Item": p["name"],
            "Cost per pack ($)": p["cost_per_pkg"],
            "Items per pack": p["qty_per_pkg"],
            "Source": p["source"],
        } for p in packaging]
        pkg_editor_df = pd.DataFrame(pkg_rows_for_editor) if pkg_rows_for_editor else pd.DataFrame(
            columns=["id", "Item", "Cost per pack ($)", "Items per pack", "Source"]
        )

    # Recomputed from whatever's currently in the other two columns (not
    # read back from the database), so it stays accurate for a row she's
    # still mid-edit on, not just already-saved ones.
    if len(pkg_editor_df):
        pkg_editor_df = pkg_editor_df.copy()
        pkg_editor_df["Cost per item"] = pkg_editor_df.apply(
            lambda r: (r["Cost per pack ($)"] / r["Items per pack"])
            if pd.notna(r["Cost per pack ($)"]) and pd.notna(r["Items per pack"]) and r["Items per pack"]
            else None,
            axis=1,
        )
    else:
        pkg_editor_df["Cost per item"] = pd.Series(dtype="float64")

    pkg_edited = st.data_editor(
        pkg_editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key=f"pkg_bulk_editor_{st.session_state.pkg_editor_version}",
        column_config={
            "id": None,
            "Item": st.column_config.TextColumn(required=True),
            "Cost per pack ($)": st.column_config.NumberColumn(format="$%.2f", min_value=0.0, required=True),
            "Items per pack": st.column_config.NumberColumn(format="%d", min_value=1, required=True),
            "Cost per item": st.column_config.NumberColumn(
                format="$%.4f", disabled=True,
                help="Calculated automatically from cost per pack ÷ items per pack.",
            ),
            "Source": st.column_config.TextColumn(),
        },
    )
    # Drop the calculated column before it goes back into the snapshot —
    # it gets rebuilt fresh every render, so persisting it would just be
    # carrying stale numbers into the next rerun.
    st.session_state.pkg_editor_snapshot = pkg_edited.drop(columns=["Cost per item"])

    pbc1, pbc2 = st.columns([1, 4])
    with pbc1:
        save_pkg_bulk = st.button("Save changes", key="save_pkg_bulk", type="primary",
                                   use_container_width=True)

    if save_pkg_bulk:
        pkg_errors = []
        pkg_merged_names = []
        existing_pkg_ids = {p["id"] for p in packaging}
        edited_pkg_ids = set()

        for _, row in pkg_edited.iterrows():
            name = str(row["Item"]).strip() if pd.notna(row["Item"]) else ""
            if not name:
                continue
            cost = row["Cost per pack ($)"]
            qty  = row["Items per pack"]
            source = str(row["Source"]) if pd.notna(row["Source"]) else ""

            if pd.isna(cost) or cost <= 0:
                pkg_errors.append(f"'{name}': cost must be greater than 0")
                continue
            if pd.isna(qty) or qty < 1:
                pkg_errors.append(f"'{name}': items per pack must be at least 1")
                continue

            row_id = row["id"] if pd.notna(row.get("id")) else None
            result_id, merged = upsert_packaging(
                name=name, cost_per_pkg=float(cost), qty_per_pkg=int(qty),
                source=source,
                packaging_id=int(row_id) if row_id else None,
            )
            edited_pkg_ids.add(int(result_id))
            if merged:
                pkg_merged_names.append(name)

        # Every existing item no longer present goes through a confirmation
        # step before it's actually deleted — same reasoning as ingredients:
        # a row missing from the grid was never a deliberate delete action
        # on its own.
        removed_pkg_ids = existing_pkg_ids - edited_pkg_ids
        if removed_pkg_ids:
            pkg_id_to_name = {p["id"]: p["name"] for p in packaging}
            st.session_state.pending_pkg_deletions = [
                {"id": rid, "name": pkg_id_to_name.get(rid, "?")} for rid in removed_pkg_ids
            ]

        if pkg_errors:
            st.error("Some rows weren't saved:\n\n" + "\n".join(f"- {e}" for e in pkg_errors))
        else:
            if pkg_merged_names:
                st.info(
                    "Matched to an existing item rather than creating a duplicate: "
                    + ", ".join(f"'{n}'" for n in pkg_merged_names)
                )
            if not removed_pkg_ids:
                st.session_state.pop("pkg_editor_snapshot", None)
                st.session_state.pkg_editor_version += 1
                st.success("Saved.")
                st.rerun()

    if st.session_state.get("pending_pkg_deletions"):
        pending_pkg = st.session_state.pending_pkg_deletions
        pkg_names = ", ".join(f"**{d['name']}**" for d in pending_pkg)
        st.warning(
            f"{pkg_names} disappeared from the table above — might have been "
            "a stray keystroke rather than something you meant to delete. "
            "Delete for real, or keep them?"
        )
        ppcol1, ppcol2 = st.columns(2)
        with ppcol1:
            if st.button("Yes, delete for real", key="confirm_delete_pkg", type="primary"):
                for d in pending_pkg:
                    delete_packaging(d["id"])
                st.session_state.pending_pkg_deletions = []
                st.session_state.pop("pkg_editor_snapshot", None)
                st.session_state.pkg_editor_version += 1
                st.success("Deleted.")
                st.rerun()
        with ppcol2:
            if st.button("No, keep them", key="cancel_delete_pkg"):
                st.session_state.pending_pkg_deletions = []
                st.session_state.pop("pkg_editor_snapshot", None)
                st.session_state.pkg_editor_version += 1
                st.rerun()

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    with st.expander("Prefer to add or edit one item at a time?"):
        # ── Add / edit form ───────────────────────────────────────────────────
        pkg_edit_options = ["— add new —"] + [p["name"] for p in packaging]
        pkg_edit_choice = st.selectbox("Edit an existing item, or add a new one",
                                       pkg_edit_options, key="pkg_edit_select")

        editing_pkg = None
        if pkg_edit_choice != "— add new —":
            editing_pkg = next(p for p in packaging if p["name"] == pkg_edit_choice)

        with st.form("pkg_form", clear_on_submit=True):
            st.markdown(f"#### {'Edit' if editing_pkg else 'Add'} packaging item")

            col1, col2, col3, col4 = st.columns([3, 2, 2, 3])

            with col1:
                pkg_name = st.text_input(
                    "Item name",
                    value=editing_pkg["name"] if editing_pkg else "",
                    placeholder='e.g. 6" cake box',
                )
            with col2:
                pkg_cost = st.number_input(
                    "Cost per pack ($)",
                    min_value=0.0, step=0.01, format="%.2f",
                    value=float(editing_pkg["cost_per_pkg"]) if editing_pkg else 0.0,
                )
            with col3:
                pkg_qty = st.number_input(
                    "Items per pack",
                    min_value=1, step=1,
                    value=int(editing_pkg["qty_per_pkg"]) if editing_pkg else 1,
                )
            with col4:
                preview_cpi = pkg_cost / pkg_qty if pkg_qty else 0.0
                st.markdown(
                    f"<br><span class='cost-badge'>= ${preview_cpi:.4f} / item</span>",
                    unsafe_allow_html=True,
                )

            pkg_source = st.text_input(
                "Where you buy it (optional)",
                value=editing_pkg["source"] if editing_pkg else "",
                placeholder="e.g. Amazon, local supplier",
            )

            save_pkg = st.form_submit_button("Save item", use_container_width=False)

        if save_pkg:
            if not pkg_name.strip():
                st.error("Please enter an item name.")
            elif pkg_cost <= 0:
                st.error("Cost must be greater than $0.")
            else:
                _, pkg_merged = upsert_packaging(
                    name=pkg_name.strip(),
                    cost_per_pkg=pkg_cost,
                    qty_per_pkg=pkg_qty,
                    source=pkg_source.strip(),
                    packaging_id=editing_pkg["id"] if editing_pkg else None,
                )
                if pkg_merged:
                    st.info(f"'{pkg_name}' already existed — updated it instead "
                            "of creating a duplicate.")
                else:
                    st.success(f"{'Updated' if editing_pkg else 'Added'} **{pkg_name}**.")
                st.rerun()

        # ── Delete ────────────────────────────────────────────────────────────
        if packaging:
            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            del_pkg = st.selectbox(
                "Or remove an item",
                [p["name"] for p in packaging],
                key="del_pkg_select",
            )
            if st.button("Remove", key="del_pkg_btn", type="secondary"):
                row = next(p for p in packaging if p["name"] == del_pkg)
                delete_packaging(row["id"])
                st.success(f"Removed **{del_pkg}**.")
                st.rerun()

render_footer("1_Ingredients_&_Packaging.py")