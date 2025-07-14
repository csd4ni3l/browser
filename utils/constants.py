import arcade.color, re
from arcade.types import Color
from arcade.gui.widgets.buttons import UITextureButtonStyle, UIFlatButtonStyle
from arcade.gui.widgets.slider import UISliderStyle

# Regex is by AI
emoji_pattern = re.compile(
    r'['
    r'\U0001F300-\U0001F5FF'
    r'\U0001F600-\U0001F64F'
    r'\U0001F680-\U0001F6FF'
    r'\U0001F700-\U0001F77F'
    r'\U0001F780-\U0001F7FF'
    r'\U0001F800-\U0001F8FF'
    r'\U0001F900-\U0001F9FF'
    r'\U0001FA00-\U0001FA6F'
    r'\U0001FA70-\U0001FAFF'
    r'\u2600-\u26FF'
    r'\u2700-\u27BF'
    r']',
    flags=re.UNICODE
)

token_pattern = re.compile(
    f'({emoji_pattern.pattern})'  # emoji
    r'|(\w+)'                     # word
    r'|([^\w\s])',                # punctuation
    flags=re.UNICODE
)

menu_background_color = arcade.color.WHITE
log_dir = 'logs'
discord_presence_id = 1393164073566208051

button_style = {'normal': UITextureButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK), 'hover': UITextureButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK),
                'press': UITextureButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK), 'disabled': UITextureButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK)}
big_button_style = {'normal': UITextureButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK, font_size=26), 'hover': UITextureButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK, font_size=26),
                'press': UITextureButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK, font_size=26), 'disabled': UITextureButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK, font_size=26)}

dropdown_style = {'normal': UIFlatButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK, bg=Color(128, 128, 128)), 'hover': UIFlatButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK, bg=Color(49, 154, 54)),
                  'press': UIFlatButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK, bg=Color(128, 128, 128)), 'disabled': UIFlatButtonStyle(font_name="Roboto", font_color=arcade.color.BLACK, bg=Color(128, 128, 128))}

slider_default_style = UISliderStyle(bg=Color(128, 128, 128), unfilled_track=Color(128, 128, 128), filled_track=Color(49, 154, 54))
slider_hover_style = UISliderStyle(bg=Color(49, 154, 54), unfilled_track=Color(128, 128, 128), filled_track=Color(49, 154, 54))

slider_style = {'normal': slider_default_style, 'hover': slider_hover_style, 'press': slider_hover_style, 'disabled': slider_default_style}

settings = {
    "Graphics": {
        "Window Mode": {"type": "option", "options": ["Windowed", "Fullscreen", "Borderless"], "config_key": "window_mode", "default": "Windowed"},
        "Resolution": {"type": "option", "options": ["1366x768", "1440x900", "1600x900", "1920x1080", "2560x1440", "3840x2160"], "config_key": "resolution"},
        "Anti-Aliasing": {"type": "option", "options": ["None", "2x MSAA", "4x MSAA", "8x MSAA", "16x MSAA"], "config_key": "anti_aliasing", "default": "4x MSAA"},
        "VSync": {"type": "bool", "config_key": "vsync", "default": True},
        "FPS Limit": {"type": "slider", "min": 0, "max": 480, "config_key": "fps_limit", "default": 60},
    },
    "Sound": {
        "Music": {"type": "bool", "config_key": "music", "default": True},
        "SFX": {"type": "bool", "config_key": "sfx", "default": True},
        "Music Volume": {"type": "slider", "min": 0, "max": 100, "config_key": "music_volume", "default": 50},
        "SFX Volume": {"type": "slider", "min": 0, "max": 100, "config_key": "sfx_volume", "default": 50},
    },
    "Miscellaneous": {
        "Discord RPC": {"type": "bool", "config_key": "discord_rpc", "default": True},
    },
    "Credits": {}
}
settings_start_category = "Graphics"
