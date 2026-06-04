const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const isWin = process.platform === "win32";
const nodemon = path.join(
  root,
  "node_modules",
  "nodemon",
  "bin",
  "nodemon.js"
);

if (!fs.existsSync(nodemon)) {
  console.error("[dev] nodemon belum ada. Jalankan: npm install");
  process.exit(1);
}

const child = spawn(process.execPath, [nodemon], {
  cwd: root,
  stdio: "inherit",
  windowsHide: true,
});

child.on("exit", (code) => process.exit(code ?? 0));
process.on("SIGINT", () => child.kill("SIGINT"));
