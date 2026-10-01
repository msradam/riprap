/** Shim for `$app/paths` in unit tests: no base path. Like SvelteKit's
 *  resolve, it drops route-group segments such as `/(app)`. */
export const base = '';
export function resolve(path: string, params: Record<string, string> = {}): string {
  const out = path
    .replace(/\/\([^)]+\)/g, '')
    .replace(/\[(\w+)\]/g, (_, k: string) => params[k] ?? '');
  return out || '/';
}
/** Like SvelteKit's asset: a file in static/, under the (empty) base. */
export const asset = (file: string): string => base + file;
