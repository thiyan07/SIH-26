"""Configurable business-category catalog for competitor discovery (P0).

This is the single, configurable source of truth that maps a GramBiz business
``category_code`` to the OpenStreetMap tags that describe competing businesses,
the default search radius, a human-readable label, and a **direct/indirect
competitor relationship matrix**.

Everything here is data-driven and lives in one place so category logic is
never scattered through backend engines (plan requirement: don't hard-code
category logic throughout the backend; keep it configurable).

The taxonomy is a superset of GramBiz's existing ``known_categories()`` from
``app/engines/profit.py`` so it composes with the existing scoring engines
(dairy, poultry, grocery, textile, food_processing, restaurant, agriculture,
manufacturing, handicrafts, other) and adds finer-grained retail/service
categories that OSM actually tags in India (pharmacy, salon, hardware,
mechanic, bakery, tea_shop, mobile_shop, electronics, clothing, furniture,
stationery, fertilizer/seed, etc.).
"""
from __future__ import annotations


class _Cat:
    """Descriptor bundle for one category.

    ``osm`` is the OSM (key, [values]) pairs used to build the Overpass tag
    filter. ``radius_km`` is the default competitor search radius for the
    business (larger for destination categories like hardware/furniture, smaller
    for convenience categories like grocery/tea_shop). ``relationships`` is a
    list of (category_code, relation) pairs where ``relation`` is one of
    ``direct`` / ``indirect`` / ``unrelated``.
    """

    __slots__ = ("code", "label", "osm", "radius_km", "relationships")

    def __init__(self, code, label, osm, radius_km=3.0, relationships=()):
        self.code = code
        self.label = label
        self.osm = osm  # list[(key, [value,...])]
        self.radius_km = radius_km
        self.relationships = list(relationships)


# ---------------------------------------------------------------------------
# OSM tag value synonyms used throughout the catalog. Kept as plain lists so
# the mapping is easy to extend without touching code.
# ---------------------------------------------------------------------------
_GROCERY = ["grocery", "convenience", "supermarket", "general", "greengrocer", "wholesale"]
_RESTAURANT = ["restaurant", "fast_food", "food_court"]
_RETAIL_APPAREL = ["clothes", "clothing", "fashion", "boutique", "tailor"]
_ELECTRONICS = ["electronics", "mobile_phone", "computer", "radio_technician"]
_AGRICULTURAL = ["agrarian", "agricultural_supplies", "garden_centre", "fertilizer", "pesticide", "seeds", "feed", "animal_feed"]
_AUTO = ["car_repair", "motorcycle_repair", "bicycle_repair", "tyres"]   # tyres used for tyre_shop below


_CATS: dict[str, _Cat] = {}


def _add(code, label, osm, radius_km=3.0, relationships=()):
    _CATS[code] = _Cat(code, label, osm, radius_km, relationships)


# ----- FOOD ----------------------------------------------------------------
_add("grocery", "Grocery / Kirana store",
     [("shop", _GROCERY)], radius_km=3.0,
     relationships=[("grocery", "direct"), ("bakery", "indirect"),
                    ("tea_shop", "indirect"), ("restaurant", "indirect")])

_add("restaurant", "Restaurant / Food service",
     [("amenity", _RESTAURANT)], radius_km=3.0,
     relationships=[("restaurant", "direct"), ("bakery", "indirect"),
                    ("tea_shop", "indirect"), ("grocery", "indirect")])

_add("tea_shop", "Tea / snack shop",
     [("amenity", ["cafe"]), ("shop", ["tea", "coffee"])], radius_km=1.5,
     relationships=[("tea_shop", "direct"), ("restaurant", "indirect"),
                    ("bakery", "indirect"), ("grocery", "indirect")])

_add("bakery", "Bakery",
     [("shop", ["bakery", "pastry", "confectionery"])], radius_km=2.0,
     relationships=[("bakery", "direct"), ("grocery", "indirect"),
                    ("tea_shop", "indirect")])

_add("meat_shop", "Meat / Poultry shop",
     [("shop", ["butcher", "meat", "poultry"]), ("amenity", ["marketplace"])],
     radius_km=3.0, relationships=[("meat_shop", "direct"), ("grocery", "indirect")])

