"""
db.py — SQLite database layer for the baker app

All public functions take/return plain dicts or lists of dicts so
Streamlit pages never need to import sqlite3 directly.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "baker.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row          # rows behave like dicts
    con.execute("PRAGMA foreign_keys = ON")
    return con


# ── Schema ─────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables if they don't already exist."""
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS ingredients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            cost        REAL    NOT NULL,
            unit        TEXT    NOT NULL,          -- "lb" or "kg"
            cost_per_g  REAL    NOT NULL,
            source      TEXT    DEFAULT '',
            cost_known  INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS packaging (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL UNIQUE,
            cost_per_pkg  REAL    NOT NULL,
            qty_per_pkg   INTEGER NOT NULL,
            cost_per_item REAL    NOT NULL,
            source        TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS recipes (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT    NOT NULL UNIQUE,
            base_layers         INTEGER NOT NULL,
            base_size_in        REAL    NOT NULL,
            base_height_in      REAL    NOT NULL,
            base_shape          TEXT    NOT NULL DEFAULT 'round',
            base_num_cakes      REAL    NOT NULL DEFAULT 1.0,
            notes               TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id      INTEGER NOT NULL REFERENCES recipes(id)     ON DELETE CASCADE,
            ingredient_id  INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
            base_qty       REAL    NOT NULL,
            unit           TEXT    NOT NULL,
            weight_g       REAL    NOT NULL,
            UNIQUE (recipe_id, ingredient_id)
        );

        CREATE TABLE IF NOT EXISTS products (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id     INTEGER NOT NULL REFERENCES recipes(id)   ON DELETE CASCADE,
            packaging_id  INTEGER          REFERENCES packaging(id) ON DELETE SET NULL,
            name          TEXT    NOT NULL,
            cake_size_in  REAL    NOT NULL,
            cake_shape    TEXT    NOT NULL DEFAULT 'round',
            rect_width_in REAL    DEFAULT 0,
            cake_height_in REAL   NOT NULL,
            num_layers    INTEGER NOT NULL DEFAULT 1,
            num_cakes     REAL    NOT NULL DEFAULT 1,
            adjustment_pct REAL   NOT NULL DEFAULT 0,
            UNIQUE (recipe_id, name)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS recipe_quote_stats (
            recipe_id      INTEGER PRIMARY KEY REFERENCES recipes(id) ON DELETE CASCADE,
            quote_count    INTEGER NOT NULL DEFAULT 0,
            last_quoted_at TEXT
        );
        """)
        _migrate(con)


def _migrate(con: sqlite3.Connection) -> None:
    """
    Add columns to existing databases created before a schema change.
    CREATE TABLE IF NOT EXISTS won't add new columns to a table that
    already exists, so this handles upgrading a pre-existing baker.db.
    """
    recipe_cols = {
        row["name"] for row in
        con.execute("PRAGMA table_info(recipes)").fetchall()
    }
    if "base_num_cakes" not in recipe_cols:
        con.execute(
            "ALTER TABLE recipes ADD COLUMN base_num_cakes REAL NOT NULL DEFAULT 1.0"
        )

    ingredient_cols = {
        row["name"] for row in
        con.execute("PRAGMA table_info(ingredients)").fetchall()
    }
    if "cost_known" not in ingredient_cols:
        # Existing rows all have a real cost already entered, so they're
        # known by definition — only rows created after this point via
        # create_placeholder_ingredient() start out unknown.
        con.execute(
            "ALTER TABLE ingredients ADD COLUMN cost_known INTEGER NOT NULL DEFAULT 1"
        )


# ── Settings (small persisted preferences: last-used margin, per-recipe ───────
# ── quote defaults, etc. — this is what lets the app "remember" things) ───────

def get_setting(key: str, default=None):
    with _conn() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value) -> None:
    with _conn() as con:
        con.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, str(value)))


def get_setting_json(key: str, default=None):
    raw = get_setting(key, None)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def set_setting_json(key: str, value) -> None:
    set_setting(key, json.dumps(value))


# ── Recipe quote stats (drives "most-quoted recipes sort to the top") ─────────

def record_recipe_quote(recipe_id: int) -> None:
    with _conn() as con:
        con.execute("""
            INSERT INTO recipe_quote_stats (recipe_id, quote_count, last_quoted_at)
            VALUES (?, 1, datetime('now'))
            ON CONFLICT(recipe_id) DO UPDATE SET
                quote_count = quote_count + 1,
                last_quoted_at = datetime('now')
        """, (recipe_id,))


def get_recipe_quote_counts() -> dict:
    with _conn() as con:
        rows = con.execute(
            "SELECT recipe_id, quote_count FROM recipe_quote_stats"
        ).fetchall()
    return {r["recipe_id"]: r["quote_count"] for r in rows}


# ── Ingredients ───────────────────────────────────────────────────────────────

# Grams-per-unit for every purchase unit the Costs page supports. Kept as a
# single source of truth so the UI dropdown and the cost math can never
# drift out of sync with each other.
#
# Deliberately weight-only: lb/kg/oz/g all convert to grams with a fixed,
# unambiguous factor. Volume units (ml, cups, fl oz) are NOT included here —
# converting volume to weight requires the ingredient's density, which
# varies per ingredient and isn't something the app knows. Silently guessing
# a density would produce a confidently wrong cost/g, the same class of bug
# as the earlier baseline-num_cakes issue. If she buys something by volume,
# the practical workaround already exists at the recipe level: enter the
# purchased weight in lb/kg here (e.g. "1 quart heavy cream ≈ 1.05 lb"), the
# same convention already used for count items like eggs.
UNIT_TO_GRAMS = {
    "g":  1.0,
    "kg": 1000.0,
    "oz": 28.3495,
    "lb": 453.592,
}


def _cost_per_g(cost: float, unit: str, qty: float) -> float:
    """Derive cost per gram from purchase cost, unit, and quantity."""
    grams_per_unit = UNIT_TO_GRAMS.get(unit)
    if grams_per_unit is None:
        total_g = qty  # unknown unit: fall back to treating qty as grams
    else:
        total_g = qty * grams_per_unit
    return cost / total_g if total_g else 0.0


def upsert_ingredient(
    name: str,
    cost: float,
    purchase_qty: float,
    unit: str,          # one of UNIT_TO_GRAMS's keys: "g", "kg", "oz", "lb"
    source: str = "",
    ingredient_id: int | None = None,
) -> tuple[int, bool]:
    """
    Insert or update an ingredient with a real, known cost.
    Returns (row_id, merged) — merged is True when a "new" ingredient
    (ingredient_id=None) actually matched an existing name (case-insensitive)
    and was folded into that row instead of failing on the UNIQUE constraint.
    Always marks the ingredient cost_known=1, since this is the path used
    whenever she enters an actual price — including pricing a placeholder
    ingredient that was created with an unknown cost from the Recipes page.
    """
    cpg = _cost_per_g(cost, unit, purchase_qty)
    with _conn() as con:
        if ingredient_id:
            con.execute("""
                UPDATE ingredients
                SET name=?, cost=?, unit=?, cost_per_g=?, source=?, cost_known=1
                WHERE id=?
            """, (name, cost, unit, cpg, source, ingredient_id))
            return ingredient_id, False

        # New ingredient — check for an existing one with the same name
        # (case-insensitive) first, so a typo'd or re-entered "new" row
        # merges into that existing ingredient instead of crashing on the
        # UNIQUE constraint or silently failing. This is also the path a
        # placeholder ingredient (added from the Recipes page with an
        # unknown cost) takes once she prices it here by name.
        existing = con.execute(
            "SELECT id FROM ingredients WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if existing:
            con.execute("""
                UPDATE ingredients
                SET name=?, cost=?, unit=?, cost_per_g=?, source=?, cost_known=1
                WHERE id=?
            """, (name, cost, unit, cpg, source, existing["id"]))
            return existing["id"], True

        cur = con.execute("""
            INSERT INTO ingredients (name, cost, unit, cost_per_g, source, cost_known)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (name, cost, unit, cpg, source))
        return cur.lastrowid, False


def create_placeholder_ingredient(name: str) -> tuple[int, bool]:
    """
    Add an ingredient with no known cost yet, so building a recipe is never
    blocked on having priced every ingredient first. Shows up everywhere as
    cost_known=0 / "cost unknown" until she prices it on the Costs page
    (upsert_ingredient sets cost_known=1 the moment a real cost is saved).
    Returns (id, existed) — existed True if an ingredient with this name
    already existed (priced or not) and was reused instead of duplicated.
    """
    with _conn() as con:
        existing = con.execute(
            "SELECT id FROM ingredients WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if existing:
            return existing["id"], True
        cur = con.execute("""
            INSERT INTO ingredients (name, cost, unit, cost_per_g, source, cost_known)
            VALUES (?, 0, 'g', 0, '', 0)
        """, (name,))
        return cur.lastrowid, False


def get_ingredients() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM ingredients ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def delete_ingredient(ingredient_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM ingredients WHERE id=?", (ingredient_id,))


# ── Packaging ─────────────────────────────────────────────────────────────────

def upsert_packaging(
    name: str,
    cost_per_pkg: float,
    qty_per_pkg: int,
    source: str = "",
    packaging_id: int | None = None,
) -> tuple[int, bool]:
    """
    Returns (row_id, merged) — same merge-on-duplicate-name behavior as
    upsert_ingredient.
    """
    cpi = cost_per_pkg / qty_per_pkg if qty_per_pkg else 0.0
    with _conn() as con:
        if packaging_id:
            con.execute("""
                UPDATE packaging
                SET name=?, cost_per_pkg=?, qty_per_pkg=?, cost_per_item=?, source=?
                WHERE id=?
            """, (name, cost_per_pkg, qty_per_pkg, cpi, source, packaging_id))
            return packaging_id, False

        existing = con.execute(
            "SELECT id FROM packaging WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if existing:
            con.execute("""
                UPDATE packaging
                SET name=?, cost_per_pkg=?, qty_per_pkg=?, cost_per_item=?, source=?
                WHERE id=?
            """, (name, cost_per_pkg, qty_per_pkg, cpi, source, existing["id"]))
            return existing["id"], True

        cur = con.execute("""
            INSERT INTO packaging (name, cost_per_pkg, qty_per_pkg, cost_per_item, source)
            VALUES (?, ?, ?, ?, ?)
        """, (name, cost_per_pkg, qty_per_pkg, cpi, source))
        return cur.lastrowid, False


def get_packaging() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM packaging ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def delete_packaging(packaging_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM packaging WHERE id=?", (packaging_id,))


# ── Recipes ───────────────────────────────────────────────────────────────────

def upsert_recipe(
    name: str,
    base_layers: int,
    base_size_in: float,
    base_height_in: float,
    base_shape: str = "round",
    base_num_cakes: float = 1.0,
    notes: str = "",
    recipe_id: int | None = None,
) -> int:
    with _conn() as con:
        if recipe_id:
            con.execute("""
                UPDATE recipes
                SET name=?, base_layers=?, base_size_in=?, base_height_in=?,
                    base_shape=?, base_num_cakes=?, notes=?
                WHERE id=?
            """, (name, base_layers, base_size_in, base_height_in,
                  base_shape, base_num_cakes, notes, recipe_id))
            return recipe_id
        else:
            cur = con.execute("""
                INSERT INTO recipes
                    (name, base_layers, base_size_in, base_height_in, base_shape,
                     base_num_cakes, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, base_layers, base_size_in, base_height_in, base_shape,
                  base_num_cakes, notes))
            return cur.lastrowid


def get_recipes() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM recipes ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_recipe(recipe_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM recipes WHERE id=?", (recipe_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_recipe(recipe_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM recipes WHERE id=?", (recipe_id,))


# ── Recipe ingredients ────────────────────────────────────────────────────────

def set_recipe_ingredient(
    recipe_id: int,
    ingredient_id: int,
    base_qty: float,
    unit: str,
    weight_g: float,
) -> None:
    """Add or update one ingredient line in a recipe."""
    with _conn() as con:
        con.execute("""
            INSERT INTO recipe_ingredients
                (recipe_id, ingredient_id, base_qty, unit, weight_g)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(recipe_id, ingredient_id) DO UPDATE SET
                base_qty=excluded.base_qty,
                unit=excluded.unit,
                weight_g=excluded.weight_g
        """, (recipe_id, ingredient_id, base_qty, unit, weight_g))


def remove_recipe_ingredient(recipe_id: int, ingredient_id: int) -> None:
    with _conn() as con:
        con.execute("""
            DELETE FROM recipe_ingredients
            WHERE recipe_id=? AND ingredient_id=?
        """, (recipe_id, ingredient_id))


def get_recipe_ingredients(recipe_id: int) -> list[dict]:
    """Return recipe ingredients joined with name, cost_per_g, and cost_known."""
    with _conn() as con:
        rows = con.execute("""
            SELECT
                ri.id,
                ri.ingredient_id,
                i.name,
                ri.base_qty,
                ri.unit,
                ri.weight_g,
                i.cost_per_g,
                i.cost_known,
                ROUND(ri.weight_g * i.cost_per_g, 4) AS line_cost
            FROM recipe_ingredients ri
            JOIN ingredients i ON i.id = ri.ingredient_id
            WHERE ri.recipe_id = ?
            ORDER BY i.name
        """, (recipe_id,)).fetchall()
    return [dict(r) for r in rows]


# ── Products ──────────────────────────────────────────────────────────────────

def upsert_product(
    recipe_id: int,
    name: str,
    cake_size_in: float,
    cake_shape: str,
    cake_height_in: float,
    num_layers: int,
    num_cakes: float,
    adjustment_pct: float = 0.0,
    rect_width_in: float = 0.0,
    packaging_id: int | None = None,
    product_id: int | None = None,
) -> int:
    with _conn() as con:
        if product_id:
            con.execute("""
                UPDATE products SET
                    recipe_id=?, packaging_id=?, name=?, cake_size_in=?,
                    cake_shape=?, rect_width_in=?, cake_height_in=?,
                    num_layers=?, num_cakes=?, adjustment_pct=?
                WHERE id=?
            """, (recipe_id, packaging_id, name, cake_size_in, cake_shape,
                  rect_width_in, cake_height_in, num_layers, num_cakes,
                  adjustment_pct, product_id))
            return product_id
        else:
            cur = con.execute("""
                INSERT INTO products
                    (recipe_id, packaging_id, name, cake_size_in, cake_shape,
                     rect_width_in, cake_height_in, num_layers, num_cakes, adjustment_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (recipe_id, packaging_id, name, cake_size_in, cake_shape,
                  rect_width_in, cake_height_in, num_layers, num_cakes,
                  adjustment_pct))
            return cur.lastrowid


def get_products(recipe_id: int | None = None) -> list[dict]:
    """All products, optionally filtered by recipe."""
    with _conn() as con:
        if recipe_id:
            rows = con.execute("""
                SELECT p.*, r.name AS recipe_name,
                       pk.name AS packaging_name,
                       pk.cost_per_item AS packaging_cost
                FROM products p
                JOIN recipes r ON r.id = p.recipe_id
                LEFT JOIN packaging pk ON pk.id = p.packaging_id
                WHERE p.recipe_id = ?
                ORDER BY p.name
            """, (recipe_id,)).fetchall()
        else:
            rows = con.execute("""
                SELECT p.*, r.name AS recipe_name,
                       pk.name AS packaging_name,
                       pk.cost_per_item AS packaging_cost
                FROM products p
                JOIN recipes r ON r.id = p.recipe_id
                LEFT JOIN packaging pk ON pk.id = p.packaging_id
                ORDER BY r.name, p.name
            """).fetchall()
    return [dict(r) for r in rows]


def delete_product(product_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM products WHERE id=?", (product_id,))