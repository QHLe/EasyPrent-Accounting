-- Entirely synthetic records spanning every supported Legacy table and case.
-- Explicit IDs make migration relationship and ID-preservation checks stable.

INSERT INTO organizations (id, name, organization_type) VALUES
  (10, 'Fixture Verwaltung Nord', 'property_management'),
  (20, 'Fixture Verwaltung Süd', 'property_management');

INSERT INTO users (id, full_name, email) VALUES
  (10, 'Fixture Nutzer Eins', 'one@example.invalid'),
  (20, 'Fixture Nutzer Zwei', 'two@example.invalid');

INSERT INTO memberships (id, organization_id, user_id, role) VALUES
  (10, 10, 10, 'manager'),
  (20, 20, 20, 'viewer');

INSERT INTO properties (
  id, organization_id, name, street, city, postal_code, is_archived, archived_at
) VALUES
  (10, 10, 'Fixture Objekt Nord', 'Testweg 1', 'Teststadt', '10000', 0, NULL),
  (20, 20, 'Fixture Objekt Süd', 'Musterweg 2', 'Teststadt', '20000', 1, '2025-06-01T00:00:00+00:00');

INSERT INTO buildings (
  id, property_id, name, year_built, street, city, postal_code, is_archived, archived_at
) VALUES
  (10, 10, 'Haus Nord', 1998, 'Testweg 1', 'Teststadt', '10000', 0, NULL),
  (20, NULL, 'Freistehendes Haus', NULL, 'Alleinweg 3', 'Teststadt', '30000', 1, '2025-06-02T00:00:00+00:00');

INSERT INTO units (
  id, building_id, label, area_sqm, room_count, street, city, postal_code,
  is_archived, archived_at, mea_percent
) VALUES
  (10, 10, 'Wohnung 1', 70.50, 2, 'Testweg 1', 'Teststadt', '10000', 0, NULL, 35.1250),
  (20, 20, 'Wohnung 2', 45.00, 1, 'Alleinweg 3', 'Teststadt', '30000', 0, NULL, NULL),
  (30, NULL, 'Freistehende Wohnung', 32.25, 1, 'Einzelweg 4', 'Teststadt', '40000', 1, '2025-06-03T00:00:00+00:00', NULL);

INSERT INTO rooms (
  id, unit_id, label, area_sqm, is_archived, archived_at, area_share_percent
) VALUES
  (10, 10, 'Zimmer A', 25.25, 0, NULL, 40.0000),
  (20, 10, 'Zimmer B', NULL, 1, '2025-06-04T00:00:00+00:00', NULL);

INSERT INTO tenants (
  id, full_name, email, phone, alternate_street, alternate_postal_code,
  alternate_city, gnucash_nk_account_guid, gnucash_nk_account_name
) VALUES
  (10, 'Fixture Mieter Eins', 'tenant1@example.invalid', NULL,
   'Ausweichweg 5', '50000', 'Nebenstadt', 'nk-legacy-10', 'NK:Legacy'),
  (20, 'Fixture Mieter Zwei', NULL, '000-123', NULL, NULL, NULL, NULL, NULL),
  (30, 'Fixture Mieter Drei', NULL, NULL, NULL, NULL, NULL, NULL, NULL);

INSERT INTO leases (
  id, unit_id, room_id, tenant_id, rent_cold, additional_charges_advance,
  occupant_count, start_date, end_date, status,
  gnucash_nk_account_guid, gnucash_nk_account_name
) VALUES
  (10, 10, 10, 10, 500.25, 100.10, 1, '2024-01-01', NULL, 'active', NULL, NULL),
  (20, 10, 20, 20, 450.00, 90.00, 2, '2024-01-01', '2024-12-31', 'closed',
   'nk-lease-20', 'NK:Altvertrag'),
  (30, 20, NULL, 20, 600.00, 120.50, 1, '2025-01-01', NULL, 'active',
   'nk-lease-30', 'NK:Neu'),
  (40, 30, NULL, 30, 300.00, 60.00, 1, '2025-02-01', NULL, 'active', NULL, NULL);

