import logging
from typing import Literal

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.publishers.services.membership import (
    enforce_member_scope,
    enforce_publisher_membership,
    get_user_member_publisher_ids,
)
from apps.publishers.services.publisher_member_invitation_service import PublisherMemberInvitationService
from apps.publishers.services.publisher_member_service import PublisherMemberService

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])
logger = logging.getLogger(__name__)


class MemberOut(Schema):
    id: int
    name: str
    email: str
    role: str
    status: str
    publisher_id: int
    expires_at: AwareDatetime | None = None
    created_at: AwareDatetime

    @staticmethod
    def resolve_name(obj: PublisherMember) -> str:
        return obj.user.name

    @staticmethod
    def resolve_email(obj: PublisherMember) -> str:
        return obj.user.email

    @staticmethod
    def resolve_expires_at(obj: PublisherMember):
        inv = next(
            (i for i in obj.invitations.all() if i.status == PublisherMemberInvitation.StatusChoice.PENDING),
            None,
        )
        return inv.expires_at if inv else None


class MemberCreateIn(Schema):
    publisher_id: int
    name: str
    email: str
    role: Literal["admin", "staff"] = "staff"


def _members_qs():
    return (
        PublisherMember.objects.select_related("user", "publisher")
        .prefetch_related("invitations")
        .order_by("-created_at")
    )


@router.post(
    "members/",
    response={
        201: MemberOut,
        403: NinjaErrorResponse,
        409: NinjaErrorResponse[Literal["already_a_member"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)])
def invite_member(request: Request, data: MemberCreateIn):
    publisher = get_object_or_404(Publisher, id=data.publisher_id)
    enforce_publisher_membership(request.user, data.publisher_id)
    member, _invitation, _raw = PublisherMemberInvitationService().create_invitation(
        publisher=publisher, email=data.email, role=data.role, invited_by=request.user, name=data.name
    )
    logger.info(f"Member invited [member_id={member.id}, publisher_id={data.publisher_id}, user_id={request.user.id}]")
    member = _members_qs().get(id=member.id)
    return 201, member


class MemberFilter(FilterSchema):
    publisher_id: int | None = None
    status: Literal["pending", "active"] | None = None


class MemberPatchIn(Schema):
    name: str | None = None
    role: Literal["admin", "staff"] | None = None


@router.get("members/", response=list[MemberOut])
@permission_required([permission_class(PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS)])
@paginate
@ordering(ordering_fields=["created_at", "name", "id"])
@searching(search_fields=["user__name", "user__email"])
def list_members(request: Request, filters: MemberFilter = Query(...)):
    qs = _members_qs()
    if not request.user.is_staff:
        qs = qs.filter(publisher_id__in=get_user_member_publisher_ids(request.user))
    qs = filters.filter(qs)
    return qs


@router.get(
    "members/{int:member_id}/",
    response={200: MemberOut, 403: NinjaErrorResponse, 404: NinjaErrorResponse},
)
@permission_required([permission_class(PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS)])
def retrieve_member(request: Request, member_id: int):
    member = get_object_or_404(_members_qs(), id=member_id)
    enforce_member_scope(request.user, member)
    return member


@router.patch(
    "members/{int:member_id}/",
    response={200: MemberOut, 403: NinjaErrorResponse, 404: NinjaErrorResponse},
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_PUBLISHER_MEMBERS)])
def update_member(request: Request, member_id: int, data: MemberPatchIn):
    member = get_object_or_404(_members_qs(), id=member_id)
    enforce_member_scope(request.user, member)
    if member.user_id == request.user.id and not request.user.is_staff:
        raise ItqanError(
            error_name="permission_denied",
            message=_("You cannot change your own membership."),
            status_code=403,
        )
    return PublisherMemberService().update_member(member, fields=data.model_dump(exclude_unset=True))


@router.delete(
    "members/{int:member_id}/",
    response={204: None, 403: NinjaErrorResponse, 404: NinjaErrorResponse},
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_PUBLISHER_MEMBERS)])
def delete_member(request: Request, member_id: int):
    member = get_object_or_404(_members_qs(), id=member_id)
    enforce_member_scope(request.user, member)
    if member.user_id == request.user.id and not request.user.is_staff:
        raise ItqanError(
            error_name="permission_denied",
            message=_("You cannot delete your own membership."),
            status_code=403,
        )
    if member.status == PublisherMember.StatusChoice.PENDING:
        invitation = PublisherMemberInvitation.objects.filter(
            member=member, status=PublisherMemberInvitation.StatusChoice.PENDING
        ).first()
        if invitation is not None:
            PublisherMemberInvitationService().cancel(invitation, request.user)
        else:
            PublisherMemberService().delete_member(member)
        outcome = "cancelled"
    else:
        PublisherMemberService().delete_member(member)
        outcome = "removed"
    logger.info(f"Member {outcome} [member_id={member_id}, user_id={request.user.id}]")
    return 204, None


@router.post(
    "members/{int:member_id}/resend-invite/",
    response={200: MemberOut, 400: NinjaErrorResponse, 403: NinjaErrorResponse, 404: NinjaErrorResponse},
)
@permission_required([permission_class(PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)])
def resend_invite(request: Request, member_id: int):
    member = get_object_or_404(_members_qs(), id=member_id)
    enforce_member_scope(request.user, member)
    if member.status == PublisherMember.StatusChoice.ACTIVE:
        raise ItqanError(
            error_name="invalid_invitation",
            message=_("Member is already active; nothing to resend."),
            status_code=400,
        )
    invitation = PublisherMemberInvitation.objects.filter(
        member=member, status=PublisherMemberInvitation.StatusChoice.PENDING
    ).first()
    if invitation is None:
        raise ItqanError(
            error_name="invalid_invitation",
            message=_("No pending invitation to resend."),
            status_code=400,
        )
    PublisherMemberInvitationService().resend(invitation, request.user)
    return _members_qs().get(id=member.id)


class InvitationDetailsOut(Schema):
    publisher_name: str
    role: str
    invited_by_name: str
    email: str
    expires_at: AwareDatetime
    status: str

    @staticmethod
    def resolve_publisher_name(obj: PublisherMemberInvitation) -> str:
        return obj.publisher.name

    @staticmethod
    def resolve_role(obj: PublisherMemberInvitation) -> str:
        return obj.member.get_role_display()

    @staticmethod
    def resolve_invited_by_name(obj: PublisherMemberInvitation) -> str:
        return obj.invited_by.name if obj.invited_by else "An administrator"


@router.get(
    "invitations/{token}/",
    auth=None,
    response={200: InvitationDetailsOut, 400: NinjaErrorResponse[Literal["invalid_invitation"]]},
)
def get_invitation(request: Request, token: str):
    return 200, PublisherMemberInvitationService().get_invitation_details(token)


class AcceptOut(Schema):
    status: str = "accepted"


@router.post(
    "invitations/{token}/accept/",
    auth=None,
    response={200: AcceptOut, 400: NinjaErrorResponse[Literal["invalid_invitation"]]},
)
def accept_invitation(request: Request, token: str):
    PublisherMemberInvitationService().accept_invitation(token)
    return 200, AcceptOut()
