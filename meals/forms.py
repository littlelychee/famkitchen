import unicodedata

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Dish, DishCategory, DishMealSection, Family, UserAvatar, UserProfile


MAIN_DISH_SECTION_CHOICES = [
    choice
    for choice in Dish.MEAL_SECTION_CHOICES
    if choice[0] in {Dish.BREAKFAST, Dish.LUNCH, Dish.DINNER}
]
MAIN_DISH_SECTIONS = tuple(choice[0] for choice in MAIN_DISH_SECTION_CHOICES)
USERNAME_MAX_DISPLAY_WIDTH = 16
USERNAME_MAX_HAN_LENGTH = 8
FAMILY_NAME_MAX_DISPLAY_WIDTH = 14
FAMILY_NAME_MAX_HAN_LENGTH = 7
DISH_NAME_MAX_DISPLAY_WIDTH = 16
DISH_NAME_MAX_HAN_LENGTH = 8


def display_width(value):
    return sum(
        2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
        for char in value
    )


def validate_display_width(value, *, max_width, max_han_length, label):
    if display_width(value) > max_width:
        raise forms.ValidationError(f"{label}不能超过 {max_han_length} 个汉字长度。")
    return value


def apply_display_width_limit(field, *, max_width, max_han_length, label):
    field.widget.attrs.update(
        {
            "maxlength": str(max_width),
            "data-max-display-width": str(max_width),
            "data-max-display-message": f"{label}不能超过 {max_han_length} 个汉字长度。",
        }
    )


class StyledFormMixin:
    def apply_widget_classes(self):
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            if isinstance(widget, forms.Textarea):
                css_class = "textarea textarea-bordered w-full"
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                css_class = "choice-grid"
            elif isinstance(widget, forms.Select):
                css_class = "select select-bordered w-full text-base"
                existing_style = widget.attrs.get("style", "").strip()
                if "font-size" not in existing_style:
                    widget.attrs["style"] = (
                        f"{existing_style.rstrip(';')}; font-size: 16px;"
                    ).lstrip("; ")
            elif isinstance(widget, forms.FileInput):
                css_class = "file-input file-input-bordered w-full"
            else:
                css_class = "input input-bordered w-full"
            widget.attrs["class"] = f"{existing} {css_class}".strip()


class RegisterForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(label="邮箱", required=True)
    phone_number = forms.CharField(label="手机号", max_length=30, required=False)

    class Meta:
        model = User
        fields = ["username", "email", "phone_number", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_display_width_limit(
            self.fields["username"],
            max_width=USERNAME_MAX_DISPLAY_WIDTH,
            max_han_length=USERNAME_MAX_HAN_LENGTH,
            label="用户名",
        )
        self.fields["email"].widget.attrs.update(
            {"autocomplete": "email", "inputmode": "email"}
        )
        self.apply_widget_classes()

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        return validate_display_width(
            username,
            max_width=USERNAME_MAX_DISPLAY_WIDTH,
            max_han_length=USERNAME_MAX_HAN_LENGTH,
            label="用户名",
        )

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("这个邮箱已经被注册。")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "").strip()
        if commit:
            user.save()
            profile, _created = UserProfile.objects.get_or_create(user=user)
            profile.phone_number = self.cleaned_data.get("phone_number", "").strip()
            profile.save(update_fields=["phone_number", "updated_at"])
        return user


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(label="用户名或邮箱")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"autocomplete": "username email"}
        )
        self.apply_widget_classes()

    def clean(self):
        username = self.cleaned_data.get("username", "").strip()
        if "@" in username:
            matched_user = User.objects.filter(email__iexact=username).first()
            if matched_user:
                self.cleaned_data["username"] = matched_user.get_username()
        return super().clean()


class FamilyForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Family
        fields = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_display_width_limit(
            self.fields["name"],
            max_width=FAMILY_NAME_MAX_DISPLAY_WIDTH,
            max_han_length=FAMILY_NAME_MAX_HAN_LENGTH,
            label="家庭名称",
        )
        self.apply_widget_classes()

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        return validate_display_width(
            name,
            max_width=FAMILY_NAME_MAX_DISPLAY_WIDTH,
            max_han_length=FAMILY_NAME_MAX_HAN_LENGTH,
            label="家庭名称",
        )


