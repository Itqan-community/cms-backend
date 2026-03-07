from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("publishers", "0006_alter_publisher_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="publisher",
            name="foundation_year",
            field=models.PositiveIntegerField(
                blank=True, help_text="Year the publisher was founded", null=True
            ),
        ),
        migrations.AddField(
            model_name="publisher",
            name="country",
            field=models.CharField(
                blank=True, help_text="Country of the publisher", max_length=100
            ),
        ),
    ]
