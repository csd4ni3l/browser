use crate::http_client::connection::HTTPClient;
use bevy_egui::egui::Ui;

enum Widget {

}

struct DocumentLayout {

}

pub struct Renderer {
    content: String,
    request_scheme: String,
    scroll_y: f64,
    scroll_y_speed: f64,
    smallest_y: f64,
    document: Option<DocumentLayout>,
    widgets: Vec<Widget>
}

impl Renderer {
    pub fn new() -> Renderer {
        Renderer {
            content: String::new(),
            request_scheme: String::new(),
            scroll_y: 0.0,
            scroll_y_speed: 50.0,
            smallest_y: 0.0,
            document: None,
            widgets: Vec::new()
        }
    }

    pub fn render(&mut self, http_client: &HTTPClient, ui: &mut Ui) {
    }
}