# Generated manually for dish meal sections and snack meal plans.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("meals", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="meal_section",
            field=models.CharField(
                choices=[
                    ("breakfast", "早餐菜品"),
                    ("lunch", "午餐菜品"),
                    ("dinner", "晚餐菜品"),
                    ("snack", "零食"),
                ],
                default="lunch",
                max_length=20,
                verbose_name="菜品归类",
            ),
        ),
        migrations.AlterField(
            model_name="mealplan",
            name="meal_type",
            field=models.CharField(
                choices=[
                    ("breakfast", "早餐"),
                    ("lunch", "午餐"),
                    ("dinner", "晚餐"),
                    ("snack", "许愿·小零嘴"),
                ],
                max_length=20,
                verbose_name="餐次",
            ),
        ),
    ]
