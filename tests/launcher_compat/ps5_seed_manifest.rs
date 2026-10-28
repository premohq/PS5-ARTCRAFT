//! PS5-ARTCRAFT's seeded installed.json, read with the launcher's own types (copied into crates/native/tests by
//! tests/launcher_compat/run.sh). PS5_SEED_DATA names the staged ArtCraftLauncherData/data folder.
use artcraft_launcher_core::PackageKind;
use artcraft_launcher_native::manifest::Manifest;

#[test]
fn the_seeded_records_are_portable_installs_the_launcher_reads() {
    let data = std::env::var("PS5_SEED_DATA").expect("PS5_SEED_DATA");
    let bytes = std::fs::read(std::path::Path::new(&data).join("installed.json")).expect("installed.json");
    // Manifest::load answers an empty manifest for a file it cannot read, which would hide a format break.
    let manifest: Manifest = serde_json::from_slice(&bytes).expect("installed.json is the launcher's Manifest");
    let expected: Vec<&str> = std::env::var("PS5_SEED_APPS").expect("PS5_SEED_APPS").leak().split(',').collect();
    assert_eq!(manifest.apps.keys().map(String::as_str).collect::<Vec<_>>(), {
        let mut sorted = expected.clone();
        sorted.sort();
        sorted
    });
    for (id, record) in &manifest.apps {
        assert_eq!(record.kind, PackageKind::PortableZip, "{id}");
        assert!(!record.needs_root, "{id}");
        let path = record.path.to_string_lossy();
        assert_eq!(path, format!(r"C:\ArtCraft\Apps\{id}\{id}.exe"), "{id}");
        let folder = format!(r"C:\ArtCraft\Apps\{id}\");
        assert!(record.files.iter().all(|f| f.to_string_lossy().starts_with(&folder)), "{id}: a file outside its folder");
        assert!(record.files.iter().any(|f| f.to_string_lossy() == path), "{id}: its exe is not recorded");
        assert!(artcraft_launcher_core::version::parse(&record.version).is_some(), "{id}: version {}", record.version);
    }
}
