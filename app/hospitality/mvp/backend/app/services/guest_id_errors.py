"""Why a guest ID action was refused. `code` is stable; the page translates it."""

from app.services.front_desk_errors import FrontDeskError
from app.services.id_validation import Problem


class GuestIdError(FrontDeskError):
    code = "guest_id_error"
    message = "This ID action is not possible."


class StayClosedError(GuestIdError):
    code = "stay_closed"
    message = "This stay is finished or cancelled; its guests can no longer change."


class GuestNotOnBookingError(GuestIdError):
    code = "guest_not_on_booking"
    message = "This guest is not on this booking."
    status_code = 404


class DocumentNotFoundError(GuestIdError):
    code = "id_not_found"
    message = "This ID document was not found on this booking."
    status_code = 404


class NumberClearedError(GuestIdError):
    code = "id_number_cleared"
    message = "This number was deleted at the end of its retention period."
    status_code = 410


class ImageGoneError(GuestIdError):
    code = "id_image_gone"
    message = "This image was deleted after the stay, as the retention rule says."
    status_code = 410


class ScanNotUsableError(GuestIdError):
    code = "scan_not_usable"
    message = "This image cannot be used. Take or choose the photo again."
    status_code = 422


class MainGuestRemovalError(GuestIdError):
    code = "main_guest_removal"
    message = "The main guest stays on the booking."


class TooManyGuestsError(GuestIdError):
    code = "too_many_guests"
    message = "This booking already lists as many guests as it can hold."


class EmptyImageError(GuestIdError):
    code = "image_empty"
    message = "The file is empty."
    status_code = 422


class ImageTooLargeError(GuestIdError):
    code = "image_too_large"
    message = "The image is too large."
    status_code = 413


class NotAnImageError(GuestIdError):
    code = "not_an_image"
    message = "Only JPEG, PNG or WebP photos are accepted."
    status_code = 415


class InvalidIdError(GuestIdError):
    """The fields do not pass the checks; `problems` says which and why."""

    code = "id_invalid"
    message = "Some fields do not look right. Check them against the document."
    status_code = 422

    def __init__(self, problems: list[Problem]) -> None:
        super().__init__()
        self.problems = problems


class IdMissingError(GuestIdError):
    code = "id_missing"
    message = "Confirm the main guest's KTP or passport before check-in."


class NoIdPermissionError(GuestIdError):
    code = "no_id_permission"
    message = "Only someone who can edit bookings may check a guest in without an ID."
    status_code = 403


class NumberUnreadableError(GuestIdError):
    code = "id_unreadable"
    message = "This ID cannot be opened with the current encryption key. Contact support."
    status_code = 500


class NumberOnOtherGuestError(GuestIdError):
    code = "number_on_other_guest"
    message = "Another guest on this booking already has this document number."


class TooManyScansError(GuestIdError):
    code = "too_many_scans"
    message = "Too many photos are waiting to be confirmed. Confirm or wait a day."
    status_code = 429


class TryAgainError(GuestIdError):
    code = "try_again"
    message = "This guest's ID was just changed elsewhere. Try again."
