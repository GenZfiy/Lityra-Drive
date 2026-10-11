# Placement drive management

Lityra Hire owns placement-drive records and recruitment data. Lityra Learn remains the source of college and learner administration; Hire uses the authenticated college assignments carried by the Hire identity and does not read Learn's database directly.

## Organization models

| Model | Organizer | Host / participants | Publication gate | Candidate pipeline |
| --- | --- | --- | --- | --- |
| Company off-campus | Company | No college participation | Company publishes | Organizing company |
| Company-hosted at college | Company | Host college is invited; host acceptance is required | Host acceptance, then company publishes | Organizing company |
| College-hosted | College | College may invite companies and peer colleges | College approval is required; optional company acceptance can also be required | One independent pipeline per accepted company |
| College-adopted | College | Exactly one adopting company | Adoption acceptance and college approval | Adopting company |
| Joint | Company | Colleges and recruiting companies can participate | Organizer publishes; host gate can be enabled | One independent pipeline per accepted partner company |
| Multi-college pooled | Company | Multiple colleges and recruiting companies can participate | Organizer publishes; host gate can be enabled | One independent pipeline per accepted partner company |

Each accepted recruiting company receives a linked child drive for its own pipeline. Candidate registrations, scores, interview records, submissions, offers and decisions are keyed by the child drive ID, so companies can operate independently while the parent event retains its shared schedule and college coordination. Child pipelines start in draft; the recruiting company configures and opens its own pipeline after the parent event has been approved and published. Closing or cancelling the parent closes its active pipelines. Students apply to a company pipeline rather than to the coordination-only college event.

## Permission and data boundaries

| Actor | Event coordination | Candidate and recruitment pipeline | Lifecycle / approval |
| --- | --- | --- | --- |
| Company organizer | Yes | Yes | Organizer lifecycle permissions |
| Recruiting/adopting company | Accepted invitation | Its own linked pipeline only | Does not own or publish the parent event |
| Other company partner | Accepted invitation | Its own linked pipeline only | Does not own or publish the parent event |
| Assigned college organizer | Yes | No | Can submit/manage the event; approval permission can publish after review |
| Invited college/host | Accepted invitation | No | Cannot change drive lifecycle |
| Student | Only the active drive entered through its access grant | Own application/progress only | No |
| Super admin | Platform-wide | Platform-wide | Platform-wide |

The backend checks ownership and assigned organizations on every operation. UI visibility is not an authorization boundary. Non-recruitment views omit compensation, role descriptions, and round configuration. Partner companies cannot use the parent event ID to read candidate lists or recruiting records; each company is restricted to its own pipeline drive.

## Lifecycle

`draft -> pending_review -> published -> open -> closed -> completed -> archived`

Some transitions can be cancelled or returned to draft as allowed by the API. A drive cannot be opened without at least one configured round. College-organized drives submit for approval; college-adopted drives also require the adopter to accept. A company-hosted event can require its host college to accept first. Only the organizer or super admin controls lifecycle transitions; the designated recruiting company can operate the recruitment pipeline without becoming the event owner.

## API surface

- `POST /drive/v1/drives` creates a typed drive using the caller's authenticated company/college scope.
- `POST /drive/v1/drives/<id>/institutions/invite` invites college participants (company organizer) or peer colleges (college organizer).
- `POST /drive/v1/drives/<id>/companies/invite` invites companies or the single adopter (college organizer).
- `GET /drive/v1/invitations` lists invitations addressed to the caller's organization.
- `POST /drive/v1/drives/<id>/participation/<company|college>/<organization-id>` accepts, declines, requests changes, or withdraws.
- `POST /drive/v1/drives/<id>/transition` changes status subject to owner, approval, acceptance, and round checks.

Organization invites and decisions publish events on the existing event bus. The Notification service resolves active Hire staff by company tenant or college role assignment through a service-authenticated Auth endpoint, then sends deduplicated in-app and email notifications. Invitations also appear in the Hire UI. Global drive search, calendar results, assigned-candidate lookup, and drive access-code reads/changes are constrained to drives visible to the caller.

## Schema and migration

The Drive service adds organization and event-pipeline fields to `drives` and creates `drive_institution_participation` and `drive_company_participation`. Existing drives are treated as company-organized; the migration backfills their tenant/organizer and event-group IDs. The migration function checks/adds columns and can be rerun. `init-db` runs it and `create_all` creates the relationship tables. Run the existing local initializer before starting the product:

```powershell
python scripts/run_local.py --init-db
```

For a deployed environment, run the product release command with a dedicated `MIGRATION_DATABASE_URL` as a release/migration task before deploying the new application version. Do not use the web runtime credential or add long migrations to normal server startup. Back up the database before migration and retain the previous deploy for rollback. The migration is additive, so rolling back the application does not require dropping the new columns/tables.

## Verification performed

- Drive unit tests cover college-vs-recruiter access, cross-company tenant isolation, adoption acceptance, invalid transitions, derived company ownership, additive migration idempotence, independent company pipeline cloning, and rejection of coordinator-only acceptance.
- A Flask API test uses separate signed company and college identities to accept invitations, create two pipelines, confirm each company sees only its own candidate records, and confirm the college cannot read candidate records.
- Auth recipient resolution is tested to include assigned Hire staff while excluding student accounts. Notification fan-out is tested for separate in-app/email sends with per-recipient idempotency.
- The Hire frontend production build completed.

Production migration and real email delivery were not run in this workspace. The release command requires a separately configured `MIGRATION_DATABASE_URL`; none is present in the local environment. Run the migration after supplying that owner credential through the local environment or deployment release environment. The SQLite/API checks do not replace staging verification with real company and college accounts.
