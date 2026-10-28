//! PS5-ARTCRAFT's seeded app.ron, read the way eframe reads its storage (a RON map of keys to RON strings, the
//! settings under "settings"), with the launcher's own Settings (copied into crates/ui-egui/tests by
//! tests/launcher_compat/run.sh). PS5_SEED_DATA names the staged ArtCraftLauncherData/data folder.
use std::collections::HashMap;

use artcraft_launcher_core::PackageKind;
use artcraft_launcher_ui_egui::settings::{CheckEvery, Settings};

#[test]
fn the_seeded_settings_are_what_the_edition_chose() {
    let data = std::env::var("PS5_SEED_DATA").expect("PS5_SEED_DATA");
    let text = std::fs::read_to_string(std::path::Path::new(&data).join("app.ron")).expect("app.ron");
    let storage: HashMap<String, String> = ron::from_str(&text).expect("app.ron is eframe's RON map");
    let settings: Settings = ron::from_str(&storage["settings"]).expect("the settings value is the launcher's Settings");
    assert!(settings.auto_update);
    assert!(settings.notify);
    assert!(!settings.close_to_tray);
    assert_eq!(settings.check_every, CheckEvery::Hour);
    assert_eq!(settings.preferred_kinds, vec![PackageKind::PortableZip]);
    assert_eq!(settings.install_locations.root.as_deref(), Some(r"C:\ArtCraft\Apps"));
    assert!(settings.install_locations.per_app.is_empty());
    // What the edition does not set keeps the launcher's own defaults.
    let defaults = Settings::default();
    assert_eq!((settings.view, settings.theme, &settings.language), (defaults.view, defaults.theme, &defaults.language));
}
