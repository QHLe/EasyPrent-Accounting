import { useEffect, useMemo, useRef, useState } from 'react';
import * as echarts from 'echarts';
import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';
import { buildDevelopmentChart } from './developmentChartModel';

type Development = components['schemas']['ExpenseDevelopmentResponse'];

export function ExpenseDevelopmentChart({ year, category, revision }: Readonly<{
  year: number;
  category: string | null;
  revision: unknown;
}>) {
  const [data, setData] = useState<Development | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'bar' | 'line'>('bar');
  const host = useRef<HTMLDivElement>(null);
  const chart = useMemo(() => data ? buildDevelopmentChart(data, category) : null, [data, category]);
  const annualAmount = data ? (category === null ? data.total_amount : data.categories.find(item => item.expense_category === category)?.amount) : null;

  useEffect(() => {
    if (!Number.isInteger(year) || year < 1900 || year > 9998) return;
    let active = true;
    setData(null);
    void apiClient.GET('/api/v1/expenses/development', { params: { query: { year } } })
      .then(response => { if (active && response.data) { setData(response.data); setError(null); } })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : String(cause)); });
    return () => { active = false; };
  }, [year, revision]);

  useEffect(() => {
    if (!chart || !host.current) return;
    const instance = echarts.init(host.current);
    instance.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: chart.labels },
      yAxis: { type: 'value', name: 'EUR', min: 0 },
      series: [{ name: category ?? 'Kosten', type: mode, data: chart.values, smooth: false, barMaxWidth: 28 }],
    });
    const resize = () => instance.resize();
    window.addEventListener('resize', resize);
    return () => { window.removeEventListener('resize', resize); instance.dispose(); };
  }, [chart, mode, category]);

  return <section className="panel"><h3>Kostenentwicklung {year}</h3>
    <label>Diagramm<select value={mode} onChange={event => setMode(event.target.value as 'bar' | 'line')}><option value="bar">Balken</option><option value="line">Linie</option></select></label>
    {error && <p role="alert" className="message error">{error}</p>}
    {chart && <>
      <div className="echarts-host" ref={host} role="img" aria-label={`Kostenentwicklung ${year}`} style={{ minHeight: 280 }} />
      {chart.unavailableMonths.length > 0 && <p className="hint">Für {chart.unavailableMonths.length} Monat(e) liegt kein berechenbarer Betrag vor.</p>}
      {data && <p>Jahresbetrag: {annualAmount === null || annualAmount === undefined ? 'Nicht berechenbar' : `${annualAmount} €`}</p>}
    </>}
  </section>;
}
