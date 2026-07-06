import { existsSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const venvPython =
  process.platform === "win32"
    ? path.join(root, ".venv", "Scripts", "python.exe")
    : path.join(root, ".venv", "bin", "python");

const python = process.env.CODEATLAS_PYTHON || (existsSync(venvPython) ? venvPython : "python");
const mode = process.argv[2];

const commands =
  mode === "dev"
    ? [["-m", "uvicorn", "app.main:app", "--reload", "--app-dir", "backend"]]
    : [
        ["-m", "ruff", "check", "backend/app", "backend/tests"],
        ["-m", "mypy", "backend/app"],
        ["-m", "pytest", "backend/tests"],
      ];

if (!mode || !["dev", "verify"].includes(mode)) {
  console.error("Usage: node scripts/backend.mjs <dev|verify>");
  process.exit(1);
}

for (const args of commands) {
  const result = spawnSync(python, args, {
    cwd: root,
    stdio: "inherit",
    shell: false,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}
