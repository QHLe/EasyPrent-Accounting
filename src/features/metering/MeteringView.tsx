import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import type { components } from '../../api/schema';
import { apiClient } from '../../api/client';
import { useGlobalMessages } from '../../app/AppShell';
import { useDeleteActions } from '../../hooks/useDeleteActions';
import { MeterChart } from './MeterChart';
import { useMetering } from './useMetering';

type Meter = components['schemas']['MeterResponse'];
type MeterWrite = components['schemas']['MeterWrite'];
type Assets = components['schemas']['AssetListResponse'];
type Consumption = components['schemas']['ConsumptionResponse'];

function MeterForm({ assets, initial, onSave, onCancel }: Readonly<{
  assets: Assets; initial?: Meter; onSave: (body: MeterWrite) => Promise<void>; onCancel: () => void;
}>) {
  const [target, setTarget] = useState(initial ? `${initial.object_type}:${initial.object_id}` : '');
  const [label, setLabel] = useState(initial?.label ?? '');
  const [meterType, setMeterType] = useState(initial?.meter_type ?? '');
  const [unit, setUnit] = useState(initial?.unit ?? 'kWh');
  const [serial, setSerial] = useState(initial?.serial_number ?? '');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const options = [
    ...assets.properties.filter(item => !item.is_archived).map(item => ({ type: 'property' as const, id: item.id, label: `Anlage: ${item.name}` })),
    ...assets.buildings.filter(item => !item.is_archived).map(item => ({ type: 'building' as const, id: item.id, label: `Gebäude: ${item.name}` })),
    ...assets.units.filter(item => !item.is_archived).map(item => ({ type: 'unit' as const, id: item.id, label: `Wohnung: ${item.label}` })),
    ...assets.rooms.filter(item => !item.is_archived).map(item => ({ type: 'room' as const, id: item.id, label: `Zimmer: ${item.label}` })),
  ];
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const [type, id] = target.split(':');
    if (!id) return;
    setSaving(true); setError(null);
    try { await onSave({ object_type: type as MeterWrite['object_type'], object_id: Number(id), label: label.trim(), meter_type: meterType.trim() || null, unit: unit.trim(), serial_number: serial.trim() || null }); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setSaving(false); }
  };
  return <form className="panel" onSubmit={event => void submit(event)}>
    <div className="form-grid">
      <label>Zielobjekt<select required value={target} onChange={event => setTarget(event.target.value)}><option value="">Objekt wählen</option>{options.map(item => <option key={`${item.type}:${item.id}`} value={`${item.type}:${item.id}`}>{item.label}</option>)}</select></label>
      <label>Bezeichnung<input required value={label} onChange={event => setLabel(event.target.value)} /></label>
      <label>Zählertyp<input value={meterType} onChange={event => setMeterType(event.target.value)} /></label>
      <label>Einheit<input required value={unit} onChange={event => setUnit(event.target.value)} /></label>
      <label>Seriennummer<input value={serial} onChange={event => setSerial(event.target.value)} /></label>
    </div>
    {error && <p role="alert" className="message error">{error}</p>}
    <button className="button" disabled={saving} type="submit">Speichern</button> <button className="button button-outline" type="button" onClick={onCancel}>Abbrechen</button>
  </form>;
}

