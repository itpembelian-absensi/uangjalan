/**
 * Backend dengan auto-restart jika crash.
 * Perubahan file .py ditangani nodemon (npm run dev) — stop lalu nyala ulang semua.
 */
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const backendDir = path.join(__dirname, "..", "backend");
const isWin = process.platform === "win32";
const python = path.join(
  backendDir,
  ".venv",
  isWin ? "Scripts/python.exe" : "bin/python"
);

let child = null;
let stopping = false;
let restartTimer = null;

function log(msg) {
  console.log(`[backend] ${msg}`);
}

function start() {
  if (stopping || !fs.existsSync(python)) {
    if (!fs.existsSync(python)) {
      console.error("[backend] venv belum ada. Jalankan: npm run setup");
      process.exit(1);
    }
    return;
  }

  child = spawn(
    python,
    [
      "-m",
      "uvicorn",
      "app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      "8002",
      "--reload",
      "--reload-dir",
      "app",
    ],
    { cwd: backendDir, stdio: "inherit", shell: false, windowsHide: true }
  );

  child.on("exit", (code, signal) => {
    child = null;
    if (stopping) return;

    if (signal === "SIGINT" || signal === "SIGTERM" || code === 0) {
      process.exit(0);
    }

    log(`berhenti (kode ${code}). Nyala ulang otomatis dalam 3 detik...`);
    restartTimer = setTimeout(start, 3000);
  });
}

function stopChild() {
  stopping = true;
  if (restartTimer) clearTimeout(restartTimer);
  if (child && !child.killed) {
    child.kill(isWin ? "SIGTERM" : "SIGINT");
    setTimeout(() => {
      if (child && !child.killed) child.kill("SIGKILL");
    }, 2000);
  }
}

process.on("SIGINT", () => {
  stopChild();
  process.exit(0);
});
process.on("SIGTERM", stopChild);

start();
