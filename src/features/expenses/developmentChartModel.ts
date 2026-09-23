import type { components } from '../../api/schema';

type Development = components['schemas']['ExpenseDevelopmentResponse'];
export type DevelopmentChart = Readonly<{
  labels: string[];
  values: Array<number | null>;
  unavailableMonths: number[];
  category: string | null;
}>;

const monthLabels = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'];

/** Maps the server projection to chart coordinates; it never prices or sums expenses. */
export function buildDevelopmentChart(projection: Development, category: string | null = null): DevelopmentChart {
  const months = new Map(projection.months.map(month => [month.month, month]));
  const values = monthLabels.map((_, index) => {
    const month = months.get(index + 1);
    const value = category === null
      ? month?.total_amount
      : month?.categories.find(item => item.expense_category === category)?.amount;
    return value == null ? null : Number(value);
  });
  return {
    labels: monthLabels.map(label => `${label} ${projection.year}`),
    values,
    unavailableMonths: values.flatMap((value, index) => value === null ? [index + 1] : []),
    category,
  };
}
