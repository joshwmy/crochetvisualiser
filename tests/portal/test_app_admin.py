import io

from PIL import Image

from crochet_reconstruction.physical_validation.trial_matrix import TRIAL_MATRIX, compile_trial
from crochet_reconstruction.portal.models import AdminUser
from tests.portal.conftest import extract_csrf


def _jpeg_bytes(color: tuple[int, int, int] = (10, 200, 30)) -> bytes:
    img = Image.new("RGB", (600, 600), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_pending_list_requires_login(app_client, admin_user: AdminUser) -> None:
    response = app_client.get("/admin/pending")
    assert response.status_code == 200
    assert "/admin/login" in str(response.url)


def test_login_with_wrong_password_fails(app_client, admin_user: AdminUser) -> None:
    response = app_client.get("/admin/login")
    csrf = extract_csrf(response.text)
    response = app_client.post(
        "/admin/login",
        data={"username": "admin", "password": "wrong-password", "csrf_token": csrf},
    )
    assert "Incorrect username or password" in response.text


def test_login_with_correct_password_succeeds(app_client, admin_user: AdminUser) -> None:
    response = app_client.get("/admin/login")
    csrf = extract_csrf(response.text)
    response = app_client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "correct-horse-battery-staple",
            "csrf_token": csrf,
        },
    )
    assert response.status_code == 200
    assert "/admin/pending" in str(response.url)


def test_login_csrf_rejection(app_client, admin_user: AdminUser) -> None:
    response = app_client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "correct-horse-battery-staple",
            "csrf_token": "wrong",
        },
    )
    assert response.status_code == 400


def test_login_rate_limited_after_repeated_failures(app_client, admin_user: AdminUser) -> None:
    # portal_settings fixture sets rate_limit_max_attempts=5.
    last_response = None
    for _ in range(6):
        response = app_client.get("/admin/login")
        csrf = extract_csrf(response.text)
        last_response = app_client.post(
            "/admin/login",
            data={"username": "admin", "password": "wrong", "csrf_token": csrf},
        )
    assert "Too many login attempts" in last_response.text


def _login(app_client) -> None:
    response = app_client.get("/admin/login")
    csrf = extract_csrf(response.text)
    app_client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "correct-horse-battery-staple",
            "csrf_token": csrf,
        },
    )


def test_unauthorized_image_access_is_rejected(app_client, admin_user: AdminUser, db) -> None:
    from crochet_reconstruction.portal import services

    _invitation, token = services.create_invitation(db, label="x", expiry_days=30)
    response = app_client.get(f"/invite/{token}")
    csrf = extract_csrf(response.text)
    response = app_client.post(
        f"/invite/{token}/redeem", data={"display_identifier": "T", "csrf_token": csrf}
    )
    project_ref = str(response.url).split("/")[-2]

    # No admin session yet -> should redirect to login, not serve the image.
    response = app_client.get(f"/admin/projects/{project_ref}/images/1/preview")
    assert "/admin/login" in str(response.url)


def test_admin_review_and_export_flow(app_client, admin_user: AdminUser, db) -> None:
    from crochet_reconstruction.portal import services

    _invitation, token = services.create_invitation(db, label="x", expiry_days=30)
    response = app_client.get(f"/invite/{token}")
    csrf = extract_csrf(response.text)
    response = app_client.post(
        f"/invite/{token}/redeem", data={"display_identifier": "T", "csrf_token": csrf}
    )
    project_ref = str(response.url).split("/")[-2]

    csrf = extract_csrf(response.text)
    response = app_client.post(
        str(response.url),
        data={
            "csrf_token": csrf,
            "owns_photographs": "true",
            "privacy_notice_accepted": "true",
            "research_evaluation_use": "true",
        },
    )
    csrf = extract_csrf(response.text)
    response = app_client.post(
        str(response.url), data={"csrf_token": csrf, "project_category": "beanie"}
    )
    csrf = extract_csrf(response.text)
    response = app_client.post(str(response.url), data={"csrf_token": csrf})

    csrf = extract_csrf(response.text)
    for image_type in ["front", "crown_top", "stitch_macro"]:
        response = app_client.post(
            f"/contributor/project/{project_ref}/images/upload",
            data={"csrf_token": csrf, "image_type": image_type},
            files={"file": (f"{image_type}.jpg", _jpeg_bytes(), "image/jpeg")},
        )
        csrf = extract_csrf(response.text)

    app_client.post(f"/contributor/project/{project_ref}/submit", data={"csrf_token": csrf})

    _login(app_client)

    response = app_client.get("/admin/pending")
    assert project_ref in response.text

    response = app_client.get(f"/admin/projects/{project_ref}")
    csrf = extract_csrf(response.text)
    response = app_client.post(
        f"/admin/projects/{project_ref}/start-review", data={"csrf_token": csrf}
    )
    assert "under_review" in response.text

    csrf = extract_csrf(response.text)
    trial = TRIAL_MATRIX[0]
    pattern = compile_trial(trial)
    response = app_client.post(
        f"/admin/projects/{project_ref}/decision",
        data={
            "csrf_token": csrf,
            "decision": "approve",
            "verified_craft_type": "crochet",
            "verified_project_category": "beanie",
        },
    )
    assert "approved" in response.text

    csrf = extract_csrf(response.text)
    response = app_client.post(
        f"/admin/projects/{project_ref}/link-trial",
        data={
            "csrf_token": csrf,
            "trial_id": trial.trial_id,
            "pattern_fingerprint": pattern.fingerprint,
        },
    )
    assert trial.trial_id in response.text

    # Now the admin CAN view the private image.
    image_id = 1
    response = app_client.get(f"/admin/projects/{project_ref}/images/{image_id}/preview")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"

    export_page = app_client.get("/admin/export")
    csrf = extract_csrf(export_page.text)
    response = app_client.post("/admin/export", data={"csrf_token": csrf})
    assert "Exported 1 project" in response.text


def test_audit_history_visible_on_detail_page(app_client, admin_user: AdminUser, db) -> None:
    from crochet_reconstruction.portal import services

    _invitation, token = services.create_invitation(db, label="x", expiry_days=30)
    response = app_client.get(f"/invite/{token}")
    csrf = extract_csrf(response.text)
    response = app_client.post(
        f"/invite/{token}/redeem", data={"display_identifier": "T", "csrf_token": csrf}
    )
    project_ref = str(response.url).split("/")[-2]

    _login(app_client)
    response = app_client.get(f"/admin/projects/{project_ref}")
    assert "project_created" in response.text
