""" File used for not the main database models but for the configuration of how a database connects """


# from sqlalchemy import create_engine
# from sqlalchemy.orm import DeclarativeBase, sessionmaker


from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Since we are converting code from sync to async, we remove the sync imports and convert it into async

from config import settings




# SQLALCHEMY_DATABASE_URL = "sqlite:///./blog.db"
# SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./blog.db"

# Now instead of using the SQLite + the aiosqlite driver, we would use postgres, and instead of hardcoding it here, we set it up in our settings and import from there

SQLALCHEMY_DATABASE_URL =settings.db_url

# We also install a driver for sqlite to know how to use async, this driver is known as 'aiosqlite' and then we change our database url to include it

# database_engine = create_engine(SQLALCHEMY_DATABASE_URL,connect_args={"check_same_thread":False})

# we use create_async_engine instead of create_engine


# database_engine = create_async_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread":False})

# The connect_args was meant for sqlite to avoid using the same thread, but since we are using postgres, we don't need that
database_engine = create_async_engine(SQLALCHEMY_DATABASE_URL)

class Base(DeclarativeBase):
    pass

# 



# To create a object for sessions not the sessions itself
# SessionLocal = sessionmaker(bind=database_engine,autoflush=False)


# Now we change the session_maker to async and instead of auto_flush we use expire_on_commit = False and add another parameter of class_ and give it an argument of AsyncSession
AsyncSessionLocal = async_sessionmaker(bind=database_engine,class_=AsyncSession, expire_on_commit=False) 


# Dunno why they included class_

# expire_on_commit=False is recommended for async because after a commit,
# SQLAlchemy expires all loaded objects. When you access their attributes again,
# SQLAlchemy tries to silently reload them from the database (implicit I/O).
# This doesn't work in async because Python can't `await` a plain attribute access,
# causing a greenlet/MissingGreenlet error.
# Setting this to False keeps objects usable in memory after a commit.



#def get_db_session() :
#    with SessionLocal() as db_session:
#        # don't forget the parenthesis for the SessionLocal, as we are calling it as a function
#        yield db_session

# Then we convert our session maker function or dependency function

async def get_db_session() :
    async with AsyncSessionLocal() as db_session:
        # don't forget the parenthesis for the SessionLocal, as we are calling it as a function
        yield db_session