INSERT INTO meters (
  id, property_id, object_type, object_id, label, meter_type, unit,
  serial_number, is_archived, archived_at
) VALUES
  (10, 10, 'property', 10, 'Hauptwasser', 'water', 'm3', 'W-10', 0, NULL),
  (20, 10, 'unit', 10, 'Wohnungswasser', 'water', 'm3', NULL, 0, NULL),
  (30, 10, 'room', 10, 'Zimmerstrom', 'electricity', 'kWh', 'E-30', 0, NULL),
  (40, NULL, 'building', 20, 'Hausstrom', 'electricity', 'kWh', NULL, 1,
   '2025-06-05T00:00:00+00:00');

INSERT INTO meter_readings (id, meter_id, reading_date, reading_value) VALUES
  (10, 10, '2024-01-01', 10.50),
  (20, 10, '2024-02-29', 20.75),
  (30, 10, '2024-12-31', 29.25),
  (40, 20, '2024-01-01', 0.00),
  (50, 20, '2024-12-31', 25.25),
  (60, 30, '2025-01-01', 100.00);

INSERT INTO expense_items (
  id, property_id, object_type, object_id, expense_category, beneficiary_name,
  label, amount, allocation_method, charge_type, recurrence, interval_name,
  meter_id, consumption_unit, consumption_value, conversion_factor,
  booking_date, period_start, period_end, is_archived, archived_at
) VALUES
  (10, 10, 'property', 10, 'Wasser', 'Versorger Fixture', 'Jahreswasser', 120.25,
   'area', 'one_time', 'one_time', NULL, NULL, NULL, NULL, 1.00,
   '2024-02-29', '2024-02-29', '2024-02-29', 0, NULL),
  (20, 10, 'property', 10, 'Reinigung', 'Reinigung Fixture', 'Hausreinigung', 19.99,
   'unit_count', 'monthly', 'recurring', 'monthly', NULL, NULL, NULL, 1.00,
   NULL, '2024-01-01', '2024-12-31', 0, NULL),
  (30, 10, 'unit', 10, 'Wasser', 'Versorger Fixture', 'Verbrauch', 88.88,
   'consumption', 'consumption', 'one_time', NULL, 20, 'm3', 20.00, 1.50,
   NULL, '2024-01-01', '2024-12-31', 0, NULL),
  (40, NULL, 'building', 20, 'Versicherung', 'Versicherer Fixture', 'Police', 45.50,
   'area', 'one_time', 'one_time', NULL, NULL, NULL, NULL, 1.00,
   '2025-05-01', '2025-05-01', '2025-05-01', 1, '2025-06-06T00:00:00+00:00'),
  (50, 10, 'room', 10, 'Strom', 'Versorger Fixture', 'Zimmerstrom', 200.00,
   'area', 'yearly', 'recurring', 'yearly', NULL, NULL, NULL, 1.00,
   NULL, '2025-01-01', '2025-12-31', 0, NULL),
  (60, NULL, 'unit', 30, 'Wartung', 'Wartung Fixture', 'Quartalswartung', 25.25,
   'unit_count', 'quarterly', 'recurring', 'quarterly', NULL, NULL, NULL, 1.00,
   NULL, '2025-01-01', '2025-12-31', 0, NULL);

INSERT INTO paperless_settings (
  id, base_url, api_token, created_at, updated_at
) VALUES
  (10, 'https://paperless.example.invalid', 'synthetic-paperless-token',
   '2024-01-01T00:00:00+00:00', '2024-02-01T00:00:00+00:00');

INSERT INTO application_settings (
  id, show_delete_actions, created_at, updated_at,
  sender_name, sender_street, sender_city
) VALUES
  (10, 0, '2024-01-01T00:00:00+00:00', '2024-02-01T00:00:00+00:00',
   'Fixture Absender', 'Absendeweg 6', 'Teststadt');

INSERT INTO gnucash_settings (
  id, host, port, database_name, username, password, sslmode,
  created_at, updated_at, bank_account_guid, bank_account_name
) VALUES
  (10, 'gnucash.example.invalid', 5432, 'synthetic_gnucash', 'fixture_user',
   'synthetic-password', 'require', '2024-01-01T00:00:00+00:00',
   '2024-02-01T00:00:00+00:00', 'bank-synthetic-10', 'Bank:Fixture');

