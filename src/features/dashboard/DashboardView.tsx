import { useDashboard } from './useDashboard';

const countLabels = [
  ['properties', 'Anlagen'], ['buildings', 'Gebäude'], ['units', 'Wohnungen'],
  ['rooms', 'Zimmer'], ['meters', 'Zähler'], ['tenants', 'Mieter'],
  ['leases', 'Mietverträge'], ['expenses', 'Kosten'], ['depreciation_assets', 'AfA-Objekte'],
] as const;

export function DashboardView() {
  const { summary, loading, error, refresh } = useDashboard();
  return <section className="panel panel-wide">
    <h2>Übersicht</h2>
    {loading && !summary && <p>Lade Übersicht…</p>}
    {error && <p role="alert" className="message error">{error} <button onClick={() => void refresh()}>Erneut laden</button></p>}
    {summary && <>
      <div className="cards">{countLabels.map(([key, label]) => <div className="card" key={key}><h3>{label}</h3><p>{summary.summary[key]}</p></div>)}</div>
      <h3>Mandanten und Rollen</h3>
      <table className="data-table"><thead><tr><th>Name</th><th>E-Mail</th><th>Rolle</th><th>Organisation</th></tr></thead><tbody>
        {summary.roles.map((role, index) => <tr key={`${role.email}:${index}`}><td>{role.full_name}</td><td>{role.email}</td><td>{role.role}</td><td>{role.organization_name}</td></tr>)}
      </tbody></table>
      {summary.roles.length === 0 && <p className="hint">Keine Rollen vorhanden.</p>}
    </>}
  </section>;
}
