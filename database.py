""" File used for not the main database models but for the configuration of how a database connects """


from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker



SQLALCHEMY_DATABASE_URL = "sqlite:///./blog.db"


database_engine = create_engine(SQLALCHEMY_DATABASE_URL,connect_args={"check_same_thread":False})

class Base(DeclarativeBase):
    pass

# 



# To create a object for sessions not the sessions itself
SessionLocal = sessionmaker(bind=database_engine,autoflush=False)


def get_db_session() :
    with SessionLocal() as db_session:
        # don't forget the parenthesis for the SessionLocal, as we are calling it as a function
        yield db_session
