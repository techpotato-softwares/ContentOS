#!/usr/bin/env node
/**
 * Run a command with cwd set (cross-platform helper for lint-staged).
 * Usage: node scripts/run-in.mjs <relative-cwd> <command> [args...]
 */
import { spawnSync } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const [relCwd, command, ...args] = process.argv.slice(2)

if (!relCwd || !command) {
  console.error("Usage: node scripts/run-in.mjs <cwd> <command> [args...]")
  process.exit(1)
}

const cwd = path.resolve(root, relCwd)
const result = spawnSync(command, args, {
  cwd,
  stdio: "inherit",
  shell: true,
  env: process.env,
})

process.exit(result.status ?? 1)
