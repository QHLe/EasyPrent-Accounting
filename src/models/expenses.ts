export interface Target {
  type: string;
  id: number;
}

export interface Expense {
  id: number;
  target?: Target;
  expense_category?: string;
  label?: string;
  period_start?: string;
  period_end?: string;
  is_open_ended?: boolean;
  booking_date?: string;
  charge_type?: string;
}

export interface ExpenseFilter {
  target?: Target;
  expense_category?: string;
  year?: string;
}

function targetsEqual(t1?: Target, t2?: Target): boolean {
  if (!t1 && !t2) return true;
  if (!t1 || !t2) return false;
  return t1.type === t2.type && t1.id === t2.id;
}

function normalizedFilterText(text?: string): string {
  return (text || "").trim().toLowerCase();
}

export function expenseOverlapsYear(expense: Expense, year?: string): boolean {
  if (!/^\d{4}$/.test(String(year || ""))) {
    return true;
  }

  const yearStart = String(year) + "-01-01";
  const yearEnd = String(year) + "-12-31";
  const startDate = expense.period_start || expense.booking_date;
  const endDate = expense.is_open_ended
    ? ""
    : expense.period_end || (expense.charge_type === "one_time" ? expense.booking_date : "");

  return !!startDate && startDate <= yearEnd && (!endDate || endDate >= yearStart);
}

export function buildFilteredExpenses(expenses: Expense[], filters: ExpenseFilter): Expense[] {
  const safeFilters = filters || {};
  const normalizedCategory = normalizedFilterText(safeFilters.expense_category);

  return (expenses || []).filter(expense => {
    const targetMatch = !safeFilters.target || targetsEqual(expense.target, safeFilters.target);
    
    const categoryMatch =
      !normalizedCategory ||
      normalizedFilterText(expense.expense_category || expense.label || "") === normalizedCategory;
    
    return targetMatch && categoryMatch && expenseOverlapsYear(expense, safeFilters.year);
  });
}

