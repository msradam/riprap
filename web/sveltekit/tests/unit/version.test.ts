import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { APP_VERSION } from '$lib/version';

describe('APP_VERSION', () => {
  it('matches the release in pyproject.toml', () => {
    const toml = readFileSync(join(process.cwd(), '../../pyproject.toml'), 'utf8');
    expect(APP_VERSION).toBe(/^version = "([^"]+)"/m.exec(toml)?.[1]);
  });
});
