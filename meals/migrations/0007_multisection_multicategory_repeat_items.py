# Generated manually for multi-section dishes, multi-category dishes, and repeatable meal items.

from django.db import migrations, models
import django.db.models.deletion


SECTION_CHOICES = [
    ("breakfast", "早餐"),
    ("lunch", "午餐"),
    ("dinner", "晚餐"),
    ("snack", "零食"),
    ("discarded", "废弃"),
]


def copy_existing_dish_relations(apps, schema_editor):
    Dish = apps.get_model("meals", "Dish")
    DishMealSection = apps.get_model("meals", "DishMealSection")

    for dish in Dish.objects.all().iterator():
        if dish.meal_section:
            DishMealSection.objects.get_or_create(
                dish_id=dish.id,
                meal_section=dish.meal_section,
            )
        if dish.category_id:
            dish.categories.add(dish.category_id)


class Migration(migrations.Migration):
    dependencies = [
        ("meals", "0006_add_discarded_section"),
    ]

    operations = [
        migrations.CreateModel(
            name="DishMealSection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "meal_section",
                    models.CharField(
                        choices=SECTION_CHOICES,
                        max_length=20,
                        verbose_name="大类",
                    ),
                ),
                (
                    "dish",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="meal_section_links",
                        to="meals.dish",
                        verbose_name="菜品",
                    ),
                ),
            ],
            options={
                "ordering": ["meal_section"],
            },
        ),
        migrations.AddField(
            model_name="dish",
            name="categories",
            field=models.ManyToManyField(
                blank=True,
                related_name="multi_category_dishes",
                to="meals.dishcategory",
                verbose_name="小类",
            ),
        ),
        migrations.AddConstraint(
            model_name="dishmealsection",
            constraint=models.UniqueConstraint(
                fields=("dish", "meal_section"),
                name="unique_dish_meal_section",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="mealplanitem",
            name="unique_meal_plan_dish",
        ),
        migrations.RunPython(
            copy_existing_dish_relations,
            migrations.RunPython.noop,
        ),
    ]
