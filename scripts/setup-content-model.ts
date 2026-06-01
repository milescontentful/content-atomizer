#!/usr/bin/env tsx
/**
 * scripts/setup-content-model.ts
 *
 * Idempotent reset + provision for the content-atomization-poc Contentful space.
 *
 * Steps executed in order:
 *   1. Unpublish + delete ALL entries (all pages)
 *   2. Unpublish + delete all existing content types
 *   3. Create 4 content types from model/*.json
 *   4. Publish 4 content types
 *
 * Usage:
 *   tsx scripts/setup-content-model.ts             # live run (5-second safety pause)
 *   tsx scripts/setup-content-model.ts --dry-run   # preview — no network writes
 *
 * Reads credentials from .env (CTFL_SPACE_ID, CTFL_CMA_TOKEN, CTFL_ENVIRONMENT_ID).
 * Safe to re-run: idempotent — deleted/missing items are skipped, not errored.
 */

import { readFileSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');

// ── .env loader ────────────────────────────────────────────────────────────────

function loadEnv(): void {
  try {
    const lines = readFileSync(join(ROOT, '.env'), 'utf-8').split('\n');
    for (const line of lines) {
      const t = line.trim();
      if (!t || t.startsWith('#') || !t.includes('=')) continue;
      const [rawKey, ...rest] = t.split('=');
      const key = rawKey?.trim();
      if (key && !process.env[key]) process.env[key] = rest.join('=').trim();
    }
  } catch {
    // .env not found — rely on existing env vars
  }
}

loadEnv();

const SPACE_ID = process.env.CTFL_SPACE_ID ?? '';
const ENV_ID   = process.env.CTFL_ENVIRONMENT_ID ?? 'master';
const TOKEN    = process.env.CTFL_CMA_TOKEN ?? '';
const DRY_RUN  = process.argv.includes('--dry-run');

if (!SPACE_ID || !TOKEN) {
  console.error('[setup] ERROR: CTFL_SPACE_ID and CTFL_CMA_TOKEN must be set in .env');
  process.exit(1);
}

const BASE = `https://api.contentful.com/spaces/${SPACE_ID}/environments/${ENV_ID}`;

// ── CMA helpers ────────────────────────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function cmaReq(
  method: string,
  path: string,
  body?: unknown,
  version?: number,
): Promise<Response> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${TOKEN}`,
    'Content-Type': 'application/vnd.contentful.management.v1+json',
  };
  if (version !== undefined) headers['X-Contentful-Version'] = String(version);

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 429) {
    const wait = Number(res.headers.get('X-Contentful-RateLimit-Reset') ?? '2') + 1;
    console.log(`[setup]   rate-limited — retrying in ${wait}s`);
    await sleep(wait * 1000);
    return cmaReq(method, path, body, version);
  }

  return res;
}

async function cmaJson<T>(method: string, path: string, body?: unknown, version?: number): Promise<T> {
  const res = await cmaReq(method, path, body, version);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`CMA ${method} ${path} → ${res.status}: ${text.slice(0, 300)}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ──────────────────────────────────────────────────────────────────────

interface Sys { id: string; version: number; publishedVersion?: number }
interface CfItem { sys: Sys }
interface CfCollection<T> { items: T[]; total: number }

// ── Step 1: Delete all entries ─────────────────────────────────────────────────

async function deleteAllEntries(): Promise<void> {
  console.log('\n[setup] Step 1 — deleting all entries …');
  let deleted = 0;

  if (DRY_RUN) {
    // In dry-run, use skip-based pagination so the loop terminates (nothing is deleted).
    let skip = 0;
    const limit = 200;
    while (true) {
      const col = await cmaJson<CfCollection<CfItem>>(`GET`, `/entries?limit=${limit}&skip=${skip}&order=sys.createdAt`);
      if (!col.items.length) break;
      for (const entry of col.items) {
        console.log(`[setup]   [dry-run] would delete entry ${entry.sys.id}`);
        deleted++;
      }
      skip += col.items.length;
      if (skip >= col.total) break;
    }
  } else {
    // In live mode, always fetch from skip=0: as items are deleted the page shrinks
    // toward empty, which is the correct termination signal.
    while (true) {
      const col = await cmaJson<CfCollection<CfItem>>('GET', '/entries?limit=200&skip=0&order=sys.createdAt');
      if (!col.items.length) break;
      for (const entry of col.items) {
        const { id, publishedVersion } = entry.sys;
        try {
          if (publishedVersion !== undefined) {
            const r = await cmaReq('DELETE', `/entries/${id}/published`);
            if (!r.ok && r.status !== 404) console.warn(`[setup]   warn: unpublish ${id} → ${r.status}`);
            await sleep(120);
          }
          const r2 = await cmaReq('DELETE', `/entries/${id}`);
          if (!r2.ok && r2.status !== 404) console.warn(`[setup]   warn: delete ${id} → ${r2.status}`);
          deleted++;
          await sleep(120);
        } catch (e) {
          console.warn(`[setup]   warn: could not remove entry ${id}: ${(e as Error).message}`);
        }
      }
    }
  }

  console.log(`[setup]   ${deleted} entries ${DRY_RUN ? 'would be deleted' : 'deleted'}`);
}

