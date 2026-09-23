import { useState, type FormEvent } from 'react';
import type { components } from '../../api/schema';

type Expense = components['schemas']['ExpenseResponse'];
type ExpenseWrite = components['schemas']['ExpenseWrite'];
type Assets = components['schemas']['AssetListResponse'];
type Meter = components['schemas']['MeterResponse'];
type TargetType = ExpenseWrite['object_type'];

const chargeTypes: ReadonlyArray<[ExpenseWrite['charge_type'], string]> = [
  ['one_time', 'Einmalig'], ['monthly', 'Monatlich'], ['quarterly', 'Vierteljährlich'],
  ['yearly', 'Jährlich'], ['consumption', 'Verbrauch'],
];

function targetOptions(assets: Assets) {
  return [
    ...assets.properties.filter(item => !item.is_archived).map(item => ({ type: 'property' as const, id: item.id, label: `Anlage: ${item.name}` })),
    ...assets.buildings.filter(item => !item.is_archived).map(item => ({ type: 'building' as const, id: item.id, label: `Gebäude: ${item.name}` })),
    ...assets.units.filter(item => !item.is_archived).map(item => ({ type: 'unit' as const, id: item.id, label: `Wohnung: ${item.label}` })),
    ...assets.rooms.filter(item => !item.is_archived).map(item => ({ type: 'room' as const, id: item.id, label: `Zimmer: ${item.label}` })),
  ];
}

export function ExpenseForm({ initial, assets, meters, onSave, onCancel }: Readonly<{
  initial?: Expense;
  assets: Assets;
  meters: Meter[];
  onSave: (value: ExpenseWrite) => Promise<void>;
  onCancel: () => void;
}>) {
  const [target, setTarget] = useState(initial ? `${initial.object_type}:${initial.object_id}` : '');
  const [category, setCategory] = useState(initial?.expense_category ?? '');
  const [label, setLabel] = useState(initial?.label ?? '');
  const [beneficiary, setBeneficiary] = useState(initial?.beneficiary_name ?? '');
  const [amount, setAmount] = useState(initial?.amount ?? '');
  const [allocation, setAllocation] = useState(initial?.allocation_method ?? 'area');
  const [chargeType, setChargeType] = useState<ExpenseWrite['charge_type']>(initial?.charge_type ?? 'one_time');
  const [bookingDate, setBookingDate] = useState(initial?.booking_date ?? '');
  const [periodStart, setPeriodStart] = useState(initial?.period_start ?? '');
  const [periodEnd, setPeriodEnd] = useState(initial?.is_open_ended ? '' : initial?.period_end ?? '');
  const [meterId, setMeterId] = useState(initial?.meter_id ? String(initial.meter_id) : '');
  const [consumptionValue, setConsumptionValue] = useState(initial?.consumption_value ?? '');
  const [consumptionUnit, setConsumptionUnit] = useState(initial?.consumption_unit ?? '');
  const [conversionFactor, setConversionFactor] = useState(initial?.conversion_factor ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedMeter = meters.find(item => String(item.id) === meterId);
  const eligibleMeters = meters.filter(item => !item.is_archived && `${item.object_type}:${item.object_id}` === target);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const [objectType, objectId] = target.split(':');
    if (!objectId) return;
    const body: ExpenseWrite = {
      object_type: objectType as TargetType,
      object_id: Number(objectId), expense_category: category.trim(), label: label.trim(),
      beneficiary_name: beneficiary.trim(), amount, allocation_method: allocation,
      charge_type: chargeType,
      booking_date: chargeType === 'one_time' ? bookingDate : null,
      period_start: periodStart || null, period_end: periodEnd || null,
      meter_id: chargeType === 'consumption' && meterId ? Number(meterId) : null,
      consumption_value: chargeType === 'consumption' && !meterId ? consumptionValue : null,
      consumption_unit: chargeType === 'consumption' ? consumptionUnit || null : null,
      conversion_factor: chargeType === 'consumption' && meterId && selectedMeter?.unit !== consumptionUnit ? conversionFactor || null : null,
    };
    setSaving(true);
    setError(null);
    try { await onSave(body); } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setSaving(false); }
  };

  return <form onSubmit={event => void submit(event)} className="panel">
    <div className="form-grid">
      <label>Zielobjekt<select required value={target} onChange={event => { setTarget(event.target.value); setMeterId(''); setConsumptionUnit(''); }}>
        <option value="">Objekt wählen</option>
        {targetOptions(assets).map(item => <option key={`${item.type}:${item.id}`} value={`${item.type}:${item.id}`}>{item.label}</option>)}
      </select></label>
      <label>Kostenart<input required value={category} onChange={event => setCategory(event.target.value)} /></label>
      <label>Bezeichnung<input value={label} onChange={event => setLabel(event.target.value)} /></label>
      <label>Empfänger<input value={beneficiary} onChange={event => setBeneficiary(event.target.value)} /></label>
      <label>{chargeType === 'consumption' ? 'Preis je Einheit (EUR)' : 'Wert (EUR)'}<input required type="number" min="0" step="any" value={amount} onChange={event => setAmount(event.target.value)} /></label>
      <label>Verteilerschlüssel<select value={allocation} onChange={event => setAllocation(event.target.value)}>
        <option value="area">Nach Fläche</option><option value="unit_count">Nach Einheiten</option><option value="occupants">Nach Personen</option>
      </select></label>
      <label>Abrechnungsart<select value={chargeType} onChange={event => setChargeType(event.target.value as ExpenseWrite['charge_type'])}>
        {chargeTypes.map(([value, text]) => <option value={value} key={value}>{text}</option>)}
      </select></label>
      {chargeType === 'one_time' && <label>Buchungsdatum<input required type="date" value={bookingDate} onChange={event => setBookingDate(event.target.value)} /></label>}
      <label>Von<input required={chargeType !== 'one_time'} type="date" value={periodStart} onChange={event => setPeriodStart(event.target.value)} /></label>
      <label>Bis<input required={chargeType === 'consumption' && !meterId} type="date" value={periodEnd} onChange={event => setPeriodEnd(event.target.value)} /></label>
      {chargeType === 'consumption' && <>
        <label>Zähler<select value={meterId} onChange={event => { setMeterId(event.target.value); setConsumptionUnit(meters.find(item => String(item.id) === event.target.value)?.unit ?? ''); }}>
          <option value="">Manueller Verbrauch</option>{eligibleMeters.map(item => <option key={item.id} value={item.id}>{item.label} ({item.unit})</option>)}
        </select></label>
        {!meterId && <label>Verbrauch<input required type="number" min="0" step="any" value={consumptionValue} onChange={event => setConsumptionValue(event.target.value)} /></label>}
        <label>Verbrauchseinheit<input required={!meterId} value={consumptionUnit} onChange={event => setConsumptionUnit(event.target.value)} /></label>
        {selectedMeter && consumptionUnit && consumptionUnit !== selectedMeter.unit && <label>Umrechnungsfaktor<input required type="number" min="0" step="any" value={conversionFactor} onChange={event => setConversionFactor(event.target.value)} /></label>}
      </>}
    </div>
    {error && <p className="message error" role="alert">{error}</p>}
    <div className="actions"><button className="button" type="submit" disabled={saving}>{saving ? 'Speichern…' : 'Speichern'}</button> <button className="button button-outline" type="button" onClick={onCancel}>Abbrechen</button></div>
  </form>;
}
