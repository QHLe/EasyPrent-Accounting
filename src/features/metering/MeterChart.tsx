import { useEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts';
import type { components } from '../../api/schema';
import { buildMeterChartPoints } from './meterChartModel';

type Reading = components['schemas']['ReadingResponse'];

export function MeterChart({ readings, unit }: Readonly<{ readings: readonly Reading[]; unit: string }>) {
  const host = useRef<HTMLDivElement>(null);
  const points = useMemo(() => buildMeterChartPoints(readings), [readings]);

  useEffect(() => {
    if (!host.current || points.length === 0) return;
    const chart = echarts.init(host.current);
    chart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'time' },
      yAxis: { type: 'value', name: unit, scale: true },
      series: [
        { name: 'Zählerstand', type: 'line', data: points.map(point => [point.date, point.value]), smooth: false },
        { name: 'Messpunkt', type: 'scatter', symbolSize: 10, data: points.filter(point => point.source === 'recorded').map(point => [point.date, point.value]) },
      ],
    });
    const resize = () => chart.resize();
    window.addEventListener('resize', resize);
    return () => { window.removeEventListener('resize', resize); chart.dispose(); };
  }, [points, unit]);

  if (points.length === 0) return <p className="hint">Noch keine Messwerte für dieses Diagramm.</p>;
  return <div className="chart-card">
    <div className="echarts-host" ref={host} role="img" aria-label={`Zählerstände in ${unit}`} style={{ minHeight: 280 }} />
    <p className="hint">Punkte zwischen Messwerten sind für die Anzeige interpoliert. Der abrechnungsrelevante Verbrauch kommt vom Server.</p>
  </div>;
}
