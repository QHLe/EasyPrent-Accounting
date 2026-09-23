import { useState, type FormEvent } from 'react';
import type { components } from '../../api/schema';
import { useGlobalMessages } from '../../app/AppShell';
import { useSettlements } from './useSettlements';

type Period = components['schemas']['SettlementPeriodWrite'];
type Payment = components['schemas']['SettlementPaymentResponse'];
const currentYear = new Date().getFullYear();

function documentUrl(kind: 'pdf' | 'ods', period: Period, leaseId: number): string {
  const query = new URLSearchParams({ lease_id: String(leaseId), period_start: period.period_start, period_end: period.period_end });
  if (period.property_id) query.set('property_id', String(period.property_id));
  if (period.unit_id) query.set('unit_id', String(period.unit_id));
  return `/api/v1/settlements/document.${kind}?${query}`;
}

function Payments({ title, payments, actionLabel, onAction }: Readonly<{
  title: string; payments: Payment[]; actionLabel?: string; onAction?: (payment: Payment) => void;
}>) {
  return <section><h4>{title} ({payments.length})</h4>
    {payments.length > 0 && <table className="data-table"><thead><tr><th>Mieter</th><th>Datum</th><th>Betrag</th><th>Beschreibung</th><th>Aktion</th></tr></thead><tbody>
      {payments.map(payment => <tr key={payment.split_guid}><td>{payment.tenant_name}</td><td>{payment.booking_date}</td><td>{payment.amount} €</td><td>{payment.description}{payment.warning && <p className="message error">{payment.warning}</p>}</td><td>{onAction && <button className="button button-small button-outline" onClick={() => onAction(payment)}>{actionLabel}</button>}</td></tr>)}
    </tbody></table>}
  </section>;
}

