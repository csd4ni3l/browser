import socket, logging, ssl, threading, os, ujson, time

from http_client.html_parser import HTML, CSSParser, Element, tree_to_list, get_inline_styles

class HTTPClient():
    def __init__(self):
        self.scheme = "http"
        self.host = ""
        self.path = ""
        self.port = 0
        self.request_headers = {}
        self.response_explanation = None
        self.response_headers = {}
        self.response_http_version = None
        self.response_status = None
        self.nodes = []
        self.css_rules = []
        self.content_response = ""
        self.view_source = False
        self.redirect_count = 0
        self.needs_render = False

    def file_request(self, url):
        with open(url.split("file://", 1)[1], "r") as file:
            self.content_response = file.read()

    def get_request(self, url, request_headers, css=False):
        if url.startswith("view-source:"):
            url = url.split("view-source:")[1]
            self.view_source = True
        else:
            self.view_source = False

        self.scheme, url_parts = url.split("://", 1)

        if "/" not in url_parts:
            self.host = url_parts
            self.path = "/"
        else:
            self.host, self.path = url_parts.split("/", 1)
            self.path = f"/{self.path}"

        if ":" in self.host:
            self.host, port = self.host.split(":", 1)
            self.port = int(port)
        else:
            self.port = 80 if self.scheme == "http" else 443

        self.request_headers = request_headers
        self.response_explanation = None
        self.response_headers = {}
        self.response_http_version = None
        self.response_status = None
        self.content_response = ""
        
        if "Host" not in self.request_headers:
            self.request_headers["Host"] = self.host

        cache_filename = f"{self.scheme}_{self.host}_{self.port}_{self.path.replace('/', '_')}.json"
        if os.path.exists(f"http_cache/{cache_filename}"):
            threading.Thread(target=self.parse, daemon=True).start()
            return
        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

        if self.scheme == "https":
            ctx = ssl.create_default_context()
            try:
                self.socket = ctx.wrap_socket(self.socket, server_hostname=self.host)
            except ssl.SSLCertVerificationError:
                logging.debug(f"Invalid SSL cert for {self.host}:{self.port}{self.path}")
                return

        request_header_lines = '\r\n'.join([f"{header_name}: {header_value}" for header_name, header_value in self.request_headers.items()])
        request = f"GET {self.path} HTTP/1.0\r\n{request_header_lines}\r\n\r\n"
        
        logging.debug(f"Sending Request:\n{request}")

        self.socket.send(request.encode())

        threading.Thread(target=self.receive_response, daemon=True, args=(css,)).start()

    def receive_response(self, css=False):
        buffer = b""
        headers_parsed = False
        content_length = None
        
        while True:
            try:
                data = self.socket.recv(2048)
                if not data:
                    logging.debug("Connection closed by peer.")
                    break
                buffer += data

                if not headers_parsed:
                    header_end_index = buffer.find(b"\r\n\r\n")
                    if header_end_index != -1: # not found
                        header_data = buffer[:header_end_index].decode('latin-1')
                        body_data = buffer[header_end_index + 4:] # +4 for the \r\n\r\n
                        
                        self._parse_headers(header_data)
                        headers_parsed = True

                        content_length_header = self.response_headers.get("Content-Length")
                        if content_length_header:
                            try:
                                content_length = int(content_length_header)
                            except ValueError:
                                logging.debug(f"Invalid Content-Length header: {content_length_header}")
                        
                        self.content_response = body_data.decode('utf-8', errors='ignore') # Assuming body is UTF-8
                        
                        if content_length is not None and len(body_data) >= content_length:
                            break
                        elif content_length is None:
                            pass
                    else:
                        continue
                else:
                    self.content_response += data.decode('utf-8', errors='ignore')
                    if content_length is not None and len(self.content_response.encode('utf-8')) >= content_length:
                        break

            except Exception as e:
                logging.error(f"Error receiving messages: {e}")
                break

        self.socket.close()
        self.socket = None

        if 300 <= int(self.response_status) < 400:
            if self.redirect_count >= 4:
                return

            location_header = self.response_headers["Location"]
            if "http" in location_header or "https" in location_header:
                self.get_request(location_header, self.request_headers)
            else:
                self.get_request(f"{self.scheme}://{self.host}{location_header}", self.request_headers)
        else:
            self.redirect_count = 0

        if not css:
            self.parse()

    def _parse_headers(self, header_data):
        lines = header_data.splitlines()
        
        if not lines:
            logging.debug("Received empty header data.")
            return

        response_status_line = lines[0]
        try:
            self.response_http_version, self.response_status, *explanation_parts = response_status_line.split(" ", 2)
            self.response_explanation = " ".join(explanation_parts)
        except ValueError:
            logging.error(f"Error parsing status line: {response_status_line}")
            return

        headers = {}
        for i in range(1, len(lines)):
            line = lines[i]
            if not line:
                break
            try:
                header_name, value = line.split(":", 1)
                headers[header_name.strip()] = value.strip()
            except ValueError:
                logging.error(f"Error parsing header line: {line}")
        self.response_headers = headers

    def parse(self):
        self.css_rules = []

        cache_filename = f"{self.scheme}_{self.host}_{self.port}_{self.path.replace('/', '_')}.json"

        original_scheme = self.scheme
        original_host = self.host
        original_port = self.port
        original_path = self.path
        original_response = self.content_response

        if cache_filename in os.listdir("http_cache"):
            with open(f"http_cache/{cache_filename}", "r") as file:
                self.nodes = HTML.from_json(ujson.load(file))
        else:
            self.nodes = HTML(self.content_response).parse()
            with open(f"http_cache/{cache_filename}", "w") as file:
                json_list = HTML.to_json(self.nodes)
                file.write(ujson.dumps(json_list))

        css_links = [
            node.attributes["href"]
            for node in tree_to_list(self.nodes, [])
            if isinstance(node, Element)
            and node.tag == "link"
            and node.attributes.get("rel") == "stylesheet"
            and "href" in node.attributes
        ]

        for css_link in css_links:
            self.content_response = ""
            
            if "://" in css_link: 
                self.get_request(css_link, self.request_headers, True)
            
            if not css_link.startswith("/"):
                dir, _ = self.path.rsplit("/", 1)
                css_link = dir + "/" + css_link

            if css_link.startswith("//"):
                self.get_request(self.scheme + ":" + css_link, self.request_headers, True)
            else:
                self.get_request(self.scheme + "://" + self.host + ":" + str(self.port) + css_link, self.request_headers, True)
            
            while not self.content_response:
                time.sleep(0.025)

            self.css_rules.extend(CSSParser(self.content_response).parse())

        self.css_rules.extend(get_inline_styles(self.nodes))

        self.scheme = original_scheme
        self.host = original_host
        self.port = original_port
        self.path = original_path
        self.content_response = original_response
        self.needs_render = True