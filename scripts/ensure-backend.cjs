const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const backendDir = path.join(__dirname, "..", "backend");
const isWin = process.platform === "win32";
const venvDir = path.join(backendDir, ".venv");
const python = path.join(venvDir, isWin ? "Scripts/python.exe" : "bin/python");

function run(exe, args) {
  const result = spawnSync(exe, args, {
    cwd: backendDir,
    stdio: "inherit",
    shell: false,
    windowsHide: true,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

if (!fs.existsSync(python)) {
  console.log("[setup] Membuat virtual environment Python...");
  run("python", ["-m", "venv", ".venv"]);
}

console.log("[setup] Memastikan dependency backend terpasang...");
run(python, ["-m", "pip", "install", "-q", "-U", "pip"]);
run(python, ["-m", "pip", "install", "-q", "-r", "requirements.txt"]);

const envPath = path.join(backendDir, ".env");
const envExample = path.join(backendDir, ".env.example");
if (!fs.existsSync(envPath) && fs.existsSync(envExample)) {
  fs.copyFileSync(envExample, envPath);
  console.log("[setup] File backend/.env dibuat dari .env.example — sesuaikan DATABASE_URL jika perlu.");
}
