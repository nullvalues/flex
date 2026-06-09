/**
 * Extracts metadata from raw markdown content.
 */

/**
 * Return the text of the first markdown heading found in the content.
 * Accepts any heading level (# through ######).
 * If no heading is found, returns the filename stem passed as `fallback`.
 */
export function firstHeading(content: string, fallback = ''): string {
  const lines = content.split('\n');
  for (const line of lines) {
    const match = line.match(/^#{1,6}\s+(.+)/);
    if (match) {
      return match[1].trim();
    }
  }
  return fallback;
}
