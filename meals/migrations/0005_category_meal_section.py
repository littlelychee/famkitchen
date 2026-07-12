# Generated manually for section-scoped dish categories.

from django.db import migrations, models


def infer_category_sections(apps, schema_editor):
    DishCategory = apps.get_model("meals", "DishCategory")
    Dish = apps.get_model("meals", "Dish")

    for category in DishCategory.objects.all():
        dish = (
            Dish.objects.filter(category_id=category.id)
            .order_by("created_at", "id")
            .first()
        )
        if dish:
            category.meal_section = dish.meal_section
            category.save(update_fields=["meal_section"])


class Migration(migrations.Migration):
    dependencies = [
        ("meals", "0004_dish_calories"),
    ]

    operations = [
        migrations.AddField(
            model_name="dishcategory",
            name="meal_section",
            field=models.CharField(
                choices=[
                    ("breakfast", "早餐"),
                    ("lunch", "午餐"),
                    ("dinner", "晚餐"),
                    ("snack", "零食"),
                ],
                default="lunch",
                max_length=20,
                verbose_name="归属大类",
            ),
        ),
        migrations.RunPython(infer_category_sections, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="dishcategory",
            name="unique_family_category_name",
        ),
        migrations.AddConstraint(
            model_name="dishcategory",
            constraint=models.UniqueConstraint(
                fields=("family", "meal_section", "name"),
                name="unique_family_category_name",
            ),
        ),
        migrations.AlterModelOptions(
            name="dishcategory",
            options={"ordering": ["meal_section", "name"]},
        ),
        migrations.AlterField(
            model_name="dish",
            name="meal_section",
            field=models.CharField(
                choices=[
                    ("breakfast", "早餐"),
                    ("lunch", "午餐"),
                    ("dinner", "晚餐"),
                    ("snack", "零食"),
                ],
                default="lunch",
                max_length=20,
                verbose_name="菜品归类",
            ),
        ),
    ]
