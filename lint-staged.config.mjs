import path from "node:path"
import { fileURLToPath } from "node:url"

const root = path.dirname(fileURLToPath(import.meta.url))

function quote(file) {
  return `"${file.replace(/"/g, '\\"')}"`
}

function relArgs(appDir, files) {
  return files
    .map((file) => path.relative(path.join(root, appDir), file))
    .map((rel) => rel.split(path.sep).join("/"))
}

function prettierWrite(files) {
  // Use local prettier via run-in so Windows/npx path resolution is reliable
  return `node scripts/run-in.mjs . npx prettier --write ${files.map(quote).join(" ")}`
}

/** @type {import('lint-staged').Configuration} */
export default {
  "apps/web/**/*.{ts,tsx,js,jsx,css,json,md}": (files) => {
    const scriptFiles = files.filter((f) => /\.(ts|tsx|js|jsx)$/.test(f))
    const cmds = [prettierWrite(files)]
    if (scriptFiles.length > 0) {
      cmds.push(
        `node scripts/run-in.mjs apps/web npx oxlint ${relArgs("apps/web", scriptFiles)
          .map(quote)
          .join(" ")}`,
      )
    }
    return cmds
  },

  "apps/web/**/*.{ts,tsx}": () => ["node scripts/run-in.mjs apps/web npm run typecheck"],

  "apps/marketing/**/*.{ts,tsx,js,jsx,mjs,css,json,md}": (files) => {
    const scriptFiles = files.filter((f) => /\.(ts|tsx|js|jsx|mjs)$/.test(f))
    const cmds = [prettierWrite(files)]
    if (scriptFiles.length > 0) {
      cmds.push(
        `node scripts/run-in.mjs apps/marketing npx eslint --max-warnings 0 ${relArgs(
          "apps/marketing",
          scriptFiles,
        )
          .map(quote)
          .join(" ")}`,
      )
    }
    return cmds
  },

  "apps/marketing/**/*.{ts,tsx}": () => ["node scripts/run-in.mjs apps/marketing npx tsc --noEmit"],

  // Root / shared config files (Prettier)
  "*.{json,md,yml,yaml,mjs,cjs}": (files) => [prettierWrite(files)],

  // Critical Ruff rules only (undefined names / syntax) — style debt is not a commit gate yet
  "apps/api/**/*.py": (files) => [
    `node scripts/run-ruff.mjs check --config apps/api/pyproject.toml ${files
      .map(quote)
      .join(" ")}`,
  ],

  "infra/**/*.py": (files) => [
    `node scripts/run-ruff.mjs check --config apps/api/pyproject.toml ${files
      .map(quote)
      .join(" ")}`,
  ],
}
