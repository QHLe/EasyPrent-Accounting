import { AppShell, type ShellSection } from './app/AppShell';
import { AssetRegistryView } from './features/asset-registry';
import { DashboardView } from './features/dashboard';
import { DepreciationView } from './features/depreciation';
import { ExpensesView } from './features/expenses';
import { MeteringView } from './features/metering';
import { SettingsView } from './features/settings';
import { SettlementsView } from './features/settlements';
import { TenancyView } from './features/tenancy';

const sections: readonly ShellSection[] = [
  { id: 'overview', label: 'Übersicht', content: <DashboardView /> },
  { id: 'asset-registry', label: 'Objektverwaltung', content: <AssetRegistryView /> },
  { id: 'expenses', label: 'Kostenverwaltung', content: <ExpensesView /> },
  { id: 'metering', label: 'Zählerverwaltung', content: <MeteringView /> },
  { id: 'tenancy', label: 'Mieterverwaltung', content: <TenancyView /> },
  { id: 'settlements', label: 'Abrechnungen', content: <SettlementsView /> },
  { id: 'depreciation', label: 'Abschreibungen', content: <DepreciationView /> },
  { id: 'settings', label: 'Einstellungen', content: <SettingsView /> },
];

export function App() {
  return <AppShell sections={sections} initialSectionId="overview" />;
}
