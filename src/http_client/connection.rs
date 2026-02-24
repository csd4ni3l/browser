use std::{collections::HashMap, net::{Shutdown, TcpStream}, io::{Read, Write}, fs};
use native_tls::{TlsConnector, TlsStream};
use base64::{engine::general_purpose::URL_SAFE, Engine as _};
use crate::http_client::html_parser::{CSSCache, CSSParser, CSSSelector, HTML, Node, get_inline_styles, tree_to_vec};
use serde_json;

pub enum Connection {
    Plain(TcpStream),
    Tls(TlsStream<TcpStream>),
}

impl Connection {
    fn shutdown(&mut self, how: Shutdown) -> std::io::Result<()> {
        match self {
            Connection::Plain(s) => s.shutdown(how),
            Connection::Tls(s) => {let _ = s.shutdown(); Ok(())},
        }
    }
}

impl Read for Connection {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        match self {
            Connection::Plain(s) => s.read(buf),
            Connection::Tls(s) => s.read(buf),
        }
    }
}

impl Write for Connection {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        match self {
            Connection::Plain(s) => s.write(buf),
            Connection::Tls(s) => s.write(buf),
        }
    }

    fn flush(&mut self) -> std::io::Result<()> {
        match self {
            Connection::Plain(s) => s.flush(),
            Connection::Tls(s) => s.flush(),
        }
    }
}

pub fn resolve_url(scheme: &str, host: &str, port: u16, path: &str, url: &str) -> String {
    let mut new_url = url;
    if new_url.contains("://") {
        return new_url.to_string();
    }

    let resolved_path = if !new_url.starts_with("/") {
        let mut dir = path.rsplitn(2, '/').nth(1).unwrap_or("");

        while new_url.starts_with("../") {
            new_url = new_url.strip_prefix("../").unwrap();
            if dir.contains('/') {
                dir = dir.rsplitn(2, '/').nth(1).unwrap_or("");
            }
        }

        format!("{}/{}", dir, new_url)
    } else {
        new_url.to_string()
    };

    if resolved_path.starts_with("//") {
        format!("{}:{}", scheme, resolved_path)
    }
    else {
        format!("{}://{}:{}{}", scheme, host, port, resolved_path)
    }
}
pub struct HTTPClient {
    pub scheme: String,
    pub host: String,
    pub path: String,
    pub port: u16,
    pub request_headers: HashMap<String, String>,
    pub response_explanation: Option<String>,
    pub response_headers: HashMap<String, String>,
    pub response_http_version: Option<String>,
    pub response_status: Option<u32>,
    pub node: Option<Node>,
    pub css_rules: Vec<(CSSSelector, HashMap<String, String>)>,
    pub content_response: String,
    pub view_source: bool,
    pub redirect_count: u32,
    pub needs_render: bool,
    pub tcp_stream: Option<Connection>
}

impl HTTPClient {
    pub fn new() -> HTTPClient {
        HTTPClient {
            scheme: String::new(),
            host: String::new(),
            path: String::new(),
            port: 0,
            request_headers: HashMap::new(),
            response_explanation: None,
            response_headers: HashMap::new(),
            response_http_version: None,
            response_status: None,
            node: None,
            css_rules: Vec::new(),
            content_response: String::new(),
            view_source: false,
            redirect_count: 0,
            needs_render: false,
            tcp_stream: None
        }
    }

    pub fn file_request(&mut self, url: &String) {
        self.content_response = fs::read_to_string(url.split_once("file://").unwrap().1).unwrap();
    }

