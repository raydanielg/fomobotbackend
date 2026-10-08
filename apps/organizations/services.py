import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.billing.services import PlanService
from apps.common import exceptions
from apps.common.utils import random_token
from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)

logger = logging.getLogger("fomobot.organizations")

INVITE_TTL = timedelta(days=7)


class OrganizationService:
    @staticmethod
    @transaction.atomic
    def create_organization(*, owner, name, **fields) -> Organization:
        org = Organization.objects.create(owner=owner, name=name, **fields)
        plan = PlanService.get_free_plan()
        org.plan = plan
        org.save(update_fields=["plan", "updated_at"])
        from apps.billing.models import Subscription

        Subscription.objects.create(organization=org, plan=plan)
        OrganizationMembership.objects.create(
            organization=org,
            user=owner,
            role=OrganizationMembership.Role.OWNER,
            status=OrganizationMembership.Status.ACTIVE,
        )
        from apps.audit.services import AuditService

        AuditService.log(actor=owner, organization=org, action="organization.created", target=org)
        return org

    @staticmethod
    @transaction.atomic
    def ensure_personal_workspace(user) -> OrganizationMembership | None:
        """Return the user's first active membership, provisioning a personal
        workspace if they have none (legacy/org-less signups)."""
        qs = OrganizationMembership.objects.select_related("organization").filter(
            user=user, status=OrganizationMembership.Status.ACTIVE
        )
        membership = qs.order_by("joined_at").first()
        if membership is not None:
            return membership
        base = user.first_name or user.email.split("@")[0]
        OrganizationService.create_organization(owner=user, name=f"{base}'s workspace")
        return qs.order_by("joined_at").first()

    @staticmethod
    @transaction.atomic
    def update_organization(org: Organization, **fields) -> Organization:
        for k, v in fields.items():
            setattr(org, k, v)
        org.save()
        return org

    @staticmethod
    @transaction.atomic
    def invite_member(*, organization, email, role, invited_by) -> OrganizationInvitation:
        PlanService.check_limit(
            organization,
            "max_members",
            organization.memberships.filter(
                status=OrganizationMembership.Status.ACTIVE
            ).count(),
            noun="members",
        )
        email = email.lower()
        if organization.memberships.filter(
            user__email=email, status=OrganizationMembership.Status.ACTIVE
        ).exists():
            raise exceptions.ConflictError(detail="User is already a member.")

        invite, _ = OrganizationInvitation.objects.update_or_create(
            organization=organization,
            email=email,
            status=OrganizationInvitation.Status.PENDING,
            defaults={
                "role": role,
                "token": random_token(32),
                "invited_by": invited_by,
                "expires_at": timezone.now() + INVITE_TTL,
            },
        )
        from apps.notifications.services import NotificationService

        NotificationService.send_email(
            to=email,
            subject=f"You've been invited to {organization.name} on FomoBot",
            body=f"Accept your invitation:\n{invite_url(invite)}\n",
        )
        return invite

    @staticmethod
    @transaction.atomic
    def accept_invitation(*, token, user) -> OrganizationMembership:
        invite = OrganizationInvitation.objects.filter(token=token).select_for_update().first()
        if not invite or invite.status != OrganizationInvitation.Status.PENDING:
            raise exceptions.APIError(detail="Invalid invitation.")
        if invite.is_expired:
            invite.status = OrganizationInvitation.Status.EXPIRED
            invite.save(update_fields=["status"])
            raise exceptions.APIError(detail="Invitation expired.")
        if invite.email.lower() != user.email.lower():
            raise exceptions.Forbidden(
                detail="This invitation was sent to a different email address."
            )
        membership, _ = OrganizationMembership.objects.update_or_create(
            organization=invite.organization,
            user=user,
            defaults={
                "role": invite.role,
                "status": OrganizationMembership.Status.ACTIVE,
                "joined_at": timezone.now(),
            },
        )
        invite.status = OrganizationInvitation.Status.ACCEPTED
        invite.accepted_at = timezone.now()
        invite.save(update_fields=["status", "accepted_at"])
        return membership

    @staticmethod
    @transaction.atomic
    def remove_member(*, organization, membership: OrganizationMembership):
        OrganizationService._guard_last_owner(organization, membership)
        membership.status = OrganizationMembership.Status.REMOVED
        membership.save(update_fields=["status", "updated_at"])

    @staticmethod
    @transaction.atomic
    def change_role(*, organization, membership: OrganizationMembership, role):
        if role == OrganizationMembership.Role.OWNER:
            raise exceptions.APIError(
                detail="Transfer ownership via the dedicated endpoint."
            )
        OrganizationService._guard_last_owner(organization, membership)
        membership.role = role
        membership.save(update_fields=["role", "updated_at"])
        return membership

    @staticmethod
    @transaction.atomic
    def transfer_ownership(*, organization, new_owner_membership: OrganizationMembership, actor):
        current_owner = organization.memberships.filter(
            role=OrganizationMembership.Role.OWNER,
            status=OrganizationMembership.Status.ACTIVE,
        ).first()
        if current_owner and current_owner.user_id != actor.id:
            raise exceptions.Forbidden(
                detail="Only the current owner can transfer ownership."
            )
        if new_owner_membership.status != OrganizationMembership.Status.ACTIVE:
            raise exceptions.APIError(detail="Target member is not active.")
        if current_owner:
            current_owner.role = OrganizationMembership.Role.ADMIN
            current_owner.save(update_fields=["role", "updated_at"])
        new_owner_membership.role = OrganizationMembership.Role.OWNER
        new_owner_membership.save(update_fields=["role", "updated_at"])
        organization.owner = new_owner_membership.user
        organization.save(update_fields=["owner", "updated_at"])

    @staticmethod
    @transaction.atomic
    def leave(*, organization, membership: OrganizationMembership):
        if membership.role == OrganizationMembership.Role.OWNER:
            other_owners = (
                organization.memberships.filter(
                    role=OrganizationMembership.Role.OWNER,
                    status=OrganizationMembership.Status.ACTIVE,
                )
                .exclude(pk=membership.pk)
                .exists()
            )
            if not other_owners:
                raise exceptions.APIError(
                    detail="The last owner cannot leave. Transfer ownership first."
                )
        membership.status = OrganizationMembership.Status.REMOVED
        membership.save(update_fields=["status", "updated_at"])

    @staticmethod
    def _guard_last_owner(organization, membership):
        if membership.role == OrganizationMembership.Role.OWNER:
            owner_count = organization.memberships.filter(
                role=OrganizationMembership.Role.OWNER,
                status=OrganizationMembership.Status.ACTIVE,
            ).count()
            if owner_count <= 1:
                raise exceptions.APIError(
                    detail="An organization must always have an owner."
                )


def invite_url(invite: OrganizationInvitation) -> str:
    from django.conf import settings

    base = settings.FOMOBOT["FRONTEND_URL"].rstrip("/")
    return f"{base}/invitations/accept?token={invite.token}"
