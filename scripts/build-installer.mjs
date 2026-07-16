import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const scriptsDir = path.dirname(__filename);
const projectRoot = path.resolve(scriptsDir, "..");

const options = parseArgs(process.argv.slice(2));
const target = options.target ?? detectTarget();
const bundle = options.bundle ?? defaultBundleForTarget(target);
const mixedWindowsLinuxShell = isMixedWindowsLinuxShell();

if (mixedWindowsLinuxShell) {
  throw new Error(
    [
      "Windows installer builds must run from Windows PowerShell, Command Prompt, or a normal Windows terminal.",
      "This shell looks like WSL/Linux calling Windows Node/npm, which cannot reliably spawn npm.cmd from this path.",
      "Use `npm run installer:windows` in Windows, or use `npm run installer:linux` inside Ubuntu.",
    ].join(" "),
  );
}

if (!isNativeTarget(target)) {
  throw new Error(
    `This command builds native installers only. Run the ${target} installer build on ${target}.`,
  );
}

console.log(`Building AI Git Assistant installer for ${target} (${bundle})`);

if (!options.skipTests) {
  runNpm(["run", "sidecar:test"]);
}

runNpm(["run", "sidecar:build"]);
runCommand("npx", ["tauri", "build", "--bundles", bundle]);

const outputs = findBundleOutputs(bundle);
if (outputs.length > 0) {
  console.log("\nInstaller output:");
  for (const output of outputs) {
    console.log(`- ${output}`);
  }
}

function parseArgs(args) {
  const parsed = {};
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--target") {
      parsed.target = args[index + 1];
      index += 1;
    } else if (arg === "--bundle") {
      parsed.bundle = args[index + 1];
      index += 1;
    } else if (arg === "--skip-tests") {
      parsed.skipTests = true;
    }
  }
  return parsed;
}

function detectTarget() {
  if (process.platform === "win32") {
    return "windows";
  }
  if (process.platform === "linux") {
    return "linux";
  }
  if (process.platform === "darwin") {
    return "mac";
  }
  throw new Error(`Unsupported installer platform: ${process.platform}`);
}

function defaultBundleForTarget(target) {
  if (target === "windows") {
    return "nsis";
  }
  if (target === "linux") {
    return "deb";
  }
  if (target === "mac") {
    return "dmg";
  }
  throw new Error(`Unsupported installer target: ${target}`);
}

function isNativeTarget(target) {
  return (
    (target === "windows" && process.platform === "win32") ||
    (target === "linux" && process.platform === "linux") ||
    (target === "mac" && process.platform === "darwin")
  );
}

function isMixedWindowsLinuxShell() {
  return (
    process.platform === "win32" &&
    (Boolean(process.env.WSL_DISTRO_NAME) ||
      Boolean(process.env.WSL_INTEROP) ||
      process.cwd().startsWith("/mnt/"))
  );
}

function runNpm(args) {
  runCommand("npm", args);
}

function runCommand(command, args) {
  const useShell = process.platform === "win32";
  const result = spawnSync(command, args, {
    cwd: projectRoot,
    env: process.env,
    stdio: "inherit",
    shell: useShell,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with exit code ${result.status}.`);
  }
}

function findBundleOutputs(bundle) {
  const bundleRoot = path.join(projectRoot, "src-tauri", "target", "release", "bundle");
  const directories = bundle.split(",").map((entry) => entry.trim()).filter(Boolean);
  const outputs = [];

  for (const directory of directories) {
    const bundleDirectory = path.join(bundleRoot, directory);
    if (!existsSync(bundleDirectory)) {
      continue;
    }

    for (const entry of readdirSync(bundleDirectory)) {
      const fullPath = path.join(bundleDirectory, entry);
      if (statSync(fullPath).isFile()) {
        outputs.push(fullPath);
      }
    }
  }

  return outputs;
}
