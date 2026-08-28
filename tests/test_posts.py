import pytest
from  httpx import AsyncClient

from tests.conftest import auth_header, create_test_user, login_user   # We imported this because we didn't use pytest.fixture decorator on the helper functions 

# We also didn't import the rest because they are fixtures, and pytest automatically imports any fixture in conftest into any test files

@pytest.mark.anyio        # The anyio seems to be because of the pytest plugins but what is a pytest mark 
async def test_get_posts_empty(client : AsyncClient):  # Nothing is passed into the client but because pytest already passed it in, recall that we gave the client function a pytest.fixture decorator
    # We just gave it a type hint of AsyncClient so that pylance would know what the object is

    response = await client.get("/api/posts")   # Never forget the first slash (/)

    assert response.status_code == 200  # Check for status code

    data = response.json()  # Converts it from JSON, which is the normal sending language of APIs to a dict

    # Then we check our post schemas to know what this route returns and we check for that
    # If you remember, we switched from the normal posts schema to the PaginatedPostResponse schema when we set up pagination.
    # So we would check for every of that schema class attribute

    assert data["posts"] == []   # Since we are starting afresh, no posts should exist therefore we should have an empty list
    assert data["total"] == 0    # Since we are starting afresh, and no post exist currently, then total should be 0
    assert data["has_more"] is False  # Since we are starting afresh, has_more should be false as there isn't more posts to load

    # for the assert data["has_more"], note that the pythonic way is assert not data["has_more"] instead of what we wrote above but both works, for assert, we are just trying to find a truth value

    # NOTE that when comparing bool, using `is` is the recommended way instead of ==, so is False , is True is better that == False, == True

    # I would have asserted for skip and limit, but I think those two uses the values hardcoded in the settings or configuration, and we aren't importing settings into this file 


# So now, our aim is to find errors, one of the ways I thought of doing that, was to remember status codes, and then try to find this that would trigger that error code.
# For example, I know that a status code of 404 will be triggered when a post doesn't exist so I would write a test for that
# I also know, that I can see all posts without been authenticated but before I can create a post I would have to be authenticated
#  I know that before I edit a post, I would have to be authorized to do that( I can't change another person post because I'm not authorized to do so)


@pytest.mark.anyio
async def test_get_posts_not_found(client : AsyncClient):

    response = await client.get("/api/posts/999") # You might be asking , what if we have 1000 posts, would that post not be found ? Well, if you remember our function and session scoped functions, we set the database session function to be of scope function, that is it doesn't remain for a full session and always restarts when a new function is called.

    # However, we set our database to be session based, that is we are using that same database , but the session database is different, so with every session, the things in the database are discarded because of our transactional rollback pattern that we used save points instead of committing and we always have a fresh empty database 

    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found" 


@pytest.mark.anyio
async def test_create_new_post(client : AsyncClient):

    response_user_create = await create_test_user(client)
    response_user_login_token = await login_user(client)
    response_user_auth_headers = auth_header(token = response_user_login_token)

    response = await client.post("/api/posts",
                json={"title" : "First test Post",
                      "content" : "This is the first test post"}, 
                headers=response_user_auth_headers)

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == "First test Post"
    assert data["content"] == "This is the first test post"
    assert "id" in data
    assert data["user_id"] == response_user_create["id"]
    assert "date_posted" in data
    assert data["author"]["username"] == "testuser"


@pytest.mark.anyio
async def test_create_post_unauthorized(client: AsyncClient):
    response = await client.post(
        "/api/posts",
        json={"title": "Test Post", "content": "Test content"},
    )  # Notice that no authorization header was passed in, so we won't be authorized

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"



@pytest.mark.anyio
async def test_update_post_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    response = await client.post(
        "/api/posts",
        json={"title": "Original Title", "content": "Original content"},
        headers=headers,
    )
    post_id = response.json()["id"]  # we would get the id of the post we just created through this 

    response = await client.patch(  # Then we update or patch the post here
        f"/api/posts/{post_id}",
        json={"title": "Updated Title"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["content"] == "Original content"


@pytest.mark.anyio
async def test_update_post_wrong_user(client: AsyncClient):

    # Create first test user
    await create_test_user(client, username="user1", email="user1@example.com")
    token1 = await login_user(client, email="user1@example.com")

    response = await client.post(  
        "/api/posts",
        json={"title": "User 1's Post", "content": "Only user 1 can edit this"},
        headers=auth_header(token1),
    )
    post_id = response.json()["id"]   # Get post id from here

    # Create second test user
    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.patch(  # Attempt to patch first user post with second user login
        f"/api/posts/{post_id}",
        json={"title": "Hacked Title"},
        headers=auth_header(token2),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this post"


@pytest.mark.anyio
async def test_get_posts_with_pagination(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    for i in range(5):   # Use a for loop to send numerous requests to create multiple posts
        response = await client.post(
            "/api/posts",
            json={"title": f"Post {i}", "content": f"Content for post {i}"},
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/posts")   
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5  # We created 5 posts so we would assert the total posts to 5
    assert len(data["posts"]) == 5
    assert data["has_more"] is False

    response = await client.get("/api/posts?limit=2") # then we paginate with a limit of 2, so there would be 3 more posts remaining to be displayed
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 2
    assert data["has_more"] is True

    response = await client.get("/api/posts?skip=2&limit=2") # we paginate with skip and limit, so we check for both 
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 2
    assert data["skip"] == 2
    assert data["limit"] == 2