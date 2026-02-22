use std::{collections::HashMap, net::TcpStream, io::{Read, Write}, fs, thread};
use native_tls::TlsConnector;
use crate::html_parser::{Node, Rule};

pub fn resolve_url(scheme: &str, host: &str, port: u16, path: &str, mut url: &str) -> String {
    if url.contains("://") {
        return url.to_string();
    }

    let resolved_path = if !url.starts_with("/") {
        let mut dir = path.rsplitn(2, '/').nth(1).unwrap_or("");

        while url.starts_with("../") {
            url = url.strip_prefix("../").unwrap();
            if dir.contains('/') {
                dir = dir.rsplitn(2, '/').nth(1).unwrap_or("");
            }
        }

        format!("{}/{}", dir, url)
    } else {
        url.to_string()
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
    pub port: u32,
    pub request_headers: HashMap<String, String>,
    pub response_explanation: Option<String>,
    pub response_headers: HashMap<String, String>,
    pub response_http_version: Option<String>,
    pub response_status: Option<u32>,
    pub nodes: Option<Vec<Node>>,
    pub css_rules: Vec<Rule>,
    pub content_response: String,
    pub view_source: bool,
    pub redirect_count: u32,
    pub needs_render: bool,
    pub tcp_stream: Option<Box<dyn Read + Write>>
}

impl HTTPClient {
    pub fn new(scheme: String, host: String, path: String, port: u32) -> HTTPClient {
        HTTPClient {
            scheme,
            host,
            path,
            port,
            request_headers: HashMap::new(),
            response_explanation: None,
            response_headers: HashMap::new(),
            response_http_version: None,
            response_status: None,
            nodes: None,
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
        let mut parsed_url = url;
        if parsed_url.starts_with("view-source:") {
            parsed_url = parsed_url.split_once("view-source:")[1];
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
            self.path = format!("/{}", path_str.to_string());
        }

        if self.host.contains(":") {
            let (host_str, port_str) = self.host.split_once(":").unwrap();

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

        if !self.request_headers.contains_key("Host") {
            self.request_headers["Host"] = self.host;
        }

        let cache_filename = format!("{}_{}_{}_{}.html", self.scheme, self.host, self.port, self.path.replace("/", "_"));
        if std::fs::exists(format!("html_cache/{}", cache_filename)).unwrap() {
            std::thread(move || {
                self.parse()
            });

            return;
        }

        let tcp = TcpStream::connect(format!("{}:{}", self.host, self.port.to_string())).unwrap();

        if self.scheme == "https" {
            let connector = TlsConnector::new().unwrap();
            self.tcp_stream = Some(Box::new(connector.connect(self.host.as_str(), stream).unwrap()));   
        }
        else {
            self.tcp_stream = Some(Box::new(tcp));
        }

    }

    fn receive_response(&mut self, css: bool) {
        
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

        let mut headers = HashMap::new();
        for i in 1..lines.len() {
            let line = &lines[i];
            
            if line.is_empty() {
                break;
            }

            let (header_name, value) = line.split_once(":").unwrap();
            headers.insert(header_name.trim().to_string(), value.trim().to_string());
        }

        self.response_headers = headers;
    }

    pub fn parse(self) {

    }
}