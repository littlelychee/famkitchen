# Generated manually to rename the dish category field label.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("meals", "0009_dish_customization_mealitem_levels"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dish",
            name="categories",
            field=models.ManyToManyField(
                blank=True,
                related_name="multi_category_dishes",
                to="meals.dishcategory",
                verbose_name="类别标签",
            ),
        ),
    ]
