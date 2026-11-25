"""Drop the tables left behind by the removed djangosaml2idp app.

The Mixpanel SSO identity provider was the only user of djangosaml2idp. Its
package is gone, so its migrations can no longer run; this removes its tables
and migration history directly. IF EXISTS keeps it safe on databases that never
had the app installed (fresh test and dev databases).
"""

from django.db import migrations

DROP_TABLES = """
DROP TABLE IF EXISTS djangosaml2idp_persistentid;
DROP TABLE IF EXISTS djangosaml2idp_serviceprovider;
DELETE FROM django_migrations WHERE app = 'djangosaml2idp';
"""


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0002_user_preferred_language"),
    ]

    operations = [
        migrations.RunSQL(DROP_TABLES, reverse_sql=migrations.RunSQL.noop),
    ]
