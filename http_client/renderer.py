import arcade, pyglet

from utils.constants import BLOCK_ELEMENTS, token_pattern, emoji_pattern
from utils.utils import get_color_from_name, hex_to_rgb

from http_client.connection import HTTPClient, resolve_url
from http_client.html_parser import CSSParser, Text, Element, style, cascade_priority, replace_symbols, tree_to_list

from pyglet.font.base import Font as BaseFont

from functools import lru_cache

HSTEP = 13
VSTEP = 18

font_cache = {}

def ensure_font(font_family, size, weight, style, emoji):
    if not (font_family, size, weight, style, emoji) in font_cache:
        font_cache[(font_family, size, weight, style, emoji)] = pyglet.font.load(font_family if pyglet.font.have_font(font_family) else "Arial", size, weight, style == "italic") if not emoji else pyglet.font.load("OpenMoji Color", size, weight, style == "italic")
    
    return font_cache[(font_family, size, weight, style, emoji)]

@lru_cache
def get_space_width(font: BaseFont):
    return font.get_text_size(" ")[0]

class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.color = color
    
class DrawRect:
    def __init__(self, x1, y1, width, height, color):
        self.top = y1
        self.left = x1
        self.width = width
        self.height = height
        self.color = color

class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def paint(self):
        return []

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        for word in self.children:
            word.layout()

        if not self.children:
            self.height = 0
            return

        fonts_on_line = [word.font for word in self.children]
        max_ascent = max(font.ascent for font in fonts_on_line)

        baseline = self.y + 2 * max_ascent

        for word in self.children:
            word.y = baseline - word.font.ascent

        max_descent = min(font.descent for font in fonts_on_line)

        self.height = 2 * (max_ascent + max_descent)

class TextLayout():
    def __init__(self, node, word, emoji, parent, previous):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous
        self.emoji = emoji

    def paint(self):
        color = get_color_from_name(self.node.style["color"])
        return [DrawText(self.x, self.y, self.word, self.font, color)]

    def layout(self):
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        font_family = self.node.style["font-family"]
        style = "roman" if style == "normal" else style
        size = int(float(self.node.style["font-size"][:-2]))
        self.font = ensure_font(font_family, size, weight, style, self.emoji)

        self.width = self.font.get_text_size(self.word + ("  " if not self.emoji else " "))[0]

        if self.previous:
            space = get_space_width(self.previous.font)
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x

        self.height = self.font.ascent + self.font.descent

class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        
        self.children = []
        self.cursor_x = 0
        
        self.x, self.y, self.width, self.height = None, None, None, None

    def paint(self):
        cmds = []
        if self.layout_mode() == "inline":
            bgcolor = self.node.style.get("background-color", "transparent")
            if bgcolor != "transparent":
                rect = DrawRect(self.x, self.y, self.width, self.height, hex_to_rgb(bgcolor) if bgcolor.startswith("#") else get_color_from_name(bgcolor))
                cmds.append(rect)

        return cmds

    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif any([isinstance(child, Element) and child.tag in BLOCK_ELEMENTS for child in self.node.children]):
            return "block"
        elif self.node.children:
            return "inline"
        else:
            return "block"

    def layout(self):
        self.x = self.parent.x
        self.width = self.parent.width

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        mode = self.layout_mode()
        if mode == "block":
            previous = None
            for child in self.node.children:
                next = BlockLayout(child, self, previous)
                self.children.append(next)
                previous = next
        else:
            self.new_line()
            self.recurse(self.node)

        for child in self.children:
            child.layout()

        self.height = sum([child.height for child in self.children])

    def recurse(self, node):
        if isinstance(node, Text):
            word_list = [match.group(0) for match in token_pattern.finditer(node.text)]

            for word in word_list:
                if emoji_pattern.fullmatch(word):
                    self.word(self.node, word, emoji=True)
                else:
                    self.word(self.node, word)
        else:
            if node.tag == "br":
                self.new_line()

            for child in node.children:
                self.recurse(child)

    def word(self, node, word: str, emoji=False):
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        font_family = node.style["font-family"]
        style = "roman" if style == "normal" else style
        size = int(float(node.style["font-size"][:-2]))

        font = ensure_font(font_family, size, weight, style, emoji)

        w = font.get_text_size(word + ("  " if not emoji else " "))[0]
        
        if self.cursor_x + w > self.width:
            self.new_line()

        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        text = TextLayout(node, word, emoji, line, previous_word)
        line.children.append(text)

        self.cursor_x += w + get_space_width(font)

    def new_line(self):
        self.cursor_x = 0
        
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)

        self.children.append(new_line)

