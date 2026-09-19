import { describe, it, expect } from 'vitest';
import { buildFilteredExpenses, Expense } from './expenses';

describe('buildFilteredExpenses', () => {
  it('includes overlapping and open-ended costs for the given year', () => {
    const expenses: Expense[] = [
      { id: 1, period_start: "2024-12-15", period_end: "2025-01-15" },
      { id: 2, period_start: "2025-06-01", period_end: "2025-06-30" },
      { id: 3, period_start: "2025-12-31", is_open_ended: true },
      { id: 4, period_start: "2026-01-01", period_end: "2026-12-31" },
      { id: 5, booking_date: "2025-04-01", charge_type: "one_time" },
      { id: 6, period_start: "2024-01-01", charge_type: "consumption" },
    ];
    
    const result = buildFilteredExpenses(expenses, { target: undefined, expense_category: "", year: "2025" });
    const resultIds = result.map(e => e.id);
    
    expect(resultIds).toEqual([1, 2, 3, 5, 6]);
  });
});

