from io import BytesIO
from pathlib import Path
import unicodedata

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils.text import get_valid_filename
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Dish, DishCategory, DishMealSection, Family, UserAvatar, UserProfile

try:
    from pillow_heif import register_heif_opener
except ImportError:
    HEIF_SUPPORT_ENABLED = False
else:
    register_heif_opener()
    HEIF_SUPPORT_ENABLED = True


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
HEIF_BRANDS = {
    b"heif",
    b"heic",
    b"heix",
    b"hevc",
    b"hevx",
    b"heim",
    b"heis",
    b"mif1",
    b"msf1",
}


def looks_like_heif(raw_data):
    return (
        len(raw_data) >= 12
        and raw_data[4:8] == b"ftyp"
        and raw_data[8:12] in HEIF_BRANDS
    )


def converted_image_name(uploaded_file):
    original_name = Path(getattr(uploaded_file, "name", "") or "image").stem
    safe_stem = get_valid_filename(original_name) or "image"
    return f"{safe_stem}.jpg"


def image_as_rgb(image):
    try:
        image.seek(0)
    except EOFError:
        pass

    image = ImageOps.exif_transpose(image)
    if image.mode == "RGB":
        return image

    has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
    if has_alpha:
        rgba_image = image.convert("RGBA")
        background = Image.new("RGBA", rgba_image.size, (255, 255, 255, 255))
        background.alpha_composite(rgba_image)
        return background.convert("RGB")

    return image.convert("RGB")


def normalize_uploaded_image(uploaded_file):
    try:
        uploaded_file.seek(0)
    except (AttributeError, OSError):
        pass

    raw_data = uploaded_file.read()
    try:
        uploaded_file.seek(0)
    except (AttributeError, OSError):
        pass

    if not raw_data:
        raise forms.ValidationError("图片文件是空的，请重新选择一张图片。")

    try:
        image = Image.open(BytesIO(raw_data))
        source_format = (image.format or "").upper()
        image.load()
    except Image.DecompressionBombError:
        raise forms.ValidationError("这张图片尺寸过大，请压缩后再上传。")
    except (UnidentifiedImageError, OSError):
        if looks_like_heif(raw_data) and not HEIF_SUPPORT_ENABLED:
            raise forms.ValidationError(
                "这张图片是 HEIC/HEIF 格式，当前环境还不能自动转换。"
                "请先转成 JPG/PNG，或重新安装项目依赖后再试。"
            )
        raise forms.ValidationError(
            "这个文件不是可识别的图片，或图片文件已经损坏。"
            "请换一张 JPG、PNG、WebP、AVIF 或 HEIC 图片后再试。"
        )

    if not image.width or not image.height:
        raise forms.ValidationError("这张图片没有有效尺寸，请换一张图片后再试。")

    output = BytesIO()
    rgb_image = image_as_rgb(image)
    rgb_image.save(output, format="JPEG", quality=88, optimize=True)

    converted_file = ContentFile(
        output.getvalue(),
        name=converted_image_name(uploaded_file),
    )
    converted_file.content_type = "image/jpeg"
    converted_file.original_upload_size = getattr(uploaded_file, "size", len(raw_data))
    converted_file.original_image_format = source_format or "UNKNOWN"
    converted_file.was_auto_converted = source_format != "JPEG"
    return converted_file


class AutoConvertingImageField(forms.FileField):
    default_error_messages = {
        "invalid": "请上传一张图片文件。",
    }

    def to_python(self, data):
        uploaded_file = super().to_python(data)
        if uploaded_file in self.empty_values:
            return None
        return normalize_uploaded_image(uploaded_file)


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


class DataAdminPasswordForm(StyledFormMixin, forms.Form):
    password = forms.CharField(
        label="管理员授权码",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "输入管理员授权码",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_classes()


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
    image = AutoConvertingImageField(label="上传头像", widget=forms.FileInput())

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
        upload_size = getattr(image, "original_upload_size", image.size)
        if upload_size > UserAvatar.MAX_UPLOAD_SIZE:
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
    image = AutoConvertingImageField(
        label="菜品图片",
        required=False,
        widget=forms.FileInput(),
    )

    class Meta:
        model = Dish
        fields = [
            "name",
            "calories",
            "categories",
            "supports_spice",
            "supports_ice",
            "supports_warm",
            "image",
            "description",
        ]
        widgets = {
            "categories": forms.CheckboxSelectMultiple(),
            "supports_spice": forms.CheckboxInput(attrs={"class": "sr-only"}),
            "supports_ice": forms.CheckboxInput(attrs={"class": "sr-only"}),
            "supports_warm": forms.CheckboxInput(attrs={"class": "sr-only"}),
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
        self.fields["supports_warm"].label = "可温热"

        self.order_fields(
            [
                "name",
                "calories",
                "categories",
                "supports_spice",
                "supports_ice",
                "supports_warm",
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