    pub fn get_request(&mut self, url: &String, headers: HashMap<String, String>, css: bool) {
        let mut parsed_url = url.clone();
        if parsed_url.starts_with("view-source:") {
            parsed_url = parsed_url.split_once("view-source:").unwrap().1.to_string();
            self.view_source = true;
        }
        else {
            self.view_source = false;
        }

        let (scheme_str, parsed_url_parts) = parsed_url.split_once("://").unwrap();
        self.scheme = scheme_str.to_string();

        if !(parsed_url_parts.contains("/")) {
            self.host = parsed_url_parts.to_string();
            self.path = "/".to_string();
        }
        else {
            let (host_str, path_str) = parsed_url_parts.split_once("/").unwrap();
            self.host = host_str.to_string();
            self.path = format!("/{}", path_str.to_string());
        }

        if self.host.contains(":") {
            let temp_host = self.host.clone();
            let (host_str, port_str) = temp_host.split_once(":").unwrap();

            self.host = host_str.to_string();
            self.port = port_str.parse().unwrap();
        }
        else {
            if self.scheme == "http" {
                self.port = 80;
            }
            else {
                self.port = 443;
            }
        }

        self.request_headers = headers;
        self.response_explanation = None;
        self.response_headers = HashMap::new();
        self.response_http_version = None;
        self.response_status = None;
        self.content_response = "".to_string();
        self.tcp_stream = None;

        if self.request_headers.contains_key("Host") {
            self.request_headers.remove("Host");
        }

        self.request_headers.insert("Host".to_string(), self.host.clone());

        let html_cache_key = URL_SAFE.encode(format!("{}_{}_{}_{}", self.scheme, self.host, self.port, self.path).as_bytes());
        let html_cache_path = format!("html_cache/{}.html", html_cache_key);
        if std::fs::exists(html_cache_path.clone()).unwrap() {
            self.content_response = fs::read_to_string(html_cache_path).unwrap();
            self.parse();
            return;
        }
        let tcp = TcpStream::connect(format!("{}:{}", self.host, self.port.to_string())).unwrap();

        if self.scheme == "https" {
            let connector = TlsConnector::new().unwrap();
            self.tcp_stream = Some(Connection::Tls(connector.connect(self.host.as_str(), tcp).unwrap()));   
        }
        else {
            self.tcp_stream = Some(Connection::Plain(tcp));
        }

        let request_header_lines: String = self.request_headers
            .iter()
            .map(|(header_name, header_value)|{
                format!("{}: {}", header_name, header_value)
            })
            .collect::<Vec<_>>()
            .join("\r\n");
        
        let request = format!("GET {} HTTP/1.0\r\n{}\r\n\r\n", self.path, request_header_lines);
        
        self.tcp_stream.as_mut().unwrap().write_all(request.as_bytes()).unwrap();

        self.receive_response(css); // TODO: use threading

    }

    fn receive_response(&mut self, css: bool) {
        let mut temp_buffer = [0; 16384];
        let mut headers_parsed: bool = false;
        let mut content_length: Option<usize> = None;
        
        loop {
            let bytes_read = self.tcp_stream.as_mut().unwrap().read(&mut temp_buffer).unwrap_or(0);
            if bytes_read == 0 {
                println!("Connection closed by peer.");
                break;
            }

            if !headers_parsed {
                let header_end_index = temp_buffer[..bytes_read].windows(4).position(|window| {window == b"\r\n\r\n"});
                if let Some(header_end_index) = header_end_index {
                    let header_data = std::str::from_utf8(&temp_buffer[..header_end_index]).unwrap_or("");
                    let body_data = &temp_buffer[header_end_index + 4..bytes_read]; // +4 for the \r\n\r\n
                    
                    self._parse_headers(header_data.to_string());
                    headers_parsed = true;

                    let content_length_header = self.response_headers.get("content-length");
                    if let Some(content_length_header) = content_length_header {
                        content_length = Some(content_length_header.parse().unwrap());
                    }

                    self.content_response = std::str::from_utf8(&body_data).unwrap_or("").to_string(); // Assuming body is UTF-8
                    
                    if !content_length.is_none() && body_data.len() >= content_length.unwrap() {
                        break;
                    }
                    else if content_length.is_none() {}
                }
                else {
                    continue;
                }
            }
            else {
                self.content_response.push_str(std::str::from_utf8(&temp_buffer[..bytes_read]).unwrap_or(""));
                if !content_length.is_none() && self.content_response.len() >= content_length.unwrap() {
                    break;
                }
            }
        };

        if let Some(ref mut stream) = self.tcp_stream {
            stream.shutdown(Shutdown::Both).ok();
        }

        self.tcp_stream = None;

        if 300 <= self.response_status.unwrap() && self.response_status.unwrap() < 400 {
            if self.redirect_count >= 4 {
                return;
            }

            self.redirect_count += 1;

            let headers = self.request_headers.clone();
            let location = self.response_headers.get("location")
                .cloned()
                .unwrap_or("/".to_string());
            if location.starts_with("http") || location.starts_with("https") {
               self.get_request(&location, headers, false);
            }
            else {
                self.get_request(&format!("{}://{}{}", self.scheme, self.host, location), headers, false);
            }
        }
        else {
            self.redirect_count = 0;
        }

        if !css {
            if !(300..400).contains(&self.response_status.unwrap_or(0)) {
                self.parse();
            }
        }
    }

