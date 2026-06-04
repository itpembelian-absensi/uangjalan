/**
 * Jalankan backend + frontend sekali.
 * Dipanggil nodemon saat startup / setelah file berubah (stop lalu nyala ulang).
 */
const { spawn, execSync } = require("child_process");
const path = require("path");

const root = path.join(__dirname, "..");
const isWin = process.platform === "win32";

console.log("[dev] Memulai server...");

try {
  execSync("powershell -ExecutionPolicy Bypass -File scripts/stop-dev.ps1", {
    cwd: root,
    stdio: "inherit",
    windowsHide: true,
  });
} catch (_) {
  /* port kosong */
}

const concurrentlyBin = path.join(
  root,
  "node_modules",
  "concurrently",
  "dist",
  "bin",
  "concurrently.js"
);

const child = spawn(
  process.execPath,
  [
    concurrentlyBin,
    "--success",
    "first",
    "--restart-tries",
    "10",
    "--restart-after",
    "3000",
    "-n",
    "backend,frontend",
    "-c",
    "blue,magenta",
    "node scripts/run-backend-watch.cjs",
    "node scripts/run-frontend-dev.cjs",
  ],
  { cwd: root, stdio: "inherit", shell: false, windowsHide: true }
);

function shutdown() {
  if (child && !child.killed) {
    child.kill(isWin ? "SIGTERM" : "SIGINT");
  }
}

child.on("exit", (code) => process.exit(code ?? 0));
process.on("SIGTERM", shutdown);
process.on("SIGINT", () => {
  shutdown();
  process.exit(0);
});
