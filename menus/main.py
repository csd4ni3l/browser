import arcade, arcade.gui, asyncio, pypresence, time, copy, json, asyncio

from utils.constants import discord_presence_id, DEFAULT_HEADERS
from utils.utils import FakePyPresence

from http_client.connection import HTTPClient, resolve_url
from http_client.html_parser import tree_to_list, Text
from http_client.renderer import Renderer

class Tab():
    def __init__(self, url, window, tab_button, pypresence_client):
        self.pypresence_client = pypresence_client
        self.tab_button = tab_button
        self.window = window
        self.http_client = HTTPClient()
        self.renderer = Renderer(self.http_client, window)

        self.request(url)
            
    def request(self, url):
        if url.startswith("http://") or url.startswith("https://") or url.startswith("view-source:"):
            self.http_client.get_request(url, DEFAULT_HEADERS)
        elif url.startswith("file://"):
            self.http_client.file_request(url)
        elif url.startswith("data:text/html,"):
            self.http_client.content_response = url.split("data:text/html,")[1]
            self.http_client.scheme = "http"
        elif url == "about:blank":
            self.http_client.content_response = ""
            self.http_client.scheme = "http"
        elif url == "about:config" or url == "about:settings":
            self.settings()
        else:
            self.http_client.get_request(f"https://{url}", DEFAULT_HEADERS)

        self.tab_button.text = url

    def settings(self):
        from menus.settings import Settings
        self.window.show_view(Settings(self.pypresence_client))

class Main(arcade.gui.UIView):
    def __init__(self, pypresence_client=None):
        super().__init__()

        self.pypresence_client = pypresence_client

        with open("settings.json", "r") as file:
            self.settings_dict = json.load(file)

        if self.settings_dict.get('discord_rpc', True):
            if self.pypresence_client == None: # Game has started
                try:
                    asyncio.get_event_loop()
                except:
                    asyncio.set_event_loop(asyncio.new_event_loop())
                try:
                    self.pypresence_client = pypresence.Presence(discord_presence_id)
                    self.pypresence_client.connect()
                    self.pypresence_client.start_time = time.time()
                except:
                    self.pypresence_client = FakePyPresence()
                    self.pypresence_client.start_time = time.time()

            elif isinstance(self.pypresence_client, FakePyPresence): # the user has enabled RPC in the settings in this session.
                # get start time from old object
                start_time = copy.deepcopy(self.pypresence_client.start_time)
                try:
                    self.pypresence_client = pypresence.Presence(discord_presence_id)
                    self.pypresence_client.connect()
                    self.pypresence_client.start_time = start_time
                except:
                    self.pypresence_client = FakePyPresence()
                    self.pypresence_client.start_time = start_time

            self.pypresence_client.update(state='Browsing', details='In the browser', start=self.pypresence_client.start_time)
        else: # game has started, but the user has disabled RPC in the settings.
            self.pypresence_client = FakePyPresence()
            self.pypresence_client.start_time = time.time()

        self.pypresence_client.update(state='Browsing', details='In the browser', start=self.pypresence_client.start_time)

        self.tabs: list[Tab] = []
        self.tab_buttons = []
        self.active_tab = None

    def on_show_view(self):
        super().on_show_view()

        self.anchor = self.add_widget(arcade.gui.UIAnchorLayout(size_hint=(1, 1)))
        self.navigation_box = self.anchor.add(arcade.gui.UIBoxLayout(space_between=10), anchor_x="center", anchor_y="top")

        self.tab_box = self.navigation_box.add(arcade.gui.UIBoxLayout(space_between=5, vertical=False))
        
        self.new_tab_button = self.tab_box.add(arcade.gui.UIFlatButton(text="+", width=self.window.width / 25, height=30, style=arcade.gui.UIFlatButton.DEFAULT_STYLE))
        self.new_tab_button.on_click = lambda event: self.new_tab()

        self.tab_buttons.append(self.tab_box.add(arcade.gui.UIFlatButton(text="about:blank", width=self.window.width / 7, height=30, style=arcade.gui.UIFlatButton.STYLE_BLUE)))

        self.search_bar = self.navigation_box.add(arcade.gui.UIInputText(width=self.window.width * 0.5, height=30, font_name="Roboto", font_size=14, text_color=arcade.color.BLACK, caret_color=arcade.color.BLACK, border_color=arcade.color.BLACK))        

        default_tab = Tab("about:blank", self.window, self.tab_buttons[0], self.pypresence_client)
        self.tabs.append(default_tab)  
        self.tab_buttons[-1].on_click = lambda event, tab=self.tabs[0]: self.switch_to_tab(tab)

        self.switch_to_tab(default_tab)

    def search(self):
        url = self.search_bar.text

        self.active_tab.request(url)

    def switch_to_tab(self, tab):
        if self.active_tab:
            self.active_tab.tab_button.style = arcade.gui.UIFlatButton.DEFAULT_STYLE

        self.active_tab = tab
        self.active_tab.tab_button.style = arcade.gui.UIFlatButton.STYLE_BLUE

        if self.active_tab.renderer.current_window_size != self.window.size:
            self.active_tab.renderer.on_resize(self.window.width, self.window.height)

        self.window.on_mouse_scroll = self.active_tab.renderer.on_mouse_scroll

        http_client = self.active_tab.http_client
        if http_client.scheme and http_client.host and http_client.path:
            port_str = f':{http_client.port}' if not http_client.port in [80, 443, 0] else ''
            self.search_bar.text = f"{http_client.scheme}://{http_client.host}{port_str}{http_client.path}"

    def new_tab(self, url="about:blank"):
        self.tab_buttons.append(self.tab_box.add(arcade.gui.UIFlatButton(text=url, width=self.window.width / 7, height=30, style=arcade.gui.UIFlatButton.STYLE_BLUE)))
        self.tabs.append(Tab(url, self.window, self.tab_buttons[-1], self.pypresence_client))
        self.tab_buttons[-1].on_click = lambda event, tab=self.tabs[-1]: self.switch_to_tab(tab)

        self.switch_to_tab(self.tabs[-1])

    def on_resize(self, width, height):
        for tab_button in self.tab_buttons:
            tab_button.rect = tab_button.rect.resize(width / 7, 30)

        self.active_tab.renderer.on_resize(width, height)

    def on_key_press(self, symbol, modifiers):
        self.search_bar.text = self.search_bar.text.encode("ascii", "ignore").decode().strip("\n")
        if symbol == arcade.key.ENTER:
            self.search()

    def on_update(self, delta_time):
        self.active_tab.renderer.update()

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int):
        if not self.active_tab.renderer.document:
            return
        
        y -= self.active_tab.renderer.scroll_y
        
        objs = [
            obj for obj in tree_to_list(self.active_tab.renderer.document, [])
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
                url = resolve_url(self.active_tab.http_client.scheme, self.active_tab.http_client.host, self.active_tab.http_client.port, self.active_tab.http_client.path, elt.attributes["href"])
                self.new_tab(url)
                return

            elt = elt.parent

    def on_draw(self):
        super().on_draw()
        
        self.active_tab.renderer.batch.draw()