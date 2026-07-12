from django.db import migrations, models


def initialize_category_sort_order(apps, schema_editor):
    DishCategory = apps.get_model("meals", "DishCategory")
    Family = apps.get_model("meals", "Family")
    active_sections = ("breakfast", "lunch", "dinner")

    for family_id in Family.objects.values_list("id", flat=True):
        categories = (
            DishCategory.objects.filter(
                family_id=family_id,
                meal_section__in=active_sections,
            )
            .order_by("name", "id")
        )
        for index, category in enumerate(categories, start=1):
            category.sort_order = index * 10
            category.save(update_fields=["sort_order"])


class Migration(migrations.Migration):

    dependencies = [
        ("meals", "0011_userprofile_phone_number_familynotification"),
    ]

    operations = [
        migrations.AddField(
            model_name="family",
            name="category_sort_mode",
            field=models.CharField(
                choices=[
                    ("name_asc", "名称正序"),
                    ("name_desc", "名称倒序"),
                    ("custom", "自定义排序"),
                ],
                default="name_asc",
                max_length=20,
                verbose_name="分类排序方式",
            ),
        ),
        migrations.AddField(
            model_name="dishcategory",
            name="sort_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                verbose_name="自定义排序",
            ),
        ),
        migrations.AddField(
            model_name="dish",
            name="supports_warm",
            field=models.BooleanField(default=False, verbose_name="可温热"),
        ),
        migrations.AddField(
            model_name="mealplanitem",
            name="serve_warm",
            field=models.BooleanField(default=False, verbose_name="温热"),
        ),
        migrations.AddField(
            model_name="familynotification",
            name="kind",
            field=models.CharField(
                choices=[("meal", "排餐提醒"), ("message", "家庭留言")],
                db_index=True,
                default="meal",
                max_length=20,
                verbose_name="消息类型",
            ),
        ),
        migrations.AddField(
            model_name="familynotification",
            name="message_body",
            field=models.TextField(blank=True, verbose_name="留言内容"),
        ),
        migrations.AddField(
            model_name="familynotification",
            name="message_thread_id",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="留言会话",
            ),
        ),
        migrations.RunPython(
            initialize_category_sort_order,
            migrations.RunPython.noop,
        ),
    ]
