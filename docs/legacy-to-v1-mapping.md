# Legacy to schema v1: one-time data mapping

This is the reviewable mapping contract for the [frozen source schema](legacy-schema-inventory.md).
Only its one accepted fingerprint is supported. The migrator never infers a
different historical layout and never changes GnuCash or Paperless databases.

| Source data | Version 1 mapping | Rejected ambiguity |
| --- | --- | --- |
| All 22 application tables | Same table names and row IDs. Shared values, including nullable addresses, archive timestamps, local document BLOBs and Paperless metadata, are copied unchanged. Foreign-key relationships are retained. | Missing references, invalid values, or changed counts/checksums fail validation. |
| `properties`, `buildings`, `units`, `rooms` | Parent IDs are copied; standalone buildings and units keep `NULL` parent IDs. Room IDs and their unit links stay unchanged. | A room with no unit or a lease room belonging to another unit is rejected. |
| `meters` and `expense_items` polymorphic targets | `object_type/object_id` is the canonical target. Redundant `property_id` is removed. A non-null source `property_id` must agree with the target's property ancestry; standalone targets may have no property. | Unknown object type, missing target, or conflicting ancestry is rejected. |
| `tenants.gnucash_nk_account_guid/name` | The NK account belongs to one lease. An existing same-tenant lease with the GUID is kept; otherwise the sole lease of that tenant receives it if that lease has no GUID. Tenant-level columns are removed. | No lease, multiple eligible leases, duplicate GUIDs, conflicting names/GUIDs, or a name without a GUID are rejected. |
| `leases.gnucash_nk_account_guid/name` | Existing links and lease IDs are preserved, except for the uniquely resolved tenant-level link above. Null links stay null. | Conflicting or duplicate NK links are rejected. |
| `gnucash_payments.lease_id` | A non-null link must exist and belong to the same tenant. A null link resolves first to the sole same-tenant lease with matching NK account GUID; otherwise to the sole same-tenant lease whose period contains `booking_date`. The resolved link becomes non-null with a foreign key. | Zero or multiple candidates, a wrong-tenant explicit link, or an invalid booking date are rejected. |
| `expense_items.charge_type/recurrence/interval_name` | `charge_type` remains calculation-canonical; redundant `recurrence` and `interval_name` are dropped. Nonempty values must agree: `monthly`, `quarterly`, and `yearly` pair with `recurring` and the matching interval; `one_time` and `consumption` pair with `one_time` and no interval. `NULL` or empty redundant fields are accepted as absent because `charge_type` alone determines the cadence. | Nonempty contradictory cadence fields or unknown charge types are rejected rather than silently rewritten. |
| Costs, leases, payments, settlement assignments, depreciation | Original money values, dates, status, categories, targets, and IDs are copied. Null `assigned_amount` remains null. The schema ledger receives version 1 and its application timestamp. | Non-finite money, inverted periods, invalid dates, non-monotone or duplicate meter readings, a depreciation method other than `linear`, or a settlement with zero/two targets are rejected. |
| Application, Paperless, and GnuCash settings; linked documents | Local settings, bank link metadata, documents and Paperless IDs remain in SQLite. External services are not contacted or copied. | Lost or changed local values/BLOBs fail row checksums. |

No new business default is fabricated during migration. Source nulls stay null
where the v1 column permits them. The payment lease link is the one documented
exception; it must resolve uniquely. Source values equal to old defaults are
copied explicitly, not recalculated from current code.

Before activation, the JSON report must show schema v1 and the frozen target
fingerprint, matching row counts and stable-column SHA-256 checksums, valid
transformed links, no foreign-key violations, `integrity_check = ok`, and exact
Decimal totals grouped by year, object, and cost category. Categories are keyed
by hash in the report so user-defined labels are not logged. Any failed check
keeps the active database unchanged.
