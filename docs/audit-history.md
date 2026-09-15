# Audit History — Developer Guide

## Adding history to a model

1. Add the field:

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

> **All three parameters are mandatory:**
>
> - **`app="simple_history"`**: Sets the generated model's `app_label` to `simple_history`. This is required by `apps.core.db_routers.AuditRouter` to correctly route history tables to the `audit` database.
> - **`use_base_model_db=False`**: Instructs `django-simple-history` to respect `DATABASE_ROUTERS` instead of writing to the tracked model's database. Omitting it silently routes history tables to `default`.
> - **`history_user_id_field=models.BigIntegerField(null=True)`**: Stores the authenticated user's ID as a plain scalar column instead of a Django `ForeignKey`. This avoids cross-database relational constraint errors between the `audit` database and the `default` database.

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

`history_user_id` is a plain big integer column (`history_user_id_field=models.BigIntegerField(null=True)`) — no cross-database foreign key or ORM relation constraint.
