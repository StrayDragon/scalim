import type { VizEvent } from '$domain/types';

export function parseJsonl(text: string): VizEvent[] {
  const events: VizEvent[] = [];
  const lines = text.split(/\r?\n/).filter(Boolean);
  for (const line of lines) {
    try {
      const parsed = JSON.parse(line) as VizEvent;
      if (parsed && parsed.event_type) {
        events.push(parsed);
      }
    } catch (err) {
      continue;
    }
  }
  return events;
}

export function groupEventsByType(events: VizEvent[]) {
  const map = new Map<string, number>();
  for (const event of events) {
    map.set(event.event_type, (map.get(event.event_type) ?? 0) + 1);
  }
  return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
}

export function formatTimestamp(ts: number) {
  if (!ts) {
    return '';
  }
  const date = new Date(ts * 1000);
  return date.toISOString().replace('T', ' ').slice(0, 19);
}
