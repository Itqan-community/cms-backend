from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0026_reciter_bio_ar_reciter_bio_en_riwayah_bio_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="reciter",
            name="nationality",
            field=models.CharField(blank=True, default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="reciter",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reciter",
            name="date_of_death",
            field=models.DateField(blank=True, null=True),
        ),
    ]
