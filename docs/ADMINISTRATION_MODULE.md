# Lityra Hire Administration module

## Pages and data sources

| Page | Hire API / behavior | Permission and scope |
| --- | --- | --- |
| Training Centers | Deliberately links to Learn. Hire has no training-center, program, batch, or participant API; it does not call the Learn-only `/lms/...` routes. | Visible to roles with `training.center.view` or `training.center.manage`; access to training records is still handled in Learn. |
| Institution Analytics | `/analytics/v1/dashboard/<role>`; displays the analytics-fact counts returned for the caller's signed scope. | `analytics.platform.view`, `analytics.college.view`, `analytics.branch.view`, or `analytics.section.view`. Branch/section facts are currently intentionally empty because analytics facts have no branch identifier. |
| Placement Readiness | `/analytics/v1/colleges/ranking` for platform scope, or `/analytics/v1/college/<id>/readiness` for assigned college IDs. | Platform or college scope plus `analytics.platform.view` or `analytics.college.view`. Branch/section identities are rejected by the page guard and by the API. |
| Institutions | `/org/v1/organizations` for platform operators; `/org/v1/me` for other authorized users. Create/update/soft-delete call existing Hire organization endpoints. | `institution.view`/`institution.manage`. Company Admin list/get/update calls are limited to its own `tenant_id`; only Super Admin can enumerate all tenants, create, or soft-delete. |
| User Management | Existing Auth `/auth/v1/admin/users` APIs, through the shared Access Control interface. | `auth.user.view` gives scoped read access; `auth.user.manage` enables creation and status changes. Role grants/removals are checked by the API and require `auth.role.assign`. |
| Roles & Permissions | Existing Auth `/auth/v1/roles` and `/auth/v1/permissions`; permission counts come from actual role records. | `auth.role.assign` grants read-only role inspection; `auth.role.manage` enables role edits. System-role and assignment safeguards remain server-side. |
| Audit Trails | `/audit/v1/logs`, filtered by actor, action, entity, and partition. The UI is read-only and shows at most 100 records per query. | `platform.audit.view`; the current Hire defaults grant this only to Super Admin. Date filters, pagination cursor, and export are not exposed by the current API. |
| Access IDs | Existing drive access-code APIs under `/drive/v1/access/codes`; IDs remain bound to a single drive. | `drive.access.manage`; every operation is also checked by the drive service. |

## Built-in role page visibility

This reflects `ROLE_DEFAULTS` in `backend/services/auth/app/seed.py`, plus the page guards and scope constraints. Custom roles can differ; the runtime sidebar reads the effective permissions on the signed-in user. `interviewer` is an additional Hire role beyond the thirteen roles listed in the original LMS-oriented prompt.

| Hire role | Training Centers | Institution Analytics | Placement Readiness | Institutions | User Management | Roles & Permissions | Audit Trails | Access IDs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `super_admin` | Link to Learn | View | View platform ranking | Manage | Manage | Manage | View | Manage |
| `company_admin` | Link to Learn | View | View | Manage | Manage | Read-only | — | Manage |
| `principal` | Link to Learn | View | View assigned college | View own tenant | View scoped users | — | — | — |
| `dean` | Link to Learn | View | View assigned college | View own tenant | — | — | — | — |
| `hod` | Link to Learn | Branch-scoped aggregates (facts currently unavailable) | — (branch scope unsupported) | View own tenant | — | — | — | — |
| `tpo` | — | View | View assigned college | View own tenant | — | — | — | Manage |
| `college_admin` | Link to Learn | View | View assigned college | View own tenant | View scoped users | — | — | — |
| `training_center_admin` | Link to Learn | View | View assigned college | — | View scoped users | — | — | — |
| `program_manager` | Link to Learn | Branch-scoped aggregates (facts currently unavailable) | — (branch scope unsupported) | — | — | — | — | — |
| `trainer` | Link to Learn | Section-scoped aggregates (facts currently unavailable) | — | — | — | — | — | — |
| `faculty` | Link to Learn | Branch-scoped aggregates (facts currently unavailable) | — | — | — | — | — | — |
| `recruiter` | — | — | — | — | — | — | — | Manage |
| `student` | — | — | — | — | — | — | — | — |
| `interviewer` | — | — | — | — | — | — | — | — |

“Link to Learn” is not cross-product data access. Hire and Learn use separate sessions and deployments, so users must sign in to Learn separately. No new tables or migrations are required for these pages. Existing endpoint checks remain authoritative; the frontend guards only control navigation and page presentation.

## Verification

Run the Hire frontend build from `frontend/` with `npm run build`. Backend APIs were reused without schema changes. Staging should verify the runtime role catalog and tenant-specific organization data before production rollout. The page implementation does not provision users or modify the hosted database.
