import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mock = vi.hoisted(() => ({
  get: vi.fn(),
  useMetering: vi.fn(),
  deleteEnabled: false,
}));

vi.mock('../../api/client', () => ({ apiClient: { GET: mock.get } }));
vi.mock('../../app/AppShell', () => ({ useGlobalMessages: () => ({ showMessage: vi.fn() }) }));
vi.mock('./useMetering', () => ({ useMetering: mock.useMetering }));
vi.mock('./MeterChart', () => ({ MeterChart: () => null }));

import { MeteringView } from './MeteringView';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

function buttonWithText(container: ParentNode, text: string): HTMLButtonElement {
  const button = Array.from(container.querySelectorAll('button')).find(item => item.textContent === text);
  expect(button).toBeDefined();
  return button as HTMLButtonElement;
}

function changeDate(input: HTMLInputElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  expect(setter).toBeDefined();
  setter?.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
}

describe('MeteringView', () => {
  let container: HTMLDivElement;
  let root: Root;
  const consumption = vi.fn();

  beforeEach(() => {
    container = document.createElement('div');
    document.body.append(container);
    root = createRoot(container);
    consumption.mockReset().mockResolvedValue({ quantity: '10.0' });
    mock.deleteEnabled = false;
    mock.get.mockReset().mockImplementation(async (path: string) =>
      path === '/api/v1/settings/application'
        ? { data: { show_delete_actions: mock.deleteEnabled } }
        : { data: { properties: [], buildings: [], units: [], rooms: [] } },
    );
    mock.useMetering.mockReset().mockReturnValue({
      metering: {
        meters: [
          { id: 1, label: 'Hauptzähler', object_type: 'property', object_id: 1, unit: 'm³', is_archived: false },
          { id: 2, label: 'Alter Zähler', object_type: 'property', object_id: 1, unit: 'm³', is_archived: true },
        ],
        meter_readings: [{ id: 3, meter_id: 1, reading_date: '2025-01-01', reading_value: '5' }],
      },
      loading: false,
      error: null,
      refresh: vi.fn(),
      createMeter: vi.fn(),
      updateMeter: vi.fn(),
      archiveMeter: vi.fn(),
      restoreMeter: vi.fn(),
      deleteMeter: vi.fn(),
      createReading: vi.fn(),
      deleteReading: vi.fn(),
      consumption,
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.restoreAllMocks();
  });

  async function renderView() {
    await act(async () => {
      root.render(<MeteringView />);
      await Promise.resolve();
    });
  }

  it('removes a displayed consumption value when its date range changes', async () => {
    await renderView();
    act(() => buttonWithText(container, 'Hauptzähler').click());
    const form = buttonWithText(container, 'Verbrauch anzeigen').closest('form');
    expect(form).not.toBeNull();

    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await Promise.resolve();
    });
    expect(container.textContent).toContain('Verbrauch: 10.0');

    const start = form?.querySelector<HTMLInputElement>('input[type="date"]');
    expect(start).not.toBeNull();
    act(() => changeDate(start as HTMLInputElement, '2025-02-01'));
    expect(container.textContent).not.toContain('Verbrauch: 10.0');
  });

  it('hides delete actions when the application setting is disabled', async () => {
    await renderView();
    act(() => buttonWithText(container, 'Hauptzähler').click());
    expect(Array.from(container.querySelectorAll('button')).filter(button => button.textContent === 'Löschen')).toHaveLength(0);

    act(() => root.unmount());
    root = createRoot(container);
    mock.deleteEnabled = true;
    await renderView();
    act(() => buttonWithText(container, 'Hauptzähler').click());
    expect(Array.from(container.querySelectorAll('button')).filter(button => button.textContent === 'Löschen')).toHaveLength(1);
  });
});
