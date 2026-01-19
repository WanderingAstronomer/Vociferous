from src.ui.views.base_view import BaseView
from src.ui.views.settings_view import SettingsView
from src.ui.views.user_view import UserView

# Attempt to expose other views if they follow the pattern,
# ensuring the package is usable.
# Note: I am not verifying the existence of classes in the other files
# as that is outside my strict scope, but good hygiene suggests
# I should at least expose what I created.

__all__ = [
    "BaseView",
    "SettingsView",
    "UserView",
]
