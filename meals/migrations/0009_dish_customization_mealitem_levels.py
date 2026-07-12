# Generated manually for dish customization flags and per-meal serving levels.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("meals", "0008_user_profile_avatars"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="supports_spice",
            field=models.BooleanField(default=False, verbose_name="可调辣度"),
        ),
        migrations.AddField(
            model_name="dish",
            name="supports_ice",
            field=models.BooleanField(default=False, verbose_name="可调冰量"),
        ),
        migrations.AddField(
            model_name="mealplanitem",
            name="spice_level",
            field=models.CharField(
                blank=True,
                choices=[
                    ("none", "不辣"),
                    ("mild", "微辣"),
                    ("medium", "中辣"),
                    ("hot", "爆辣"),
                ],
                default="",
                max_length=20,
                verbose_name="辣度",
            ),
        ),
        migrations.AddField(
            model_name="mealplanitem",
            name="ice_level",
            field=models.CharField(
                blank=True,
                choices=[
                    ("none", "去冰"),
                    ("less", "少冰"),
                    ("medium", "中冰"),
                    ("more", "多冰"),
                ],
                default="",
                max_length=20,
                verbose_name="冰量",
            ),
        ),
    ]
