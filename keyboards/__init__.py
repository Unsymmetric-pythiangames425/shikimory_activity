"""Keyboards package"""
from keyboards.inline import (
    main_menu_keyboard,
    profiles_list_keyboard,
    profile_menu_keyboard,
    settings_keyboard,
    confirm_delete_keyboard,
    back_to_main_keyboard,
    cancel_keyboard
)
from keyboards.reply import main_reply_keyboard, remove_keyboard

__all__ = [
    'main_menu_keyboard',
    'profiles_list_keyboard',
    'profile_menu_keyboard',
    'settings_keyboard',
    'confirm_delete_keyboard',
    'back_to_main_keyboard',
    'cancel_keyboard',
    'main_reply_keyboard',
    'remove_keyboard'
]
