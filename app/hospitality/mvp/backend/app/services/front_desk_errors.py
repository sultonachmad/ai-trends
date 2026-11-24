"""Why the front desk refused something, in a form the page can act on."""


class FrontDeskError(Exception):
    """A refused front desk action. `code` is stable; the page translates it."""

    code = "front_desk_error"
    message = "This action is not possible."
    status_code = 409

    def __init__(self, rooms: list[str] | None = None) -> None:
        super().__init__(self.code)
        self.rooms = rooms or []


class NotFoundError(FrontDeskError):
    code = "not_found"
    message = "Not found."
    status_code = 404


class NotConfirmedError(FrontDeskError):
    code = "not_confirmed"
    message = "Only a confirmed booking can be checked in."


class OutsideStayError(FrontDeskError):
    code = "outside_stay"
    message = "Check-in is possible only between the arrival and departure dates."


class RoomsMissingError(FrontDeskError):
    code = "rooms_missing"
    message = "Assign a room to every part of this booking first."


class RoomOutOfOrderError(FrontDeskError):
    code = "room_out_of_order"
    message = "This room is out of order."


class RoomOccupiedError(FrontDeskError):
    code = "room_occupied"
    message = "Another guest is still in this room."


class RoomNotReadyError(FrontDeskError):
    code = "room_not_ready"
    message = "This room is not marked clean."


class NotInHouseError(FrontDeskError):
    code = "not_in_house"
    message = "Only a guest who is checked in can check out."


class EarlyChoiceNeededError(FrontDeskError):
    code = "early_choice_needed"
    message = "The guest is leaving early. Choose how to charge the unused nights."


class CannotNoShowError(FrontDeskError):
    code = "cannot_no_show"
    message = "Only a confirmed booking can be a no-show, from its arrival date."


class UndoNotAllowedError(FrontDeskError):
    code = "undo_not_allowed"
    message = "This can no longer be undone."


class NoRoomsLeftError(FrontDeskError):
    code = "no_rooms_left"
    message = "These nights have been sold again, so this cannot be undone."


class RoomTakenError(FrontDeskError):
    code = "room_taken"
    message = "This room is taken on some of these dates."


class WrongRoomError(FrontDeskError):
    code = "wrong_room"
    message = "This room is not available for this booking's room type."
    status_code = 422


class RoomLockedError(FrontDeskError):
    code = "room_locked"
    message = "This room is locked for the guest. Unlock it first."


class RoomRequiredError(FrontDeskError):
    code = "room_required"
    message = "A guest who is checked in must keep a room. Move them instead."


class PricePermissionError(FrontDeskError):
    code = "price_permission"
    message = "Only staff who can edit bookings may reduce the price."
    status_code = 403


class NotAssignableError(FrontDeskError):
    code = "not_assignable"
    message = "Rooms can be assigned only to confirmed or checked-in bookings."
