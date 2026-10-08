from django.shortcuts import get_object_or_404
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.common import exceptions, responses
from apps.organizations import serializers as s
from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from apps.organizations.services import OrganizationService


class OrganizationViewSet(viewsets.ModelViewSet):
    """CRUD for organizations the authenticated user belongs to."""

    permission_classes = [IsAuthenticated]
    serializer_class = s.OrganizationSerializer
    lookup_field = "id"

    def get_queryset(self):
        return Organization.objects.filter(
            memberships__user=self.request.user,
            memberships__status=OrganizationMembership.Status.ACTIVE,
        ).select_related("plan")

    def create(self, request, *args, **kwargs):
        serializer = s.OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = OrganizationService.create_organization(
            owner=request.user, **serializer.validated_data
        )
        return responses.success(
            s.OrganizationSerializer(org).data,
            status=status.HTTP_201_CREATED,
            request=request,
        )

    def retrieve(self, request, *args, **kwargs):
        return responses.success(
            self.get_serializer(self.get_object()).data, request=request
        )

    def partial_update(self, request, *args, **kwargs):
        org = self.get_object()
        self._require_admin(request, org)
        serializer = self.get_serializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return responses.success(serializer.data, request=request)

    def _require_admin(self, request, org):
        membership = org.memberships.filter(
            user=request.user, status=OrganizationMembership.Status.ACTIVE
        ).first()
        if membership is None or membership.role not in (
            OrganizationMembership.Role.OWNER,
            OrganizationMembership.Role.ADMIN,
        ):
            raise exceptions.Forbidden(detail="Admin or owner role required.")
        return membership

    # --- Members -----------------------------------------------------
    @action(detail=True, methods=["get"])
    def members(self, request, id=None):
        org = self.get_object()
        members = org.memberships.select_related("user").exclude(
            status=OrganizationMembership.Status.REMOVED
        )
        return responses.success(s.MembershipSerializer(members, many=True).data, request=request)

    @action(detail=True, methods=["post"], url_path="members/invite")
    def invite(self, request, id=None):
        org = self.get_object()
        self._require_admin(request, org)
        serializer = s.InviteMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite = OrganizationService.invite_member(
            organization=org, invited_by=request.user, **serializer.validated_data
        )
        return responses.success(
            s.InvitationSerializer(invite).data,
            status=status.HTTP_201_CREATED,
            request=request,
        )

    @action(detail=True, methods=["post"], url_path="members/(?P<member_id>[^/.]+)/role")
    def change_role(self, request, id=None, member_id=None):
        org = self.get_object()
        self._require_admin(request, org)
        serializer = s.ChangeRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = get_object_or_404(org.memberships, pk=member_id)
        membership = OrganizationService.change_role(
            organization=org, membership=membership, role=serializer.validated_data["role"]
        )
        return responses.success(s.MembershipSerializer(membership).data, request=request)

    @action(
        detail=True,
        methods=["delete"],
        url_path="members/(?P<member_id>[^/.]+)",
    )
    def remove_member(self, request, id=None, member_id=None):
        org = self.get_object()
        self._require_admin(request, org)
        membership = get_object_or_404(org.memberships, pk=member_id)
        OrganizationService.remove_member(organization=org, membership=membership)
        return responses.success({"detail": "Member removed."}, request=request)

    @action(detail=True, methods=["post"])
    def leave(self, request, id=None):
        org = self.get_object()
        membership = org.memberships.filter(
            user=request.user, status=OrganizationMembership.Status.ACTIVE
        ).first()
        if not membership:
            raise exceptions.APIError(detail="Not a member.")
        OrganizationService.leave(organization=org, membership=membership)
        return responses.success({"detail": "Left organization."}, request=request)

    @action(detail=True, methods=["get"])
    def invitations(self, request, id=None):
        org = self.get_object()
        self._require_admin(request, org)
        invites = org.invitations.filter(status=OrganizationInvitation.Status.PENDING)
        return responses.success(s.InvitationSerializer(invites, many=True).data, request=request)


class AcceptInvitationView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = s.AcceptInvitationSerializer

    def post(self, request):
        serializer = s.AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = OrganizationService.accept_invitation(
            token=serializer.validated_data["token"], user=request.user
        )
        return responses.success(
            s.MembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
            request=request,
        )
