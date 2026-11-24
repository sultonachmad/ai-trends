"""Why the bill refused something; the page translates the code."""

from app.services.front_desk_errors import FrontDeskError


class BillClosedError(FrontDeskError):
    code = "bill_closed"
    message = "This bill is closed to new charges."


class DiscountTooLargeError(FrontDeskError):
    code = "discount_too_large"
    message = "This would make the bill less than zero."
    status_code = 422


class AlreadyVoidedError(FrontDeskError):
    code = "already_voided"
    message = "This line has already been voided."


class VoidTooLateError(FrontDeskError):
    code = "void_too_late"
    message = "Only today's lines can be voided. Add a correction instead."


class NotVoidableError(FrontDeskError):
    code = "not_voidable"
    message = "This line cannot be voided."


class ZeroCorrectionError(FrontDeskError):
    code = "zero_correction"
    message = "A correction needs an amount."
    status_code = 422


class TooManyLinesError(FrontDeskError):
    code = "too_many_lines"
    message = "This bill has too many lines."


class CategoryOffError(FrontDeskError):
    code = "category_off"
    message = "This category is switched off for this property."


class BalanceOwedError(FrontDeskError):
    code = "balance_owed"
    message = "The guest still owes money. Take the payment before check-out."
