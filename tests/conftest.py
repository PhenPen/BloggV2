import os
from collections.abc import AsyncGenerator


# Setting testing environmental values
#os.environ["DATABASE_URL"] = (
#    "postgresql+psycopg://bloguser:blogpass@localhost/#test_blog"
#)

# The above database URL had some issues, so I used the one below 
#"This error occurs because psycopg (v3) in async mode on Windows is incompatible with Python's default ProactorEventLoop. It requires the SelectorEventLoop instead."
# Gemini said the comment above
# Link to gemini chat : https://share.gemini.google/TCQKW6moRg2z


#os.environ["DATABASE_URL"] = (
#    "postgresql+psycopg://bloguser:blogpass@localhost/#test_blog"
#)

# Changed the localhost to 127.0.0.1, because that localhost takes more time to load up on windows because it would try to resolve to IPv6 first before IPv4, but using 127.0.0.1, makes windows know that it is IPv4

os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://postgres:postgres@127.0.0.1/test_blog"
)  # Changed owner and password to mine
os.environ["AWS_BUCKET_NAME"] = "test-bucket"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"



## Dummy S3/AWS Credentials
os.environ["S3_ACCESS_KEY_ID"] = "testing"
os.environ["S3_SECRET_ACCESS_KEY"] = "testing"
os.environ["S3_REGION"] = "us-east-1"

os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# You might be wondering why we duplicated the two pieces of code above, well, our app uses the first piece of code, that is one that pydantic settings would read from, however, BOTO3 SDK has hardcoded variables, that we would need to set, so we would set both just to be sure

# So we would set the values that our testing app would use, and then to avoid any issues, of BOTO SDK using another thing, we would set the AWS BOTO hardcoded variables too


# NOTE : All the environ values that are above should match what is in our .env file so that it would override it 

# Imports

import boto3
import pytest
from httpx import ASGITransport, AsyncClient
from moto import mock_aws
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

from database import Base, get_db_session
from main import app


# You would notice that some functions are synchronous and the others are asynchronous, we already know that async is used when a task is taking time , and is not using the CPU.
# So for our first function, we left it as a sync function because it only returns the string "asyncio" and it doesn't do anything
# for the second function,def test_engine(), that remains sync too because we are just creating the engine, it just acts as a place holder for engine, but we aren't doing anything with the engine. It's just like saying , this is the description for the engine you would use
# for the third function, which is async setup_database, we used async for that, that is because we are using the starting and closing the engine, which would be take some time. You can also we that we passed in await , which states that it is an async function 

pytest_plugins = ["anyio"]   # so this is the default way of telling pytest the plugin in that it should use

# Then since we want to use anyio as our pytest plugin, we would need to set a fixture that will return the async library that anyio would use

# anyio_backend is a hardcoded fixture that would be used to set what async library we would use, and it must be exactly "anyio_backend" not another name or word

# A fixture in pytest, is a basically a function but the difference is that , pytest can't recognize a normal function, so we use the decorator @pytest.fixture, to tell pytest, this function is for you

# scope = session, is telling pytest to use the fixture for the entire round of tests, we could either use fixture test by test, that is use it for a test and then the value could change , but instead we are setting it to session ,so we would use it for the entire round of test from the beginning to the end 

@pytest.fixture(scope ="session")
def anyio_backend():
    return "asyncio"


# Also, we would avoid our tests touching our development or production database, tests should be separate and have it's own resources (one of the reasons, why we configured environmental variables above)

# However, the resources should be similar, for example, if we have a postgresql database named A, we shouldn't use that database A but instead create a new similar postgresql database and use it

@pytest.fixture(scope="session")
def test_engine() -> AsyncEngine:
    database_engine = create_async_engine(
        os.environ["DATABASE_URL"], 
        poolclass=NullPool,  # NullPool to avoid connection pools
        )
    return database_engine

# so we would start by creating the engine to be used, a test engine, we would create it using our test database url (and the test database should be created already), then we give it a poolclass of NullPool, because we don't want a connection pool to be used

@pytest.fixture(scope="session")
async def setup_database(test_engine : AsyncEngine):

    """ Function to setup database , database is created and the tables are created and dropped immediately.

    Note that this is not the main session generator, but this just setup creation and teardown of our tables"""

    # Startup
    # Used a context manager, to trigger open for the engine, which gives the connection, that we can use to run queries
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # This should create all tables

    yield 

    # Shutdown

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)  # Drops all tables but database would still exist

    await test_engine.dispose()  # This would dispose of the engine, turns shutting down the test_engine

# I was confused because I saw this line, `test_engine.connect()` , connect is used to create the connection without doing anything, while `.being()`does the connection and starts using the connection by creating a transaction, so `.begin()` is normally preferred so as do everything at once I think


# In a database, there is a connection, a session, transaction...

