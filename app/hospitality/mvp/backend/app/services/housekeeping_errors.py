"""Why a housekeeping or staff action was refused. `code` is stable; the page translates it."""

from app.services.front_desk_errors import FrontDeskError


class HousekeepingError(FrontDeskError):
    code = "housekeeping_error"
    message = "This action is not possible."


class NoStaffProfileError(HousekeepingError):
    code = "no_staff_profile"
    message = "Your account has no staff profile in this workspace."


class TaskNotFoundError(HousekeepingError):
    code = "task_not_found"
    message = "This task was not found."
    status_code = 404


class RoomNotFoundError(HousekeepingError):
    code = "room_not_found"
    message = "This room was not found."
    status_code = 404


class NotYourTaskError(HousekeepingError):
    code = "not_your_task"
    message = "This room is given to someone else."
    status_code = 403


class TaskClosedError(HousekeepingError):
    code = "task_closed"
    message = "This task is already finished or no longer needed."


class NotOccupiedError(HousekeepingError):
    code = "not_occupied"
    message = "Do not disturb and refused service are only for rooms with a guest."


class NotDoneYetError(HousekeepingError):
    code = "not_done_yet"
    message = "Only a cleaned room can be inspected."


class ReasonNeededError(HousekeepingError):
    code = "reason_needed"
    message = "Say why the room did not pass."
    status_code = 422


class UnknownStaffError(HousekeepingError):
    code = "unknown_staff"
    message = "This person is not an active staff member here."
    status_code = 422


class InspectPermissionError(HousekeepingError):
    code = "inspect_permission"
    message = "Only a supervisor can mark a room inspected."
    status_code = 403


class ClearPermissionError(HousekeepingError):
    code = "clear_permission"
    message = "Only the front desk or a supervisor can mark a problem as dealt with."
    status_code = 403


class TaskExistsError(HousekeepingError):
    code = "task_exists"
    message = "This room already has a cleaning task today."


# --- staff join links ----------------------------------------------------------------


class StaffError(FrontDeskError):
    code = "staff_error"
    message = "This action is not possible."


class InviteNotFoundError(StaffError):
    code = "invite_not_found"
    message = "This join link is not valid."
    status_code = 404


class InviteExpiredError(StaffError):
    code = "invite_expired"
    message = "This join link has expired. Ask for a new one."
    status_code = 410


class InviteUsedError(StaffError):
    code = "invite_used"
    message = "This join link was already used."
    status_code = 410


class InviteRevokedError(StaffError):
    code = "invite_revoked"
    message = "This join link was cancelled. Ask for a new one."
    status_code = 410


class WrongEmailError(StaffError):
    code = "wrong_email"
    message = "This link is for another email address. Sign in with the invited email."
    status_code = 403


class AlreadyMemberError(StaffError):
    code = "already_member"
    message = "This account already belongs to a workspace."


class AlreadyInvitedError(StaffError):
    code = "already_invited"
    message = "This email already has an open join link or is already on the team."


class StaffNotFoundError(StaffError):
    code = "staff_not_found"
    message = "This staff member was not found."
    status_code = 404


class CannotChangeOwnerError(StaffError):
    code = "cannot_change_owner"
    message = "The owner's access cannot be changed or removed here."


class CannotChangeSelfError(StaffError):
    code = "cannot_change_self"
    message = "You cannot change or remove your own access."


class ManagerOnlyError(StaffError):
    code = "manager_only"
    message = "Only the owner or a manager can give someone the manager role."
    status_code = 403
