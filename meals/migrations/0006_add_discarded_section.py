# Generated manually for discarded dishes.

from django.db import migrations, models


SECTION_CHOICES = [
    ("breakfast", "早餐"),
    ("lunch", "午餐"),
    ("dinner", "晚餐"),
    ("snack", "零食"),
    ("discarded", "废弃"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("meals", "0005_category_meal_section"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dishcategory",
            name="meal_section",
            field=models.CharField(
                choices=SECTION_CHOICES,
                default="lunch",
                max_length=20,
                verbose_name="归属大类",
            ),
        ),
        migrations.AlterField(
            model_name="dish",
            name="meal_section",
            field=models.CharField(
                choices=SECTION_CHOICES,
                default="lunch",
                max_length=20,
                verbose_name="菜品归类",
            ),
        ),
    ]
