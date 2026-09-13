#!/usr/bin/env node
/**
 * Cross-platform ruff runner for apps/api (uses local .venv).
 * Usage: node scripts/run-ruff.mjs check [extra args...]
 */
import fs from "node:fs"
import path from "node:path"
import { spawnSync } from "node:child_process"
import { fileURLToPath } from "node:url"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const args = process.argv.slice(2)
const subcommand = args[0] || "check"
const rest = args.slice(1)

const pythonCandidates =
  process.platform === "win32"
    ? [
        path.join(root, "apps", "api", ".venv", "Scripts", "python.exe"),
        path.join(root, "apps", "api", ".venv", "Scripts", "python"),
      ]
    : [path.join(root, "apps", "api", ".venv", "bin", "python")]

const python = pythonCandidates.find((p) => fs.existsSync(p))
if (!python) {
  console.error("apps/api/.venv not found. Run: npm run install:api")
  process.exit(1)
}

const target = rest.length > 0 ? rest : ["apps/api"]
const result = spawnSync(python, ["-m", "ruff", subcommand, ...target], {
  cwd: root,
  stdio: "inherit",
  shell: false,
})

process.exit(result.status ?? 1)
