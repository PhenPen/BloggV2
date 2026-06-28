from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, EmailStr


class UserBase(BaseModel):
    username : str  = Field(min_length=1, max_length=50)
    email : EmailStr = Field(max_length = 120)
    # No need to put min_length in email because EmailStr already validates that for us 

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int 
    image_file : str | None
    image_path : str

class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    username : str | None  = Field(min_length=1, max_length=50, default= None)
    email : EmailStr | None = Field(max_length = 120, default= None)
    # No need to put min_length in email because EmailStr already validates that for us 
    image_file : str | None  = Field(min_length=1, max_length=200
    , default= None)

    # Wanted to include a property decorator to create image_path and inside the image_path, will do if image_file is None and so onc, but I didn't know how to complete the logic and I think exclude_unset = True, would take care of the None and give back the old value so that issue should be taken care of 


class PostBase(BaseModel):
    title: str = Field(min_length=1,max_length=100,description="Title of post(Min of 1 letter and and maximum of 100)")
    content: str = Field(min_length=1)
    # author: str = Field(min_length=1,max_length=50,description="Author of post(Min of 1 letter and and maximum of 100)")

    # Removed or commented line 23 because we can get the author from the UserResponse class, which shows the author and everything about them.
    # Recall that we did User.posts = Post.author (ln 20 in schemas.py)

class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)
    
    id :int 
    user_id : int 
    date_posted :datetime  # Using a type hint of datetime automatically serializes the date into a ISO8601 format instead of str , that we won't know it is a datetime object 
    author : UserResponse


class PostCreate(PostBase):
    user_id : int #TEMPORARY 


# Now we are creating a schema for updating a resource

# We have two types of update : Put (Full update) and Patch (Partial Update)
# For full update, we can just re-use our PostCreate schema as we would replace everything inside 
# For partial update, we would have to create another schema that uses optional fields instead of PostCreate that the Fields must contain something

# NOTE THAT PostUpdate inherits from BaseModel and not from PostBase, if we inherited from  PostBase, we would have some issues as we would inherit title and content that we want to change from PostBase but the title and content would have the type hint of str but since we are changing things partially, we would want our type hint to be str or None, as a field can be filled while the other remains None.
# But we can't change the inherited type hint from PostBase, so we create another class and create title and content attributes with the type hint str | None 


class PostUpdate(BaseModel):
    title: str | None= Field(default=None, min_length=1,max_length=100,description="Title of post(Min of 1 letter and and maximum of 100)")
    content: str | None = Field(default=None, min_length=1)


# I think that PostUpdate would be same with PostCreate, but for PostUpdate PATCH it would have an None type hint too for optional values and we must have a default value in case that field is not filled in 
# While we can just use PostCreate for PostUpdate PUT CRUD
# We would implement cascade delete, which is when we delete a user, we delete all his posts along with him


# We also didn't include user_id in the PostUpdate, this is because it is considered wrong to change ownership of an object through a PATCH CRUD. Example : Changing ownership of a post through a PATCH is considered wrong

