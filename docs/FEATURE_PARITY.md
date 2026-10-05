# Feature parity with `jameshgordy/snipeit-mcp`

Audit date: 2026-08-07. The [reference project](https://github.com/jameshgordy/snipeit-mcp) was inspected across its README, source, tests, prompts, setup/update scripts, Dockerfile, environment contract, OAuth proxy, direct client, third-party SDK calls, pagination, annotations, and file confinement.

The new implementation does not reuse the reference architecture. It removes synchronous `requests`, removes the `snipeit-api` wrapper, replaces broad CRUD tools, centralizes deletion, and uses explicit output schemas.

## Tool mapping

| Reference tool | Reference actions/capability | New tool/action | Status |
|---|---|---|---|
| `manage_assets` | create/get/list/update/delete, tag/serial/filter | `assets_search`, `assets_write`, `delete_resource(asset)` | Retained; safety split |
| `asset_operations` | checkout/checkin/audit/restore | `asset_lifecycle` | Retained |
| `asset_files` | upload/list/download/delete | `files_read`, `files_upload`, `delete_resource(asset_file)` | Retained; unified |
| `asset_labels` | PDF labels | `asset_labels` | Retained; bounded base64 |
| `asset_maintenance` | maintenance create | `asset_maintenance(create)` | Retained and expanded |
| `asset_licenses` | asset licence list | `asset_licenses` | Retained |
| `asset_requests` | request/cancel | `asset_requests` | Retained |
| `manage_consumables` | CRUD | `inventory_search`, `inventory_write`, `delete_resource(consumable)` | Retained |
| `manage_accessories` | CRUD | `inventory_search`, `inventory_write`, `delete_resource(accessory)` | Retained |
| `accessory_operations` | checkout/checkin/list checkouts | `inventory_lifecycle`, `inventory_search(assignments)` | Retained |
| `manage_components` | CRUD | `inventory_search`, `inventory_write`, `delete_resource(component)` | Retained |
| `component_operations` | checkout/checkin/list assets | `inventory_lifecycle`, `inventory_search(assignments)` | Retained |
| `manage_users` | CRUD/restore/me | `users_search`, `users_write`, `delete_resource(user)` | Retained |
| `user_assets` | assets/accessories/licences/consumables/EULAs | `user_inventory` | Retained; assets are richer |
| `manage_companies` | CRUD | `organization_search`, `organization_write`, `delete_resource(company)` | Retained |
| `manage_departments` | CRUD | `organization_search`, `organization_write`, `delete_resource(department)` | Retained |
| `manage_groups` | CRUD | `organization_search`, `organization_write`, `delete_resource(group)` | Retained |
| `user_two_factor` | reset | `users_write(reset_2fa)` | Retained; explicit intent |
| `manage_categories` | CRUD | `catalog_search`, `catalog_write`, `delete_resource(category)` | Retained |
| `manage_manufacturers` | CRUD | `catalog_search`, `catalog_write`, `delete_resource(manufacturer)` | Retained |
| `manage_models` | CRUD/assets by model | `catalog_search`, `catalog_write`, `delete_resource(model)` | Retained |
| `manage_status_labels` | CRUD/assets by status | `catalog_search`, `catalog_write`, `delete_resource(status_label)` | Retained |
| `manage_locations` | CRUD/assets/users | `catalog_search`, `catalog_write`, `delete_resource(location)` | Retained |
| `manage_suppliers` | CRUD | `catalog_search`, `catalog_write`, `delete_resource(supplier)` | Retained |
| `manage_depreciations` | CRUD | `catalog_search`, `catalog_write`, `delete_resource(depreciation)` | Retained |
| `model_files` | upload/list/download/delete | `files_read`, `files_upload`, `delete_resource(model_file)` | Retained; unified |
| `manage_fields` | CRUD/associate/disassociate | `custom_fields_search`, `custom_fields_write`, `delete_resource(custom_field)` | Retained |
| `manage_fieldsets` | CRUD/fields/reorder | `custom_fields_search`, `custom_fields_write`, `delete_resource(fieldset)` | Retained |
| `manage_licenses` | CRUD | `licenses_search`, `licenses_write`, `delete_resource(licence)` | Retained |
| `license_seats` | list/checkout/checkin | `license_seats` | Retained and update added |
| `license_files` | upload/list/download/delete | `files_read`, `files_upload`, `delete_resource(licence_file)` | Retained; unified |
| `activity_reports` | activity/item activity | `reports(activity/item_activity)` | Retained |
| `status_summary` | assets by status | `reports(status_summary)` | Retained |
| `audit_tracking` | due/overdue/summary | `reports(audit_due/audit_overdue/status_summary)` | Retained and due-or-overdue added |
| `manage_imports` | list/get/upload/update/process/delete | `imports`, `delete_resource(import)` | Retained; staged safety |
| `system_info` | version | `system_read(version)` | Retained |
| `manage_backups` | list/download | `system_read(backups/backup_download)` | Retained; bounded content |
| `ldap_operations` | test/sync | `ldap_operations` | Retained; high-impact annotation |

## Behavioral parity

| Concern | Reference behavior | New behavior |
|---|---|---|
| API token | Environment bearer | Retained with separate inbound boundary token |
| Per-user OAuth | Passport OAuth proxy | Retained with explicit redirect allowlist and signing key |
| Permissions | Snipe-IT authoritative | Retained; 403 becomes `permission_denied` |
| Tool filtering | Exact allowlist | Retained; unknown names fail closed |
| Pagination | limit/offset | Retained and page/per-page normalized |
| File handling | confined server paths | Replaced by bounded base64/multipart contract suitable for remote Copilot |
| HTTP 200 error payload | detected | Retained with validation details |
| TLS | verified | Retained; custom CA added |
| Secret redaction | formatter patterns | Retained with structured JSON logs |
| Endpoint safety | path validation | Retained and route-family allowlist strengthened |
| Deletion | mixed into CRUD/file tools | Retained only through `delete_resource` |

## Conditional behavior and justified differences

- Snipe-IT's current route source does not consistently expose user consumables on every supported version. `user_inventory` calls it where present and returns an empty supported section when the endpoint is absent; it never fabricates data.
- EULA/acceptance routes vary by version and permission. They are returned when supported and explicitly requested.
- Large file/backup/label bytes are not dumped unbounded into model context. Metadata and `content_truncated` are returned when above the inline limit.
- Local server filesystem paths from the reference are intentionally not accepted from Copilot. Upload bytes must be explicitly provided, eliminating path traversal and remote/local path confusion.
- Legacy endpoint aliases are not used to bypass permissions. Current documented/source routes are preferred; version-unavailable operations fail clearly.

## Functionality beyond the reference

- Maintenance list/get/update/complete, notes, and maintenance types.
- Generalized current attachment parent types.
- Predefined kit catalog CRUD surface with centralized deletion.
- Page/per-page normalization.
- Audit due-or-overdue and depreciation report actions.
- Explicit licence-seat update.
- Copilot schema linter and runtime tool-contract regression tests.