_add("dairy", "Dairy",
     [("shop", ["dairy", "dairy_farm"])], radius_km=5.0,
     relationships=[("dairy", "direct"), ("grocery", "indirect")])

# ----- RETAIL --------------------------------------------------------------
_add("clothing", "Clothing / Apparel",
     [("shop", _RETAIL_APPAREL)], radius_km=3.0,
     relationships=[("clothing", "direct"), ("footwear", "indirect"),
                    ("textile", "indirect"), ("tailoring", "indirect")])

_add("footwear", "Footwear",
     [("shop", ["shoes", "footwear"])], radius_km=3.0,
     relationships=[("footwear", "direct"), ("clothing", "indirect")])

_add("electronics", "Electronics",
     [("shop", _ELECTRONICS)], radius_km=5.0,
     relationships=[("electronics", "direct"), ("mobile_shop", "direct"),
                    ("furniture", "indirect"), ("computer_service", "indirect")])

_add("mobile_shop", "Mobile phone shop",
     [("shop", ["mobile_phone"]), ("amenity", ["phone"]),
      ("shop", ["electronics"])], radius_km=3.0,
     relationships=[("mobile_shop", "direct"), ("electronics", "indirect"),
                    ("computer_service", "indirect")])

_add("furniture", "Furniture",
     [("shop", ["furniture", "household_linen", "interior_decoration"])],
     radius_km=5.0, relationships=[("furniture", "direct"), ("electronics", "indirect")])

_add("stationery", "Stationery / Books",
     [("shop", ["stationery", "books", "copyshop"])], radius_km=2.0,
     relationships=[("stationery", "direct"), ("textile", "indirect"),
                    ("printing", "indirect")])

# ----- AGRICULTURE ----------------------------------------------------------
_add("fertilizer", "Fertilizer / Pesticide store",
     [("shop", ["agrarian", "agricultural_supplies", "fertilizer", "pesticide", "garden_centre"])],
     radius_km=5.0, relationships=[("fertilizer", "direct"), ("seed_shop", "direct"),
                                   ("agricultural_equipment", "indirect")])

_add("seed_shop", "Seed store",
     [("shop", ["agrarian", "agricultural_supplies", "seeds"])], radius_km=5.0,
     relationships=[("seed_shop", "direct"), ("fertilizer", "indirect"),
                    ("agricultural_equipment", "indirect")])

_add("agricultural_equipment", "Agricultural equipment / implements",
     [("shop", ["agrarian", "agricultural_machinery", "machinery", "agricultural_supplies"])],
     radius_km=8.0, relationships=[("agricultural_equipment", "direct"),
                                   ("fertilizer", "indirect"), ("seed_shop", "indirect")])

_add("animal_feed", "Animal feed store",
     [("shop", ["feed", "animal_feed", "pet"]), ("shop", _AGRICULTURAL)],
     radius_km=5.0, relationships=[("animal_feed", "direct"), ("fertilizer", "indirect")])

_add("tractor_dealer", "Tractor / farm machinery dealer",
     [("shop", ["tractor", "agricultural_machinery", "machinery", "agrarian"])],
     radius_km=10.0, relationships=[("tractor_dealer", "direct"),
                                    ("agricultural_equipment", "direct"),
                                    ("mechanic", "indirect")])

_add("irrigation_supplies", "Irrigation / pumpset supplies",
     [("shop", ["irrigation", "pump"]), ("craft", ["pump_repair"])],
     radius_km=8.0, relationships=[("irrigation_supplies", "direct"),
                                   ("tractor_dealer", "indirect"),
                                   ("agricultural_equipment", "direct")])

# ----- AUTOMOTIVE -----------------------------------------------------------
_add("mechanic", "Automobile / bike mechanic",
     [("shop", ["car_repair", "motorcycle_repair"]), ("craft", ["motorcycle_repair"])],
     radius_km=5.0, relationships=[("mechanic", "direct"), ("tyre_shop", "indirect"),
                                   ("car_service", "indirect")])

