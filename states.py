from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
    waiting_nickname = State()
    waiting_avatar = State()


class UploadSolutionState(StatesGroup):
    waiting_type = State()
    waiting_subject = State()
    waiting_content = State()
    waiting_description = State()
    waiting_assessment = State()


class BrowseSolutionsState(StatesGroup):
    waiting_type = State()
    waiting_subject = State()
    browsing = State()


class AdminState(StatesGroup):
    waiting_new_admin_id = State()
    waiting_ban_user_id = State()
