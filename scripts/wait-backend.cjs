/**
 * Tunggu backend siap di port 8002 sebelum frontend memanggil /api
 */
const http = require("http");

const host = "127.0.0.1";
const port = 8002;
const maxAttempts = 90;

let attempts = 0;

function probe() {
  attempts += 1;
  const req = http.get({ host, port, path: "/docs", timeout: 2000 }, (res) => {
    res.resume();
    if (res.statusCode && res.statusCode < 500) {
      console.log(`[wait] Backend siap di http://${host}:${port}`);
      process.exit(0);
    }
    scheduleRetry();
  });

  req.on("error", scheduleRetry);
  req.on("timeout", () => {
    req.destroy();
    scheduleRetry();
  });
}

function scheduleRetry() {
  if (attempts >= maxAttempts) {
    console.error(
      `[wait] Backend tidak merespons di port ${port} setelah ${maxAttempts} detik.`
    );
    console.error("[wait] Cek terminal [backend] untuk error Python/PostgreSQL.");
    process.exit(1);
  }
  if (attempts === 1 || attempts % 5 === 0) {
    console.log(`[wait] Menunggu backend... (${attempts}s)`);
  }
  setTimeout(probe, 1000);
}

probe();
