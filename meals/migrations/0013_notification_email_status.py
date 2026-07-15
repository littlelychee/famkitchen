from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meals", "0012_v14_family_sort_messages_warm"),
    ]

    operations = [
        migrations.AddField(
            model_name="familynotification",
            name="email_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", "等待发送"),
                    ("sent", "已交给邮件服务器"),
                    ("skipped", "未发送"),
                    ("failed", "发送失败"),
                ],
                db_index=True,
                default="",
                max_length=20,
                verbose_name="邮件状态",
            ),
        ),
        migrations.AddField(
            model_name="familynotification",
            name="email_error",
            field=models.CharField(
                blank=True,
                max_length=255,
                verbose_name="邮件错误",
            ),
        ),
        migrations.AddField(
            model_name="familynotification",
            name="email_sent_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="邮件发送时间",
            ),
        ),
    ]
