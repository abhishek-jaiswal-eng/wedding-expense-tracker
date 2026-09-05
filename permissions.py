"""
Visibility / permission rules between Groom, Bride, and Admin.

This is intentionally separate from database.py (which just applies
whatever filter it's given) and from app.py (UI). Centralizing the
rule here means there is exactly one place that decides "who can
see whose expenses", which is what item 8 of the spec calls for.
"""

from config import (
    ROLE_ADMIN,
    ROLE_BRIDE,
    ROLE_GROOM,
    SETTING_BRIDE_SEES_GROOM,
    SETTING_GROOM_SEES_BRIDE,
)
from database import get_bool_setting


def allowed_entered_by_for_role(role):
    """
    Returns the list of `entered_by` values a given role is allowed
    to see, or None for "no restriction" (Admin).

    This is the single source of truth used everywhere data is
    fetched — dashboards, lists, manage/edit, and exports all funnel
    through this so a hidden row can never leak out via a different
    page or query path.
    """

    if role == ROLE_ADMIN:
        return None  # unrestricted

    if role == ROLE_GROOM:
        allowed = ["Groom"]
        if get_bool_setting(SETTING_GROOM_SEES_BRIDE):
            allowed.append("Bride")
        return allowed

    if role == ROLE_BRIDE:
        allowed = ["Bride"]
        if get_bool_setting(SETTING_BRIDE_SEES_GROOM):
            allowed.append("Groom")
        return allowed

    # Unknown/unauthenticated role — see nothing.
    return []


def can_view_side(role, side):
    """Whether `role` is currently permitted to see rows entered by `side`."""

    allowed = allowed_entered_by_for_role(role)
    return allowed is None or side in allowed


def available_views(role):
    """
    Views (Overall / Groom POV / Bride POV) a role is entitled to
    pick from in the sidebar. Views that visibility settings don't
    currently permit are simply not offered, rather than shown and
    blocked — this keeps the UI honest about what's possible.
    """

    views = ["Overall"]

    if can_view_side(role, "Groom"):
        views.append("Groom POV")

    if can_view_side(role, "Bride"):
        views.append("Bride POV")

    return views


def entered_by_filter_for_view(role, view):
    """
    Combines the role's permitted sides with the currently selected
    view, returning the final `entered_by` list (or None for
    unrestricted) to pass to database.get_expenses().
    """

    allowed = allowed_entered_by_for_role(role)

    if view == "Groom POV":
        wanted = {"Groom"}
    elif view == "Bride POV":
        wanted = {"Bride"}
    else:  # Overall
        wanted = {"Groom", "Bride"}

    if allowed is None:
        return sorted(wanted)

    return [side for side in allowed if side in wanted]
