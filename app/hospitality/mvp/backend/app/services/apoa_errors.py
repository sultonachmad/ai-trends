"""Why an APOA action was refused. `code` is stable; the page translates it."""

from app.services.front_desk_errors import FrontDeskError


class ApoaError(FrontDeskError):
    code = "apoa_error"
    message = "This APOA action is not possible."


class NotOnBookingError(ApoaError):
    code = "guest_not_on_booking"
    message = "This guest is not on this booking."
    status_code = 404


class NotForeignError(ApoaError):
    code = "not_foreign"
    message = "Only guests with a confirmed foreign passport are reported to APOA."


class NotCheckedInError(ApoaError):
    code = "not_checked_in"
    message = "Report a guest to APOA after they have checked in."


class NotCheckedOutError(ApoaError):
    code = "not_checked_out"
    message = "Check the guest out of APOA after they have checked out here."


class AlreadyMarkedError(ApoaError):
    code = "already_marked"
    message = "This step is already marked."


class ArrivalFirstError(ApoaError):
    code = "arrival_first"
    message = "Mark the guest as checked in to APOA first."


class ArrivalSkippedError(ApoaError):
    code = "arrival_skipped"
    message = "The APOA check-in was marked not required, so no APOA check-out is needed."


class ApoaMarkedError(ApoaError):
    code = "apoa_marked"
    message = "This guest is recorded in APOA. Undo the APOA record on the APOA page first."


class DepartureFirstError(ApoaError):
    code = "departure_first"
    message = "Undo the APOA check-out first."


class NotMarkedError(ApoaError):
    code = "not_marked"
    message = "This step is not marked, so there is nothing to undo."


class RangeError(ApoaError):
    code = "register_range"
    message = "Choose a start date before the end date, at most one year apart."
    status_code = 422


class RegisterTooLargeError(ApoaError):
    code = "register_too_large"
    message = "Too many guests in this range. Choose a shorter range."
    status_code = 422
