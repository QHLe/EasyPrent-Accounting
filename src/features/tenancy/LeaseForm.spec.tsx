import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';
import { LeaseForm } from './LeaseForm';

vi.mock('../../api/client', () => ({
  apiClient: { GET: vi.fn() },
}));
vi.mock('../asset-registry', () => ({
  useAssetRegistry: () => ({
    assets: {
      units: [{ id: 1, label: 'Wohnung 1' }],
      rooms: [],
    },
  }),
}));
vi.mock('../linked-documents', () => ({
  LinkedDocumentsPanel: () => null,
}));

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const lease: components['schemas']['LeaseResponse'] = {
  id: 2,
  tenant_id: 1,
  unit_id: 1,
  room_id: null,
  rent_cold: '500.00',
  additional_charges_advance: '100.00',
  occupant_count: 2,
  start_date: '2025-01-01',
  end_date: null,
  status: 'active',
  gnucash_nk_account_guid: 'old-guid',
  gnucash_nk_account_name: 'Assets:Old Advances',
};

describe('lease GnuCash NK account selection', () => {
  let container: HTMLDivElement;
  let root: Root;
  const get = apiClient.GET as unknown as Mock;
  const onSave = vi.fn(async () => {});

  beforeEach(() => {
    container = document.createElement('div');
    document.body.append(container);
    root = createRoot(container);
    get.mockImplementation(async (path: string) => {
      if (path === '/api/v1/settings/gnucash') {
        return { data: { configured: true } };
      }
      return {
        data: [
          { guid: 'new-guid', name: 'Advances', full_name: 'Assets:Advances', parent_guid: null },
        ],
      };
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    vi.resetAllMocks();
    container.remove();
  });

  async function renderForm() {
    await act(async () => {
      root.render(
        <LeaseForm
          initialData={lease}
          tenants={[{ id: 1, full_name: 'Mieterin' }]}
          onSave={onSave}
          onCancel={() => {}}
        />,
      );
      await Promise.resolve();
    });
  }

  async function submit() {
    const form = container.querySelector('form');
    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await Promise.resolve();
    });
  }

  it('saves the selected account GUID and display name with the lease', async () => {
    await renderForm();

    const select = container.querySelector<HTMLSelectElement>('#leaseGnuCashAccount');
    expect(select).not.toBeNull();
    expect(select?.value).toBe('old-guid');
    expect(select?.textContent).toContain('Assets:Advances');

    act(() => {
      if (select) select.value = 'new-guid';
      select?.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await submit();

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        gnucash_nk_account_guid: 'new-guid',
        gnucash_nk_account_name: 'Assets:Advances',
      }),
    );
  });

  it('explains how to configure GnuCash on a fresh install', async () => {
    get.mockResolvedValue({ data: { configured: false } });
    await renderForm();

    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      'GnuCash-Verbindung ist nicht eingerichtet. Bitte unter Einstellungen hinterlegen.',
    );
    expect(get).not.toHaveBeenCalledWith('/api/v1/settings/gnucash/accounts');
    expect(container.querySelector<HTMLSelectElement>('#leaseGnuCashAccount')?.value).toBe('old-guid');
  });

  it('explains account loading failure and keeps an existing account link', async () => {
    get.mockImplementation(async (path: string) => {
      if (path === '/api/v1/settings/gnucash') {
        return { data: { configured: true } };
      }
      throw new Error('Verbindung nicht erreichbar');
    });
    await renderForm();

    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      'GnuCash-Konten konnten nicht geladen werden: Verbindung nicht erreichbar',
    );
    expect(container.querySelector<HTMLSelectElement>('#leaseGnuCashAccount')?.value).toBe('old-guid');
    await submit();

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        gnucash_nk_account_guid: 'old-guid',
        gnucash_nk_account_name: 'Assets:Old Advances',
      }),
    );
  });
});
