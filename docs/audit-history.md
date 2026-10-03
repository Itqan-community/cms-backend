# Audit History — Developer Guide

This document describes the audit history architecture in Itqan CMS, how `django-simple-history` is configured across models, how records are routed to the dedicated `audit` database, and how to maintain tracked models.

---

## Architecture Overview

Audit logging in Itqan CMS uses [`django-simple-history`](https://django-simple-history.readthedocs.io/) with a dual-database setup:
- **`default` database**: Stores all primary operational application data (`users`, `publishers`, `content`, `quran`).
- **`audit` database**: Stores all historical audit trail tables (`simple_history` app).

The separation is enforced at runtime via `apps.core.db_routers.AuditRouter`.

```mermaid
flowchart TD
    subgraph AppServer["Application Server (Django / Ninja)"]
        View["API View (Mutates Model)"]
        Middleware["HistoryRequestMiddleware (Captures request.user)"]
        Router["apps.core.db_routers.AuditRouter"]
    end

    subgraph DefaultDB["Default Database (PostgreSQL)"]
        AppTables["Operational Tables (e.g., content_asset, users_user)"]
    end

    subgraph AuditDB["Audit Database (PostgreSQL)"]
        AuditTables["Historical Tables (e.g., historicalasset, historicaluser)"]
    end

    View --> Middleware
    View -->|"model.save() (writes base model)"| Router
    Router -->|"db_for_write -> 'default'"| AppTables
    View -->|"post_save trigger (writes historical record)"| Router
    Router -->|"db_for_write -> 'audit'"| AuditTables
```

---

## Adding History to a Model

1. **Add the `history` field** to the model definition:

   ```python
   from django.db import models
   from simple_history.models import HistoricalRecords

   class MyModel(BaseModel):
       # ... fields ...
       history = HistoricalRecords(
           app="simple_history",
           use_base_model_db=False,
           history_user_id_field=models.BigIntegerField(null=True),
       )
   ```

   > [!IMPORTANT]
   > **All three parameters are mandatory:**
   >
   > - **`app="simple_history"`**: Sets the generated historical model's `app_label` to `simple_history`. This is required by `apps.core.db_routers.AuditRouter` to correctly route historical tables to the `audit` database.
   > - **`use_base_model_db=False`**: Instructs `django-simple-history` to respect `DATABASE_ROUTERS` instead of writing to the tracked model's database. Omitting it silently routes history tables to `default`.
   > - **`history_user_id_field=models.BigIntegerField(null=True)`**: Stores the authenticated user's ID as a plain scalar column instead of a Django `ForeignKey`. This eliminates cross-database relational constraint errors between the `audit` database and the `default` database.

2. **ForeignKey String Qualification Rule**:
   When defining string-based ForeignKey references on a model with `history` (e.g. self-referential or same-app models), **always use the fully qualified app label** (e.g. `"content.Asset"` instead of `"Asset"`). Because historical models belong to `app_label="simple_history"`, unqualified strings will otherwise resolve against `simple_history.<Model>` and trigger migration errors (`fields.E300`/`fields.E307`).

3. **Generate the migration**:
   Historical model migrations are redirected to `apps/core/audit_migrations/` via `settings.MIGRATION_MODULES`:

   ```bash
   uv run python manage.py makemigrations
   ```

4. **Apply to both databases**:

   ```bash
   # 1. Apply to default DB (records migration state; router skips historical tables)
   uv run python manage.py migrate

   # 2. Apply to audit DB (creates historical tables in the audit database)
   uv run python manage.py migrate --database=audit
   ```

---

## Tracked Models (28 Models)

All mutable business and content entities are tracked in the audit trail:

### `apps.users` (3 models)
| Model | Description |
|-------|-------------|
| `User` | User accounts, roles, and profiles |
| `APIKey` | API authentication keys |
| `Developer` | External developer profiles |

### `apps.publishers` (5 models)
| Model | Description |
|-------|-------------|
| `Publisher` | Publisher organization details |
| `PublisherMember` | Publisher membership and role mappings |
| `Domain` | Custom tenant domains associated with publishers |
| `PublisherMemberInvitation` | Invitations to join publisher organizations |
| `MemberLanguage` | Language specializations for publisher members |

### `apps.content` (20 models)
| Category | Models |
|----------|--------|
| **Core Assets & Versions** | `Asset`, `AssetLanguage`, `AssetVersion`, `AssetVersionEntry`, `AssetVersionChange`, `AssetVersionChangeReview`, `AssetPreview`, `AssetAccessRequest`, `AssetAccess`, `Distribution` |
| **Recitation & Metadata** | `Reciter`, `Qiraah`, `Riwayah`, `MushafLayout`, `RecitationFolder`, `RecitationSurahTrack`, `RecitationAyahTiming` |
| **Editorial & Reports** | `ContentIssueReport`, `EditorialRecommendation`, `EditorialRecommendationAsset` |

---

## Explicit Exclusions

The following models are **intentionally not tracked** by `django-simple-history`:

1. **`apps.content.models.UsageEvent`**:
   - High-volume, append-only telemetry/analytics events (views, downloads, API hits).
   - Slated for migration to a dedicated metrics store; adding historical versioning would double write IOPS with zero audit utility.
2. **`apps.quran` (`Sura`, `Ayah`, `Word`)**:
   - Canonical reference data of the Holy Quran.
   - Seeded from authoritative static datasets and completely immutable at application runtime.
3. **`apps.core`**:
   - Contains abstract base models (`BaseModel`, `TenantModel`), not concrete tables.

---

## User Attribution Flow

```
HistoryRequestMiddleware
  └─ sets HistoricalRecords.context.request = request  (live reference)
      └─ calls get_response(request)
          └─ Ninja view dispatch
              └─ auth class sets request.user = authenticated_user
                  └─ view logic → model.save()
                      └─ simple_history reads .context.request.user → correct user ID
```

The middleware stores a reference to the active `request` object (not a snapshot). Ninja auth mutates `request.user` on that same object during view execution. When `model.save()` triggers the post-save signal, `django-simple-history` inspects the context request and stores the user's primary key into `history_user_id`.

---

## Migration Architecture

Historical models belong to the third-party `simple_history` app. To ensure all migrations remain committed to source control and are tracked alongside application code:

```python
# config/settings/base.py
MIGRATION_MODULES = {
    "simple_history": "apps.core.audit_migrations",
}
```

This ensures `manage.py makemigrations` and `manage.py makemigrations --check` automatically manage historical migrations under `apps/core/audit_migrations/`.

---

## Operational Impact & Performance

- **Write Amplification**: Every create, update, or soft/hard delete on a tracked model generates a corresponding row in the historical table on the `audit` database. This results in approximately ~2x write queries for tracked model mutations.
- **Zero Read Overhead**: Normal application read queries (`SELECT`) only target the `default` database and never touch the historical tables.
- **Cross-Database Integrity**: Because `history_user_id` is a scalar `BigIntegerField` rather than a Django `ForeignKey`, no cross-database foreign key constraints or integrity errors occur between PostgreSQL instances.