_add("tyre_shop", "Tyre & auto parts shop",
     [("shop", ["tyres", "car_parts", "motorcycle_parts"])], radius_km=5.0,
     relationships=[("tyre_shop", "direct"), ("mechanic", "indirect")])

_add("car_service", "Car / bike service centre",
     [("shop", ["car_repair", "car_service", "motorcycle_repair"]),
      ("amenity", ["vehicle_repair"])], radius_km=5.0,
     relationships=[("car_service", "direct"), ("mechanic", "indirect"),
                    ("tyre_shop", "indirect")])

# ----- SERVICES -------------------------------------------------------------
_add("salon", "Salon / Beauty parlour",
     [("shop", ["hairdresser", "beauty"]), ("beauty", ["beauty_salon"])],
     radius_km=2.0, relationships=[("salon", "direct"), ("tailoring", "indirect")])

_add("tailoring", "Tailor / Alterations",
     [("shop", ["tailor", "sewing"])], radius_km=2.0,
     relationships=[("tailoring", "direct"), ("clothing", "indirect"),
                    ("textile", "indirect")])

_add("printing", "Printing / Xerox shop",
     [("shop", ["copyshop", "printing"]), ("craft", ["printer"])], radius_km=3.0,
     relationships=[("printing", "direct"), ("stationery", "indirect"),
                    ("computer_service", "indirect")])

_add("computer_service", "Computer / mobile repair",
     [("shop", ["computer", "repair"]), ("craft", ["electronics_repair"])],
     radius_km=3.0, relationships=[("computer_service", "direct"),
                                   ("electronics", "indirect"), ("mobile_shop", "indirect")])

_add("laundry", "Laundry / Dry cleaning",
     [("shop", ["laundry", "dry_cleaning"])], radius_km=3.0,
     relationships=[("laundry", "direct"), ("hotel", "indirect")])

_add("photography", "Photography / Studio",
     [("shop", ["photo", "photography"])], radius_km=3.0,
     relationships=[("photography", "direct"), ("printing", "indirect")])

_add("internet_centre", "Internet / Cyber cafe",
     [("amenity", ["internet_cafe"]), ("shop", ["internet"])], radius_km=3.0,
     relationships=[("internet_centre", "direct"), ("printing", "direct"),
                    ("computer_service", "indirect")])

_add("travel_agency", "Travel agency",
     [("office", ["travel_agent"]), ("amenity", ["travel_agency"])], radius_km=5.0,
     relationships=[("travel_agency", "direct"), ("hotel", "indirect")])

_add("finance", "Finance / Insurance office",
     [("office", ["insurance", "financial", "accountant"]),
      ("amenity", ["bank", "money_transfer"])], radius_km=5.0,
     relationships=[("finance", "direct")])

_add("welding", "Welding / Fabrication shop",
     [("craft", ["welder", "metal_construction", "blacksmith"]),
      ("shop", ["welding"])], radius_km=5.0,
     relationships=[("welding", "direct"), ("hardware", "indirect"),
                    ("agriculture", "indirect")])

_add("home_appliances", "Home appliances shop",
     [("shop", ["household", "appliance", "vacuum"])], radius_km=5.0,
     relationships=[("home_appliances", "direct"), ("electronics", "direct")])

_add("battery_shop", "Battery shop",
     [("shop", ["battery"])], radius_km=5.0,
     relationships=[("battery_shop", "direct"), ("mechanic", "indirect"),
                    ("tyre_shop", "indirect")])

_add("auto_parts", "Auto spare parts / accessories",
     [("shop", ["car_parts", "motorcycle_parts", "auto_parts"])], radius_km=8.0,
     relationships=[("auto_parts", "direct"), ("mechanic", "indirect"),
                    ("tyre_shop", "direct")])

# ----- HEALTH ---------------------------------------------------------------
_add("pharmacy", "Pharmacy / Medical store",
     [("amenity", ["pharmacy"]), ("shop", ["chemist", "medical_supply"])],
     radius_km=3.0, relationships=[("pharmacy", "direct"), ("clinic", "indirect"),
                                   ("diagnostic", "indirect")])

