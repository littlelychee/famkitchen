import secrets

from django.contrib.auth.models import User
from django.db import models


def generate_invite_code():
    return secrets.token_urlsafe(12)[:16]


def user_avatar_upload_path(instance, filename):
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    token = secrets.token_urlsafe(8)
    return f"avatars/user_{instance.user_id}/{token}.{suffix}"


class Family(models.Model):
    CATEGORY_SORT_NAME_ASC = "name_asc"
    CATEGORY_SORT_NAME_DESC = "name_desc"
    CATEGORY_SORT_CUSTOM = "custom"
    CATEGORY_SORT_MODE_CHOICES = [
        (CATEGORY_SORT_NAME_ASC, "名称正序"),
        (CATEGORY_SORT_NAME_DESC, "名称倒序"),
        (CATEGORY_SORT_CUSTOM, "自定义排序"),
    ]

    name = models.CharField(max_length=100, verbose_name="家庭名称")
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_families",
        verbose_name="创建者",
    )
    invite_code = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        verbose_name="家庭邀请码",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    category_sort_mode = models.CharField(
        max_length=20,
        choices=CATEGORY_SORT_MODE_CHOICES,
        default=CATEGORY_SORT_NAME_ASC,
        verbose_name="分类排序方式",
    )

    def save(self, *args, **kwargs):
        if not self.invite_code:
            code = generate_invite_code()
            while Family.objects.filter(invite_code=code).exists():
                code = generate_invite_code()
            self.invite_code = code
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class FamilyMember(models.Model):
    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        related_name="members",
        verbose_name="家庭",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="family_memberships",
        verbose_name="用户",
    )
    role = models.CharField(max_length=20, default="member", verbose_name="角色")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="加入时间")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["family", "user"],
                name="unique_family_member",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.family.name}"


class UserAvatar(models.Model):
    MAX_UPLOAD_SIZE = 4 * 1024 * 1024
    MAX_CUSTOM_AVATARS = 10

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="custom_avatars",
        verbose_name="用户",
    )
    image = models.ImageField(upload_to=user_avatar_upload_path, verbose_name="头像图片")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} custom avatar {self.id}"


class UserProfile(models.Model):
    DEFAULT_AVATARS = [
        ("chef-01", "圆帽小厨", "images/default-avatars/chef-01.svg"),
        ("chef-02", "温火汤勺", "images/default-avatars/chef-02.svg"),
        ("chef-03", "米饭竹笼", "images/default-avatars/chef-03.svg"),
        ("chef-04", "青蔬小碗", "images/default-avatars/chef-04.svg"),
        ("chef-05", "红枣甜盅", "images/default-avatars/chef-05.svg"),
        ("chef-06", "煎锅晨光", "images/default-avatars/chef-06.svg"),
        ("chef-07", "桂花蒸笼", "images/default-avatars/chef-07.svg"),
        ("chef-08", "暖茶小盏", "images/default-avatars/chef-08.svg"),
        ("chef-09", "橙瓣餐盘", "images/default-avatars/chef-09.svg"),
        ("chef-10", "青瓷饭匙", "images/default-avatars/chef-10.svg"),
    ]
    DEFAULT_AVATAR_CHOICES = [
        (key, label) for key, label, _path in DEFAULT_AVATARS
    ]
    DEFAULT_AVATAR_PATHS = {
        key: path for key, _label, path in DEFAULT_AVATARS
    }

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="meal_profile",
        verbose_name="用户",
    )
    default_avatar = models.CharField(
        max_length=30,
        choices=DEFAULT_AVATAR_CHOICES,
        default="chef-01",
        verbose_name="默认头像",
    )
    custom_avatar = models.ForeignKey(
        UserAvatar,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="selected_by_profiles",
        verbose_name="自定义头像",
    )
    phone_number = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="手机号",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "用户资料"
        verbose_name_plural = "用户资料"

    @property
    def default_avatar_path(self):
        return self.DEFAULT_AVATAR_PATHS.get(
            self.default_avatar,
            self.DEFAULT_AVATAR_PATHS["chef-01"],
        )

    @property
    def selected_avatar_key(self):
        if self.custom_avatar_id:
            return f"custom:{self.custom_avatar_id}"
        return f"default:{self.default_avatar}"

    def __str__(self):
        return f"{self.user.username} profile"


class DishCategory(models.Model):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    DISCARDED = "discarded"

    MEAL_SECTION_CHOICES = [
        (BREAKFAST, "早餐"),
        (LUNCH, "午餐"),
        (DINNER, "晚餐"),
        (SNACK, "零食"),
        (DISCARDED, "废弃"),
    ]
    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        related_name="categories",
        verbose_name="家庭",
    )
    meal_section = models.CharField(
        max_length=20,
        choices=MEAL_SECTION_CHOICES,
        default=LUNCH,
        verbose_name="归属大类",
    )
    name = models.CharField(max_length=50, verbose_name="分类名称")
    sort_order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="自定义排序")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["family", "meal_section", "name"],
                name="unique_family_category_name",
            )
        ]
        ordering = ["meal_section", "name"]

    def __str__(self):
        return self.name


