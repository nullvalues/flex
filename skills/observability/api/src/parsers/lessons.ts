import { promises as fs } from 'node:fs';

// ---------------------------------------------------------------------------
// Lesson shape
// ---------------------------------------------------------------------------

export interface MethodologyChange {
  affects?: string[];
  description?: string;
}

export interface Lesson {
  id: string;
  date?: string;
  status?: string;
  trigger?: string;
  problem?: string;
  learning?: string;
  methodology_change?: MethodologyChange;
  applies_to?: string[];
  source_project?: string;
  /** Computed fields — set by applyPromotionFilter */
  promotion_candidate: boolean;
  promotion_reasons: string[];
}

// ---------------------------------------------------------------------------
// Raw shape as stored in lessons.json (before promotion filter)
// ---------------------------------------------------------------------------

interface RawLesson {
  id?: unknown;
  date?: unknown;
  status?: unknown;
  trigger?: unknown;
  problem?: unknown;
  learning?: unknown;
  methodology_change?: {
    affects?: unknown;
    description?: unknown;
  };
  applies_to?: unknown;
  source_project?: unknown;
  [key: string]: unknown;
}

interface LessonsFile {
  version?: string;
  lessons?: RawLesson[];
}

// ---------------------------------------------------------------------------
// D6 promotion-candidate filter patterns
// ---------------------------------------------------------------------------

/** Matches a Python module filename: alphanumeric/underscore, optional path prefix, .py extension */
const MODULE_FILENAME_RE = /^(?:[a-zA-Z0-9_]+\/)?[a-zA-Z0-9_]+\.py$/;

/** Procedural-verb patterns (case-insensitive) from D6 */
const PROCEDURAL_VERB_PATTERNS: Array<{ re: RegExp; label: string }> = [
  { re: /add\s+a\s+(check|warning|gate)/i, label: 'add a (check|warning|gate)' },
  { re: /block\s+when/i, label: 'block when' },
  { re: /warn\s+if/i, label: 'warn if' },
  { re: /default\s+to/i, label: 'default to' },
  { re: /fail\s+(open|closed)\s+when/i, label: 'fail (open|closed) when' },
];

// ---------------------------------------------------------------------------
// Main exports
// ---------------------------------------------------------------------------

/**
 * Parse lessons from a lessons.json file path.
 * Returns an empty array if the file is absent or unparseable.
 * Returned lessons have `promotion_candidate: false` and `promotion_reasons: []`
 * — call `applyPromotionFilter` to compute those fields.
 */
export async function parseLessons(filePath: string): Promise<Lesson[]> {
  let raw: string;
  try {
    raw = await fs.readFile(filePath, 'utf8');
  } catch {
    return [];
  }

  let parsed: LessonsFile;
  try {
    parsed = JSON.parse(raw) as LessonsFile;
  } catch {
    return [];
  }

  if (!parsed || !Array.isArray(parsed.lessons)) {
    return [];
  }

  return parsed.lessons.map((r) => {
    const mc = r.methodology_change;
    const methodologyChange: MethodologyChange | undefined =
      mc && typeof mc === 'object'
        ? {
            affects: Array.isArray(mc.affects)
              ? (mc.affects as unknown[]).filter((x) => typeof x === 'string') as string[]
              : [],
            description: typeof mc.description === 'string' ? mc.description : undefined,
          }
        : undefined;

    return {
      id: typeof r.id === 'string' ? r.id : String(r.id ?? ''),
      date: typeof r.date === 'string' ? r.date : undefined,
      status: typeof r.status === 'string' ? r.status : undefined,
      trigger: typeof r.trigger === 'string' ? r.trigger : undefined,
      problem: typeof r.problem === 'string' ? r.problem : undefined,
      learning: typeof r.learning === 'string' ? r.learning : undefined,
      methodology_change: methodologyChange,
      applies_to: Array.isArray(r.applies_to)
        ? (r.applies_to as unknown[]).filter((x) => typeof x === 'string') as string[]
        : [],
      source_project: typeof r.source_project === 'string' ? r.source_project : undefined,
      promotion_candidate: false,
      promotion_reasons: [],
    };
  });
}

/**
 * Apply the D6 promotion-candidate filter to a list of lessons.
 * Returns a new array with `promotion_candidate` and `promotion_reasons` populated.
 * Original lesson objects are not mutated.
 */
export function applyPromotionFilter(lessons: Lesson[]): Lesson[] {
  return lessons.map((lesson) => {
    const reasons: string[] = [];

    // Condition 1: status must be "applied"
    if (lesson.status !== 'applied') {
      return { ...lesson, promotion_candidate: false, promotion_reasons: [] };
    }

    const mc = lesson.methodology_change;

    // Condition 2: methodology_change.affects must contain a Python module filename
    const affects = mc?.affects ?? [];
    const moduleMatches = affects.filter((a) => MODULE_FILENAME_RE.test(a));
    if (moduleMatches.length === 0) {
      return { ...lesson, promotion_candidate: false, promotion_reasons: [] };
    }
    for (const m of moduleMatches) {
      reasons.push(`module-named: ${m}`);
    }

    // Condition 3: methodology_change.description must match a procedural-verb pattern
    const description = mc?.description ?? '';
    const verbMatches: string[] = [];
    for (const { re, label } of PROCEDURAL_VERB_PATTERNS) {
      if (re.test(description)) {
        verbMatches.push(`procedural-verb: '${label}'`);
      }
    }
    if (verbMatches.length === 0) {
      return { ...lesson, promotion_candidate: false, promotion_reasons: [] };
    }
    reasons.push(...verbMatches);

    return { ...lesson, promotion_candidate: true, promotion_reasons: reasons };
  });
}