@pytest.fixture           # We didn't use scope="session" because we want it to run for a function not the entire function
async def db_session(test_engine : AsyncEngine, setup_database):

    # I think the setup database acts as the session factory, Though I feel that would be wrong.
    # Also, I don't think we would use the setup_database, because we would create a session factory here too
    # The reason why we passed in setup_database, so that pytest would run the setup_database before the transaction is ran , basically we would want to create our tables before performing transactions , so we are initializing that

    # However, I thought that arguments passed into a function are not initialized unless it had parenthesis , and that's a bit of why we used Depends for current_user and also parameters in as arguments in a function have the same memory , so changing it later affects the initial state or is this different because it is pytest ?
    # And yes, pytest normally goes through the parameters and if it seems an argument that as the same name as a pytest fixtures, it would execute that 

    # So the setup_database is ran, and then the create tables is ran, however, drop tables is not ran immediately because the yield keyword tells the setup_database yield control back, so we would run the db_session function and then when it is done we would return back to the setup_database and drop the tables.
    # Weird how ,it seems to be like a decorator

    conn = await test_engine.connect()
    trans = await conn.begin()   # why start the transaction, when it isn't going to be used till the transaction is closed and the sessionmaker bind to the connection not the engine

    test_session_factory = async_sessionmaker(
        bind = conn,   # In my original database file, I would bind to the engine, but here we are binding to the connection, why ?
        # So , were binding to the connection because we want only that connection to be used for it, If we mapped to an engine, then the engine can serve out multiple connections, which is wrong for transactional rollback
        class_= AsyncSession,
        expire_on_commit= False,
        join_transaction_mode="create_savepoint",     # This parameter is the one that overrides the db.commit() and instead of committing, we would set this parameter so it creates a save point instead, making it seem like it committed(saved to database) but we just created a save point so we can revert back to it
    )


    async with test_session_factory() as session:
        try: 
            yield session   # In my original database file, we only yield session, we didn't close the session or close thr transaction or the connection
            # However, we did that because connection is automatically handled but in test, it is better to reverse every change we have done by closing them in the order we did them, that is why we closed the session, transaction then the connection 

        finally :
            await session.close()
            await trans.close()
            await conn.close()



# For some weird reason , this function is not session based but function based
# The reason why the scope for this function is not session based is because it is better to run every test with a test bucket afresh , so every test function , starts with a clean bucket
@pytest.fixture
def mocked_aws():
    # with mock_aws() as mock :  # This was my initial line but it seems the "as mock" was needed as it was not used
    with mock_aws():
        #s3 = boto3.client("s3",region_name="us-east-1")

        # The line above is the Corey Line, I dunno why but I felt it was better to call it from environ instead of hard coding it
        s3 = boto3.client("s3",region_name=os.environ["S3_REGION"])
        s3.create_bucket(Bucket=os.environ["AWS_BUCKET_NAME"])

        yield s3  # Yield is used to return the s3 object without stopping the fixture

# The reason why def mocked_aws is sync is because boto3 calls are synchronous, because it actually performs an action in create bucket, but boto3 is synchronous so we leave it at that


## Client Fixture
@pytest.fixture
async def client(
    db_session: AsyncSession,
    mocked_aws,
) -> AsyncGenerator[AsyncClient]:

    async def override_get_db():  # function that returns the db session, no need to worry about the () as pytest would find the function for us and run it by itself
        yield db_session  # it yields db_session, it keeps handing those out when

    app.dependency_overrides[get_db_session] = override_get_db
    # The line above is what is used to change the mapping, so that whenever get_db_session is called, override_get_db would be used instead.
    # FastAPI has an internal dictionary and if you remember, we get_db_session uses Depends and is mapped, so now instead of using the actual mapping, this would override it

    # Seems the AsyncClient would require a form of transport, so we would use ASGITransport for that
    # ASGITransport is a type of transport for talking to ASGI apps, ASGI stands for asynchronous server gateway interface
    # ASGITransport is also used because we want to avoid talking 
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",     # The base url is for ?
        # The base url is used because HTTPX requires it and so when we are writing other test urls , we would write them relative to this base_url
        # so it becomes , "http://test/{test_name}" where the test_name placeholder would be replaced by the name of the test
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


## Auth Helpers
async def create_test_user(
    client: AsyncClient,
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = "testpassword123",
) -> dict:
    response = await client.post(
        "/api/users",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, f"Failed to create user: {response.text}"
    return response.json()


async def login_user(  
    client: AsyncClient,
    email: str = "test@example.com",
    password: str = "testpassword123",
) -> str:
    response = await client.post(
        "/api/users/token",
        data={    # Note that here we didn't use json, unlike the first auth helper function, this is because this route uses a oauth2 form data form, and if we use json for that, the route/test would fail, so we would use the parameter data instead of json
            "username": email,
            "password": password,
        },
    )
    assert response.status_code == 200, f"Failed to login: {response.text}"
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:    # Returns and compares the authorization header
    return {"Authorization": f"Bearer {token}"}

