from __future__ import annotations

from datetime import datetime, UTC
from sqlalchemy.types import String, DateTime, Integer, Text
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship


from database import Base   

class User(Base) :
    __tablename__ = "users"

    id : Mapped[int] = mapped_column(Integer,primary_key=True, index=True)
    username : Mapped[str] = mapped_column(String(50),nullable=False, unique=True)
    email : Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    password_hash : Mapped[str] = mapped_column(String(200),nullable=False)    # Added Password Hash , Note that we should never add passwords to the database and only add password hashes 

    # We used Mapped Str for the password because 200 characters should be enough to contain the hash 
    image_file : Mapped[str | None] = mapped_column(String(200), nullable=True,default=None)


    posts : Mapped[list[Post]] = relationship(back_populates="author", cascade='all, delete-orphan')

    # reset_tokens : Mapped[PasswordResetToken] = relationship(back_populates="user") # I did this 
    reset_tokens : Mapped[list[PasswordResetToken]] = relationship(back_populates="user", cascade="all, delete-orphan") # Corey did this
    # Why a list of tokens, why not one token or so ?


    # Came back to add cascade so I can cascade delete a user posts , which basically means deleting all a user post 

    # We added all and delete-orphan , why delete-orphan 

    # Note that we only added cascade for the attribute in the User table and not in the post table, I think this is because we can only cascade delete through the User.
    # Deleting all users through a post sounds dumb asf 

    @property
    def image_path(self) -> str :
            if self.image_file:
                return f'/media/profile_pics/{self.image_file}'
            return "/static/profile_pics/default.jpg"


# I used a property decorator, I kinda get the concept but I think I will have to study classes in general again, it seems more easy now 

# The type annotation is different too, I just noticed that, it seems the type annotations for functions are different from variables
# Variables   >> AGE : int = 23
# Function    >> def func() -> :

# In the function, we can't use : as with the variable, so we use a dash and a greater than arrow



# The explanation you provided about `back_populates` in SQLAlchemy relationships is quite detailed
# and accurate. Let me summarize it for you:
# still confused about backpopulates # Finally learnt backpopulates but I think learning relationship in SQL would help with this as stuffs like one way relationship, and other types comes up

# However, back to backpopulates is a python (not sure if it is originally python but I think it is for the orm) way of showing a relationship or something points back to something
# first of all, since there is no mappedcolumn function, no column is created in the SQL database, so if you check the database for the users table (Class User), we would only see id, username, email and image_file as the column attributes, the same thing applies to the posts table, no mapped column for the author , means SQL doesn't create it , so it only has columns for id, title, content, user_id and date_posted
# the relationship, is just python way of saying something is the same with another, In the Class User (users table), there is a property of posts, now instead of always trying to add the person post to the person object, we can simply link it up so python updates it automatically
# Using posts : Mapped[list[Post]] = relationship(back_populates='author')
# we are saying the posts property under the class User is same or linked to the Class Post with the property author
# The list in list[Post] doesn't matter as python we digger deeper until it finds the variable


# We also do the same in the Post Class, if we only linked it from the User class, we would have a "one way relationship" (learn that from SQL) but we link it together in both places so they both update or can be updated from anywhere
# So author : Mapped[User] = relationship (back_populates = 'posts')

# so since author is under the Class Post, it goes or looks like this
# the author property under Class post is linked to the posts property under the Class User


# will have to learn SQL Joins # learnt it, it wasn't that hard
# will have to learn datetime # learnt it, it wasn't that hard
# still confused about index and what it does 



# Note that in ln 18, we called post before creating it (Mapped[list[Post]]), in python , this is called a forward reference and in python versions after or equal to 3.14, this doesn't matter but in earlier versions, we would have to import annotations from __future__ as we did on line 1 to fix this issue.
# It also recommended to include the ln 1 import for backward compatibly especially in older python version or codes

class Post(Base):
    __tablename__ = "posts"

    id : Mapped[int] = mapped_column(Integer,primary_key=True, index=True)
    title : Mapped[str] = mapped_column(String, nullable=False)
    content : Mapped[str] = mapped_column(Text, nullable=False)
    user_id : Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index= True)

    likes : Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    date_posted : Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda : datetime.now(UTC))

    # What the date_posted is saying, it has a type of datetime which is aware not naive, it is aware because the timezone is set to True, and then we set a default value with a lambda function that always gets the current date and time based on the UTC

    # As for ln 33, the ForeignKey("users.id") I dunno if that is correct, there is a class of Users but at that isn't it meant to be Users.id not user.id, let's observe for now though

    # Fixed and answered the question for ln 55, the users.id is from the table name, the one we gave the table using __tablename__ and not the Class name, so it is users not Users


    author : Mapped[User] = relationship(back_populates="posts")

# In a database, instead of searching everywhere, Index helps to find things easier, Just like the index in a textbook




# We would then create a new model for storing our PasswordResetTokens, We use a database to track the tokens and see it's state
# Basically, two conditions
# - Whether token has been used (We can't invalidate JSON tokens even if it has been used but hasn't expired)
# - Whether the token has expired 

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  #It's String(64) because the function producing the token hash must always be 64 characters, it could be a different number for another API but for this API, we standardized 64 characters

    # Also we are storing the hash of the token , not the token itself, and this is often good practice for security reasons
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    user: Mapped[User] = relationship(back_populates="reset_tokens")