INSERT INTO gnucash_payments (
  id, split_guid, transaction_guid, tenant_id, account_guid, account_name,
  booking_date, amount, description, imported_at, lease_id
) VALUES
  (10, 'split-synthetic-10', 'transaction-synthetic-10', 10, 'nk-legacy-10',
   'NK:Legacy', '2024-03-01', 77.77, 'Vorauszahlung Fixture',
   '2024-03-02T00:00:00+00:00', NULL),
  (20, 'split-synthetic-20', 'transaction-synthetic-20', 20, 'nk-lease-30',
   'NK:Neu', '2025-03-01', 50.25, 'Vorauszahlung Fixture',
   '2025-03-02T00:00:00+00:00', 30);

INSERT INTO settlement_runs (
  id, property_id, unit_id, period_start, period_end, status, created_at, updated_at
) VALUES
  ('run-synthetic-2024', 10, NULL, '2024-01-01', '2024-12-31', 'finalized',
   '2025-01-01T00:00:00+00:00', '2025-01-02T00:00:00+00:00'),
  ('run-synthetic-2025', NULL, 20, '2025-01-01', '2025-12-31', 'draft',
   '2025-01-01T00:00:00+00:00', '2025-01-02T00:00:00+00:00');

INSERT INTO settlement_payment_assignments (
  id, settlement_id, split_guid, lease_id, status, reason, assigned_amount,
  created_at, updated_at
) VALUES
  (10, 'run-synthetic-2024', 'split-synthetic-10', 10, 'considered', NULL, 77.77,
   '2025-01-01T00:00:00+00:00', '2025-01-02T00:00:00+00:00'),
  (20, 'run-synthetic-2025', 'split-synthetic-20', 30, 'excluded', 'test exclusion',
   NULL, '2025-01-01T00:00:00+00:00', '2025-01-02T00:00:00+00:00');

INSERT INTO expense_documents (
  id, expense_id, filename, content_type, content_size, content_blob,
  paperless_document_id, paperless_task_id, paperless_reference_url,
  upload_status, upload_error, created_at
) VALUES
  (10, 10, 'expense-local.pdf', 'application/pdf', 4, X'74657374',
   NULL, NULL, NULL, 'local', NULL, '2024-03-01T00:00:00+00:00'),
  (20, 20, 'expense-linked.pdf', 'application/pdf', 0, X'',
   'paperless-synthetic-20', NULL, 'https://paperless.example.invalid/20',
   'uploaded', NULL, '2024-03-02T00:00:00+00:00');

INSERT INTO tenant_documents (
  id, tenant_id, filename, content_type, content_size, content_blob,
  paperless_document_id, paperless_task_id, paperless_reference_url,
  upload_status, upload_error, created_at
) VALUES
  (10, 10, 'tenant-local.txt', 'text/plain', 4, X'74657374',
   NULL, NULL, NULL, 'local', NULL, '2024-03-01T00:00:00+00:00'),
  (20, 20, 'tenant-linked.pdf', 'application/pdf', 0, X'',
   NULL, 'paperless-task-synthetic-20', NULL, 'pending', NULL,
   '2024-03-02T00:00:00+00:00');

INSERT INTO lease_documents (
  id, lease_id, filename, content_type, content_size, content_blob,
  paperless_document_id, paperless_task_id, paperless_reference_url,
  upload_status, upload_error, created_at
) VALUES
  (10, 10, 'lease-local.txt', 'text/plain', 4, X'74657374',
   NULL, NULL, NULL, 'local', NULL, '2024-03-01T00:00:00+00:00'),
  (20, 30, 'lease-linked.pdf', 'application/pdf', 0, X'',
   'paperless-synthetic-lease-20', NULL,
   'https://paperless.example.invalid/lease/20', 'uploaded', NULL,
   '2024-03-02T00:00:00+00:00');

INSERT INTO depreciation_assets (
  id, property_id, asset_name, acquisition_cost, building_share_percent,
  useful_life_years, placed_in_service, method
) VALUES
  (10, 10, 'Fixture Dach', 1000.25, 80.00, 10, '2024-02-29', 'linear'),
  (20, 20, 'Fixture Anlage', 50.00, 100.00, 5, '2025-01-01', 'linear');
