#!/usr/bin/env tsx
/**
 * Extract stage: GAS atomization-export JSON → normalized IR.
 *
 * Reads  pipeline/staging/01_raw/{deckId}.json   (output of exportForAtomization() in
 *        apps/google-slides-addon/src/atomization-export.gs)
 * Writes pipeline/staging/02_ir/{deckId}.json    (input to pipeline/transform.py)
 *
 * Usage:
 *   npm run extract -- --deck <deckId>
 *   tsx pipeline/extract.ts --deck <deckId>
 *
 * The IR format mirrors the contract in pipeline/extract.py so both the
 * TypeScript and Python paths are interchangeable at this stage boundary.
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const STAGING = join(__dirname, 'staging');

// ─── Input types (GAS atomization-export format) ──────────────────────────────

interface BodyLine {
  text: string;
  isBullet: boolean;
}

/** One text shape with its bounding box — emitted by export-for-atomization.gs v2 */
interface RawShape {
  objectId: string;
  top: number;
  left: number;
  width: number;
  height: number;
  lines: BodyLine[];
}

/** One image element with its bounding box — emitted by export-for-atomization.gs v2 */
interface RawImageRef {
  objectId: string;
  top: number;
  left: number;
  width: number;
  height: number;
  altText: string;
  contentUrl: string;
}

interface RawSlide {
  slideIndex: number;
  objectId: string;
  layoutName: string;
  slideType: string;
  title: string;
  subtitle?: string;
  bodyText: string;
  bodyLines: BodyLine[];
  /** Per-shape geometry — present in exports from GAS v2 (export-for-atomization.gs) */
  shapes?: RawShape[];
  /** Per-image geometry — present in exports from GAS v2; replaces imageCount */
  imageRefs?: RawImageRef[];
  speakerNotes: string;
  imageCount: number;
}

interface RawDeck {
  presentationId: string;
  title: string;
  slides: RawSlide[];
}

// ─── Output types (IR / staging/02_ir format) ─────────────────────────────────

interface ParsedNotes {
  Goal?: string;
  'Talk Track'?: string;
  'Key Points'?: string;
  'Key Takeaway'?: string;
  'Discovery Questions'?: string;
  [key: string]: string | undefined;
}

interface SlideFlags {
  unfinished: boolean;
  internal: boolean;
}

/** Geometry-aware shape in the IR — maps directly from GAS v2 shapes[] */
interface IrShape {
  objectId: string;
  top: number;
  left: number;
  width: number;
  height: number;
  lines: BodyLine[];
}

/** Image reference in the IR */
interface IrImageRef {
  objectId: string;
  top: number;
  left: number;
  width: number;
  height: number;
  altText: string;
  contentUrl: string;
}

interface IrSlide {
  slideIndex: number;
  objectId: string;
  layoutName: string;
  slideType: string;
  title: string;
  subtitle?: string;
  /** Flat ordered array of non-empty text runs (back-compat; used by coarse transform) */
  textRuns: string[];
  /**
   * Per-shape text + bounding box, sorted top-to-bottom then left-to-right.
   * Present when the export was produced by GAS v2. The geometry-aware transform
   * uses this to correctly pair stat numbers with their labels.
   */
  shapes: IrShape[];
  /** Per-image geometry + altText. Use instead of imageCount for ingestion. */
  imageRefs: IrImageRef[];
  imageCount: number;
  /** Speaker notes split into named sections */
  notes: ParsedNotes;
  rawNotes: string;
  flags: SlideFlags;
}

