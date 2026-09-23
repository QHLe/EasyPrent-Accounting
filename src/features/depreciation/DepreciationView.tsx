import { useState, type FormEvent } from 'react';
import type { components } from '../../api/schema';
import { useGlobalMessages } from '../../app/AppShell';
import { useDepreciation } from './useDepreciation';

type AssetWrite = components['schemas']['AssetWrite'];

export function DepreciationView() {
  const [year, setYear] = useState(new Date().getFullYear());
  const { assets, properties, schedule, loading, error, refresh, create } = useDepreciation(year);
  const { showMessage } = useGlobalMessages();
  const [adding, setAdding] = useState(false);
  const [propertyId, setPropertyId] = useState('');
  const [assetName, setAssetName] = useState('');
  const [cost, setCost] = useState('');
  const [share, setShare] = useState('100');
  const [life, setLife] = useState('50');
  const [serviceDate, setServiceDate] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const body: AssetWrite = { property_id: Number(propertyId), asset_name: assetName.trim(), acquisition_cost: cost, building_share_percent: share, useful_life_years: Number(life), placed_in_service: serviceDate };
    setSaving(true); setFormError(null);
    try { await create(body); setAdding(false); setAssetName(''); setCost(''); setServiceDate(''); showMessage({ type: 'success', text: 'AfA-Objekt erfasst.' }); }
    catch (cause) { setFormError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setSaving(false); }
  };

  return <section className="panel panel-wide">
    <h2>Abschreibung</h2>
    <div className="inline-form"><label>Jahr<input type="number" min="1900" max="9999" value={year} onChange={event => setYear(Number(event.target.value))} /></label>
      <button className="button" onClick={() => setAdding(true)}>AfA-Objekt erfassen</button></div>
    {loading && !schedule && <p>Lade Abschreibungen…</p>}
    {error && <p role="alert" className="message error">{error} <button onClick={() => void refresh()}>Erneut laden</button></p>}
    {adding && <form className="panel" onSubmit={event => void submit(event)}><div className="form-grid">
      <label>Anlage<select required value={propertyId} onChange={event => setPropertyId(event.target.value)}><option value="">Anlage wählen</option>{properties.filter(item => !item.is_archived).map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
      <label>Objektname<input required value={assetName} onChange={event => setAssetName(event.target.value)} /></label>
      <label>Anschaffungskosten (EUR)<input required type="number" min="0" step="any" value={cost} onChange={event => setCost(event.target.value)} /></label>
      <label>Gebäudeanteil (%)<input required type="number" min="0" max="100" step="any" value={share} onChange={event => setShare(event.target.value)} /></label>
      <label>Nutzungsdauer (Jahre)<input required type="number" min="1" step="1" value={life} onChange={event => setLife(event.target.value)} /></label>
      <label>Inbetriebnahme<input required type="date" value={serviceDate} onChange={event => setServiceDate(event.target.value)} /></label>
    </div>{formError && <p role="alert" className="message error">{formError}</p>}
      <button className="button" type="submit" disabled={saving}>Speichern</button> <button className="button button-outline" type="button" onClick={() => setAdding(false)}>Abbrechen</button>
    </form>}
    <h3>AfA-Objekte</h3><table className="data-table"><thead><tr><th>Anlage</th><th>Objekt</th><th>Anschaffungskosten</th><th>Gebäudeanteil</th><th>Nutzungsdauer</th><th>Inbetriebnahme</th></tr></thead><tbody>
      {assets.map(item => <tr key={item.id}><td>{properties.find(property => property.id === item.property_id)?.name ?? item.property_id}</td><td>{item.asset_name}</td><td>{item.acquisition_cost} €</td><td>{item.building_share_percent} %</td><td>{item.useful_life_years} Jahre</td><td>{item.placed_in_service}</td></tr>)}
    </tbody></table>
    <h3>Jahresplan {year}</h3><table className="data-table"><thead><tr><th>Objekt</th><th>AfA-Basis</th><th>Monate</th><th>Jahreswert</th></tr></thead><tbody>
      {schedule?.rows.map((row, index) => <tr key={`${row.asset_name}:${index}`}><td>{row.asset_name}</td><td>{row.depreciable_basis} €</td><td>{row.months_in_year}</td><td>{row.yearly_depreciation} €</td></tr>)}
    </tbody></table>{schedule && <p><strong>Gesamt-AfA: {schedule.total} €</strong></p>}
  </section>;
}
