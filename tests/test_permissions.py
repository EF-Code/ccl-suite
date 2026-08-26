from permissions import canonical_role, permission_matrix, permissions_for_role, role_can


def test_permission_matrix_lists_four_roles_and_explicit_operations() -> None:
    matrix = permission_matrix()

    assert set(matrix) == {"administrator", "supervisor", "staff", "intern"}
    assert "user.manage" in matrix["administrator"]
    assert "approval.decide" in matrix["supervisor"]
    assert "file.upload" in matrix["staff"]
    assert matrix["intern"] == ["project.read", "file.read"]


def test_legacy_roles_are_scoped_aliases() -> None:
    assert canonical_role(" member ") == "staff"
    assert canonical_role("reviewer") == "supervisor"
    assert role_can("member", "file.upload") is True
    assert role_can("intern", "file.upload") is False
    assert permissions_for_role("unknown") == frozenset()