_add("clinic", "Clinic",
     [("amenity", ["clinic", "doctors"]),
      ("healthcare", ["centre", "health_centre", "clinic"])], radius_km=3.0,
     relationships=[("clinic", "direct"), ("pharmacy", "indirect"),
                    ("diagnostic", "indirect")])

_add("hospital", "Hospital",
     [("amenity", ["hospital"])], radius_km=10.0,
     relationships=[("hospital", "direct"), ("clinic", "direct"),
                    ("pharmacy", "indirect"), ("diagnostic", "indirect")])

_add("diagnostic", "Diagnostic lab",
     [("healthcare", ["laboratory"]), ("amenity", ["laboratory"])], radius_km=3.0,
     relationships=[("diagnostic", "direct"), ("clinic", "indirect"),
                    ("pharmacy", "indirect")])

_add("dental_clinic", "Dental clinic",
     [("healthcare", ["dentist"]), ("amenity", ["dentist"])], radius_km=3.0,
     relationships=[("dental_clinic", "direct"), ("clinic", "indirect"),
                    ("pharmacy", "indirect")])

_add("optical_shop", "Optical / Spectacles shop",
     [("shop", ["optician"])], radius_km=3.0,
     relationships=[("optical_shop", "direct"), ("clinic", "indirect")])

_add("veterinary", "Veterinary clinic",
     [("amenity", ["veterinary"]), ("healthcare", ["veterinary"])], radius_km=5.0,
     relationships=[("veterinary", "direct"), ("animal_feed", "direct")])

# ----- GROCERY EXPANDED -------------------------------------------------------
_add("fruit_shop", "Fruit shop",
     [("shop", ["fruit", "greengrocer"])], radius_km=2.0,
     relationships=[("fruit_shop", "direct"), ("grocery", "direct"),
                    ("vegetable_shop", "direct")])

_add("vegetable_shop", "Vegetable shop",
     [("shop", ["greengrocer", "vegetables"])], radius_km=2.0,
     relationships=[("vegetable_shop", "direct"), ("grocery", "direct"),
                    ("fruit_shop", "direct")])

_add("sweet_shop", "Sweet / Confectionery shop",
     [("shop", ["confectionery", "sweet"])], radius_km=3.0,
     relationships=[("sweet_shop", "direct"), ("bakery", "direct"),
                    ("restaurant", "indirect")])

_add("hotel", "Hotel / Lodge",
     [("tourism", ["hotel", "motel", "hostel", "guest_house"]),
      ("building", ["hotel"])], radius_km=5.0,
     relationships=[("hotel", "direct"), ("restaurant", "indirect")])

_add("fast_food", "Fast food / Tiffin centre",
     [("amenity", ["fast_food", "food_court"]),
      ("shop", ["fast_food"])], radius_km=2.0,
     relationships=[("fast_food", "direct"), ("restaurant", "direct"),
                    ("tea_shop", "direct")])

_add("fish_shop", "Fish / Seafood shop",
     [("shop", ["seafood", "fish"])], radius_km=2.0,
     relationships=[("fish_shop", "direct"), ("grocery", "indirect")])

# ----- CONSTRUCTION ----------------------------------------------------------
_add("hardware", "Hardware / Building materials",
     [("shop", ["hardware", "doityourself", "building_materials", "paint", "electrical", "plumbing"])],
     radius_km=5.0, relationships=[("hardware", "direct"), ("electrical", "indirect"),
                                   ("cement", "indirect")])

_add("building_materials", "Cement / Sand / Building materials",
     [("shop", ["building_materials", "trade", "cement", "tiles", "sanitaryware"])], radius_km=8.0,
     relationships=[("building_materials", "direct"), ("hardware", "indirect")])

_add("steel_products", "Steel / Iron products",
     [("shop", ["steel", "iron", "metal"])], radius_km=8.0,
     relationships=[("steel_products", "direct"), ("building_materials", "direct"),
                    ("hardware", "indirect")])

_add("plywood", "Plywood / Timber shop",
     [("shop", ["plywood", "timber", "wood"])], radius_km=5.0,
     relationships=[("plywood", "direct"), ("hardware", "direct"),
                    ("building_materials", "indirect")])

