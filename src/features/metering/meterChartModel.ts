import type { components } from '../../api/schema';

type Reading = components['schemas']['ReadingResponse'];
export type MeterChartPoint = Readonly<{ date: string; value: number; source: 'recorded' | 'interpolated' }>;

/** Display-only interpolation; billing always uses the server consumption endpoint. */
export function interpolateMeterReading(readings: readonly Reading[], date: string): MeterChartPoint | null {
  const sorted = readings.filter(item => Number.isFinite(Number(item.reading_value)))
    .slice().sort((left, right) => left.reading_date.localeCompare(right.reading_date));
  const exact = sorted.find(item => item.reading_date === date);
  if (exact) return { date, value: Number(exact.reading_value), source: 'recorded' };
  const before = sorted.filter(item => item.reading_date < date).at(-1);
  const after = sorted.find(item => item.reading_date > date);
  if (!before || !after) return null;
  const start = Date.parse(`${before.reading_date}T00:00:00Z`);
  const end = Date.parse(`${after.reading_date}T00:00:00Z`);
  const sample = Date.parse(`${date}T00:00:00Z`);
  if (!Number.isFinite(start) || !Number.isFinite(end) || !Number.isFinite(sample) || end <= start) return null;
  return { date, value: Number(before.reading_value) + (Number(after.reading_value) - Number(before.reading_value)) * (sample - start) / (end - start), source: 'interpolated' };
}

export function buildMeterChartPoints(readings: readonly Reading[]): MeterChartPoint[] {
  const actual = readings.filter(item => Number.isFinite(Number(item.reading_value)))
    .map(item => ({ date: item.reading_date, value: Number(item.reading_value), source: 'recorded' as const }));
  if (actual.length < 2) return actual.sort((a, b) => a.date.localeCompare(b.date));
  const sorted = actual.slice().sort((a, b) => a.date.localeCompare(b.date));
  const first = sorted[0].date;
  const last = sorted[sorted.length - 1].date;
  const year = Number(first.slice(0, 4));
  const month = Number(first.slice(5, 7));
  const interpolated: MeterChartPoint[] = [];
  for (let index = year * 12 + month; index <= Number(last.slice(0, 4)) * 12 + Number(last.slice(5, 7)); index++) {
    const monthYear = Math.floor((index - 1) / 12);
    const monthNumber = ((index - 1) % 12) + 1;
    const date = `${monthYear}-${String(monthNumber).padStart(2, '0')}-01`;
    if (date > first && date < last && !sorted.some(item => item.date === date)) {
      const point = interpolateMeterReading(readings, date);
      if (point) interpolated.push(point);
    }
  }
  return [...sorted, ...interpolated].sort((a, b) => a.date.localeCompare(b.date));
}
