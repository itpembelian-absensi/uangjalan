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

if (!fs.existsSync(python)) {
  console.error("[backend] Python venv belum ada. Jalankan: npm run setup");
  process.exit(1);
}

const child = spawn(
  python,
  ["-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8001"],
  { cwd: backendDir, stdio: "inherit", shell: false, windowsHide: true }
);

child.on("exit", (code) => process.exit(code ?? 0));

process.on("SIGINT", () => child.kill("SIGINT"));
process.on("SIGTERM", () => child.kill("SIGTERM"));