    fn _parse_headers(&mut self, header_data: String) {
        let lines: Vec<&str> = header_data.lines().collect();
        
        if lines.is_empty() {
            println!("Received empty header data.");
            return
        }

        let response_status_line = lines[0];
        let mut parts = response_status_line.splitn(3, ' ');

        self.response_http_version = Some(parts.next().unwrap().to_string());
        self.response_status = Some(parts.next().unwrap().parse().unwrap());
        let explanation_parts: Vec<&str> = parts.collect();
        self.response_explanation = Some(explanation_parts.join(" "));

        let mut headers = HashMap::new();
        for i in 1..lines.len() {
            let line = &lines[i];
            
            if line.is_empty() {
                break;
            }

            let (header_name, value) = line.split_once(":").unwrap();
            headers.insert(header_name.trim().to_lowercase().to_string(), value.trim().to_string());
        }

        self.response_headers = headers;
    }

    pub fn parse(&mut self) {
        self.css_rules.clear();

        let html_cache_key = URL_SAFE.encode(format!("{}_{}_{}_{}", self.scheme, self.host, self.port, self.path).as_bytes());
        let html_cache_path = format!("html_cache/{}.html", html_cache_key);

        if std::fs::exists(html_cache_path.clone()).unwrap() {
            self.content_response = std::fs::read_to_string(html_cache_path).unwrap();
        }
        else {
            let _ = std::fs::write(html_cache_path, self.content_response.clone());
        }

        let original_scheme = self.scheme.clone();
        let original_host = self.host.clone();
        let original_port = self.port;
        let original_path = self.path.clone();
        let original_response = self.content_response.clone();

        self.node = Some(Node::Element(HTML::new(self.content_response.clone()).parse()));
        
        let mut flattened_tree = vec![];
        tree_to_vec(self.node.as_ref().unwrap(), &mut flattened_tree);

        let css_links: Vec<String> = flattened_tree.iter()
        .filter(|node| {
            matches!(node, Node::Element(_)) && node.tag().unwrap() == "link".to_string() && node.attributes().unwrap().get("rel").unwrap() == &"stylesheet".to_string() && node.attributes().unwrap().get("href").is_some()
        })
        .map(|node: &&Node| {
            node.attributes().unwrap()["href"].clone()
        }).collect();
        
        for css_link in css_links {
            self.content_response.clear();

            // we need to include the other variables so for example /styles.css wouldnt be cached for all websites
            let css_cache_key = URL_SAFE.encode(format!("{}_{}_{}_{}", self.scheme, self.host, self.port, css_link).as_bytes());
            let css_cache_path = format!("css_cache/{}.json", css_cache_key);

            let rules: Vec<(CSSSelector, HashMap<String, String>)> = if std::path::Path::new(&css_cache_path).exists() {
                let css_cache_content = std::fs::read_to_string(&css_cache_path).unwrap();
                let json: CSSCache = serde_json::from_str(&css_cache_content).unwrap();
                json.css_cache
            }
            else {
                let resolved = resolve_url(self.scheme.as_str(), self.host.as_str(), self.port, self.path.as_str(), css_link.as_str());
                let headers = self.request_headers.clone();
                self.get_request(&resolved, headers, true);
                let parsed_css = CSSParser::new(self.content_response.clone()).parse();
                let json = CSSCache { css_cache: parsed_css };
                let _ = std::fs::write(&css_cache_path, serde_json::to_string(&json).unwrap());
                json.css_cache
            };

            self.css_rules.extend(rules);
        }

        self.css_rules.extend(get_inline_styles(self.node.as_ref().unwrap()));

        self.scheme = original_scheme;
        self.host = original_host;
        self.port = original_port;
        self.path = original_path;
        self.content_response = original_response;
        self.needs_render = true;
    }
}