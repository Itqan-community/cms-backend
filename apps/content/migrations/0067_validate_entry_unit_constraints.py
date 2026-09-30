"""Validate the NOT VALID *_exactly_one_unit constraints added in 0066.

This has to be its own migration, not folded into 0066: Django wraps a
migration's operations in one transaction, and Postgres holds the
ACCESS EXCLUSIVE lock taken by `ADD CONSTRAINT ... NOT VALID` until that
transaction commits. Running VALIDATE CONSTRAINT inside the same migration
would therefore perform its full-table scan while still holding
ACCESS EXCLUSIVE — identical to a plain AddConstraint, defeating the point of
the NOT VALID split. Splitting into a separate migration lets 0066 commit and
release ACCESS EXCLUSIVE first, so this migration's VALIDATE CONSTRAINT runs
under the much lighter SHARE UPDATE EXCLUSIVE, which allows concurrent reads
and writes.

No state_operations: validating a constraint is a database-only concern and
is not modelled in Django's migration state.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0066_entry_unit_columns"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE content_assetversionchange VALIDATE CONSTRAINT change_exactly_one_unit",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE content_assetversionentry VALIDATE CONSTRAINT entry_exactly_one_unit",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
