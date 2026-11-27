"""Why a maintenance action was refused. `code` is stable; the page translates it."""

from app.services.front_desk_errors import FrontDeskError


class MaintenanceError(FrontDeskError):
    code = "maintenance_error"
    message = "This action is not possible."


class RequestNotFoundError(MaintenanceError):
    code = "request_not_found"
    message = "This repair request was not found."
    status_code = 404


class WhereNeededError(MaintenanceError):
    code = "where_needed"
    message = "Choose the room, or say where the problem is."
    status_code = 422


class RequestClosedError(MaintenanceError):
    code = "request_closed"
    message = "This request is already fixed or cancelled."


class NotYourRequestError(MaintenanceError):
    code = "not_your_request"
    message = "This repair is given to someone else."
    status_code = 403


class NoteNeededError(MaintenanceError):
    code = "note_needed"
    message = "Add a short note."
    status_code = 422


class NoRoomError(MaintenanceError):
    code = "no_room"
    message = "Only a request for a room can take that room off sale."


class BadNightsError(MaintenanceError):
    code = "bad_nights"
    message = "Choose nights from today, at most 90 nights."
    status_code = 422


class RoomBookedError(MaintenanceError):
    """A guest is in, or booked into, this room on some of those nights."""

    code = "room_booked"
    message = "A guest is in or booked into this room on those nights. Move them first."


class WouldOversellError(MaintenanceError):
    """Taking the room off sale would leave fewer rooms than are sold on some nights."""

    code = "would_oversell"
    message = "There would not be enough rooms of this type for the guests already booked."


class NotOffSaleError(MaintenanceError):
    code = "not_off_sale"
    message = "This room is not off sale for this request."


class PhotoError(MaintenanceError):
    code = "bad_photo"
    message = "The photo must be a JPEG, PNG or WebP image within the size limit."
    status_code = 422


class UnknownStaffError(MaintenanceError):
    code = "unknown_staff"
    message = "This person is not an active staff member here."
    status_code = 422


class SupervisorNeededError(MaintenanceError):
    code = "supervisor_needed"
    message = "This room is off sale. A supervisor marks it fixed and puts it back on sale."
    status_code = 403


class AlreadyOffSaleError(MaintenanceError):
    """Another request already has this room off sale on some of those nights."""

    code = "already_off_sale"
    message = "This room is already off sale on those nights for another request."
