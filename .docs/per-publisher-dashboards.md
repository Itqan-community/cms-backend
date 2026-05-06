# Per-Publisher Mixpanel Dashboards

Each publisher in the Itqan CMS gets a dedicated Mixpanel dashboard, scoped to their own API traffic.

## Current dashboards

### Public board URLs (share with publishers)

| Pub ID | Publisher | Public board URL |
|---|---|---|
| 1 | Saudi Center for Quranic Recitations | https://eu.mixpanel.com/p/31tLcwyZw74b2ybpwJLAGj |
| 2 | Tahbeer for the Ten Qira'at | https://eu.mixpanel.com/p/FJRNu2YgAZpvWsNH7k2A34 |
| 3 | المركز السعودي لتسجيل التلاوات والأحاديث النبوية | https://eu.mixpanel.com/p/5r6CPB7CZPxtR36Z7zjpuh |
| 4 | Ansary Group | https://eu.mixpanel.com/p/8iwEHiU26JF56CFCgBQCXV |
| 6 | جمعية مكنون (Maknoon) | https://eu.mixpanel.com/p/StTfGZNtSYvoQ9HuLsSmXb |
| 8 | Tahbeer | https://eu.mixpanel.com/p/6YcxFqry1aKSBdJ5x3tCuU |
| 10 | itqan | not provisioned (no PublisherMember) |

Public board URLs require no Mixpanel login — anyone with the link can view. Each board only shows events for its own publisher (filtered at the Data View workspace level).

### Internal (logged-in) URLs

For org members logged into Mixpanel:

| Pub ID | Data View workspace | Dashboard URL |
|---|---|---|
| 1 | 4515692 | https://eu.mixpanel.com/project/4012890/view/4515692/app/boards#id=11163140 |
| 2 | 4517081 | https://eu.mixpanel.com/project/4012890/view/4517081/app/boards#id=11163657 |
| 3 | 4517082 | https://eu.mixpanel.com/project/4012890/view/4517082/app/boards#id=11163660 |
| 4 | 4517083 | https://eu.mixpanel.com/project/4012890/view/4517083/app/boards#id=11163661 |
| 6 | 4517084 | https://eu.mixpanel.com/project/4012890/view/4517084/app/boards#id=11163663 |
| 8 | 4517085 | https://eu.mixpanel.com/project/4012890/view/4517085/app/boards#id=11163664 |

Every dashboard lives in its own Data View workspace with a `publisher_id={N}` filter applied at the workspace level. Reports in the workspace inherit the filter automatically — events from other publishers cannot leak in.

## Filtering / isolation

Mixpanel **Data Views** are workspaces with one or more filters applied to all reports inside. Itqan uses one Data View per publisher with the filter `publisher_id is equal to {N}`.

- Data Views are scoped at the workspace level — every report and dashboard inside inherits the filter.
- Publishers invited as Consumers on their Data View can only see filtered events. Bulletproof isolation.
- Each report's metric also carries an explicit `publisher_id={N}` filter (belt-and-suspenders) so the dashboard works correctly even if viewed in the default workspace.

Provision a Data View for a new publisher:
```bash
source scripts/.mixpanel_traffic.env
python3 scripts/provision_data_views.py
```
The script is idempotent — already-provisioned publishers are skipped.

## Reports on each dashboard

Each publisher dashboard has the same 10 reports + 1 header text card:

1. Total traffic over time
2. Status code distribution
3. Top endpoints
4. Endpoint traffic over time
5. Top reciters
6. Top recitations (listed)
7. Top recitations (streamed) — real consumption signal
8. Top riwayahs
9. Average response time
10. Error rate %

See `.docs/mixpanel-chart-explanations.md` for what each one means.

All dashboards have a global time filter (default: Last 30 days). Users can switch between 1d / 7d / 14d / 30d / 60d / 90d via the time picker.

## Provisioning a new publisher

When a new publisher is onboarded:

### Prerequisites
1. Publisher exists in CMS DB with at least one `PublisherMember` (owner or member).
2. Publisher has at least one OAuth2 application created under the member's user.

### Steps

**Option A: Ask Claude (Mixpanel MCP)**
```
"Provision Mixpanel dashboard for publisher_id=11 (name: 'New Publisher')"
```
Claude will run 10 `Run-Query` calls (with `publisher_id=11` filter on each metric) and 1 `Create-Dashboard` call.

**Option B: Run the provisioning script (when written)**
```bash
source scripts/.mixpanel_traffic.env
python3 scripts/provision_publisher_dashboard.py --publisher-id 11 --name "New Publisher"
```
*(Script not yet written — see TODO below.)*

**Option C: Manual via Mixpanel UI**
1. Duplicate the SCQR dashboard (id 11163140).
2. Edit each report's filters: replace `publisher_id=1` with the new ID.
3. Update the dashboard title and description.

## TODO — proper automation

Building a Python script that uses Mixpanel's REST API directly is the long-term path. Pending:
- Confirm the Mixpanel insights/bookmarks REST endpoints (the MCP wraps internal endpoints)
- Wire service account auth (`MIXPANEL_SERVICE_USERNAME` / `MIXPANEL_SERVICE_SECRET` in the env file)
- Idempotency: skip if dashboard already exists for that publisher
- Optional: also create Data View workspace + invite publisher's user as Consumer

## Access control

Currently dashboards are visible to anyone with project view access. To restrict to publisher only:

1. Move dashboard into a Data View workspace filtered by that publisher's `publisher_id`.
2. Invite the publisher's user with the **Consumer** role on that Data View only.
3. Send them the dashboard URL with the workspace prefix:
   `https://eu.mixpanel.com/project/4012890/view/{workspace_id}/app/boards#id={dashboard_id}`

Mixpanel guarantees the user can only see events that match the Data View filter.

See `.docs/publisher-mixpanel-onboarding.md` for the publisher-side onboarding flow.
