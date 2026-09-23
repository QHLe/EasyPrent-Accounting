import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import { AppShell } from '../../app/AppShell';
import { apiClient } from '../../api/client';
import { SettingsView } from './SettingsView';

vi.mock('../../api/client', () => ({
  apiClient: { GET: vi.fn(), PUT: vi.fn() },
}));

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

describe('GnuCash connection settings', () => {
  let container: HTMLDivElement;
  let root: Root;
  const get = apiClient.GET as unknown as Mock;
  const put = apiClient.PUT as unknown as Mock;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.append(container);
    root = createRoot(container);
    get.mockImplementation(async (path: string) => {
      if (path === '/api/v1/settings/application') {
        return { data: { show_delete_actions: true, sender_name: '', sender_street: '', sender_city: '', updated_at: null } };
      }
      if (path === '/api/v1/settings/paperless') {
        return { data: { base_url: '', token_present: false, token_masked: null, updated_at: null } };
      }
      if (path === '/api/v1/settings/gnucash') {
        return { data: { configured: true, host: 'db.local', port: 5432, database: 'books', username: 'accounting', password_present: true, password_masked: '***', sslmode: 'require', updated_at: null } };
      }
      return { data: null };
    });
    put.mockResolvedValue({
      data: { configured: true, host: 'db.local', port: 5432, database: 'books', username: 'accounting', password_present: true, password_masked: '***', sslmode: 'require', updated_at: null },
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    vi.resetAllMocks();
    container.remove();
  });

  async function renderView() {
    await act(async () => {
      root.render(<AppShell sections={[{ id: 'settings', label: 'Einstellungen', content: <SettingsView /> }]} />);
      await Promise.resolve();
    });
  }

  it('shows saved connection details and keeps its stored password when saving', async () => {
    await renderView();

    expect(container.querySelector<HTMLInputElement>('#gcHost')?.value).toBe('db.local');
    expect(container.querySelector<HTMLInputElement>('#gcPassword')?.value).toBe('');
    expect(container.textContent).toContain('Passwort ist hinterlegt');

    const form = container.querySelector('#gcHost')?.closest('form');
    expect(form).not.toBeNull();
    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await Promise.resolve();
    });

    expect(put).toHaveBeenCalledWith('/api/v1/settings/gnucash', {
      body: {
        host: 'db.local',
        port: 5432,
        database: 'books',
        username: 'accounting',
        password: null,
        sslmode: 'require',
      },
    });
    expect(container.textContent).toContain('GnuCash-Verbindung gespeichert.');
  });

  it('requires a password and saves entered credentials on a fresh install', async () => {
    get.mockImplementation(async (path: string) => {
      if (path === '/api/v1/settings/application') {
        return { data: { show_delete_actions: true, sender_name: '', sender_street: '', sender_city: '', updated_at: null } };
      }
      if (path === '/api/v1/settings/paperless') {
        return { data: { base_url: '', token_present: false, token_masked: null, updated_at: null } };
      }
      if (path === '/api/v1/settings/gnucash') {
        return { data: { configured: false, host: '', port: 5432, database: '', username: '', password_present: false, password_masked: null, sslmode: 'require', updated_at: null } };
      }
      return { data: null };
    });
    await renderView();

    const password = container.querySelector<HTMLInputElement>('#gcPassword');
    expect(password?.required).toBe(true);
    for (const [id, value] of [
      ['gcHost', 'localhost'],
      ['gcPort', '15432'],
      ['gcDatabase', 'new-books'],
      ['gcUsername', 'new-user'],
      ['gcPassword', 'secret'],
    ]) {
      const input = container.querySelector<HTMLInputElement>('#' + id);
      expect(input).not.toBeNull();
      act(() => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set?.call(input, value);
        input?.dispatchEvent(new Event('input', { bubbles: true }));
      });
    }
    const form = password?.closest('form');
    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await Promise.resolve();
    });

    expect(put).toHaveBeenCalledWith('/api/v1/settings/gnucash', {
      body: {
        host: 'localhost',
        port: 15432,
        database: 'new-books',
        username: 'new-user',
        password: 'secret',
        sslmode: 'require',
      },
    });
  });

  it('shows the server error when saving the connection fails', async () => {
    put.mockRejectedValue(new Error('Datenbank nicht erreichbar'));
    await renderView();

    const form = container.querySelector('#gcHost')?.closest('form');
    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await Promise.resolve();
    });

    expect(container.textContent).toContain('GnuCash-Verbindung konnte nicht gespeichert werden: Datenbank nicht erreichbar');
  });
});
