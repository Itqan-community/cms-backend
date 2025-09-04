from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS account_emailaddress;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
