import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, copyFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const scriptsDir = path.dirname(__filename);
const projectRoot = path.resolve(scriptsDir, "..");
const sidecarRoot = path.join(projectRoot, "sidecar");
const binaryDirectory = path.join(projectRoot, "src-tauri", "binaries");
const buildDirectory = path.join(projectRoot, ".build", "sidecar");
const distDirectory = path.join(buildDirectory, "dist");

const options = parseArgs(process.argv.slice(2));
const python = options.python ?? process.env.PYTHON ?? "python";
const targetTriple = options.targetTriple ?? process.env.AIGA_TARGET_TRIPLE ?? detectRustHostTriple();
const executableSuffix = targetTriple.includes("windows") ? ".exe" : "";
const sidecarName = "ai-git-sidecar";

run(python, ["-m", "pip", "install", ".[build]"], { cwd: sidecarRoot });
run(
  python,
  [
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--name",
    sidecarName,
    "--paths",
    sidecarRoot,
    "--distpath",
    distDirectory,
    "--workpath",
    path.join(buildDirectory, "work"),
    "--specpath",
    buildDirectory,
    "run.py",
  ],
  { cwd: sidecarRoot },
);

mkdirSync(binaryDirectory, { recursive: true });
const source = path.join(distDirectory, `${sidecarName}${executableSuffix}`);
const destination = path.join(binaryDirectory, `${sidecarName}-${targetTriple}${executableSuffix}`);

if (!existsSync(source)) {
  throw new Error(`PyInstaller did not create the expected sidecar binary: ${source}`);
}

copyFileSync(source, destination);
console.log(`Sidecar bundled at ${destination}`);

function parseArgs(args) {
  const parsed = {};
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--python") {
      parsed.python = args[index + 1];
      index += 1;
    } else if (arg === "--target-triple") {
      parsed.targetTriple = args[index + 1];
      index += 1;
    }
  }
  return parsed;
}

function detectRustHostTriple() {
  const result = spawnSync("rustc", ["-vV"], {
    cwd: projectRoot,
    encoding: "utf8",
  });
  if (result.error || result.status !== 0) {
    throw new Error("Rust is required to determine the Tauri target triple. Install Rust, then rerun.");
  }
  const hostLine = result.stdout
    .split(/\r?\n/)
    .find((line) => line.startsWith("host:"));
  if (!hostLine) {
    throw new Error("Could not determine the Rust host target triple from `rustc -vV`.");
  }
  return hostLine.replace(/^host:\s*/, "").trim();
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? projectRoot,
    env: process.env,
    stdio: "inherit",
    shell: false,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with exit code ${result.status}.`);
  }
}
