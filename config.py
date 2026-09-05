"""
Central configuration and constants for the Wedding Expense Tracker.

Keeping all the predefined dropdown values, roles, and static
configuration in one place avoids duplication across app.py /
database.py and makes it easy to extend the lists later.
"""

# ============================================================
# WEDDING DETAILS (safe to edit — no secrets here)
# ============================================================

WEDDING_TITLE = "Abhishek Weds Ishika"
WEDDING_DATE = "11 December 2026"
WEDDING_LOCATION = "Indore"


# ============================================================
# ROLES
# ============================================================

ROLE_GROOM = "groom"
ROLE_BRIDE = "bride"
ROLE_ADMIN = "admin"

ROLE_LABELS = {
    ROLE_GROOM: "🤵 Groom",
    ROLE_BRIDE: "👰 Bride",
    ROLE_ADMIN: "🛡️ Admin",
}

# The "side" values stored in the database (distinct from the
# session's logical role, since Admin is not a "side").
SIDES = ["Groom", "Bride"]


# ============================================================
# EXPENSE OWNERSHIP FIELDS
# ============================================================

# "Expense For" — whose expense this is.
EXPENSE_FOR_OPTIONS = ["Groom", "Bride", "Shared"]

# "Entered By" — which side recorded/maintains this expense.
ENTERED_BY_OPTIONS = ["Groom", "Bride"]

# "Purchased For" — who the item/service was actually purchased for.
PURCHASED_FOR_OPTIONS = ["Groom", "Bride", "Both"]

# "Paid By" — who actually paid the money.
PAID_BY_OPTIONS = ["Groom", "Bride", "Shared", "Other"]


# ============================================================
# CATEGORIES (broad expense category)
# ============================================================

CATEGORIES = [
    "Travel",
    "Transportation",
    "Stay",
    "Accommodation",
    "Food",
    "Shopping",
    "Wedding Ceremony",
    "Court Marriage / Registration",
    "Photography",
    "Videography",
    "Decoration",
    "Invitations",
    "Gifts",
    "Makeup",
    "Jewellery",
    "Clothing",
    "Venue",
    "Pandit / Priest",
    "Puja Samagri",
    "Miscellaneous",
]

# ============================================================
# EXPENSE TYPE (specific item/service within a category)
# ============================================================

EXPENSE_TYPE_OPTIONS = [
    "Train",
    "Bus",
    "Flight",
    "Cab / Taxi",
    "Tempo Traveller",
    "Hotel",
    "Guest House",
    "Breakfast",
    "Lunch",
    "Dinner",
    "Catering",
    "Wedding Outfit",
    "Jewellery",
    "Shoes",
    "Makeup",
    "Photography",
    "Videography",
    "Decoration",
    "Invitation Cards",
    "Gift",
    "Venue Booking",
    "Pandit / Priest Fees",
    "Puja Samagri",
    "Other",
]


# ============================================================
# STATUS
# ============================================================

STATUSES = ["Planned", "Committed", "Paid", "Partially Paid"]


# ============================================================
# SETTINGS KEYS (stored in the settings table)
# ============================================================

SETTING_GROOM_SEES_BRIDE = "groom_can_see_bride"
SETTING_BRIDE_SEES_GROOM = "bride_can_see_groom"

DEFAULT_SETTINGS = {
    SETTING_GROOM_SEES_BRIDE: "0",
    SETTING_BRIDE_SEES_GROOM: "0",
}
