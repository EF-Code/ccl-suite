"""Role-based access control for the local operations API."""

from __future__ import annotations

from typing import Final

ROLE_ALIASES: Final[dict[str, str]] = {
    "member": "staff",
    "reviewer": "supervisor",
}
ROLES: Final[tuple[str, ...]] = (
    "administrator",
    "supervisor",
    "staff",
    "intern",
)
PERMISSIONS: Final[tuple[str, ...]] = (
    "project.read",
    "project.create",
    "file.read",
    "file.upload",
    "file.restore",
    "backup.read",
    "backup.create",
    "backup.verify",
    "backup.restore",
    "file.organize",
    "conversion.run",
    "workflow.manage",
    "approval.decide",
    "security.read",
    "security.write",
    "user.manage",
    "knowledge.read",
    "knowledge.register",
    "knowledge.approve",
)

ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    "administrator": frozenset(PERMISSIONS),
    "supervisor": frozenset(
        {
            "project.read",
            "project.create",
            "file.read",
            "file.upload",
            "file.restore",
            "backup.read",
            "backup.create",
            "backup.verify",
            "backup.restore",
            "file.organize",
            "conversion.run",
            "workflow.manage",
            "approval.decide",
            "security.read",
            "security.write",
            "knowledge.read",
            "knowledge.register",
            "knowledge.approve",
        }
    ),
    "staff": frozenset(
        {
            "project.read",
            "project.create",
            "file.read",
            "file.upload",
            "file.restore",
            "backup.read",
            "backup.create",
            "backup.verify",
            "backup.restore",
            "file.organize",
            "conversion.run",
            "workflow.manage",
            "approval.decide",
            "security.read",
            "security.write",
            "knowledge.read",
            "knowledge.register",
        }
    ),
    "intern": frozenset({"project.read", "file.read"}),
}


def canonical_role(role: str) -> str:
    """Return the role name used by the permission matrix."""

    normalized = role.strip().lower()
    return ROLE_ALIASES.get(normalized, normalized)


def permissions_for_role(role: str) -> frozenset[str]:
    """Return a role's permissions, or none for an unknown role."""

    return ROLE_PERMISSIONS.get(canonical_role(role), frozenset())


def role_can(role: str, permission: str) -> bool:
    """Return whether a role is explicitly allowed one operation."""

    return permission in permissions_for_role(role)


def permission_matrix() -> dict[str, list[str]]:
    """Return a serialisable copy of the role-permission matrix."""

    return {
        role: [permission for permission in PERMISSIONS if permission in ROLE_PERMISSIONS[role]]
        for role in ROLES
    }


__all__ = [
    "PERMISSIONS",
    "ROLE_ALIASES",
    "ROLE_PERMISSIONS",
    "ROLES",
    "canonical_role",
    "permission_matrix",
    "permissions_for_role",
    "role_can",
]
