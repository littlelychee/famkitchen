import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import meals.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("meals", "0007_multisection_multicategory_repeat_items"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserAvatar",
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
                    "image",
                    models.ImageField(
                        upload_to=meals.models.user_avatar_upload_path,
                        verbose_name="头像图片",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="上传时间"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="custom_avatars",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="UserProfile",
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
                    "default_avatar",
                    models.CharField(
                        choices=[
                            ("chef-01", "圆帽小厨"),
                            ("chef-02", "温火汤勺"),
                            ("chef-03", "米饭竹笼"),
                            ("chef-04", "青蔬小碗"),
                            ("chef-05", "红枣甜盅"),
                            ("chef-06", "煎锅晨光"),
                            ("chef-07", "桂花蒸笼"),
                            ("chef-08", "暖茶小盏"),
                            ("chef-09", "橙瓣餐盘"),
                            ("chef-10", "青瓷饭匙"),
                        ],
                        default="chef-01",
                        max_length=30,
                        verbose_name="默认头像",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                (
                    "custom_avatar",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="selected_by_profiles",
                        to="meals.useravatar",
                        verbose_name="自定义头像",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="meal_profile",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "用户资料",
                "verbose_name_plural": "用户资料",
            },
        ),
    ]
