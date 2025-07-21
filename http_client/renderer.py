import arcade, pyglet

from utils.constants import BLOCK_ELEMENTS, token_pattern, emoji_pattern
from utils.utils import get_color_from_name, hex_to_rgb

from http_client.connection import HTTPClient
from http_client.html_parser import CSSParser, Text, Element, style, cascade_priority, replace_symbols

HSTEP = 13
VSTEP = 18

font_cache = {}
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

class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        
        self.children = []
        self.display_list = []
        self.line = []
        
        self.x, self.y, self.width, self.height = None, None, None, None

    def paint(self):
        cmds = []
        if self.layout_mode() == "inline":
            bgcolor = self.node.style.get("background-color", "transparent")
            if bgcolor != "transparent":
                rect = DrawRect(self.x, self.y, self.width, self.height, hex_to_rgb(bgcolor) if bgcolor.startswith("#") else get_color_from_name(bgcolor))
                cmds.append(rect)

            for x, y, word, font, color in self.display_list:
                cmds.append(DrawText(x, y, word, font, color))

        return cmds

    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif any([isinstance(child, Element) and \
                  child.tag in BLOCK_ELEMENTS
                  for child in self.node.children]):
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
            self.cursor_x = 0
            self.cursor_y = 0

            self.line = []
            self.recurse(self.node)
            self.flush()

        for child in self.children:
            child.layout()

        if mode == "block":
            self.height = sum([child.height for child in self.children])
        else:
            self.height = self.cursor_y

    def ensure_font(self, font_family, size, weight, style, emoji):
        if not (font_family, size, weight, style, emoji) in font_cache:
            font_cache[(font_family, size, weight, style, emoji)] = pyglet.font.load(font_family, size, weight, style == "italic") if not emoji else pyglet.font.load("OpenMoji Color", size, weight, style == "italic")
        
        return font_cache[(font_family, size, weight, style, emoji)]

    def recurse(self, node):
        if isinstance(node, Text):
            word_list = [match.group(0) for match in token_pattern.finditer(node.text)]

            for word in word_list:
                if emoji_pattern.fullmatch(word):
                    self.word(self.node, word, emoji=True)
                else:
                    self.word(self.node, replace_symbols(word))
        else:
            if node.tag == "br":
                self.flush()

            for child in node.children:
                self.recurse(child)

    def word(self, node, word: str, emoji=False):
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        font_family = node.style["font-family"]
        style = "roman" if style == "normal" else style
        size = int(float(node.style["font-size"][:-2]))
        color = get_color_from_name(node.style["color"])

        font = self.ensure_font(font_family, size, weight, style, emoji)

        w = font.get_text_size(word + ("  " if not emoji else " "))[0]
        
        if self.cursor_x + w > self.width:
            self.flush()

        self.line.append((self.cursor_x, word, font, color))
        self.cursor_x += w + font.get_text_size(" ")[0]
 
    def flush(self):
        if not self.line:
            return

        fonts_on_line = [font for x, word, font, color in self.line]
        max_ascent = max(font.ascent for font in fonts_on_line)
        max_descent = min(font.descent for font in fonts_on_line)

        baseline = self.cursor_y + 2 * max_ascent

        for rel_x, word, font, color in self.line:
            x = self.x + rel_x
            y = self.y + baseline - font.ascent
            self.display_list.append((x, y, word, font, color))

        self.cursor_x = 0
        self.line = []
        self.cursor_y = baseline + 2 * max_descent

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
        self.display_list = child.display_list

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

        self.widgets: list[pyglet.text.Label] = []
        self.text_to_create = []

        self.window.on_mouse_scroll = self.on_mouse_scroll
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