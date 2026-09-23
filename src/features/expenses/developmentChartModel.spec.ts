import { describe, expect, it } from 'vitest';
import type { components } from '../../api/schema';
import { buildDevelopmentChart } from './developmentChartModel';

type Development = components['schemas']['ExpenseDevelopmentResponse'];

describe('expense development chart projection', () => {
  const data: Development = {
    year: 2025, total_amount: null, has_uncalculated_expense: true,
    categories: [
      { expense_category: 'Heizung', amount: null, has_uncalculated_expense: true },
      { expense_category: 'Versicherung', amount: '30.00', has_uncalculated_expense: false },
    ],
    months: [
      { month: 2, total_amount: null, has_uncalculated_expense: true, categories: [
        { expense_category: 'Heizung', amount: null, has_uncalculated_expense: true },
        { expense_category: 'Versicherung', amount: '10.00', has_uncalculated_expense: false },
      ] },
      { month: 1, total_amount: '20.00', has_uncalculated_expense: false, categories: [
        { expense_category: 'Heizung', amount: '0.00', has_uncalculated_expense: false },
        { expense_category: 'Versicherung', amount: '20.00', has_uncalculated_expense: false },
      ] },
    ],
  };

  it('preserves missing server totals as chart gaps and keeps zero distinct', () => {
    const chart = buildDevelopmentChart(data);
    expect(chart.values.slice(0, 3)).toEqual([20, null, null]);
    expect(chart.unavailableMonths).toContain(2);
  });

  it('uses a category projection without summing browser expense values', () => {
    const chart = buildDevelopmentChart(data, 'Heizung');
    expect(chart.values.slice(0, 2)).toEqual([0, null]);
    expect(chart.labels[0]).toBe('Jan 2025');
  });
});
