import { AppShell, type ShellSection } from './app/AppShell';
import { SettingsView } from './features/settings';
import { AssetRegistryView } from './features/asset-registry';
import { TenancyView } from './features/tenancy';

function PendingSection({ title }: Readonly<{ title: string }>) {
  return (
    <section className="panel panel-wide">
      <h2>{title}</h2>
      <p className="hint">Dieser Bereich wird im neuen Frontend schrittweise bereitgestellt.</p>
    </section>
  );
}

const sections: readonly ShellSection[] = [
  {
    id: 'overview',
    label: 'Übersicht',
    content: <PendingSection title="Übersicht" />,
  },
  {
    id: 'asset-registry',
    label: 'Objektverwaltung',
    content: <AssetRegistryView />,
  },
  {
    id: 'expenses',
    label: 'Kostenverwaltung',
    content: <PendingSection title="Kostenverwaltung" />,
  },
  {
    id: 'tenancy',
    label: 'Mieterverwaltung',
    content: <TenancyView />,
  },
  {
    id: 'settlements',
    label: 'Abrechnungen',
    content: <PendingSection title="Abrechnungen" />,
  },
  {
    id: 'settings',
    label: 'Einstellungen',
    content: <SettingsView />,
  },
];

export function App() {
  return <AppShell sections={sections} initialSectionId="overview" />;
}
