import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const root = process.cwd();
const pythonInVenv = path.join(
  root,
  ".venv",
  process.platform === "win32" ? "Scripts" : "bin",
  process.platform === "win32" ? "python.exe" : "python",
);
const python = process.env.PYTHON || (existsSync(pythonInVenv) ? pythonInVenv : "python");
const nextCli = path.join(root, "node_modules", "next", "dist", "bin", "next");

function isPrivateIpv4(address) {
  const octets = address.split(".").map(Number);
  return (
    octets.length === 4 &&
    (octets[0] === 10 ||
      (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31) ||
      (octets[0] === 192 && octets[1] === 168))
  );
}

const lanAddresses = Object.values(os.networkInterfaces())
  .flatMap((interfaces) => interfaces ?? [])
  .filter(
    (entry) =>
      (entry.family === "IPv4" || entry.family === 4) &&
      !entry.internal &&
      isPrivateIpv4(entry.address),
  )
  .map((entry) => entry.address);

console.log("Starting banking API and web portal...");
console.log("API: http://127.0.0.1:8000 (available through the portal proxy)");
console.log("Portal: http://127.0.0.1:3000");
if (lanAddresses.length > 0) {
  for (const address of [...new Set(lanAddresses)]) {
    console.log(`LAN: http://${address}:3000`);
  }
} else {
  console.warn("No private IPv4 address detected. Check your network connection.");
}
console.log("If another device cannot connect, allow Node.js on the Private network in Windows Firewall.");

if (!existsSync(nextCli)) {
  console.error("Next.js is not installed. Run npm install, then retry.");
  process.exit(1);
}

console.log("Checking database migrations...");
const migration = spawnSync(python, ["-m", "alembic", "upgrade", "head"], {
  cwd: root,
  env: process.env,
  stdio: "inherit",
});
if (migration.error) {
  console.error(`Database migrations could not start: ${migration.error.message}`);
  process.exit(1);
}
if (migration.status !== 0) {
  console.error(`Database migrations failed with exit code ${migration.status ?? 1}.`);
  process.exit(migration.status ?? 1);
}

const services = [];
let stopping = false;

function stop(exitCode) {
  if (stopping) return;
  stopping = true;
  process.exitCode = exitCode;
  for (const service of services) {
    if (service.exitCode === null) service.kill();
  }
}

function start(name, command, args) {
  const child = spawn(command, args, {
    cwd: root,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: "inherit",
  });
  services.push(child);
  child.once("error", (error) => {
    console.error(`${name} could not start: ${error.message}`);
    stop(1);
  });
  child.once("close", (code) => {
    if (!stopping) {
      console.error(`${name} stopped${code === null ? "" : ` with exit code ${code}`}.`);
      stop(code ?? 1);
    }
  });
}

start("Banking API", python, ["main.py"]);
start("Web portal", process.execPath, [
  nextCli,
  "dev",
  "--hostname",
  "0.0.0.0",
  "--port",
  "3000",
]);

process.once("SIGINT", () => stop(0));
process.once("SIGTERM", () => stop(0));