class Dish(models.Model):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    DISCARDED = "discarded"

    MEAL_SECTION_CHOICES = [
        (BREAKFAST, "早餐"),
        (LUNCH, "午餐"),
        (DINNER, "晚餐"),
        (SNACK, "零食"),
        (DISCARDED, "废弃"),
    ]
    DEFAULT_IMAGE_BY_SECTION = {
        BREAKFAST: "images/default-dishes/breakfast.svg",
        LUNCH: "images/default-dishes/lunch.svg",
        DINNER: "images/default-dishes/dinner.svg",
        SNACK: "images/default-dishes/snack.svg",
    }

    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        related_name="dishes",
        verbose_name="家庭",
    )
    category = models.ForeignKey(
        DishCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dishes",
        verbose_name="分类",
    )
    categories = models.ManyToManyField(
        DishCategory,
        blank=True,
        related_name="multi_category_dishes",
        verbose_name="类别标签",
    )
    meal_section = models.CharField(
        max_length=20,
        choices=MEAL_SECTION_CHOICES,
        default=LUNCH,
        verbose_name="菜品归类",
    )
    name = models.CharField(max_length=100, verbose_name="菜品名称")
    calories = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="卡路里（千卡）",
    )
    image = models.ImageField(
        upload_to="dishes/",
        null=True,
        blank=True,
        verbose_name="菜品图片",
    )
    description = models.TextField(blank=True, verbose_name="描述")
    supports_spice = models.BooleanField(default=False, verbose_name="可调辣度")
    supports_ice = models.BooleanField(default=False, verbose_name="可调冰量")
    supports_warm = models.BooleanField(default=False, verbose_name="可温热")
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_dishes",
        verbose_name="创建人",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def meal_section_labels(self):
        labels_by_key = dict(self.MEAL_SECTION_CHOICES)
        linked_sections = [
            link.meal_section
            for link in self.meal_section_links.all()
        ]
        if not linked_sections and self.meal_section:
            linked_sections = [self.meal_section]
        return [labels_by_key.get(section, section) for section in linked_sections]

    @property
    def category_labels(self):
        categories = list(self.categories.all())
        if not categories and self.category_id:
            categories = [self.category]
        return [category.name for category in categories if category]

    @property
    def default_image_path(self):
        return self.DEFAULT_IMAGE_BY_SECTION.get(
            self.meal_section,
            self.DEFAULT_IMAGE_BY_SECTION[self.LUNCH],
        )

    @property
    def spice_capability_icon_path(self):
        return "images/meal-customization/spice-mild.svg"

    @property
    def ice_capability_icon_path(self):
        return "images/meal-customization/ice-medium.svg"

    def belongs_to_meal_section(self, meal_section):
        if self.meal_section_links.filter(meal_section=meal_section).exists():
            return True
        return not self.meal_section_links.exists() and self.meal_section == meal_section


class DishMealSection(models.Model):
    dish = models.ForeignKey(
        Dish,
        on_delete=models.CASCADE,
        related_name="meal_section_links",
        verbose_name="菜品",
    )
    meal_section = models.CharField(
        max_length=20,
        choices=Dish.MEAL_SECTION_CHOICES,
        verbose_name="大类",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dish", "meal_section"],
                name="unique_dish_meal_section",
            )
        ]
        ordering = ["meal_section"]

    def __str__(self):
        return f"{self.dish.name} - {self.get_meal_section_display()}"


class MealPlan(models.Model):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"

    MEAL_TYPE_CHOICES = [
        (BREAKFAST, "早餐"),
        (LUNCH, "午餐"),
        (DINNER, "晚餐"),
        (SNACK, "许愿·小零嘴"),
    ]

    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        related_name="meal_plans",
        verbose_name="家庭",
    )
    date = models.DateField(verbose_name="日期")
    meal_type = models.CharField(
        max_length=20,
        choices=MEAL_TYPE_CHOICES,
        verbose_name="餐次",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["family", "date", "meal_type"],
                name="unique_family_date_meal_type",
            )
        ]
        ordering = ["date", "meal_type"]

    def __str__(self):
        return f"{self.family.name} - {self.date} - {self.get_meal_type_display()}"


