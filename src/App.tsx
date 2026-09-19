import { AppShell, type ShellSection } from './app/AppShell';

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
    content: <PendingSection title="Objektverwaltung" />,
  },
  {
    id: 'expenses',
    label: 'Kostenverwaltung',
    content: <PendingSection title="Kostenverwaltung" />,
  },
  {
    id: 'tenancy',
    label: 'Mieterverwaltung',
    content: <PendingSection title="Mieterverwaltung" />,
  },
  {
    id: 'settlements',
    label: 'Abrechnungen',
    content: <PendingSection title="Abrechnungen" />,
  },
  {
    id: 'settings',
    label: 'Einstellungen',
    content: <PendingSection title="Einstellungen" />,
  },
];

export function App() {
  return <AppShell sections={sections} initialSectionId="overview" />;
}
