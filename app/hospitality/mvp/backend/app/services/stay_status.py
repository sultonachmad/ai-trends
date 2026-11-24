"""The life of a stay: which booking statuses mean what, in one place."""

TENTATIVE = "tentative"  # held for a guest who has not paid yet
CONFIRMED = "confirmed"
GUARANTEED = "guaranteed"
IN_HOUSE = "in_house"
CHECKED_OUT = "checked_out"
NO_SHOW = "no_show"
CANCELLED = "cancelled"

STARTED = (IN_HOUSE, CHECKED_OUT, NO_SHOW)  # the front desk has acted on it
FINISHED = (CHECKED_OUT, NO_SHOW)  # the stay can no longer change
EARNING = (CONFIRMED, IN_HOUSE, CHECKED_OUT)  # counted as revenue
HOLDS_ROOM = (TENTATIVE, CONFIRMED, GUARANTEED, IN_HOUSE)  # keeps its room from anyone else
NOT_ACTIVE = (CANCELLED, *FINISHED)  # no longer a live stay

# Keys in a booking's `source_detail`.
LEFT_EARLY = "left_early"  # the stay was shortened at check-out
NO_SHOW_AT = "no_show_at"  # when staff marked the no-show
LEFT_UNPAID = "left_unpaid"  # checked out with money still owed, and why
