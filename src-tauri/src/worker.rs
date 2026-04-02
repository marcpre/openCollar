use std::{
    env,
    io::{BufRead, BufReader, Write},
    path::PathBuf,
    process::{Child, ChildStdin, Command, Stdio},
    sync::{Arc, Mutex},
    thread,
};

use crate::models::WorkerEnvelope;
use crate::logging;

pub struct WorkerManager {
    stdin: Option<Arc<Mutex<ChildStdin>>>,
    _child: Option<Arc<Mutex<Child>>>,
}

impl WorkerManager {
    pub fn unavailable() -> Self {
        Self {
            stdin: None,
            _child: None,
        }
    }

    pub fn send(&self, envelope: &WorkerEnvelope) -> Result<(), String> {
        let stdin = self
            .stdin
            .as_ref()
            .ok_or_else(|| "Python worker is unavailable.".to_string())?;
        let line = serde_json::to_string(envelope).map_err(|error| error.to_string())?;
        let mut handle = stdin.lock().map_err(|_| "Worker stdin lock poisoned.".to_string())?;
        handle
            .write_all(format!("{line}\n").as_bytes())
            .map_err(|error| error.to_string())?;
        handle.flush().map_err(|error| error.to_string())
    }
}

enum WorkerLaunch {
    Executable(PathBuf),
    PythonScript { python: String, script: PathBuf },
}

impl WorkerLaunch {
    fn describe(&self) -> String {
        match self {
            Self::Executable(path) => format!("packaged worker executable at {}", path.display()),
            Self::PythonScript { python, script } => {
                format!("python worker script via {python} {}", script.display())
            }
        }
    }
}

fn candidate_worker_executable_paths() -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    if let Ok(explicit) = env::var("OPEN_COLLAR_WORKER_EXECUTABLE") {
        candidates.push(PathBuf::from(explicit));
    }

    if let Ok(current_exe) = env::current_exe() {
        if let Some(exe_dir) = current_exe.parent() {
            candidates.push(exe_dir.join("worker").join("open-collar-worker.exe"));
            candidates.push(exe_dir.join("..").join("worker").join("open-collar-worker.exe"));
            candidates.push(exe_dir.join("..").join("..").join("worker").join("open-collar-worker.exe"));
        }
    }

    candidates
}

fn candidate_worker_paths() -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    if let Ok(explicit) = env::var("OPEN_COLLAR_WORKER_SCRIPT") {
        candidates.push(PathBuf::from(explicit));
    }

    if let Ok(current_exe) = env::current_exe() {
        if let Some(exe_dir) = current_exe.parent() {
            candidates.push(exe_dir.join("worker").join("main.py"));
            candidates.push(exe_dir.join("..").join("worker").join("main.py"));
            candidates.push(exe_dir.join("..").join("..").join("worker").join("main.py"));
            candidates.push(exe_dir.join("..").join("..").join("..").join("worker").join("main.py"));
        }
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    if let Some(workspace_root) = manifest_dir.parent() {
        candidates.push(workspace_root.join("worker").join("main.py"));
    }

    candidates
}

fn worker_script_path() -> Result<PathBuf, String> {
    candidate_worker_paths()
        .into_iter()
        .find(|candidate| candidate.is_file())
        .ok_or_else(|| {
            let searched = candidate_worker_paths()
                .into_iter()
                .map(|path| path.display().to_string())
                .collect::<Vec<_>>()
                .join(", ");
            format!("Could not locate worker/main.py. Searched: {searched}")
        })
}

fn python_command() -> String {
    env::var("OPEN_COLLAR_PYTHON").unwrap_or_else(|_| "python".to_string())
}

fn resolve_worker_launch() -> Result<WorkerLaunch, String> {
    if let Some(path) = candidate_worker_executable_paths()
        .into_iter()
        .find(|candidate| candidate.is_file())
    {
        return Ok(WorkerLaunch::Executable(path));
    }

    Ok(WorkerLaunch::PythonScript {
        python: python_command(),
        script: worker_script_path()?,
    })
}

pub fn spawn_worker<F>(
    mut on_stdout: F,
    mut on_stderr: impl FnMut(String) + Send + 'static,
) -> Result<WorkerManager, String>
where
    F: FnMut(String) + Send + 'static,
{
    let launch = resolve_worker_launch()?;
    logging::log("INFO", format!("attempting to launch {}", launch.describe()));

    let mut command = match &launch {
        WorkerLaunch::Executable(path) => Command::new(path),
        WorkerLaunch::PythonScript { python, script } => {
            let mut command = Command::new(python);
            command.arg(script);
            command
        }
    };

    let mut child = command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| error.to_string())?;

    logging::log("INFO", format!("worker process launched via {}", launch.describe()));

    let stdin = child.stdin.take().ok_or_else(|| "Failed to capture worker stdin.".to_string())?;
    let stdout = child.stdout.take().ok_or_else(|| "Failed to capture worker stdout.".to_string())?;
    let stderr = child.stderr.take().ok_or_else(|| "Failed to capture worker stderr.".to_string())?;

    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            match line {
                Ok(content) if !content.trim().is_empty() => on_stdout(content),
                Ok(_) => {}
                Err(_) => break,
            }
        }
    });

    thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            match line {
                Ok(content) if !content.trim().is_empty() => {
                    logging::log("ERROR", format!("worker stderr: {content}"));
                    on_stderr(content)
                }
                Ok(_) => {}
                Err(error) => {
                    logging::log("ERROR", format!("worker stderr error: {error}"));
                    on_stderr(format!("worker stderr error: {error}"));
                    break;
                }
            }
        }
    });

    Ok(WorkerManager {
        stdin: Some(Arc::new(Mutex::new(stdin))),
        _child: Some(Arc::new(Mutex::new(child))),
    })
}
