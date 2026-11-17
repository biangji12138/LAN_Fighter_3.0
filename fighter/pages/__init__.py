"""One module per screen: page drawing mixins for :class:`fighter.ui.GameApp`."""
from .menu import MenuPage
from .select import SelectPage
from .showcase import ShowcasePage
from .settings import SettingsPage
from .lan import LanPage
from .room import RoomPage

__all__ = ["MenuPage", "SelectPage", "ShowcasePage", "SettingsPage", "LanPage", "RoomPage"]
