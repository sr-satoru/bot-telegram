from telegram import InlineKeyboardButton

try:
    btn = InlineKeyboardButton(text="Test", callback_data="test", style="primary")
    print("✅ InlineKeyboardButton accepts 'style' parameter!")
except TypeError as e:
    print(f"❌ InlineKeyboardButton DOES NOT accept 'style': {e}")

try:
    btn = InlineKeyboardButton(text="Test", callback_data="test", background_color="blue")
    print("✅ InlineKeyboardButton accepts 'background_color' parameter!")
except TypeError as e:
    print(f"❌ InlineKeyboardButton DOES NOT accept 'background_color': {e}")
