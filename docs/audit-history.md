# Audit History — Developer Guide

## Adding history to a model

1. Add the field:

   ```python
   from simple_history.models import HistoricalRecords

   class MyModel(BaseModel):
       # ... fields ...
       history = HistoricalRecords(
           use_base_model_db=False,
           user_db_constraint=False,
       )
   ```

2. Generate the migration:

   ```bash
   uv run python manage.py makemigrations <app_name>
   ```

3. Apply to both databases:

   ```bash
   # 1. Apply to default DB (records migration in default; router skips historical table)
   uv run python manage.py migrate

   # 2. Apply to audit DB (records migration in audit; router creates historical table)
   uv run python manage.py migrate --database=audit
   ```

> **Both parameters are mandatory:**
>
> - **`use_base_model_db=False`**: Instructs `django-simple-history` to respect `DATABASE_ROUTERS` instead of writing to the tracked model's database. Omitting it silently routes history tables to `default`.
> - **`user_db_constraint=False`**: Prevents Django from attempting to create a database-level foreign key constraint between `history_user_id` in the `audit` DB and `users_user` in the `default` DB. Cross-database foreign keys are invalid in PostgreSQL and would fail with `relation "users_user" does not exist` during migration.

## How user attribution works

```
HistoryRequestMiddleware
  └─ sets HistoricalRecords.context.request = request  (live reference)
      └─ calls get_response(request)
          └─ Ninja view dispatch
              └─ auth class sets request.user = authenticated_user
                  └─ view logic → model.save()
                      └─ simple_history reads .context.request.user → correct user
```

The middleware holds a reference to the request object, not a snapshot.
Ninja auth mutates `request.user` on that same object inside the view.
By the time `model.save()` triggers history, the user is already set.

## Database layout

| Database  | Contents                                               |
|-----------|--------------------------------------------------------|
| `default` | Application tables (users, content, publishers, quran) |
| `audit`   | `simple_history` tables, routed by `AuditRouter`       |

`history_user_id` is a plain integer column (`user_db_constraint=False`) — no cross-database FK constraint.
