"""Locality query variant generator — avoids combinatorial explosion.

For a locality X, produces variants like:
  grocery stores in X
  pharmacies in X
  shops in X
  businesses near X
  X market / bus stand / main road where geographically sensible.

Generation respects parent relationships (village + block + district).
"""
from __future__ import annotations

from app.discovery.admin import LocalityRecord

# Generic fallback suffixes for "businesses/shops" discovery
GENERIC_VARIANTS = ["businesses in {loc}", "shops in {loc}", "businesses near {loc}", "shops near {loc}"]

# Contextual suffixes only for village/rural where indexing may be under nearby town
CONTEXTUAL_SUFFIXES = ["{loc} market", "{loc} bus stand", "{loc} main road", "{loc} junction"]

def _fmt_category(category: str) -> str:
    return category.replace("_", " ")

def generate_query_variants(loc: LocalityRecord, category: str, max_variants: int = 4) -> list[str]:
    """Return query strings for a locality+category."""
    loc_name = loc.name
    block = loc.block or ""
    district = loc.district
    cat = _fmt_category(category)
    variants: list[str] = []
    # Primary: category in locality
    variants.append(f"{cat} in {loc_name}, {district}")
    # Variant: category in locality + block where block differs
    if block and block.lower() != loc_name.lower():
        variants.append(f"{cat} in {loc_name}, {block}, {district}")
    # Generic discovery variants (category-agnostic near loc)
    # Only for first few categories to avoid explosion; caller controls max_variants
    # We include generic for the village discovery class to catch shops indexed under nearby town.
    # But limit to one generic per category
    # The generic will be generated as a separate query with a broader category mapping.
    # For now return category-specific variants only.
    # Trim to max_variants
    return variants[:max_variants]

def generate_locality_variants(loc: LocalityRecord) -> list[str]:
    """Generate geographic locality phrasing variants for nearby discovery."""
    base = loc.name
    block = loc.block or ""
    district = loc.district
    variants = [base]
    if block and block.lower() != base.lower():
        variants.append(f"{base}, {block}")
        variants.append(f"{base}, {block}, {district}")
    variants.append(f"near {base}")
    # Only for villages: market/bus stand variants are useful
    if loc.type == "village":
        for tmpl in CONTEXTUAL_SUFFIXES[:2]:  # limit
            variants.append(tmpl.format(loc=base))
    return variants[:6]
