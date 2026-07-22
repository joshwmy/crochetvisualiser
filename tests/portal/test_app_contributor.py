import io

from PIL import Image

from crochet_reconstruction.portal import services
from tests.portal.conftest import extract_csrf


def _jpeg_bytes(color: tuple[int, int, int] = (10, 200, 30)) -> bytes:
    img = Image.new("RGB", (600, 600), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_invalid_invitation_token_shows_error(app_client) -> None:
    response = app_client.get("/invite/not-a-real-token")
    assert response.status_code == 200
    assert "not recognised" in response.text


def test_expired_invitation_is_rejected(app_client, db) -> None:
    invitation, token = services.create_invitation(db, label="x", expiry_days=30)
    invitation.expires_at = services._now().replace(year=2000)
    db.commit()

    response = app_client.get(f"/invite/{token}")
    assert "expired" in response.text


def test_valid_invitation_shows_start_form(app_client, invitation_token: str) -> None:
    response = app_client.get(f"/invite/{invitation_token}")
    assert response.status_code == 200
    assert "Start my submission" in response.text


def test_full_contributor_flow_reaches_confirmation(app_client, invitation_token: str) -> None:
    response = app_client.get(f"/invite/{invitation_token}")
    csrf = extract_csrf(response.text)
    response = app_client.post(
        f"/invite/{invitation_token}/redeem",
        data={"display_identifier": "Tester", "csrf_token": csrf},
    )
    assert "/consent" in str(response.url)
    project_ref = str(response.url).split("/")[-2]

    csrf = extract_csrf(response.text)
    response = app_client.post(
        str(response.url),
        data={
            "csrf_token": csrf,
            "owns_photographs": "true",
            "privacy_notice_accepted": "true",
            "attribution_preference": "anonymous",
        },
    )
    assert "/details" in str(response.url)

    csrf = extract_csrf(response.text)
    response = app_client.post(
        str(response.url), data={"csrf_token": csrf, "project_category": "beanie"}
    )
    assert "/materials" in str(response.url)

    csrf = extract_csrf(response.text)
    response = app_client.post(str(response.url), data={"csrf_token": csrf})
    assert "/images" in str(response.url)

    csrf = extract_csrf(response.text)
    for image_type in ["front", "crown_top", "stitch_macro"]:
        response = app_client.post(
            f"/contributor/project/{project_ref}/images/upload",
            data={"csrf_token": csrf, "image_type": image_type},
            files={"file": (f"{image_type}.jpg", _jpeg_bytes(), "image/jpeg")},
        )
        csrf = extract_csrf(response.text)

    response = app_client.post(
        f"/contributor/project/{project_ref}/submit", data={"csrf_token": csrf}
    )
    assert "confirmation" in str(response.url)
    assert project_ref in response.text


def test_details_form_preserves_entered_values_on_validation_error(
    app_client, invitation_token: str
) -> None:
    response = app_client.get(f"/invite/{invitation_token}")
    csrf = extract_csrf(response.text)
    response = app_client.post(
        f"/invite/{invitation_token}/redeem",
        data={"display_identifier": "Tester", "csrf_token": csrf},
    )
    project_ref = str(response.url).split("/")[-2]

    csrf = extract_csrf(response.text)
    app_client.post(
        str(response.url),
        data={
            "csrf_token": csrf,
            "owns_photographs": "true",
            "privacy_notice_accepted": "true",
        },
    )

    response = app_client.get(f"/contributor/project/{project_ref}/details")
    csrf = extract_csrf(response.text)
    # project_category omitted entirely -> required field missing -> validation error
    response = app_client.post(
        f"/contributor/project/{project_ref}/details",
        data={"csrf_token": csrf, "name_or_description": "My distinctive beanie"},
    )
    assert "My distinctive beanie" in response.text


def test_csrf_rejection_on_consent_submit(app_client, invitation_token: str) -> None:
    response = app_client.get(f"/invite/{invitation_token}")
    csrf = extract_csrf(response.text)
    response = app_client.post(
        f"/invite/{invitation_token}/redeem",
        data={"display_identifier": "Tester", "csrf_token": csrf},
    )
    response = app_client.post(str(response.url), data={"csrf_token": "wrong-token"})
    assert response.status_code == 400


def test_contributor_cannot_access_another_contributors_project(app_client, db) -> None:
    _invitation_a, token_a = services.create_invitation(db, label="a", expiry_days=30)
    _invitation_b, token_b = services.create_invitation(db, label="b", expiry_days=30)

    response = app_client.get(f"/invite/{token_a}")
    csrf = extract_csrf(response.text)
    response = app_client.post(
        f"/invite/{token_a}/redeem", data={"display_identifier": "A", "csrf_token": csrf}
    )
    project_ref_a = str(response.url).split("/")[-2]

    # A fresh client (separate cookie jar) redeems invitation B.
    from fastapi.testclient import TestClient

    client_b = TestClient(app_client.app, follow_redirects=True)
    response = client_b.get(f"/invite/{token_b}")
    csrf = extract_csrf(response.text)
    client_b.post(f"/invite/{token_b}/redeem", data={"display_identifier": "B", "csrf_token": csrf})

    response = client_b.get(f"/contributor/project/{project_ref_a}/review")
    assert response.status_code == 404
