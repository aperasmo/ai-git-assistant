import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";

const __filename = fileURLToPath(import.meta.url);
const scriptsDir = path.dirname(__filename);
const projectRoot = path.resolve(scriptsDir, "..");
const sidecarRoot = path.join(projectRoot, "sidecar");
const baseTempRoot = path.join(projectRoot, ".local", "pytest-tmp");
const runTemp = path.join(baseTempRoot, `run-${randomUUID().replaceAll("-", "")}`);

const options = parseArgs(process.argv.slice(2));
const python = options.python ?? process.env.PYTHON ?? detectPythonCommand();

if (options.installDependencies) {
  run(python, ["-m", "pip", "install", ".[dev]"], { cwd: sidecarRoot });
}

mkdirSync(baseTempRoot, { recursive: true });

run(
  python,
  [
    "-m",
    "pytest",
    "--basetemp",
    runTemp,
    "-p",
    "no:cacheprovider",
    ...options.pytestArgs,
  ],
  {
    cwd: sidecarRoot,
    env: {
      ...process.env,
      GIT_CEILING_DIRECTORIES: projectRoot,
    },
  },
);

function parseArgs(args) {
  const parsed = {
    installDependencies: false,
    pytestArgs: [],
  };
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--install-dependencies") {
      parsed.installDependencies = true;
    } else if (arg === "--python") {
      parsed.python = args[index + 1];
      index += 1;
    } else if (arg === "--") {
      parsed.pytestArgs.push(...args.slice(index + 1));
      break;
    } else {
      parsed.pytestArgs.push(arg);
    }
  }
  return parsed;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? projectRoot,
    env: options.env ?? process.env,
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

function detectPythonCommand() {
  const candidates = process.platform === "win32" ? ["python"] : ["python", "python3"];
  for (const candidate of candidates) {
    const result = spawnSync(candidate, ["--version"], {
      cwd: projectRoot,
      stdio: "ignore",
      shell: false,
    });
    if (!result.error && result.status === 0) {
      return candidate;
    }
  }
  throw new Error("Python 3.12+ was not found. Activate a Python 3.12 virtual environment or pass --python.");
}
