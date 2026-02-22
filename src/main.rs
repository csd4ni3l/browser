use bevy::{log::Level, prelude::*};
use bevy_egui::{EguiContextSettings, EguiContexts, EguiPrimaryContextPass, EguiStartupSet, egui::{self, ecolor::Color32}};
// use serde::{Deserialize, Serialize};

pub mod constants;
pub mod http_client;
use crate::constants::DEFAULT_HEADERS;
use crate::http_client::{connection::HTTPClient, renderer::Renderer};

struct Tab {
    url: String,
    title: String,
    http_client: HTTPClient,
    renderer: Renderer
}

impl Tab {
    fn new(url: &str) -> Tab {
        let http_client =  HTTPClient::new();

        Tab {
            url: url.to_string(),
            title: url.to_string(),
            http_client,
            renderer: Renderer::new()
        }
    }

    fn request(&mut self, url: String) {
        self.url = url;
        if self.url.starts_with("http://") || self.url.starts_with("https://") || self.url.starts_with("view-source:") {
            self.http_client.get_request(&self.url, DEFAULT_HEADERS.clone(), false);
        } else if self.url.starts_with("file://") {
            self.http_client.file_request(&self.url);
        } else if self.url.starts_with("data:text/html,") {
            self.http_client.content_response = self.url.split("data:text/html,").nth(1).unwrap_or("").to_string();
            self.http_client.scheme = "http".to_string();
        } else if self.url == "about:blank" {
            self.http_client.content_response = String::new();
            self.http_client.scheme = "http".to_string();
        } else {
            self.http_client.get_request(&format!("https://{}", self.url), DEFAULT_HEADERS.clone(), false);
        }
    }
}

#[derive(Resource)]
struct AppState {
    current_url: String,
    active_tab: usize,
    tabs: Vec<Tab>
}

fn main() {
    let new_tab = Tab::new("about:blank");

    let mut tabs = Vec::new();
    tabs.push(new_tab);

    App::new()
        .insert_resource(ClearColor(Color::BLACK))
        .add_plugins(
            DefaultPlugins
                .set(bevy::log::LogPlugin {
                    filter: "warn,ui=info".to_string(),
                    level: Level::INFO,
                    ..Default::default()
                })
                .set(WindowPlugin {
                    primary_window: Some(Window {
                        // You may want this set to `true` if you need virtual keyboard work in mobile browsers.
                        prevent_default_event_handling: false,
                        ..default()
                    }),
                    ..default()
                }),
        )
        .add_plugins(bevy_egui::EguiPlugin::default())
        .insert_resource(AppState {
            current_url: String::new(),
            active_tab: 0,
            tabs: tabs
        })
        .add_systems(
            PreStartup,
            setup_camera_system.before(EguiStartupSet::InitContexts),
        )
        .add_systems(
            EguiPrimaryContextPass,
            (draw, update_ui_scale_factor_system),
        )
        .run();
}

// fn update(mut app_state: ResMut<AppState>) {
// }

fn setup_camera_system(mut commands: Commands) {
    commands.spawn(Camera2d);
}

fn update_ui_scale_factor_system(egui_context: Single<(&mut EguiContextSettings, &Camera)>) {
    let (mut egui_settings, camera) = egui_context.into_inner();
    egui_settings.scale_factor = 1.5 / camera.target_scaling_factor().unwrap_or(1.5);
}

fn draw(mut contexts: EguiContexts, mut app_state: ResMut<AppState>) -> Result {
    let ctx = contexts.ctx_mut()?;

    egui::TopBottomPanel::top("top_panel").show(ctx, |ui| {
        ui.horizontal(|ui| {
            let mut i = 0;
            let mut set_active_tab_to: Option<usize> = None;
            for tab in &app_state.tabs {
                let mut button = egui::Button::new(tab.title.clone());

                if i == app_state.active_tab {
                    button = button.fill(Color32::BLACK);
                }

                if ui.add(button).clicked() {
                    set_active_tab_to = Some(i);
                }

                i += 1;
            }

            if let Some(set_active_tab_to) = set_active_tab_to {
                app_state.active_tab = set_active_tab_to;
            }

            if ui.button("+" ).clicked() {
                let new_tab = Tab::new("about:blank");

                app_state.tabs.push(new_tab);
            }
        });

        let available_width = ui.available_width();
        let available_height = ui.available_height();

        ui.add_sized([available_width, available_height / 20.0], egui::TextEdit::singleline(&mut app_state.current_url)).request_focus();
    });

    egui::CentralPanel::default().show(ctx, |ui| {
        let active_tab_index = app_state.active_tab.clone();
        let tab = &mut app_state.tabs[active_tab_index];
        tab.renderer.render(&tab.http_client, ui);
    });
    
    Ok(())
}