class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)

        self.width = arcade.get_window().width - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child.layout()
        self.height = child.height

    def paint(self):
        return []

def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)

class Renderer():
    def __init__(self, http_client: HTTPClient, window: arcade.Window):
        self.content = ''
        self.request_scheme = 'http'
        self.window = window
        self.http_client = http_client

        self.scroll_y = 0
        self.scroll_y_speed = 50
        self.allow_scroll = False
        self.smallest_y = 0
        self.document = None

        self.widgets: list[pyglet.text.Label] = []
        self.text_to_create = []

        self.window.on_mouse_scroll = self.on_mouse_scroll
        self.window.on_mouse_press = self.on_mouse_press
        self.window.on_resize = self.on_resize

        self.batch = pyglet.graphics.Batch()

    def hide_out_of_bounds_labels(self):
        for widget in self.widgets:
            invisible = (widget.y + (widget.content_height if not isinstance(widget, pyglet.shapes.Rectangle) else widget.height)) > self.window.height * 0.925
            # Doing visible flag set manually since it takes a lot of time            
            if widget.visible:
                if invisible:
                    widget.visible = False
            else:
                if not invisible:
                    widget.visible = True

    def on_resize(self, width, height):
        if self.http_client.css_rules:
            self.http_client.needs_render = True

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        if not self.allow_scroll:
            return
        
        old_y = self.scroll_y
        self.scroll_y = max(0, min(abs(self.scroll_y - (scroll_y * self.scroll_y_speed)), abs(self.smallest_y) - (self.window.height * 0.925) + 5)) # flip scroll direction


        for widget in self.widgets:
            widget.y += (self.scroll_y - old_y)

        self.hide_out_of_bounds_labels()

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int):
        if not self.document:
            return
        
        y -= self.scroll_y
        
        objs = [
            obj for obj in tree_to_list(self.document, [])
            if obj.x <= x < obj.x + obj.width
            and ((self.window.height * 0.925) - obj.y - obj.height) <= y < ((self.window.height * 0.925) - obj.y)
        ]

        if not objs:
            return
        
        
        elt = objs[-1].node

        while elt:
            if isinstance(elt, Text):
                pass
            elif elt.tag == "a" and "href" in elt.attributes:
                url = resolve_url(self.http_client.scheme, self.http_client.host, self.http_client.port, self.http_client.path, elt.attributes["href"])
                self.http_client.get_request(url, self.http_client.request_headers)

            elt = elt.parent

    def add_text(self, x, y, text, font, color, multiline=False):
        self.widgets.append(
            pyglet.text.Label(
                text=text,
                font_name=font.name,
                italic=font.italic,
                weight=font.weight,
                font_size=font.size,
                multiline=multiline,
                color=color,
                x=x,
                y=(self.window.height * 0.925) - y,
                batch=self.batch
            )
        )

        if (self.window.height * 0.925) - y < self.smallest_y:
            self.smallest_y = y

    def add_background(self, left, top, width, height, color):
        self.widgets.append(
            pyglet.shapes.Rectangle(
                left,
                (self.window.height * 0.925) - top - height,
                width,
                height,
                color,
                batch=self.batch
            )
        )

    def update(self):
        if not self.http_client.needs_render:
            return

        self.http_client.needs_render = False
        self.allow_scroll = True

        for child in self.widgets:
            child.delete()
            del child
        
        self.widgets.clear()
        self.smallest_y = 0
        
        if self.http_client.view_source or self.http_client.scheme == "file":
            self.add_text(x=HSTEP, y=0, text=self.http_client.content_response, font=pyglet.font.load("Roboto", 16), multiline=True)
        elif self.http_client.scheme == "http" or self.http_client.scheme == "https":
            style(self.http_client.nodes, sorted(self.http_client.css_rules + CSSParser(open("assets/css/browser.css").read()).parse(), key=cascade_priority))

            self.document = DocumentLayout(self.http_client.nodes)
            self.document.layout()
            self.cmds = []
            paint_tree(self.document, self.cmds)
            
            for cmd in self.cmds:
                if isinstance(cmd, DrawText):
                    self.add_text(cmd.left, cmd.top, cmd.text, cmd.font, cmd.color)
                elif isinstance(cmd, DrawRect):
                    self.add_background(cmd.left, cmd.top, cmd.width, cmd.height, cmd.color)

            self.hide_out_of_bounds_labels()