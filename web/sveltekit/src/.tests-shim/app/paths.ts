/** Shim for `$app/paths` in unit tests: no base path. */
export const base = '';
export function resolve(path: string, params: Record<string, string> = {}): string {
  return path.replace(/\[(\w+)\]/g, (_, k: string) => params[k] ?? '');
}