class UserProfileForm(StyledFormMixin, forms.ModelForm):
    phone_number = forms.CharField(label="手机号", max_length=30, required=False)

    class Meta:
        model = User
        fields = ["username", "email", "phone_number"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "用户名"
        self.fields["email"].label = "邮箱"
        apply_display_width_limit(
            self.fields["username"],
            max_width=USERNAME_MAX_DISPLAY_WIDTH,
            max_han_length=USERNAME_MAX_HAN_LENGTH,
            label="用户名",
        )
        self.fields["email"].widget.attrs.update(
            {"autocomplete": "email", "inputmode": "email"}
        )
        if self.instance and self.instance.pk:
            profile = UserProfile.objects.filter(user=self.instance).first()
            if profile:
                self.fields["phone_number"].initial = profile.phone_number
        self.apply_widget_classes()

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        return validate_display_width(
            username,
            max_width=USERNAME_MAX_DISPLAY_WIDTH,
            max_han_length=USERNAME_MAX_HAN_LENGTH,
            label="用户名",
        )

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        if email:
            existing_users = User.objects.filter(email__iexact=email)
            if self.instance and self.instance.pk:
                existing_users = existing_users.exclude(pk=self.instance.pk)
            if existing_users.exists():
                raise forms.ValidationError("这个邮箱已经被其他账号使用。")
        return email

    def clean_phone_number(self):
        return self.cleaned_data.get("phone_number", "").strip()

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile, _created = UserProfile.objects.get_or_create(user=user)
            profile.phone_number = self.cleaned_data["phone_number"]
            profile.save(update_fields=["phone_number", "updated_at"])
        return user


class AvatarChoiceForm(forms.Form):
    avatar_choice = forms.CharField(label="头像")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.selected_custom_avatar = None
        self.selected_default_avatar = None

    def clean_avatar_choice(self):
        choice = self.cleaned_data["avatar_choice"]
        if choice.startswith("default:"):
            default_key = choice.split(":", 1)[1]
            if default_key not in UserProfile.DEFAULT_AVATAR_PATHS:
                raise forms.ValidationError("请选择一个系统头像。")
            self.selected_default_avatar = default_key
            return choice

        if choice.startswith("custom:"):
            avatar_id = choice.split(":", 1)[1]
            if not avatar_id.isdigit():
                raise forms.ValidationError("请选择一个已上传头像。")
            avatar = UserAvatar.objects.filter(
                id=avatar_id,
                user=self.user,
            ).first()
            if avatar is None:
                raise forms.ValidationError("这个头像不存在或不属于当前用户。")
            self.selected_custom_avatar = avatar
            return choice

        raise forms.ValidationError("请选择头像。")

    def save(self, profile):
        if self.selected_custom_avatar:
            profile.custom_avatar = self.selected_custom_avatar
        else:
            profile.default_avatar = self.selected_default_avatar
            profile.custom_avatar = None
        profile.save(update_fields=["default_avatar", "custom_avatar", "updated_at"])
        return profile


class AvatarUploadForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = UserAvatar
        fields = ["image"]
        widgets = {"image": forms.FileInput()}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["image"].label = "上传头像"
        self.apply_widget_classes()

    def clean_image(self):
        image = self.cleaned_data["image"]
        if self.user and self.user.custom_avatars.count() >= UserAvatar.MAX_CUSTOM_AVATARS:
            raise forms.ValidationError(
                f"达到最大 {UserAvatar.MAX_CUSTOM_AVATARS} 张头像的上限了，请先删除废弃头像后，再次上传。"
            )
        if image.size > UserAvatar.MAX_UPLOAD_SIZE:
            raise forms.ValidationError("头像图片不能超过 4MB。")
        return image


class FamilyJoinForm(StyledFormMixin, forms.Form):
    invite_code = forms.CharField(label="家庭邀请码", max_length=32)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_classes()


class DishCategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DishCategory
        fields = ["name"]

    def __init__(self, *args, family=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.family = family
        self.apply_widget_classes()

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        queryset = DishCategory.objects.none()
        if self.family:
            queryset = DishCategory.objects.filter(
                family=self.family,
                meal_section__in=MAIN_DISH_SECTIONS,
                name=name,
            )
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("这个分类已经存在。")
        return name


class DishForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Dish
        fields = [
            "name",
            "calories",
            "categories",
            "supports_spice",
            "supports_ice",
            "image",
            "description",
        ]
        widgets = {
            "categories": forms.CheckboxSelectMultiple(),
            "supports_spice": forms.CheckboxInput(attrs={"class": "sr-only"}),
            "supports_ice": forms.CheckboxInput(attrs={"class": "sr-only"}),
            "image": forms.FileInput(),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, family=None, **kwargs):
        super().__init__(*args, **kwargs)

        queryset = DishCategory.objects.none()
        if family is not None:
            queryset = (
                DishCategory.objects.filter(family=family)
                .filter(meal_section__in=MAIN_DISH_SECTIONS)
                .order_by("name")
            )
        self.fields["categories"].queryset = queryset
        self.fields["categories"].required = False
        self.fields["categories"].label = "类别标签"
        self.fields["categories"].label_from_instance = lambda category: category.name

        if not self.is_bound:
            if self.instance and self.instance.pk:
                category_values = list(
                    self.instance.categories.values_list("id", flat=True)
                )
                if not category_values and self.instance.category_id:
                    category_values = [self.instance.category_id]
                self.fields["categories"].initial = category_values

        self.fields["supports_spice"].label = "可调辣度"
        self.fields["supports_ice"].label = "可调冰量"

        self.order_fields(
            [
                "name",
                "calories",
                "categories",
                "supports_spice",
                "supports_ice",
                "image",
                "description",
            ]
        )
        apply_display_width_limit(
            self.fields["name"],
            max_width=DISH_NAME_MAX_DISPLAY_WIDTH,
            max_han_length=DISH_NAME_MAX_HAN_LENGTH,
            label="菜品名称",
        )
        self.apply_widget_classes()

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        return validate_display_width(
            name,
            max_width=DISH_NAME_MAX_DISPLAY_WIDTH,
            max_han_length=DISH_NAME_MAX_HAN_LENGTH,
            label="菜品名称",
        )

    def clean(self):
        cleaned_data = super().clean()
        categories = cleaned_data.get("categories") or []
        unavailable_categories = [
            category
            for category in categories
            if category.meal_section not in MAIN_DISH_SECTIONS
        ]
        if unavailable_categories:
            self.add_error("categories", "不能在这里选择零食或废弃分类。")
        if len(categories) > 1:
            self.add_error("categories", "类别标签只能选择一个。")
        return cleaned_data

    def primary_meal_section(self):
        return Dish.LUNCH

    def primary_category(self):
        categories = list(self.cleaned_data.get("categories") or [])
        return categories[0] if categories else None

    def save_meal_sections(self, dish):
        DishMealSection.objects.filter(dish=dish).delete()
        DishMealSection.objects.bulk_create(
            [
                DishMealSection(dish=dish, meal_section=meal_section)
                for meal_section in MAIN_DISH_SECTIONS
            ],
            ignore_conflicts=True,
        )
