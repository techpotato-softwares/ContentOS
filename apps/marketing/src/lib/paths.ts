/** Compare App Router pathnames with or without a trailing slash. */
export function pathsMatch(pathname: string | null, href: string) {
  const current = (pathname ?? "").replace(/\/+$/, "") || "/";
  const target = href.replace(/\/+$/, "") || "/";
  return current === target;
}
