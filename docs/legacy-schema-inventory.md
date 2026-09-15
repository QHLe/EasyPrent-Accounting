# Frozen unversioned source schema

The one-time migrator supports the development database layout inventoried at the
start of this refactor. Its SQLite `user_version` is 0 and its schema fingerprint is
`def730f07d955d8375934fc94c24e004c462774bdc12ee18affd71401a88e312`.
The fingerprint uses application schema objects, their SQL, column metadata, and
foreign keys; it does not use or reveal row data. A different fingerprint is an
unknown source schema and must be rejected without writing to that source.

The 22 application tables are grouped below. `sqlite_sequence` is SQLite-internal
and is excluded from the inventory.

| Area | Source tables |
| --- | --- |
| Access and assets | `organizations`, `users`, `memberships`, `properties`, `buildings`, `units`, `rooms` |
| Tenancy and metering | `tenants`, `leases`, `meters`, `meter_readings` |
| Expenses and depreciation | `expense_items`, `depreciation_assets` |
| Settlements and payments | `gnucash_payments`, `settlement_runs`, `settlement_payment_assignments` |
| Settings and local documents | `application_settings`, `paperless_settings`, `gnucash_settings`, `expense_documents`, `tenant_documents`, `lease_documents` |

The frozen layout includes these historically added columns and constraints:

- `tenants.gnucash_nk_account_guid/name` and a partial unique index, although
  the canonical NK account link now belongs to a lease.
- `gnucash_payments.lease_id` is nullable and has no source foreign key because
  it was added after table creation.
- `gnucash_settings.bank_account_guid/name` holds local link metadata.
- `expense_items.property_id` and `meters.property_id` duplicate the typed
  `object_type/object_id` target and can conflict with its ancestry.
- `expense_items.recurrence/interval_name` duplicate `charge_type`.
- Standalone buildings and units, room targets, addresses, archive markers,
  document metadata, payment assignments, and settlement runs are present.

The schema-only SQL snapshot is [legacy_schema.sql](../tests/fixtures/legacy_schema.sql).
The [fixture builder](../tests/legacy_fixture.py) adds entirely synthetic records
for every source table, including nulls, defaults, standalone and archived assets,
room leases, leap-day readings, each supported expense cadence, money across
years and targets, GnuCash links, settlement statuses, local and Paperless-linked
documents, and depreciation. No development database rows were copied.

Version 1 is defined separately in [schema_v1.py](../easyprent_accounting/schema_v1.py).
Its DDL is applied by the versioned runner inside a transaction. The current
application entry remains on the Legacy schema until the later application cutover.
A pristine runner-created version-1 database, including its ledger table, has
schema fingerprint
`22ba01d2bc93dbd5a749760779e872330ab1111a5f1a61bea682d6b1320aad7d`.
