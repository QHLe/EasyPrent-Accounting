import { ReactNode } from 'react';

export interface Column<T> {
  key: keyof T;
  header: string;
  render?: (row: T) => ReactNode;
}

export interface TableProps<T> {
  data: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
}

export function Table<T>({ data, columns, rowKey }: TableProps<T>) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          {columns.map(col => (
            <th key={String(col.key)}>{col.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map(row => (
          <tr key={rowKey(row)}>
            {columns.map(col => (
              <td key={String(col.key)}>
                {col.render ? col.render(row) : String(row[col.key] ?? '')}
              </td>
            ))}
          </tr>
        ))}
        {data.length === 0 && (
          <tr>
            <td colSpan={columns.length} className="empty-state">
              No data available.
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}
