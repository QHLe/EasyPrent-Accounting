import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  AppShell,
  type AppShellProps,
  useGlobalMessages,
} from './AppShell';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const sections: AppShellProps['sections'] = [
  {
    id: 'dashboard',
    label: 'Übersicht',
    content: <h2>Dashboard-Inhalt</h2>,
  },
  {
    id: 'settings',
    label: 'Einstellungen',
    content: <h2>Einstellungen-Inhalt</h2>,
  },
];

function click(element: Element) {
  act(() => {
    element.dispatchEvent(
      new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }),
    );
  });
}

async function traverseHistory(direction: () => void) {
  await act(async () => {
    const popped = new Promise<void>((resolve) => {
      window.addEventListener('popstate', () => resolve(), { once: true });
    });
    direction();
    await popped;
  });
}

function requireElement<T extends Element>(
  container: ParentNode,
  selector: string,
): T {
  const element = container.querySelector<T>(selector);
  expect(element).not.toBeNull();
  return element as T;
}

function MessagePublisher() {
  const { showMessage } = useGlobalMessages();

  return (
    <>
      <h2>Dashboard-Inhalt</h2>
      <button
        type="button"
        onClick={() => showMessage({ type: 'success', text: 'Änderung gespeichert.' })}
      >
        Erfolg melden
      </button>
      <button
        type="button"
        onClick={() => showMessage({ type: 'error', text: 'Speichern fehlgeschlagen.' })}
      >
        Fehler melden
      </button>
    </>
  );
}

describe('AppShell', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    window.history.replaceState(null, '', '/');
    container = document.createElement('div');
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    vi.restoreAllMocks();
    container.remove();
    window.history.replaceState(null, '', '/');
  });

  function renderShell(props: Partial<AppShellProps> = {}) {
    act(() => {
      root.render(
        <AppShell
          sections={props.sections ?? sections}
          initialSectionId={props.initialSectionId ?? 'dashboard'}
        />,
      );
    });
  }

  it.each(['', '#unbekannt'])(
    'falls back to the initial section for hash %j and marks exactly one link current',
    (hash) => {
      window.history.replaceState(null, '', hash || '/');

      renderShell();

      expect(container.textContent).toContain('Dashboard-Inhalt');
      const currentLinks = container.querySelectorAll('[aria-current="page"]');
      expect(currentLinks).toHaveLength(1);
      expect(currentLinks[0]?.textContent).toBe('Übersicht');
      expect(requireElement(container, '.route-status').textContent).toContain('Übersicht');
      expect(requireElement(container, 'a[href="/openapi.json"]').textContent).toBe(
        'OpenAPI JSON',
      );
    },
  );

  it('selects a section through navigation and updates the hash', () => {
    const pushState = vi.spyOn(window.history, 'pushState');
    renderShell();

    click(requireElement(container, 'a[href="#settings"]'));

    expect(pushState).toHaveBeenCalledWith(null, '', '#settings');
    expect(window.location.hash).toBe('#settings');
    expect(container.textContent).toContain('Einstellungen-Inhalt');
    expect(container.textContent).not.toContain('Dashboard-Inhalt');
    expect(container.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
    expect(
      requireElement<HTMLAnchorElement>(container, '[aria-current="page"]').textContent,
    ).toBe('Einstellungen');
    expect(requireElement(container, '.route-status').textContent).toContain('Einstellungen');
  });

  it('restores the selected section through browser back and forward navigation', async () => {
    renderShell();

    click(requireElement(container, 'a[href="#settings"]'));
    click(requireElement(container, 'a[href="#dashboard"]'));

    await traverseHistory(() => window.history.back());
    expect(window.location.hash).toBe('#settings');
    expect(container.textContent).toContain('Einstellungen-Inhalt');
    expect(
      requireElement<HTMLAnchorElement>(container, '[aria-current="page"]').textContent,
    ).toBe('Einstellungen');

    await traverseHistory(() => window.history.forward());
    expect(window.location.hash).toBe('#dashboard');
    expect(container.textContent).toContain('Dashboard-Inhalt');
    expect(
      requireElement<HTMLAnchorElement>(container, '[aria-current="page"]').textContent,
    ).toBe('Übersicht');
  });

  it('follows externally changed hashes on hashchange and popstate', () => {
    renderShell();

    act(() => {
      window.history.replaceState(null, '', '#settings');
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    expect(container.textContent).toContain('Einstellungen-Inhalt');

    act(() => {
      window.history.replaceState(null, '', '#dashboard');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    expect(container.textContent).toContain('Dashboard-Inhalt');
    expect(
      requireElement<HTMLAnchorElement>(container, '[aria-current="page"]').textContent,
    ).toBe('Übersicht');
  });

  it('keeps global messages across navigation and dismisses only the chosen message', () => {
    renderShell({
      sections: [
        { id: 'dashboard', label: 'Übersicht', content: <MessagePublisher /> },
        sections[1],
      ],
    });

    const buttons = Array.from(container.querySelectorAll('button'));
    click(buttons.find((button) => button.textContent === 'Erfolg melden') as Element);
    click(buttons.find((button) => button.textContent === 'Fehler melden') as Element);

    expect(container.querySelectorAll('.messages-container .message')).toHaveLength(2);
    expect(container.textContent).toContain('Änderung gespeichert.');
    expect(container.textContent).toContain('Speichern fehlgeschlagen.');

    requireElement(
      container,
      '[aria-label="Meldung schließen: Änderung gespeichert."]',
    );
    click(requireElement(container, 'a[href="#settings"]'));

    expect(container.textContent).toContain('Einstellungen-Inhalt');
    expect(container.textContent).toContain('Änderung gespeichert.');
    expect(container.textContent).toContain('Speichern fehlgeschlagen.');

    click(
      requireElement(
        container,
        '[aria-label="Meldung schließen: Änderung gespeichert."]',
      ),
    );

    expect(container.querySelectorAll('.messages-container .message')).toHaveLength(1);
    expect(container.textContent).not.toContain('Änderung gespeichert.');
    expect(container.textContent).toContain('Speichern fehlgeschlagen.');
  });
});
