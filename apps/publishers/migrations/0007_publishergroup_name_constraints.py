from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("publishers", "0006_backfill_publishergroup_name_translations"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='publishergroup',
            constraint=models.UniqueConstraint(fields=('publisher', 'name_en'), name='unique_publisher_group_name_en'),
        ),
        migrations.AddConstraint(
            model_name='publishergroup',
            constraint=models.UniqueConstraint(fields=('publisher', 'name_ar'), name='unique_publisher_group_name_ar'),
        ),
    ]
