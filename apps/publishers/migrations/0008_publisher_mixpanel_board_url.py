from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("publishers", "0007_add_foundation_year_and_country_to_publisher"),
    ]

    operations = [
        migrations.AddField(
            model_name="publisher",
            name="mixpanel_board_url",
            field=models.URLField(blank=True, null=True, help_text="Public Mixpanel board URL for this publisher's analytics dashboard"),
        ),
    ]