export function MeteringView() {
  const { metering, loading, error, refresh, createMeter, updateMeter, archiveMeter, restoreMeter, deleteMeter, createReading, deleteReading, consumption } = useMetering();
  const { showMessage } = useGlobalMessages();
  const showDeleteActions = useDeleteActions();
  const [assets, setAssets] = useState<Assets | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [editing, setEditing] = useState<Meter | 'new' | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [readingDate, setReadingDate] = useState('');
  const [readingValue, setReadingValue] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [result, setResult] = useState<Consumption | null>(null);
  const consumptionRequest = useRef(0);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => { void apiClient.GET('/api/v1/assets').then(response => { if (response.data) setAssets(response.data); }).catch(cause => setLocalError(String(cause))); }, []);
  const invalidateConsumption = () => {
    consumptionRequest.current += 1;
    setResult(null);
  };
  const act = async (operation: () => Promise<void>, success: string) => {
    setLocalError(null);
    invalidateConsumption();
    try { await operation(); showMessage({ type: 'success', text: success }); }
    catch (cause) { setLocalError(cause instanceof Error ? cause.message : String(cause)); }
  };
  const meter = metering?.meters.find(item => item.id === selected);
  const readings = useMemo(() => metering?.meter_readings.filter(item => item.meter_id === selected).sort((a, b) => b.reading_date.localeCompare(a.reading_date)) ?? [], [metering, selected]);

  return <section className="panel panel-wide">
    <h2>Zähler und Messwerte</h2>
    {error && <p role="alert" className="message error">{error} <button onClick={() => void refresh()}>Erneut laden</button></p>}
    {localError && <p role="alert" className="message error">{localError}</p>}
    {loading && !metering && <p>Lade Zähler…</p>}
    <div className="inline-form"><button className="button" onClick={() => setEditing('new')}>Zähler erfassen</button>
      <label><input type="checkbox" checked={showArchived} onChange={event => setShowArchived(event.target.checked)} /> Archivierte anzeigen</label>
    </div>
    {editing === 'new' && assets && <MeterForm assets={assets} onCancel={() => setEditing(null)} onSave={async body => { await createMeter(body); invalidateConsumption(); setEditing(null); showMessage({ type: 'success', text: 'Zähler gespeichert.' }); }} />}
    <div className="settlement-table-scroll"><table className="data-table"><thead><tr><th>Zähler</th><th>Objekt</th><th>Letzter Stand</th><th>Aktionen</th></tr></thead><tbody>
      {metering?.meters.filter(item => showArchived || !item.is_archived).map(item => <tr key={item.id}>
        <td><button className="button button-small button-outline" onClick={() => { setSelected(item.id); invalidateConsumption(); }}>{item.label}</button> {item.is_archived && 'Archiviert'}</td>
        <td>{item.object_name ?? `${item.object_type} #${item.object_id}`}</td>
        <td>{item.latest_reading_value ?? '–'} {item.unit} · {item.latest_reading_date ?? '–'}</td>
        <td><button className="button button-small button-outline" onClick={() => setEditing(item)}>Bearbeiten</button>{' '}
          <button className="button button-small button-outline" onClick={() => void act(() => item.is_archived ? restoreMeter(item.id) : archiveMeter(item.id), item.is_archived ? 'Zähler wiederhergestellt.' : 'Zähler archiviert.')}>{item.is_archived ? 'Wiederherstellen' : 'Archivieren'}</button>{' '}
          {showDeleteActions && item.is_archived && <button className="button button-small button-outline" onClick={() => { if (window.confirm('Zähler löschen?')) void act(() => deleteMeter(item.id), 'Zähler gelöscht.'); }}>Löschen</button>}
        </td>
      </tr>)}</tbody></table></div>
    {editing && editing !== 'new' && assets && <MeterForm key={editing.id} assets={assets} initial={editing} onCancel={() => setEditing(null)} onSave={async body => { await updateMeter(editing.id, body); invalidateConsumption(); setEditing(null); showMessage({ type: 'success', text: 'Zähler gespeichert.' }); }} />}
    {meter && <section className="panel"><h3>{meter.label}</h3>
      {!meter.is_archived && <form className="inline-form" onSubmit={event => { event.preventDefault(); void act(async () => { await createReading({ meter_id: meter.id, reading_date: readingDate, reading_value: readingValue }); setReadingDate(''); setReadingValue(''); }, 'Messwert gespeichert.'); }}>
        <label>Messdatum<input required type="date" value={readingDate} onChange={event => setReadingDate(event.target.value)} /></label>
        <label>Zählerstand ({meter.unit})<input required type="number" min="0" step="any" value={readingValue} onChange={event => setReadingValue(event.target.value)} /></label>
        <button className="button" type="submit">Messwert erfassen</button>
      </form>}
      <MeterChart readings={readings} unit={meter.unit} />
      <form className="inline-form" onSubmit={event => { event.preventDefault(); setLocalError(null); invalidateConsumption(); const request = consumptionRequest.current; void consumption(meter.id, start, end).then(value => { if (request === consumptionRequest.current) setResult(value); }).catch(cause => { if (request === consumptionRequest.current) setLocalError(String(cause)); }); }}>
        <label>Verbrauch von<input required type="date" value={start} onChange={event => { setStart(event.target.value); invalidateConsumption(); }} /></label>
        <label>Bis<input required type="date" value={end} onChange={event => { setEnd(event.target.value); invalidateConsumption(); }} /></label>
        <button className="button" type="submit">Verbrauch anzeigen</button>
      </form>
      {result && <p role="status">Verbrauch: {result.quantity ?? 'Nicht berechenbar'} {meter.unit}</p>}
      <table className="data-table"><thead><tr><th>Datum</th><th>Stand</th><th>Aktion</th></tr></thead><tbody>{readings.map(item => <tr key={item.id}><td>{item.reading_date}</td><td>{item.reading_value} {meter.unit}</td><td>{showDeleteActions && <button className="button button-small button-outline" onClick={() => { if (window.confirm('Messwert löschen?')) void act(() => deleteReading(item.id), 'Messwert gelöscht.'); }}>Löschen</button>}</td></tr>)}</tbody></table>
    </section>}
  </section>;
}