export function SettlementsView() {
  const { assets, settlement, overview, loading, error, clear, calculate, refresh, findRun, createRun, refreshPayments, considerAll, consider, unassign } = useSettlements();
  const { showMessage } = useGlobalMessages();
  const [target, setTarget] = useState('');
  const [year, setYear] = useState(currentYear);
  const [start, setStart] = useState(`${currentYear}-01-01`);
  const [end, setEnd] = useState(`${currentYear}-12-31`);
  const [actionError, setActionError] = useState<string | null>(null);

  const targetValues = () => {
    const [kind, id] = target.split(':');
    return kind === 'unit' ? { unit_id: Number(id) } : kind === 'property' ? { property_id: Number(id) } : {};
  };
  const period: Period = { ...targetValues(), period_start: start, period_end: end };
  const run = { ...targetValues(), year };
  const act = async (operation: () => Promise<unknown>, success: string) => {
    setActionError(null);
    try { await operation(); showMessage({ type: 'success', text: success }); }
    catch (cause) { setActionError(cause instanceof Error ? cause.message : String(cause)); }
  };
  const submit = (event: FormEvent) => { event.preventDefault(); void calculate(period); };
  const runId = overview?.run.id;

  return <section className="panel panel-wide">
    <h2>Nebenkostenabrechnung</h2>
    {error && <p role="alert" className="message error">{error}</p>}
    {actionError && <p role="alert" className="message error">{actionError}</p>}
    <form className="inline-form" onSubmit={submit}>
      <label>Objekt<select required value={target} onChange={event => { setTarget(event.target.value); clear(); }}><option value="">Objekt wählen</option>
        {assets?.properties.filter(item => !item.is_archived).map(item => <option key={`property:${item.id}`} value={`property:${item.id}`}>Anlage: {item.name}</option>)}
        {assets?.units.filter(item => !item.is_archived && !item.building_id).map(item => <option key={`unit:${item.id}`} value={`unit:${item.id}`}>Wohnung: {item.label}</option>)}
      </select></label>
      <label>Von<input required type="date" value={start} onChange={event => { setStart(event.target.value); clear(); }} /></label>
      <label>Bis<input required type="date" value={end} min={start} onChange={event => { setEnd(event.target.value); clear(); }} /></label>
      <button className="button" disabled={loading || !target} type="submit">Berechnen</button>
      <button className="button button-outline" disabled={loading || !target} type="button" onClick={() => void act(() => refresh(period), 'Zahlungen eingelesen und Abrechnung aktualisiert.')}>Zahlungen einlesen</button>
    </form>
    <div className="inline-form"><label>Abrechnungsjahr<input type="number" min="1900" max="9999" value={year} onChange={event => { const value = Number(event.target.value); setYear(value); setStart(`${value}-01-01`); setEnd(`${value}-12-31`); clear(); }} /></label>
      <button className="button button-outline" disabled={loading || !target} onClick={() => { setActionError(null); void findRun(run).then(found => { if (found) showMessage({ type: 'success', text: 'Abrechnungslauf geladen.' }); else setActionError('Für dieses Jahr wurde noch kein Abrechnungslauf erstellt.'); }).catch(cause => setActionError(cause instanceof Error ? cause.message : String(cause))); }}>Lauf öffnen</button>
      <button className="button button-outline" disabled={loading || !target} onClick={() => void act(() => createRun(run), 'Abrechnungslauf erstellt.')}>Lauf erstellen</button>
    </div>
    {loading && <p role="status">Abrechnung wird geladen…</p>}
    {settlement && <>
      <h3>Ergebnis {settlement.period_start} – {settlement.period_end}</h3>
      <div className="settlement-table-scroll"><table className="data-table"><thead><tr><th>Mieter</th><th>Wohnung</th><th>Zeitraum</th><th>Kostenanteil</th><th>Vorauszahlungen</th><th>Saldo</th><th>Dokumente</th></tr></thead><tbody>
        {settlement.results.map(item => <tr key={item.lease_id}><td>{item.tenant_name}</td><td>{item.unit_label}</td><td>{item.billing_period_start} – {item.billing_period_end}</td><td>{item.allocated_costs} €</td><td>{item.advances_paid} €</td><td>{item.balance} €</td><td>
          <a href={documentUrl('pdf', settlement, item.lease_id)}>PDF</a>{' · '}
          <a href={runId ? `/api/v1/settlement-runs/${encodeURIComponent(runId)}/leases/${item.lease_id}/document.ods` : documentUrl('ods', settlement, item.lease_id)}>ODS</a>
        </td></tr>)}
      </tbody></table></div>
      <p><strong>Gesamt:</strong> Kosten {settlement.totals.costs} € · Vorauszahlungen {settlement.totals.advances} € · Saldo {settlement.totals.balance} €</p>
      {settlement.results.map(item => <details key={`lines:${item.lease_id}`}><summary>{item.tenant_name}: {item.line_items.length} Kostenpositionen</summary>
        <table className="data-table"><thead><tr><th>Kosten</th><th>Zeitraumswert</th><th>Anteil</th><th>Schlüssel</th></tr></thead><tbody>{item.line_items.map((line, index) => <tr key={`${line.source_id}:${index}`}><td>{line.label}</td><td>{line.period_amount} €</td><td>{line.share} €</td><td>{line.allocation_method}</td></tr>)}</tbody></table>
      </details>)}
    </>}
    {overview && <section className="panel"><h3>Abrechnungslauf {overview.run.year}: {overview.run.target_label}</h3>
      <p>Status: {overview.run.status}</p>
      <div className="inline-form"><button className="button button-outline" onClick={() => void act(() => refreshPayments(overview.run.id), 'Zahlungen aktualisiert.')}>Zahlungen aktualisieren</button>{' '}
        <button className="button button-outline" onClick={() => void act(() => considerAll(overview.run.id), 'Alle offenen Zahlungen berücksichtigt.')}>Alle offenen berücksichtigen</button></div>
      {overview.missing_account_leases.length > 0 && <p className="message error">GnuCash-Konto fehlt für: {overview.missing_account_leases.map(item => item.tenant_name).join(', ')}</p>}
      <Payments title="Offene Zahlungen" payments={overview.open_payments} actionLabel="Berücksichtigen" onAction={payment => void act(() => consider(overview.run.id, payment.split_guid), 'Zahlung berücksichtigt.')} />
      <Payments title="Berücksichtigte Zahlungen" payments={overview.considered_payments} actionLabel="Zuordnung lösen" onAction={payment => void act(() => unassign(overview.run.id, payment.split_guid), 'Zuordnung entfernt.')} />
      <Payments title="Zahlungen außerhalb des Zeitraums" payments={overview.outside_payments} />
    </section>}
  </section>;
}
