import arcade, arcade.gui, asyncio, pypresence, time, copy, json, asyncio

from utils.constants import discord_presence_id
from utils.utils import FakePyPresence

from http_client.connection import HTTPClient
from http_client.renderer import Renderer

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

        self.http_client = HTTPClient()

    def on_resize(self, width, height):
        self.ui.clear()
        self.on_show_view()

    def on_show_view(self):
        super().on_show_view()

        self.search_bar = self.add_widget(arcade.gui.UIInputText(x=self.window.width / 4, y=self.window.height * 0.95, width=self.window.width / 2, height=self.window.height * 0.035, font_name="Roboto", font_size=14, text_color=arcade.color.BLACK, caret_color=arcade.color.BLACK, border_color=arcade.color.BLACK))        
        self.renderer = Renderer(self.http_client, self.window)

    def on_key_press(self, symbol, modifiers):
        self.search_bar.text = self.search_bar.text.encode("ascii", "ignore").decode().strip("\n")
        if symbol == arcade.key.ENTER:
            self.search()

    def on_update(self, delta_time):
        self.renderer.update()

    def search(self):
        url = self.search_bar.text
        if url.startswith("http://") or url.startswith("https://") or url.startswith("view-source:"):
            self.http_client.get_request(url, {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"})
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

        self.search_bar.text = self.search_bar.text.encode("ascii", "ignore").decode().strip("\n")

    def settings(self):
        from menus.settings import Settings
        self.window.show_view(Settings(self.pypresence_client))

    def on_draw(self):
        super().on_draw()
        
        self.renderer.batch.draw()