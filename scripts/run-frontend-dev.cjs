const { spawnSync, spawn } = require("child_process");
const path = require("path");

const root = path.join(__dirname, "..");
const isWin = process.platform === "win32";
const npm = isWin ? "npm.cmd" : "npm";

const wait = spawnSync("node", ["scripts/wait-backend.cjs"], {
  cwd: root,
  stdio: "inherit",
  windowsHide: true,
});

if (wait.status !== 0) {
  process.exit(wait.status ?? 1);
}

const vite = spawn(npm, ["run", "dev", "--prefix", "frontend"], {
  cwd: root,
  stdio: "inherit",
  shell: isWin,
  windowsHide: true,
});

vite.on("exit", (code) => process.exit(code ?? 0));
process.on("SIGTERM", () => vite.kill("SIGTERM"));
process.on("SIGINT", () => vite.kill("SIGINT"));