// ── Step 2: Delete all content types ──────────────────────────────────────────

async function deleteAllContentTypes(): Promise<void> {
  console.log('\n[setup] Step 2 — deleting all content types …');
  const col = await cmaJson<CfCollection<CfItem & { name: string }>>('GET', '/content_types?limit=100');

  for (const ct of col.items) {
    const { id, version, publishedVersion } = ct.sys;

    if (DRY_RUN) {
      console.log(`[setup]   [dry-run] would delete content type "${ct.name}" (${id})`);
      continue;
    }

    try {
      if (publishedVersion !== undefined) {
        // Unpublish requires version header
        const r = await cmaReq('DELETE', `/content_types/${id}/published`, undefined, version);
        if (!r.ok && r.status !== 404) {
          console.warn(`[setup]   warn: unpublish CT ${id} → ${r.status}`);
        }
        await sleep(300);
      }
      // Re-fetch to get version after unpublish (unpublish does not increment version,
      // but re-fetching avoids any edge-case stale-version errors)
      const fresh = await cmaJson<CfItem & { name: string }>('GET', `/content_types/${id}`);
      await cmaReq('DELETE', `/content_types/${id}`, undefined, fresh.sys.version);
      console.log(`[setup]   deleted "${ct.name}" (${id})`);
      await sleep(300);
    } catch (e) {
      console.warn(`[setup]   warn: could not remove CT ${id}: ${(e as Error).message}`);
    }
  }
}

// ── Steps 3 + 4: Create and publish content types ─────────────────────────────

// Creation order: no-dependency types first so circular refs are satisfied at publish time.
// All 4 are created before any are published.
const CT_ORDER = ['customer', 'projectContext', 'contentAtom', 'sourceDocument'] as const;

async function createAndPublishContentTypes(): Promise<void> {
  console.log('\n[setup] Step 3 — creating content types from model/*.json …');

  const created: Array<{ id: string; version: number; name: string }> = [];

  for (const ctId of CT_ORDER) {
    const filePath = join(ROOT, 'model', `${ctId}.json`);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let def: any;
    try {
      def = JSON.parse(readFileSync(filePath, 'utf-8'));
    } catch {
      console.error(`[setup]   ERROR: model/${ctId}.json not found`);
      process.exit(1);
    }

    const body = {
      name: def.name,
      description: def.description ?? '',
      displayField: def.displayField,
      fields: def.fields,
    };

    if (DRY_RUN) {
      console.log(`[setup]   [dry-run] would create "${def.name}" (${ctId}) — ${def.fields.length} fields`);
      created.push({ id: ctId, version: 1, name: def.name });
      continue;
    }

    try {
      const res = await cmaJson<CfItem & { name: string }>('PUT', `/content_types/${ctId}`, body);
      console.log(`[setup]   created "${def.name}" (${ctId}) v${res.sys.version}`);
      created.push({ id: ctId, version: res.sys.version, name: def.name });
      await sleep(300);
    } catch (e) {
      console.error(`[setup]   ERROR creating "${ctId}": ${(e as Error).message}`);
      throw e;
    }
  }

  console.log('\n[setup] Step 4 — publishing content types …');

  for (const { id, version, name } of created) {
    if (DRY_RUN) {
      console.log(`[setup]   [dry-run] would publish "${name}" (${id})`);
      continue;
    }

    try {
      await cmaJson('PUT', `/content_types/${id}/published`, undefined, version);
      console.log(`[setup]   published "${name}" (${id})`);
      await sleep(300);
    } catch (e) {
      console.error(`[setup]   ERROR publishing "${id}": ${(e as Error).message}`);
      throw e;
    }
  }
}

// ── Main ───────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  console.log(`[setup] space=${SPACE_ID}  env=${ENV_ID}${DRY_RUN ? '  [DRY-RUN]' : ''}`);

  if (!DRY_RUN) {
    console.log('[setup] WARNING: this will DELETE ALL ENTRIES + CONTENT TYPES in the space.');
    console.log('[setup] Ctrl+C within 5 seconds to abort …');
    await sleep(5000);
  }

  await deleteAllEntries();
  await deleteAllContentTypes();
  await createAndPublishContentTypes();

  console.log('\n[setup] done.');
  if (!DRY_RUN) {
    console.log('[setup] Space is clean. 4 content types published.');
    console.log('[setup] Next: re-export your deck and run the pipeline.');
    console.log('[setup]   npm run extract -- --deck <deck-id>');
    console.log('[setup]   python pipeline/run.py --deck-id <deck-id> --apply');
  }
}

main().catch((e) => {
  console.error('[setup] FATAL:', e);
  process.exit(1);
});
