import arcade, arcade.gui, pyglet, os, ujson

from utils.constants import token_pattern, emoji_pattern

from http_client.connection import HTTPClient
from http_client.html_parser import HTML, Text, Element

BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
]

HSTEP = 13
VSTEP = 18

class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        
        self.children = []
        self.display_list = []
        self.line = []
        
        self.font_cache = {}

        self.x, self.y, self.width, self.height = None, None, None, None

    def paint(self):
        return self.display_list

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
            self.weight = "normal"
            self.style = "roman"
            self.size = 16

            self.line = []
            self.recurse(self.node)
            self.flush()

        for child in self.children:
            child.layout()

        if mode == "block":
            self.height = sum([
                child.height for child in self.children])
        else:
            self.height = self.cursor_y

    def ensure_font(self, size, weight, style, emoji):
        if not (size, weight, style, emoji) in self.font_cache:
            self.font_cache[(size, weight, style, emoji)] = pyglet.font.load("Roboto", size, weight, style == "italic") if not emoji else pyglet.font.load("OpenMoji Color", size, weight, style == "italic")
        
        return self.font_cache[(size, weight, style, emoji)]

    def word(self, word: str, emoji=False):
        font = self.ensure_font(self.size, self.weight, self.style, emoji)

        w = font.get_text_size(word + ("  " if not emoji else " "))[0]
        
        if self.cursor_x + w > self.width:
            self.flush()

        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.get_text_size(" ")[0]
 
    def flush(self):
        if not self.line:
            return

        fonts_on_line = [font for x, word, font in self.line]
        max_ascent = max(font.ascent for font in fonts_on_line)
        max_descent = min(font.descent for font in fonts_on_line)

        baseline = self.cursor_y + 1.25 * max_ascent

        for rel_x, word, font in self.line:
            x = self.x + rel_x
            y = self.y + baseline - font.ascent
            self.display_list.append((x, y, word, font))

        self.cursor_x = 0
        self.line = []
        self.cursor_y = baseline + 1.25 * max_descent

    def recurse(self, tree):
        if isinstance(tree, Text):
            if "{" in tree.text or "}" in tree.text:
                return
            
            word_list = [match.group(0) for match in token_pattern.finditer(tree.text)]

            for word in word_list:
                if emoji_pattern.fullmatch(word):
                    self.word(word, emoji=True)
                else:
                    self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4
        elif tag == "br":
            self.flush()
    
    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 4
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP

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

        self.http_client = http_client

        self.scroll_y = 0
        self.scroll_y_speed = 50
        self.allow_scroll = False
        self.smallest_y = 0

        self.text_labels: list[pyglet.text.Label] = []
        self.text_to_create = []

        self.window = window
        self.window.on_mouse_scroll = self.on_mouse_scroll
        self.window.on_resize = self.on_resize

        self.batch = pyglet.graphics.Batch()

    def on_resize(self, width, height):
        for widget in self.text_labels:
            invisible = (widget.y + widget.content_height) > self.window.height * 0.95
            # Doing visible flag set manually since it takes a lot of time            
            if widget.visible:
                if invisible:
                    widget.visible = False
            elif not widget.visible:
                if not invisible:
                    widget.visible = True
                    
        self.http_client.needs_render = True

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        if not self.allow_scroll:
            return
        
        old_y = self.scroll_y
        self.scroll_y = max(0, min(self.scroll_y - (scroll_y * self.scroll_y_speed), -self.smallest_y))

        for widget in self.text_labels:
            widget.y += self.scroll_y - old_y

            invisible = (widget.y + widget.content_height) > self.window.height * 0.95

            # Doing visible flag set manually since it takes a lot of time            
            if widget.visible:
                if invisible:
                    widget.visible = False
            elif not widget.visible:
                if not invisible:
                    widget.visible = True

    def add_text(self, x, y, text, font, multiline=False):
        self.text_labels.append(
            pyglet.text.Label(
                text=text,
                font_name=font.name,
                italic=font.italic,
                weight=font.weight,
                font_size=font.size,
                multiline=multiline,
                color=arcade.color.BLACK,
                x=x,
                y=(self.window.height * 0.95) - y,
                batch=self.batch
            )
        )

        if y < self.smallest_y:
            self.smallest_y = y

    def update(self):
        if not self.http_client.needs_render:
            return

        self.http_client.needs_render = False
        self.allow_scroll = True

        for child in self.text_labels:
            child.delete()
            del child
        
        self.text_labels.clear()
        self.smallest_y = 0
        
        if self.http_client.view_source or self.http_client.scheme == "file":
            self.add_text(x=HSTEP, y=0, text=self.http_client.content_response, font=pyglet.font.load("Roboto", 16), multiline=True)
        elif self.http_client.scheme == "http" or self.http_client.scheme == "https":
            if not os.path.exists("http_cache"):
                os.makedirs("http_cache")

            cache_filename = f"{self.http_client.scheme}_{self.http_client.host}_{self.http_client.port}_{self.http_client.path.replace('/', '_')}.json"

            if cache_filename in os.listdir("http_cache"):
                with open(f"http_cache/{cache_filename}", "r") as file:
                    self.nodes = HTML.from_json(ujson.load(file))
            else:
                self.nodes = HTML(self.http_client.content_response).parse()
                with open(f"http_cache/{cache_filename}", "w") as file:
                    json_list = HTML.to_json(self.nodes)
                    file.write(ujson.dumps(json_list))

            self.document = DocumentLayout(self.nodes)
            self.document.layout()
            self.display_list = []
            paint_tree(self.document, self.display_list)
            
            for x, y, text, font in self.display_list:
                self.add_text(x, y, text, font)