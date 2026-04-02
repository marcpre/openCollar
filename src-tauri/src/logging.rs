use std::{
    env,
    fs::{self, OpenOptions},
    io::Write,
    path::PathBuf,
    sync::OnceLock,
};

use chrono::Utc;

static LOG_FILE_PATH: OnceLock<PathBuf> = OnceLock::new();

pub fn init_logging(default_dir: PathBuf) -> Result<PathBuf, String> {
    let log_dir = env::var("OPEN_COLLAR_LOG_DIR")
        .map(PathBuf::from)
        .unwrap_or(default_dir);
    fs::create_dir_all(&log_dir).map_err(|error| error.to_string())?;
    let log_file = log_dir.join("open-collar.log");
    let _ = LOG_FILE_PATH.set(log_file.clone());
    log("INFO", "logging initialized");
    Ok(log_file)
}

pub fn log(level: &str, message: impl AsRef<str>) {
    let Some(path) = LOG_FILE_PATH.get() else {
        return;
    };

    let timestamp = Utc::now().to_rfc3339();
    let line = format!("[{timestamp}] [{level}] {}\n", message.as_ref());

    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }

    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = file.write_all(line.as_bytes());
    }
}
