from allauth.account.decorators import secure_admin_login
from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin import widgets
from django.contrib.auth import admin as auth_admin, forms as admin_forms
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.forms import EmailField, ModelForm
from django.http import HttpRequest
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from plain_permissions.utils import get_permissions_queryset

from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import PublisherMember
from apps.users.services.group import GroupService

from .models import User


class PublisherMemberInline(admin.TabularInline):
    model = PublisherMember
    extra = 0
    raw_id_fields = ["publisher"]
    fields = ["publisher", "role"]


class UserAdminChangeForm(admin_forms.UserChangeForm):
    # Declaring the field here bypasses ModelAdmin.formfield_for_manytomany, which is what
    # normally wraps a m2m widget in RelatedFieldWidgetWrapper. Without that wrapper the
    # <select> is a direct child of the same .flex-container as its <label>, and
    # SelectFilter2.js prepends the widget it builds into that container -- landing it
    # before the label, so the label renders *after* the field. Wrapping restores the
    # structure `groups` gets, giving the JS its own parent to prepend into.
    user_permissions = forms.ModelMultipleChoiceField(
        get_permissions_queryset(),
        label=_("Permissions"),
        required=False,
        widget=widgets.RelatedFieldWidgetWrapper(
            widgets.FilteredSelectMultiple(_("User Permissions"), False),
            User._meta.get_field("user_permissions").remote_field,
            admin.site,
        ),
        help_text='Hold down "Control", or "Command" on a Mac, to select more than one.',
    )

    class Meta(admin_forms.UserChangeForm.Meta):  # type: ignore[name-defined]
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.AdminUserCreationForm):
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm and UserSocialSignupForm.
    """

    class Meta(admin_forms.UserCreationForm.Meta):  # type: ignore[name-defined]
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


if getattr(settings, "DJANGO_ADMIN_FORCE_ALLAUTH", False):
    # Force the `admin` sign in process to go through the `django-allauth` workflow:
    # https://docs.allauth.org/en/latest/common/admin.html#admin
    admin.autodiscover()
    admin.site.login = secure_admin_login(admin.site.login)  # type: ignore[method-assign]


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("name",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "created_at", "updated_at")}),
    )
    inlines = [PublisherMemberInline]
    list_display = ["email", "name", "is_superuser"]
    search_fields = ["name"]
    ordering = ["id"]
    readonly_fields = ("created_at", "updated_at")
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )


# Shown to staff on the group form to explain why saving adds permissions they did not tick.
# Deliberately NOT wrapped in gettext: both languages must appear at once, whereas gettext
# would resolve to whichever one is active. The Arabic half carries dir="rtl" so it renders
# correctly even while the admin is in English.
PERMISSION_HIERARCHY_HELP_TEXT = mark_safe(  # nosec B308 - static, hardcoded markup; no request/user input to sanitize.
    "<span>"
    "Permissions are expanded automatically when you save, so you only need to pick the "
    "strongest one for each resource. Within a resource: <strong>Create</strong> and "
    "<strong>Update</strong> imply each other (choosing either grants both), "
    "<strong>Delete</strong> grants Create and Update as well, and every write permission "
    "grants <strong>View</strong>. Selecting “Delete Reciters” therefore also stores Create, "
    "Update and View for reciters. Extra permissions appearing after you save are expected."
    "</span>"
    '<span dir="rtl" lang="ar" style="display:block; margin-top:0.5em;">'
    "يتم توسيع الصلاحيات تلقائيًا عند الحفظ، لذا يكفي اختيار الصلاحية الأقوى لكل مورد. "
    "ضمن المورد الواحد: <strong>الإنشاء</strong> و<strong>التعديل</strong> يستلزم كل منهما "
    "الآخر (اختيار أيهما يمنح الاثنين)، و<strong>الحذف</strong> يمنح الإنشاء والتعديل أيضًا، "
    "وكل صلاحية كتابة تمنح <strong>العرض</strong>. لذلك فإن اختيار «حذف القراء» يخزّن أيضًا "
    "الإنشاء والتعديل والعرض للقراء. ظهور صلاحيات إضافية بعد الحفظ أمر متوقع."
    "</span>"
)


class GroupAdminForm(ModelForm):
    """Group form that enforces :class:`GroupService`'s name rules inside the admin.

    Validation lives in the service so the admin and the portal API cannot drift apart.
    ``ItqanError`` is an API-layer exception, so it is translated into a form
    ``ValidationError`` here and rendered as a normal field error instead of a 500.
    """

    # Wrapped for the same reason as UserAdminChangeForm.user_permissions -- see the note
    # there. ``required=False`` keeps a group with no permissions valid.
    permissions = forms.ModelMultipleChoiceField(
        get_permissions_queryset(),
        label=_("Permissions"),
        required=False,
        widget=widgets.RelatedFieldWidgetWrapper(
            widgets.FilteredSelectMultiple(_("permissions"), False),
            Group._meta.get_field("permissions").remote_field,
            admin.site,
        ),
        help_text=PERMISSION_HIERARCHY_HELP_TEXT,
    )

    class Meta:
        model = Group
        fields = ["name", "permissions"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.service = GroupService()

    def clean_name(self) -> str:
        name = self.cleaned_data["name"]
        try:
            return self.service.validate_name(name, exclude_id=self.instance.pk)
        except ItqanError as exc:
            raise ValidationError(exc.message, code=exc.error_name) from exc


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    form = GroupAdminForm
    list_display = ["name"]
    search_fields = ["name"]

    def get_service(self) -> GroupService:
        return GroupService()

    def save_related(self, request: HttpRequest, form: GroupAdminForm, formsets, change: bool) -> None:
        """Apply the permission hierarchy to whatever the admin selected.

        Runs after Django has saved the m2m, so the selection is expanded in place: picking
        CREATE also stores the READ it implies. The form's queryset only offers the managed
        ``PermissionChoice`` rows, so every selection is safe to hand to the service.
        """
        super().save_related(request, form, formsets, change)
        selected = form.cleaned_data.get("permissions")
        if selected is None:
            return

        self.get_service().apply_permissions(form.instance, [permission.codename for permission in selected])

    def delete_model(self, request: HttpRequest, obj: Group) -> None:
        self.get_service().delete_group(obj)

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[Group]) -> None:
        """Route the bulk "delete selected" action through the service too.

        Django's bulk action calls this instead of :meth:`delete_model`, so without the
        override the service would be bypassed for multi-select deletes.
        """
        service = self.get_service()
        for group in queryset:
            service.delete_group(group)
