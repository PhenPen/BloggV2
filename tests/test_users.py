import pytest
from  httpx import AsyncClient

from tests.conftest import auth_header, create_test_user, login_user

from io import BytesIO  # This would be probably for upload of profile pictures
from pathlib import Path # For file paths
from unittest.mock import AsyncMock, patch


@pytest.mark.anyio
async def test_create_user_validation_error(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={
            "username": "testuser",
        },  # we didn't pass in all the parameters needed so pydantic should give us a validation error
    )

    assert response.status_code == 422
    assert "email" in response.text
    assert "password" in response.text


@pytest.mark.anyio
async def test_create_user_duplicate_email(client: AsyncClient):
    await create_test_user(client)  # create a user with default parameters here

    response = await client.post(
        "/api/users",
        json={
            "username": "different_user",
            "email": "test@example.com",  # we try to create another user but we use the default email so now it becomes two users with the same email which is supposed to give us an error
            "password": "password123",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


@pytest.mark.anyio
async def test_create_user_success(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepassword123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "image_path" in data
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.anyio
async def test_upload_profile_picture(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    test_image_path = Path(__file__).parent / "test_image.jpg"
    image_bytes = test_image_path.read_bytes()

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(image_bytes), "image/jpeg")},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["image_file"] is not None  # We would check it is not None to be sure the upload went
    assert data["image_file"].endswith(".jpg")
    assert "s3" in data["image_path"]   # since it is an s3 URL, it should contain s3 in it

    # After this test, we would check the s3 bucket itself to check if the upload entered the bucket

    s3_objects = mocked_aws.list_objects_v2(Bucket="test-bucket")
    assert "Contents" in s3_objects   # check for contents in s3 objects
    assert len(s3_objects["Contents"]) == 1 # check how many items are there and it should be 1, since we sent it once
    assert s3_objects["Contents"][0]["Key"].endswith(data["image_file"])  # then we check if ends with the image file name in the response   # Still need to revise this function


@pytest.mark.anyio
async def test_forgot_password_sends_email(client: AsyncClient):
    await create_test_user(client)

    with patch(  # we imported this from unittmock, dunno why 
        "routers.users.send_password_reset_email",
        new_callable=AsyncMock,
    ) as mock_send:
        response = await client.post(
            "/api/users/forgot-password",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 202
        mock_send.assert_awaited_once()    # Check to see if it was awaited once too, not sure why 
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["to_email"] == "test@example.com"
        assert call_kwargs["username"] == "testuser"
        assert "token" in call_kwargs