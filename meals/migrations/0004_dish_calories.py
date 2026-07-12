# Generated manually for dish calories.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("meals", "0003_mealplanitem_note_quantity"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="calories",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="卡路里（千卡）",
            ),
        ),
    ]
