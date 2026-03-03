from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
    waiting_nickname = State()
    waiting_avatar = State()


class UploadSolutionState(StatesGroup):
    waiting_grade = State()
    waiting_type = State()
    waiting_subject = State()
    waiting_content = State()
    waiting_content_confirm = State()
    waiting_description = State()
    waiting_assessment = State()


class BrowseSolutionsState(StatesGroup):
    waiting_grade = State()
    waiting_type = State()
    waiting_subject = State()
    browsing = State()


class ProfileState(StatesGroup):
    waiting_new_avatar = State()


class AdminState(StatesGroup):
    waiting_new_admin_id = State()
    waiting_ban_user_id = State()
    waiting_unban_user_id = State()
    waiting_reject_reason = State()
    waiting_manage_user_id = State()
    waiting_new_nickname = State()
    waiting_new_avatar_for_user = State()
