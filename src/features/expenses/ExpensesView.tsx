import { useState } from 'react';
import type { components } from '../../api/schema';
import { useGlobalMessages } from '../../app/AppShell';
import { useDeleteActions } from '../../hooks/useDeleteActions';
import { LinkedDocumentsPanel } from '../linked-documents';
import { expenseOverlapsYear } from '../../models/expenses';
import { ExpenseForm } from './ExpenseForm';
import { ExpenseDevelopmentChart } from './ExpenseDevelopmentChart';
import { useExpenses } from './useExpenses';

type Expense = components['schemas']['ExpenseResponse'];

export function ExpensesView() {
  const { expenses, assets, metering, loading, error, refresh, create, update, archive, restore, remove } = useExpenses();
  const { showMessage } = useGlobalMessages();
  const showDeleteActions = useDeleteActions();
  const [editing, setEditing] = useState<Expense | 'new' | null>(null);
  const [category, setCategory] = useState('');
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [showArchived, setShowArchived] = useState(false);
  const [documentExpenseId, setDocumentExpenseId] = useState<number | null>(null);

  if (loading && !expenses) return <p>Lade Kosten…</p>;
  if (error && !expenses) return <div className="message error" role="alert">{error} <button onClick={() => void refresh()}>Erneut laden</button></div>;
  if (!expenses || !assets || !metering) return null;

  const visible = expenses.expenses.filter(item =>
    (showArchived || !item.is_archived) &&
    (!category || item.expense_category === category) &&
    expenseOverlapsYear({ id: item.id, period_start: item.period_start, period_end: item.period_end ?? undefined, is_open_ended: item.is_open_ended, booking_date: item.booking_date ?? undefined, charge_type: item.charge_type }, year),
  );
  const act = async (operation: () => Promise<void>, success: string) => {
    try { await operation(); showMessage({ type: 'success', text: success }); }
    catch (cause) { showMessage({ type: 'error', text: cause instanceof Error ? cause.message : String(cause) }); }
  };

  return <section className="panel panel-wide">
    <h2>Kostenverwaltung</h2>
    <div className="inline-form">
      <label>Kostenart<select value={category} onChange={event => setCategory(event.target.value)}>
        <option value="">Alle</option>{Array.from(new Set(expenses.expense_categories.map(item => item.expense_category))).map(name => <option key={name} value={name}>{name}</option>)}
      </select></label>
      <label>Jahr<input type="number" min="1900" max="9999" value={year} onChange={event => setYear(event.target.value)} /></label>
      <label><input type="checkbox" checked={showArchived} onChange={event => setShowArchived(event.target.checked)} /> Archivierte anzeigen</label>
      <button className="button" onClick={() => setEditing('new')}>Kosten erfassen</button>
    </div>
    {editing === 'new' && <ExpenseForm assets={assets} meters={metering.meters} onCancel={() => setEditing(null)} onSave={async body => {
      await create(body); setEditing(null); showMessage({ type: 'success', text: 'Kosten erfasst.' });
    }} />}
    <ExpenseDevelopmentChart year={Number(year) || new Date().getFullYear()} category={category || null} revision={expenses} />
    <div className="settlement-table-scroll"><table className="data-table">
      <thead><tr><th>Kostenart</th><th>Ziel</th><th>Wert</th><th>Zeitraum</th><th>Abrechnung</th><th>Aktionen</th></tr></thead>
      <tbody>{visible.map(item => <tr key={item.id}>
        <td><strong>{item.label}</strong><br />{item.expense_category}{item.is_archived && ' · Archiviert'}</td>
        <td>{item.object_type} #{item.object_id}</td>
        <td>{item.amount} €{item.total_amount && <><br />Gesamt: {item.total_amount} €</>}</td>
        <td>{item.period_start}{item.is_open_ended ? ' – offen' : item.period_end ? ` – ${item.period_end}` : ''}</td>
        <td>{item.charge_type} · {item.allocation_method}</td>
        <td><button className="button button-small button-outline" onClick={() => setEditing(item)}>Bearbeiten</button>{' '}
          <button className="button button-small button-outline" onClick={() => setDocumentExpenseId(documentExpenseId === item.id ? null : item.id)}>Dokumente</button>{' '}
          <button className="button button-small button-outline" onClick={() => void act(() => item.is_archived ? restore(item.id) : archive(item.id), item.is_archived ? 'Kosten wiederhergestellt.' : 'Kosten archiviert.')}>{item.is_archived ? 'Wiederherstellen' : 'Archivieren'}</button>{' '}
          {showDeleteActions && item.is_archived && <button className="button button-small button-outline" onClick={() => { if (window.confirm('Kosten endgültig löschen?')) void act(() => remove(item.id), 'Kosten gelöscht.'); }}>Löschen</button>}
        </td>
      </tr>)}</tbody>
    </table></div>
    {visible.length === 0 && <p className="hint">Keine Kosten gefunden.</p>}
    {editing && editing !== 'new' && <ExpenseForm key={editing.id} initial={editing} assets={assets} meters={metering.meters} onCancel={() => setEditing(null)} onSave={async body => {
      await update(editing.id, body); setEditing(null); showMessage({ type: 'success', text: 'Kosten gespeichert.' });
    }} />}
    {documentExpenseId !== null && <LinkedDocumentsPanel ownerType="expenses" ownerId={documentExpenseId} />}
  </section>;
}