interface IrDeck {
  sourceDocId: string;
  title: string;
  sourceUrl: string;
  slides: IrSlide[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const NOTE_SECTIONS = [
  'Goal',
  'Talk Track',
  'Key Points',
  'Key Takeaway',
  'Discovery Questions',
] as const;

/** Slide text cues that indicate the content is incomplete / placeholder */
const UNFINISHED_CUES = [
  'need numbers',
  '[add in',
  'tbd',
  'todo',
  'xx%',
  'lorem ipsum',
  '<insert',
  'placeholder',
];

/** Cues that mark a slide as internal-only */
const INTERNAL_CUES = [
  'internal only',
  'do not use',
  '[template]',
  'confidential',
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Splits speaker notes into named sections using the standard schema:
 * Goal / Talk Track / Key Points / Key Takeaway / Discovery Questions.
 * Lines not under any known header are ignored.
 */
function parseStructuredNotes(notes: string): ParsedNotes {
  if (!notes.trim()) return {};
  const out: ParsedNotes = {};
  let current: string | null = null;

  for (const rawLine of notes.split('\n')) {
    const line = rawLine.trim();
    const header = NOTE_SECTIONS.find((s) =>
      line.toLowerCase().startsWith(s.toLowerCase())
    );
    if (header) {
      current = header;
      const colonIdx = line.indexOf(':');
      out[current] = colonIdx !== -1 ? line.slice(colonIdx + 1).trim() : '';
    } else if (current && line) {
      out[current] = [out[current], line].filter(Boolean).join('\n');
    }
  }
  return out;
}

function detectUnfinished(text: string): boolean {
  const low = text.toLowerCase();
  return UNFINISHED_CUES.some((cue) => low.includes(cue));
}

function detectInternal(text: string): boolean {
  const low = text.toLowerCase();
  return INTERNAL_CUES.some((cue) => low.includes(cue));
}

/**
 * Builds an ordered flat array of non-empty text strings from a raw slide.
 * Title first, then subtitle, then body lines — preserving reading order.
 */
function buildTextRuns(slide: RawSlide): string[] {
  const runs: string[] = [];
  if (slide.title?.trim()) runs.push(slide.title.trim());
  if (slide.subtitle?.trim()) runs.push(slide.subtitle.trim());
  for (const line of slide.bodyLines ?? []) {
    if (line.text.trim()) runs.push(line.text.trim());
  }
  return runs;
}

// ─── Core transform ───────────────────────────────────────────────────────────

function buildIr(raw: RawDeck): IrDeck {
  const slides: IrSlide[] = raw.slides.map((s) => {
    const allText = [s.title, s.subtitle ?? '', s.bodyText, s.speakerNotes].join(' ');

    // shapes[] — pass through directly from GAS v2 export; fall back to empty array
    // for older exports (back-compat). The transform uses shapes for geometry-aware fusion.
    const shapes: IrShape[] = (s.shapes ?? []).map((sh) => ({
      objectId: sh.objectId,
      top: sh.top,
      left: sh.left,
      width: sh.width,
      height: sh.height,
      lines: sh.lines,
    }));

    // imageRefs[] — pass through from GAS v2; fall back to empty array
    const imageRefs: IrImageRef[] = (s.imageRefs ?? []).map((img) => ({
      objectId: img.objectId,
      top: img.top,
      left: img.left,
      width: img.width,
      height: img.height,
      altText: img.altText,
      contentUrl: img.contentUrl,
    }));

    const irSlide: IrSlide = {
      slideIndex: s.slideIndex,
      objectId: s.objectId,
      layoutName: s.layoutName,
      slideType: s.slideType,
      title: s.title,
      textRuns: buildTextRuns(s),
      shapes,
      imageRefs,
      imageCount: imageRefs.length > 0 ? imageRefs.length : (s.imageCount ?? 0),
      notes: parseStructuredNotes(s.speakerNotes ?? ''),
      rawNotes: s.speakerNotes ?? '',
      flags: {
        unfinished: detectUnfinished(allText),
        internal: detectInternal(allText),
      },
    };
    if (s.subtitle) irSlide.subtitle = s.subtitle;
    return irSlide;
  });

  return {
    sourceDocId: `gslides-${raw.presentationId}`,
    title: raw.title,
    sourceUrl: `https://docs.google.com/presentation/d/${raw.presentationId}`,
    slides,
  };
}

// ─── Stats summary ────────────────────────────────────────────────────────────

function summarize(ir: IrDeck): void {
  const total = ir.slides.length;
  const unfinished = ir.slides.filter((s) => s.flags.unfinished).length;
  const internal = ir.slides.filter((s) => s.flags.internal).length;
  const withNotes = ir.slides.filter((s) => Object.keys(s.notes).length > 0).length;
  const withDQ = ir.slides.filter((s) => !!s.notes['Discovery Questions']).length;
  const withImages = ir.slides.filter((s) => s.imageCount > 0).length;
  const totalShapes = ir.slides.reduce((n, s) => n + s.shapes.length, 0);
  const hasGeometry = ir.slides.some((s) => s.shapes.length > 0);

  console.log(`[extract] ${total} slides total`);
  console.log(`[extract]   ${unfinished} unfinished (will be skipped by transform)`);
  console.log(`[extract]   ${internal} internal`);
  console.log(`[extract]   ${withNotes} with structured notes | ${withDQ} with Discovery Questions`);
  console.log(`[extract]   ${withImages} with images`);
  if (hasGeometry) {
    console.log(`[extract]   ${totalShapes} shapes with geometry (GAS v2 export — geometry-aware fusion enabled)`);
  } else {
    console.log(`[extract]   no geometry data — re-export with updated export-for-atomization.gs for accurate stat fusion`);
  }
}

// ─── CLI ──────────────────────────────────────────────────────────────────────

function main(): void {
  const deckIdx = process.argv.indexOf('--deck');
  if (deckIdx === -1 || !process.argv[deckIdx + 1]) {
    console.error('Usage: tsx pipeline/extract.ts --deck <deckId>');
    console.error('');
    console.error('  <deckId>  Short ID matching staging/01_raw/<deckId>.json');
    console.error('            Example: npm run extract -- --deck personalization-q2fy27');
    process.exit(1);
  }
  const deckId = process.argv[deckIdx + 1];

  const rawPath = join(STAGING, '01_raw', `${deckId}.json`);
  const outDir = join(STAGING, '02_ir');
  const outPath = join(outDir, `${deckId}.json`);

  if (!existsSync(rawPath)) {
    console.error(`[extract] raw file not found: ${rawPath}`);
    console.error('[extract] Run exportForAtomization() in the GAS add-on and');
    console.error(`[extract] save the output to ${rawPath}`);
    process.exit(1);
  }

  console.log(`[extract] reading ${rawPath}`);
  const raw: RawDeck = JSON.parse(readFileSync(rawPath, 'utf-8'));
  const ir = buildIr(raw);

  mkdirSync(outDir, { recursive: true });
  writeFileSync(outPath, JSON.stringify(ir, null, 2));
  console.log(`[extract] IR written → ${outPath}`);
  summarize(ir);
  console.log('[extract] next: python pipeline/run.py --deck-id ' + deckId + ' --dry-run');
}

main();
