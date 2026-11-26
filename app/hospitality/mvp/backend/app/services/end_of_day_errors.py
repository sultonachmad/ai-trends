"""Why a cash drawer or end-of-day action was refused. `code` is stable; the page translates it."""

from app.services.front_desk_errors import FrontDeskError


class EndOfDayError(FrontDeskError):
    code = "end_of_day_error"
    message = "This action is not possible."


class NoStaffProfileError(EndOfDayError):
    code = "no_staff_profile"
    message = "Your account has no staff profile in this workspace, so it has no cash drawer."


class DrawerOpenError(EndOfDayError):
    code = "drawer_open"
    message = "Your cash drawer is already open."


class NoDrawerError(EndOfDayError):
    code = "no_drawer"
    message = "You have no open cash drawer."
    status_code = 404


class NoteNeededError(EndOfDayError):
    code = "note_needed"
    message = "The count differs from what is expected. Add a note saying why."
    status_code = 422


class DayNotOverError(EndOfDayError):
    code = "day_not_over"
    message = "Only a day that is over can be closed. Close yesterday tomorrow morning."


class DayBlockedError(EndOfDayError):
    code = "day_blocked"
    message = "Some things still need attention. Fix them, or close with a reason."

    def __init__(self, checks: list | None = None) -> None:
        super().__init__()
        self.checks = checks or []


class OverridePermissionError(EndOfDayError):
    code = "override_permission"
    message = "Only staff who can edit bookings may close a day with items still open."
    status_code = 403


class DayClosedError(EndOfDayError):
    code = "day_closed"
    message = "This day is closed. Record it with today's date, or reopen the day."


class AlreadyClosedError(EndOfDayError):
    code = "already_closed"
    message = "This day is already closed."


class NotClosedError(EndOfDayError):
    code = "not_closed"
    message = "This day is not closed."


class ReopenLatestFirstError(EndOfDayError):
    code = "reopen_latest_first"
    message = "Reopen the most recent closed day first."


class TooManyOpenDaysError(EndOfDayError):
    code = "too_many_open_days"
    message = "Too many days are still open before this one. Contact support."


class BeforeFirstDayError(EndOfDayError):
    code = "before_first_day"
    message = "This day is before the property started using the product."


class DrawerClosedError(EndOfDayError):
    code = "drawer_closed"
    message = "This payment is in a cash drawer that was already counted. Record a correction."


class StaleDrawerError(EndOfDayError):
    code = "stale_drawer"
    message = "Your cash drawer is from an earlier day. Count and close it, then open today's."
