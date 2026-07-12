# Generated manually for per-meal item notes and snack quantities.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("meals", "0002_dish_meal_section_mealplan_snack_choice"),
    ]

    operations = [
        migrations.AddField(
            model_name="mealplanitem",
            name="note",
            field=models.TextField(blank=True, verbose_name="临时备注"),
        ),
        migrations.AddField(
            model_name="mealplanitem",
            name="quantity",
            field=models.PositiveIntegerField(default=1, verbose_name="数量"),
        ),
    ]
