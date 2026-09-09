/** Product SPA login URL. Prod: same-origin `/app/login`. Local: Vite on :5173. */
export function appLoginUrl(opts?: { mode?: "login" | "register" }) {
  const fromEnv = process.env.NEXT_PUBLIC_APP_URL?.trim();
  const fallback =
    process.env.NODE_ENV === "development"
      ? "http://localhost:5173"
      : "/app";
  const raw = (fromEnv || fallback).replace(/\/$/, "");
  const mode = opts?.mode ?? "register";
  const path = `${raw}/login`;
  return mode === "register" ? `${path}?mode=register` : path;
}
