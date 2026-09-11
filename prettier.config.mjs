/** @type {import("prettier").Config} */
const config = {
  semi: false,
  singleQuote: false,
  trailingComma: "all",
  printWidth: 100,
  tabWidth: 2,
  endOfLine: "lf",
  overrides: [
    {
      // Marketing (Next.js) currently uses semicolons
      files: ["apps/marketing/**/*.{js,jsx,ts,tsx,mjs,cjs}"],
      options: {
        semi: true,
      },
    },
  ],
}

export default config