class FamilyNotification(models.Model):
    MAX_PER_FAMILY = 50
    KIND_MEAL = "meal"
    KIND_MESSAGE = "message"
    EMAIL_PENDING = "pending"
    EMAIL_SENT = "sent"
    EMAIL_SKIPPED = "skipped"
    EMAIL_FAILED = "failed"
    KIND_CHOICES = [
        (KIND_MEAL, "排餐提醒"),
        (KIND_MESSAGE, "家庭留言"),
    ]
    EMAIL_STATUS_CHOICES = [
        (EMAIL_PENDING, "等待发送"),
        (EMAIL_SENT, "已交给邮件服务器"),
        (EMAIL_SKIPPED, "未发送"),
        (EMAIL_FAILED, "发送失败"),
    ]

    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="家庭",
    )
    actor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_family_notifications",
        verbose_name="发起人",
    )
    recipient = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_family_notifications",
        verbose_name="被提醒人",
    )
    meal_plan_date = models.DateField(verbose_name="排餐日期")
    meal_type = models.CharField(
        max_length=20,
        choices=MealPlan.MEAL_TYPE_CHOICES,
        blank=True,
        verbose_name="餐次",
    )
    change_summary = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="变更摘要",
    )
    kind = models.CharField(
        max_length=20,
        choices=KIND_CHOICES,
        default=KIND_MEAL,
        db_index=True,
        verbose_name="消息类型",
    )
    message_body = models.TextField(blank=True, verbose_name="留言内容")
    message_thread_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="留言会话",
    )
    email_status = models.CharField(
        max_length=20,
        choices=EMAIL_STATUS_CHOICES,
        blank=True,
        default="",
        db_index=True,
        verbose_name="邮件状态",
    )
    email_error = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="邮件错误",
    )
    email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="邮件发送时间",
    )
    recipient_deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="收件人隐藏时间",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="提醒时间")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["family", "-created_at"]),
            models.Index(fields=["family", "recipient", "-created_at"]),
        ]

    @property
    def meal_type_label(self):
        return dict(MealPlan.MEAL_TYPE_CHOICES).get(self.meal_type, "")

    @property
    def is_family_message(self):
        return self.kind == self.KIND_MESSAGE

    def __str__(self):
        recipient = self.recipient.username if self.recipient else "家庭成员"
        actor = self.actor.username if self.actor else "某位家人"
        return f"{actor} -> {recipient} {self.meal_plan_date}"


class MealPlanItem(models.Model):
    SPICE_NONE = "none"
    SPICE_MILD = "mild"
    SPICE_MEDIUM = "medium"
    SPICE_HOT = "hot"
    SPICE_LEVEL_CHOICES = [
        (SPICE_NONE, "不辣"),
        (SPICE_MILD, "微辣"),
        (SPICE_MEDIUM, "中辣"),
        (SPICE_HOT, "爆辣"),
    ]

    ICE_NONE = "none"
    ICE_LESS = "less"
    ICE_MEDIUM = "medium"
    ICE_MORE = "more"
    ICE_LEVEL_CHOICES = [
        (ICE_NONE, "去冰"),
        (ICE_LESS, "少冰"),
        (ICE_MEDIUM, "中冰"),
        (ICE_MORE, "多冰"),
    ]

    meal_plan = models.ForeignKey(
        MealPlan,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="排餐",
    )
    dish = models.ForeignKey(
        Dish,
        on_delete=models.CASCADE,
        related_name="meal_items",
        verbose_name="菜品",
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_meal_items",
        verbose_name="添加人",
    )
    note = models.TextField(blank=True, verbose_name="临时备注")
    quantity = models.PositiveIntegerField(default=1, verbose_name="数量")
    spice_level = models.CharField(
        max_length=20,
        choices=SPICE_LEVEL_CHOICES,
        blank=True,
        default="",
        verbose_name="辣度",
    )
    ice_level = models.CharField(
        max_length=20,
        choices=ICE_LEVEL_CHOICES,
        blank=True,
        default="",
        verbose_name="冰量",
    )
    serve_warm = models.BooleanField(default=False, verbose_name="温热")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="添加时间")

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.meal_plan} - {self.dish.name}"

    @property
    def effective_spice_level(self):
        if self.spice_level:
            return self.spice_level
        if self.dish_id and self.dish.supports_spice:
            return self.SPICE_NONE
        return ""

    @property
    def effective_ice_level(self):
        if self.serve_warm:
            return ""
        if self.ice_level:
            return self.ice_level
        if self.dish_id and self.dish.supports_ice:
            return self.ICE_NONE
        return ""

    @property
    def warm_icon_path(self):
        return "images/meal-customization/warm.svg" if self.serve_warm else ""

    @property
    def spice_icon_path(self):
        return {
            self.SPICE_NONE: "images/meal-customization/spice-none.svg",
            self.SPICE_MILD: "images/meal-customization/spice-mild.svg",
            self.SPICE_MEDIUM: "images/meal-customization/spice-medium.svg",
            self.SPICE_HOT: "images/meal-customization/spice-hot.svg",
        }.get(self.effective_spice_level, "")

    @property
    def ice_icon_path(self):
        return {
            self.ICE_NONE: "images/meal-customization/ice-none.svg",
            self.ICE_LESS: "images/meal-customization/ice-less.svg",
            self.ICE_MEDIUM: "images/meal-customization/ice-medium.svg",
            self.ICE_MORE: "images/meal-customization/ice-more.svg",
        }.get(self.effective_ice_level, "")

    @property
    def spice_level_label(self):
        return dict(self.SPICE_LEVEL_CHOICES).get(self.effective_spice_level, "")

    @property
    def ice_level_label(self):
        return dict(self.ICE_LEVEL_CHOICES).get(self.effective_ice_level, "")

    @property
    def warm_label(self):
        return "温热" if self.serve_warm else ""
