// Link interni che rispettano il "base path" (es. GitHub Pages pubblica sotto /behuman/).
export function u(p: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  const path = p.startsWith("/") ? p : `/${p}`;
  return `${base}${path}`;
}
