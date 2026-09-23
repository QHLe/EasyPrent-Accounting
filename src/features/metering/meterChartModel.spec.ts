import { describe, expect, it } from 'vitest';
import type { components } from '../../api/schema';
import { buildMeterChartPoints, interpolateMeterReading } from './meterChartModel';

type Reading = components['schemas']['ReadingResponse'];
const reading = (id: number, date: string, value: string): Reading => ({ id, meter_id: 2, reading_date: date, reading_value: value });

describe('display interpolation for meter charts', () => {
  const readings = [reading(2, '2024-03-01', '29'), reading(1, '2024-02-01', '0')];

  it('uses elapsed days across a leap February and marks recorded points', () => {
    expect(interpolateMeterReading(readings, '2024-02-15')).toEqual({ date: '2024-02-15', value: 14, source: 'interpolated' });
    expect(interpolateMeterReading(readings, '2024-03-01')).toEqual({ date: '2024-03-01', value: 29, source: 'recorded' });
  });

  it('does not extrapolate outside recorded readings', () => {
    expect(interpolateMeterReading(readings, '2024-01-01')).toBeNull();
    expect(interpolateMeterReading(readings, '2024-04-01')).toBeNull();
  });

  it('adds monthly display points only between actual readings', () => {
    const points = buildMeterChartPoints([reading(1, '2024-01-15', '0'), reading(2, '2024-03-15', '60')]);
    expect(points).toEqual([
      { date: '2024-01-15', value: 0, source: 'recorded' },
      { date: '2024-02-01', value: 17, source: 'interpolated' },
      { date: '2024-03-01', value: 46, source: 'interpolated' },
      { date: '2024-03-15', value: 60, source: 'recorded' },
    ]);
  });

  it('sorts actual and monthly chart points without changing readings', () => {
    expect(buildMeterChartPoints([reading(3, '2024-04-01', '60'), ...readings])).toEqual([
      { date: '2024-02-01', value: 0, source: 'recorded' },
      { date: '2024-03-01', value: 29, source: 'recorded' },
      { date: '2024-04-01', value: 60, source: 'recorded' },
    ]);
    expect(readings[0].reading_date).toBe('2024-03-01');
  });
});