# ----- LEGACY GramBiz categories (compose with existing engines) ------------
_add("textile", "Textile / Tailoring",
     [("shop", _RETAIL_APPAREL), ("craft", ["textile"])], radius_km=3.0,
     relationships=[("textile", "direct"), ("clothing", "direct"),
                    ("tailoring", "indirect")])

_add("food_processing", "Food processing",
     [("craft", None), ("man_made", None)], radius_km=5.0,
     relationships=[("food_processing", "direct"), ("restaurant", "indirect")])

_add("agriculture", "Agriculture-related enterprise",
     [("shop", _AGRICULTURAL)], radius_km=8.0,
     relationships=[("agriculture", "direct"), ("fertilizer", "indirect")])

_add("manufacturing", "Small manufacturing",
     [("man_made", ["works"]), ("industrial", ["factory"])], radius_km=8.0,
     relationships=[("manufacturing", "direct")])

_add("handicrafts", "Handicrafts / Art",
     [("shop", ["art", "gift", "handicraft"]), ("craft", None)], radius_km=3.0,
     relationships=[("handicrafts", "direct"), ("textile", "indirect")])

# ----- fallback --------------------------------------------------------------
_add("other", "Other",
     [("shop", None)], radius_km=3.0, relationships=[])


def catalog() -> dict[str, dict]:
    """The full configurable catalog as plain dicts (JSON-friendly)."""
    return {c.code: _cat_dict(c) for c in _CATS.values()}


def _cat_dict(c: _Cat) -> dict:
    return {
        "code": c.code,
        "label": c.label,
        "osm": [{"key": k, "values": v} for k, v in c.osm],
        "radius_km": c.radius_km,
        "relationships": [{"code": r[0], "relation": r[1]} for r in c.relationships],
    }


def get_category(category_code: str) -> dict | None:
    """Catalog entry for a category_code or None if unknown."""
    c = _CATS.get(category_code)
    return _cat_dict(c) if c else None


def default_radius_km(category_code: str, fallback: float = 3.0) -> float:
    c = _CATS.get(category_code)
    return c.radius_km if c else fallback


def category_label(category_code: str, fallback: str = "Business") -> str:
    c = _CATS.get(category_code)
    return c.label if c else fallback


def relationship(category_code: str, other_code: str) -> str:
    """Direct / indirect / unrelated relation of ``other`` vs ``category``.

    `unrelated` is returned by default; direct and indirect are derived from
    the configurable per-category relationship matrix.
    """
    c = _CATS.get(category_code)
    if c is None:
        return "unrelated"
    for other, rel in c.relationships:
        if other == other_code:
            return rel
    return "unrelated"


def osm_filters(category_code: str) -> list[dict]:
    """OSM (key, [values]) filters for a category as list of dicts."""
    c = _CATS.get(category_code)
    if c is None:
        return []
    return [{"key": k, "values": v} for k, v in c.osm]


def all_codes() -> list[str]:
    return list(_CATS.keys())


# Reverse index: OSM tag value -> most specific GramBiz category code(s).
# Built from the catalog so the mapping stays configurable in one place.
# e.g. tag value "supermarket" -> ["grocery", "other"] (grocery listed first as
# the best/specific match). A tag value with no catalog entry gets "other".
_OSM_TAG_TO_CATEGORY: dict[str, list[str]] = {}


def _build_reverse_index():
    global _OSM_TAG_TO_CATEGORY
    for code, cat in _CATS.items():
        if code == "other":
            continue
        for key, values in cat.osm:
            for v in values or []:
                bucket = _OSM_TAG_TO_CATEGORY.setdefault(str(v), [])
                if code not in bucket:
                    bucket.append(code)
    # specific codes win for shared generic values; keep insertion order stable


_build_reverse_index()


def category_for_osm_tag(tag_value: str | None) -> str:
    """Map an OSM tag value (e.g. 'supermarket') to its GramBiz category code.

    Falls back to 'other' when the value is unknown. The returned code feeds the
    direct/indirect relationship matrix, translating raw OSM data into GramBiz
    taxonomy terms.
    """
    if not tag_value:
        return "other"
    codes = _OSM_TAG_TO_CATEGORY.get(str(tag_value).lower())
    if not codes:
        return "other"
    return codes[0]
