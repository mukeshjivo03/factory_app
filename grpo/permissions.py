# grpo/permissions.py
"""
Permission-based access control for GRPO module.
Uses Django's built-in permission system instead of role-based access.
Default Django permissions (add/view/change/delete) are used for standard CRUD.
"""

from rest_framework.permissions import BasePermission


# GRPO Posting Permissions (using Django defaults for view/create)

class CanViewGRPOPosting(BasePermission):
    """Permission to view GRPO postings."""

    def has_permission(self, request, view):
        return request.user.has_perm("grpo.view_grpoposting")


class CanCreateGRPOPosting(BasePermission):
    """Permission to create/post GRPO to SAP."""

    def has_permission(self, request, view):
        return request.user.has_perm("grpo.add_grpoposting")


class CanViewPendingGRPO(BasePermission):
    """Permission to view pending GRPO entries."""

    def has_permission(self, request, view):
        return request.user.has_perm("grpo.can_view_pending_grpo")


class CanPreviewGRPO(BasePermission):
    """Permission to preview GRPO data before posting."""

    def has_permission(self, request, view):
        return request.user.has_perm("grpo.can_preview_grpo")


class CanViewGRPOHistory(BasePermission):
    """Permission to view GRPO posting history."""

    def has_permission(self, request, view):
        return request.user.has_perm("grpo.can_view_grpo_history")


class CanManageGRPOAttachments(BasePermission):
    """Permission to upload/manage GRPO attachments."""

    def has_permission(self, request, view):
        return request.user.has_perm("grpo.add_grpoattachment")
