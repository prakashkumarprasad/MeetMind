# Tests for workspace membership access control (404 vs 403, authentication).

"""
Covers the IDOR fix in app/api/deps.py::get_workspace_membership.

A user must get 404 (not 403) when hitting a workspace they don't
belong to — 403 would confirm the workspace_id exists and just isn't
accessible, letting an attacker enumerate valid workspace IDs. 404 makes
"doesn't exist" and "not yours" indistinguishable from the outside.
"""
import uuid

def test_member_can_access_own_workspace(client, make_user):
    user, workspace, headers = make_user("owner@example.com")

    response = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "hi"},
        headers=headers,
    )

    assert response.status_code not in (403, 404)

def test_non_member_gets_404_not_403(client, make_user):
    _, _, headers_a = make_user("usera@example.com")
    _, workspace_b, _ = make_user("userb@example.com")

    response = client.post(
        f"/api/v1/workspaces/{workspace_b.id}/chat",
        json={"question": "hi"},
        headers=headers_a,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"

def test_nonexistent_workspace_also_gets_404(client, make_user):
    _, _, headers = make_user("userc@example.com")
    fake_workspace_id = uuid.uuid4()

    response = client.post(
        f"/api/v1/workspaces/{fake_workspace_id}/chat",
        json={"question": "hi"},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"

def test_unauthenticated_request_gets_401_not_404(client, make_user):
    _, workspace, _ = make_user("userd@example.com")

    response = client.post(
        f"/api/v1/workspaces/{workspace.id}/chat",
        json={"question": "hi"},
    )

    assert response.status_code == 401
