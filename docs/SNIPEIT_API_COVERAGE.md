# Snipe-IT API coverage

Audit date: 2026-08-07. Backend sources: current [Snipe-IT API reference](https://snipe-it.readme.io/reference/api-overview), [authentication guidance](https://snipe-it.readme.io/reference/authenticating-with-the-api), [API permissions](https://snipe-it.readme.io/reference/api-permissions), and the current [`routes/api.php`](https://github.com/grokability/snipe-it/blob/master/routes/api.php). Current stable release observed during the audit: v8.6.2.

`Conditional` means the tool remains stable but the operation depends on Snipe-IT version, configuration, or permissions. `Centralized` means the endpoint exists and only `delete_resource` may call it.

| Snipe-IT Capability | API Endpoint | HTTP Method | MCP Tool | MCP Action | Implemented | Tested |
|---|---|---:|---|---|---|---|
| Assets list/search/filter | `/api/v1/hardware` | GET | `assets_search` | list/search | Yes | Yes |
| Asset get | `/api/v1/hardware/{id}` | GET | `assets_search` | get | Yes | Yes |
| Asset exact tag | `/api/v1/hardware/bytag/{tag}` | GET | `assets_search` | by_tag | Yes | Yes |
| Asset exact serial | `/api/v1/hardware/byserial/{serial}` | GET | `assets_search` | by_serial | Yes | Yes |
| Asset advanced filter/custom field | `/api/v1/hardware?filter=...` | GET | `assets_search` | search | Yes | Yes |
| Asset create | `/api/v1/hardware` | POST | `assets_write` | create | Yes | Yes |
| Asset update | `/api/v1/hardware/{id}` | PATCH | `assets_write` | update | Yes | Yes |
| Asset bulk update | `/api/v1/hardware/bulk` | PATCH | — | — | Documented, not public | No |
| Asset delete | `/api/v1/hardware/{id}` | DELETE | `delete_resource` | asset | Centralized | Yes |
| Asset checkout | `/api/v1/hardware/{id}/checkout` | POST | `asset_lifecycle` | checkout | Yes | Yes |
| Asset checkin | `/api/v1/hardware/{id}/checkin` | POST | `asset_lifecycle` | checkin | Yes | Yes |
| Asset audit | `/api/v1/hardware/{id}/audit` | POST | `asset_lifecycle` | audit | Yes | Yes |
| Asset bulk audit | `/api/v1/hardware/audit/bulk` | POST | — | — | Documented, not public | No |
| Asset restore | `/api/v1/hardware/{id}/restore` | POST | `asset_lifecycle` | restore | Yes | Yes |
| Asset labels | `/api/v1/hardware/labels` | POST | `asset_labels` | generate | Yes | Yes |
| Asset licences | `/api/v1/hardware/{id}/licenses` | GET | `asset_licenses` | read | Yes | Yes |
| Requestable assets | `/api/v1/account/requestable/hardware` | GET | `assets_search` | requestable | Yes | Yes |
| Asset request | `/api/v1/account/request/{asset}` | POST | `asset_requests` | request | Yes | Yes |
| Asset request cancel | `/api/v1/account/request/{asset}/cancel` | POST | `asset_requests` | cancel | Yes | Yes |
| Accessory CRUD read/create/update | `/api/v1/accessories[/{id}]` | GET/POST/PATCH | `inventory_search` / `inventory_write` | get/list/create/update | Yes | Yes |
| Accessory delete | `/api/v1/accessories/{id}` | DELETE | `delete_resource` | accessory | Centralized | Yes |
| Accessory checkout/checkin | `/api/v1/accessories/{id}/checkout|checkin` | POST | `inventory_lifecycle` | checkout/checkin | Yes | Yes |
| Accessory checked-out list | `/api/v1/accessories/{id}/checkedout` | GET | `inventory_search` | assignments | Yes | Yes |
| Component CRUD read/create/update | `/api/v1/components[/{id}]` | GET/POST/PATCH | `inventory_search` / `inventory_write` | get/list/create/update | Yes | Yes |
| Component delete | `/api/v1/components/{id}` | DELETE | `delete_resource` | component | Centralized | Yes |
| Component checkout/checkin | `/api/v1/components/{id}/checkout|checkin` | POST | `inventory_lifecycle` | checkout/checkin | Yes | Yes |
| Component assigned assets | `/api/v1/components/{id}/assets` | GET | `inventory_search` | assignments | Yes | Yes |
| Consumable CRUD read/create/update | `/api/v1/consumables[/{id}]` | GET/POST/PATCH | `inventory_search` / `inventory_write` | get/list/create/update | Yes | Yes |
| Consumable delete | `/api/v1/consumables/{id}` | DELETE | `delete_resource` | consumable | Centralized | Yes |
| Consumable checkout | `/api/v1/consumables/{id}/checkout` | POST | `inventory_lifecycle` | checkout | Yes | Yes |
| Consumable assigned users | `/api/v1/consumables/{id}/users` | GET | `inventory_search` | assignments | Yes | Yes |
| User list/search/get/deleted filters | `/api/v1/users[/{id}]` | GET | `users_search` | list/search/get/exact | Yes | Yes |
| Current user | `/api/v1/users/me` | GET | `users_search` | me | Yes | Yes |
| User create/update | `/api/v1/users[/{id}]` | POST/PATCH | `users_write` | create/update | Yes | Yes |
| User delete | `/api/v1/users/{id}` | DELETE | `delete_resource` | user | Centralized | Yes |
| User restore | `/api/v1/users/{id}/restore` | POST | `users_write` | restore | Yes | Yes |
| User 2FA reset | `/api/v1/users/{id}/two_factor_reset` | POST | `users_write` | reset_2fa | Conditional | Yes |
| User assets | `/api/v1/users/{id}/assets` | GET | `user_inventory` | assets | Yes | Yes |
| User accessories | `/api/v1/users/{id}/accessories` | GET | `user_inventory` | accessories | Yes | Yes |
| User licences | `/api/v1/users/{id}/licenses` | GET | `user_inventory` | licences | Yes | Yes |
| User consumables | `/api/v1/users/{id}/consumables` | GET | `user_inventory` | consumables | Conditional | Yes |
| User EULAs | `/api/v1/users/{id}/eulas` | GET | `user_inventory` | eulas | Conditional | Yes |
| Company CRUD | `/api/v1/companies[/{id}]` | GET/POST/PATCH/DELETE | organisation tools / `delete_resource` | company | Yes | Yes |
| Department CRUD | `/api/v1/departments[/{id}]` | GET/POST/PATCH/DELETE | organisation tools / `delete_resource` | department | Yes | Yes |
| Group CRUD | `/api/v1/groups[/{id}]` | GET/POST/PATCH/DELETE | organisation tools / `delete_resource` | group | Yes | Yes |
| Category CRUD | `/api/v1/categories[/{id}]` | GET/POST/PATCH/DELETE | catalog tools / `delete_resource` | category | Yes | Yes |
| Manufacturer CRUD/restore | `/api/v1/manufacturers[/{id}]` | mixed | catalog tools / `delete_resource` | manufacturer | CRUD yes; restore not public | Partial |
| Asset model CRUD | `/api/v1/models[/{id}]` | GET/POST/PATCH/DELETE | catalog tools / `delete_resource` | model | Yes | Yes |
| Assets by model | `/api/v1/hardware?model_id={id}` | GET | `catalog_search` | assets_by_model | Yes | Yes |
| Status-label CRUD | `/api/v1/statuslabels[/{id}]` | GET/POST/PATCH/DELETE | catalog tools / `delete_resource` | status_label | Yes | Yes |
| Status summaries | `/api/v1/statuslabels/assets/name` | GET | `reports` | status_summary | Yes | Yes |
| Assets by status | `/api/v1/hardware?status_id={id}` | GET | `catalog_search` | assets_by_status | Yes | Yes |
| Location CRUD | `/api/v1/locations[/{id}]` | GET/POST/PATCH/DELETE | catalog tools / `delete_resource` | location | Yes | Yes |
| Assets/users by location | `/api/v1/hardware|users?location_id={id}` | GET | `catalog_search` | assets_at_location/users_at_location | Yes | Yes |
| Supplier CRUD | `/api/v1/suppliers[/{id}]` | GET/POST/PATCH/DELETE | catalog tools / `delete_resource` | supplier | Yes | Yes |
| Depreciation CRUD | `/api/v1/depreciations[/{id}]` | GET/POST/PATCH/DELETE | catalog tools / `delete_resource` | depreciation | Yes | Yes |
| Maintenance-type CRUD | `/api/v1/maintenance-types[/{id}]` | mixed | `asset_maintenance`, `catalog_write`, `delete_resource` | list/write/delete | Yes | Yes |
| Maintenance CRUD | `/api/v1/maintenances[/{id}]` | mixed | `asset_maintenance`, `delete_resource` | list/get/create/update/delete | Yes | Yes |
| Maintenance notes | `/api/v1/maintenances/{id}/notes` | GET/POST | `asset_maintenance` | list_notes/add_note | Yes | Yes |
| Complete maintenance | `/api/v1/maintenances/{id}/complete` | POST | `asset_maintenance` | complete | Yes | Yes |
| Custom-field CRUD | `/api/v1/fields[/{id}]` | mixed | custom-field tools / `delete_resource` | field actions | Yes | Yes |
| Fieldset CRUD | `/api/v1/fieldsets[/{id}]` | mixed | custom-field tools / `delete_resource` | fieldset actions | Yes | Yes |
| Field association/disassociation | `/api/v1/fields/{id}/associate|disassociate` | POST | `custom_fields_write` | associate/disassociate | Yes | Yes |
| Field order | `/api/v1/fields/fieldsets/{id}/order` | POST | `custom_fields_write` | reorder | Yes | Yes |
| Licence CRUD | `/api/v1/licenses[/{id}]` | mixed | licence tools / `delete_resource` | licence actions | Yes | Yes |
| Licence seats | `/api/v1/licenses/{id}/seats[/{seat}]` | GET/PATCH | `license_seats` | list/update | Yes | Yes |
| Licence seat checkout/checkin | version-dependent seat routes | POST | `license_seats` | checkout/checkin | Conditional | Yes |
| Unified file list | `/api/v1/{object}/{id}/files` | GET | `files_read` | list | Yes | Yes |
| Unified file download | `/api/v1/{object}/{id}/files/{file}` | GET | `files_read` | download | Yes | Yes |
| Unified file upload | `/api/v1/{object}/{id}/files` | POST | `files_upload` | upload | Yes | Yes |
| Unified file delete | `/api/v1/{object}/{id}/files/{file}/delete` | DELETE | `delete_resource` | `*_file` | Centralized | Yes |
| Activity report | `/api/v1/reports/activity` | GET | `reports` | activity/history | Yes | Yes |
| Activity chart | `/api/v1/reports/activity/chart` | GET | — | — | Not public; chart aggregation omitted | No |
| Asset audit due | `/api/v1/hardware/audits/due` | GET | `reports` | audit_due | Yes | Yes |
| Asset audit overdue | `/api/v1/hardware/audits/overdue` | GET | `reports` | audit_overdue | Yes | Yes |
| Audit due-or-overdue | `/api/v1/hardware/audits/due-or-overdue` | GET | `reports` | audit_due_or_overdue | Yes | Yes |
| Depreciation report | `/api/v1/reports/depreciation` | GET | `reports` | depreciation | Yes | Yes |
| Import list/get/upload/configure | `/api/v1/imports[/{id}]` | GET/POST/PATCH | `imports` | staged actions | Yes | Yes |
| Process import | `/api/v1/imports/process/{id}` | POST | `imports` | process | Yes | Yes |
| Delete import | `/api/v1/imports/{id}` | DELETE | `delete_resource` | import | Centralized | Yes |
| Version information | `/api/v1/version` | GET | `system_read` | version | Yes | Yes |
| Backup list | `/api/v1/settings/backups` | GET | `system_read` | backups | Yes | Yes |
| Backup download | `/api/v1/settings/backups/download/{file}` | GET | `system_read` | backup_download | Yes | Yes |
| LDAP connection test | `/api/v1/settings/ldaptest` | GET | `ldap_operations` | test | Yes | Yes |
| LDAP synchronize users | `/api/v1/users/ldapsync` | POST | `ldap_operations` | sync | Yes | Yes |
| Predefined kit CRUD | `/api/v1/kits[/{id}]` | mixed | catalog tools / `delete_resource` | kit | Yes | Yes |
| Kit item relationships | `/api/v1/kits/{id}/{type}` | mixed | — | — | Not public; outside reference parity/tool target | No |
| Account personal access tokens | `/api/v1/account/personal-access-tokens` | mixed | — | — | Intentionally excluded; MCP must not mint tokens | No |
| Settings mutation/mail test/login attempts | `/api/v1/settings/...` | mixed | — | — | Intentionally excluded from inventory MCP | No |

## Notes

- The Snipe-IT API's documented philosophy uses HTTP status for transport/resource handling while many application failures appear in JSON `status`. The client checks both.
- Advanced-filter prefixes and exact custom-field `db_column` names are passed only after server-side validation/resolution.
- The two official bulk asset routes are documented but intentionally not exposed until a bounded, independently confirmed batch contract is designed and tested. Single-record parity is complete.
- No unsupported UI-only function is fabricated.
