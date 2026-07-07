from typing import Annotated

from fastapi import APIRouter, Depends,status
from fastapi import HTTPException as FastapiHttpException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession



import models
from database import get_db_session
from schemas import PostResponse, UserCreate, UserResponse, UserUpdate


# We import only the modules needed for users, we also added the import APIRouter
# Not sure why we imported PostResponse so far though 

router = APIRouter()

# we left the decorator below empty because it has the same route as our base route for users
# Now every of our routes have `/api/users` so we remove it and put it in our app instance in our main.py 
# while if we leave an empty space, it would assume that it is the default or base route endpoint, but if we include a route in the router, it will get added up eg lets say we include {user_id}, then it would become `/api/users` + `{user_id}`, and would become `api/users/{user_id}`

@router.post("",response_model=UserResponse,status_code=status.HTTP_201_CREATED)
async def create_user(user :UserCreate, db_session : Annotated[AsyncSession,Depends(get_db_session)]):
    result = await db_session.execute(select(models.User).where(models.User.username == user.username))

    existing_user = result.scalars().first()

    if existing_user:
        raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail='User already exists')
    
    result = await db_session.execute(select(models.User).where(models.User.email == user.email))

    existing_email = result.scalars().first()

    if existing_email:
        raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail='Email already exists')
    
    new_user = models.User(username = user.username, email = user.email)
    db_session.add(new_user)
    await db_session.commit()
    await db_session.refresh(new_user)

    return new_user


# We used status code 201 because we are creating a new object 
# We used UserResponse as the response_model because that what the API would respond with 
# We used user : UserCreate because the user must be of type UserCreate

# So basically, we the request must pass the UserCreate pydantic schema while the API responds with UserResponse 

# db_session : Annotated[Session, Depends(get_db_session)]

# db_session is a database object that must be of type Annotated, Annotated in this context means the db must be of type Session and it is gotten from Depends(get_db_session).

# Depends is a fastAPI function ,that runs the function put inside it and gives back the output 

# the create_user function takes 2 parameters user which is of type hint UserCreate (Pydantic Validation) and db_session, which is the database session, which must be of type Session and will be gotten from the Depends (get_db_session)

#  ??? Why did we use result.scalars().first() instead of result.scalar(), because I think result.scalar().

# we then create an instance of the User class by doing  models.User(username=user.username, email = user.email) and pass that into a variable , (ln 113) , check your obsidian classes note too

# Still baffled about the concept of db_session.add(new_user), db_session.commit() and db_session.refresh(new_user)







@router.get("/{user_id}", response_model=UserResponse)
async def user(user_id : int, db:Annotated[AsyncSession, Depends(get_db_session)]):

    result = await db.execute(select(models.User).where(models.User.id == user_id))

    existing_user  = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return existing_user


@router.get('/{user_id}/posts',response_model= list[PostResponse])
async def user_post_page(user_id : int, db: Annotated[AsyncSession, Depends(get_db_session)]):

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.user_id == existing_user.id).order_by (models. Post.date_posted.desc()))
    # result = db.execute(select(models.Post).where(models.Post.user_id == user_id))

    # Note that lines above (commented and not commented ) both give the same result
    # the second line is from corey schafer, why the first is from me, I used the first because it is what I have learnt on my own

    posts = result.scalars().all()

    return posts 

    

# Note that after updating routes, we need to update some templates
# I changed how we display the date and author, recall that we set our API to return ISO 8601 date format .
# We would also change src="{{ url_for('static', path='profile_pics/default.jpg') }}" in the route as you can see that is hard coded, to the dynamic way of retrieving images.  
# Since post is an object with attributes, instead of using url_for, we can just call it directly, see home.html and check the difference between the commented out src and the current main src 


# Also I some of the content dictionary is a different across functions, so I check and found out I used posts when I was returning a list of posts , Example , returning all posts and post for a single post, Example , returning a single post



@router.patch("/{user_id}",response_model=UserResponse, name = 'update_user_partial')
async def update_user_partial(user_id :int, updated_user : UserUpdate, db: Annotated[AsyncSession, Depends(get_db_session)]):
   

    # We keep this line of code because we want it to check if the user trying to change exist, we can't change a user that doesn't exist 

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "User not found")
    

    # def update_post_full and def update_post_partial are the same , just that we removed the check for user_id.
    # We do not want someone changing ownership of a post through partial update (patch)


    # We then check if the username changed, if it changed we check if that username already exists so we won't override another person email or cause the database to return an error as every username would have to be unique 
    if updated_user.username is not None and updated_user.username != existing_user.username : 
        result = await db.execute(select(models.User).where(models.User.username == updated_user.username))
        existing_username = result.scalars().first()

        if existing_username:
            raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail = "Username already exists")
        

    # We then check if the email changed, if it changed we check if that email already exists so we won't override another person email or cause the database to return an error as every email would have to be unique 
    if updated_user.email is not None and updated_user.email != existing_user.email : 
        result = await db.execute(select(models.User).where(models.User.email == updated_user.email))
        existing_email = result.scalars().first()

        if existing_email:
            raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail = "Email already registered")
        

    # using the model_dump(exclude_unset = True) is just saying remap the values , remap the attributes with None (wasn't filled because it's optional) to it's former values and the remap the attributes with the new values to the new values 
    # Basically, only the title of the post got changed, it would change the title attribute to the new value and the remaining attributes would remain the same instead of becoming None
    # Note that it's exclude_unset that does that, model_dump is just like json dumps, we are dumping the attributes and their values into a dictionary but exclude_unset does the mroutering of attributes to new values and if new values not exist, mroutering to old values
    updated_user_dict = updated_user.model_dump(exclude_unset= True)

    # the `updated_post_dict` is going to be of type hint dict

    # setattr sets the named attribute on the given object to the specified value.
    # setattr(x, 'y', v) is equivalent to x.y = v


    for field, value in updated_user_dict.items():
        setattr(existing_user, field, value)

    # No need for db.add as the post already exists in the database, we are just changing it , so we just commit and refresh



    await db.commit() # Also, just committing, won't it clash with the posts that already had the same values
    # don't forget brackets for the commit (db.commit())
    await db.refresh(existing_user)  # I think I didn't add attribute name here because we aren't using the relationship here (Like for post, we used the relationship to get author but this is users)
    return existing_user


@router.delete('/{user_id}',status_code=status.HTTP_204_NO_CONTENT,name = 'delete_user')
async def delete_user(user_id : int, db: Annotated[AsyncSession, Depends(get_db_session)]):

    # check for if user exists
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "User not found")
    
    await db.delete(existing_user)
    await db.commit()


