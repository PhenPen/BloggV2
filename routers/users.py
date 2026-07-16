from typing import Annotated

from fastapi import APIRouter, Depends,status
from fastapi import HTTPException as FastapiHttpException
from sqlalchemy import select, func 
# we imported func so we can write queries that are case insensitive ,basically queries that check for both cases of letters (uppercase and lowercase) ; In a blog or social media website, we would want our usernames to be unique, but while displaying the username in the way the user passed it to us, we would want to convert it to lowercase

from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession



import models
from database import get_db_session
from schemas import PostResponse, UserCreate, UserResponsePublic, UserResponsePrivate, UserUpdate, Token
# Imported UserResponsePublic and UserResponsePrivate instead UserResponse as I changed that 

# Change the response from UserResponse to UserResponsePublic


from datetime import timedelta  # import timedelta so we could add our jwt expiry time here
from fastapi.security import OAuth2PasswordRequestForm 
# OAuth2PasswordRequestForm is used as the input so it could extract the password and username /email for checking 
from auth import hash_password, verify_password, Oauth2_scheme, create_access_token, verify_access_token
# we import our functions for hashing, creating , verifying.
# We also import our oauth scheme 

from config import settings


# We import only the modules needed for users, we also added the import APIRouter
# Not sure why we imported PostResponse so far though 

router = APIRouter()

# we left the decorator below empty because it has the same route as our base route for users
# Now every of our routes have `/api/users` so we remove it and put it in our app instance in our main.py 
# while if we leave an empty space, it would assume that it is the default or base route endpoint, but if we include a route in the router, it will get added up eg lets say we include {user_id}, then it would become `/api/users` + `{user_id}`, and would become `api/users/{user_id}`



# Now for post, when creating a user, we would return the private user response instead of the public response
# NOTE that the private user response also includes the email , which we wouldn't show under normal circumstances but we are creating the user and we have to return the user full details
@router.post("",response_model=UserResponsePrivate,status_code=status.HTTP_201_CREATED)
async def create_user(user :UserCreate, db_session : Annotated[AsyncSession,Depends(get_db_session)]):
    # result = await db_session.execute(select(models.User).where(models.User.username == user.username))

    # Now I tweaked the db query a bit to always check for lower case, that is, it converts our Uppercase and all to lowercase, we wouldn't want a scenario where by ones'username is "Derz" and another "derz", we want all to be unique and that includes casing
    result = await db_session.execute(select(models.User).where(func.lower(models.User.username) == user.username.lower()))

    # Now we added the func to only the database query because , well it is the database query and for the user.username, it is a string so we simply call the lower() method on it 

    existing_user = result.scalars().first()

    if existing_user:
        raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail='User already exists')
    
    result = await db_session.execute(select(models.User).where(func.lower(models.User.email) == user.email.lower()))

    existing_email = result.scalars().first()

    if existing_email:
        raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail='Email already exists')
    
    new_user = models.User(username = user.username, email = user.email.lower(), password_hash = hash_password(user.password)) # However, when creating a new user, we use the default name the user passed to us, this is because we want the user to see what he gave as the username and not the username in lowercase (the lowercase is to be stored and checked against instead )
    # However, we would store the email in lowercase, we do this because emails are case insensitive by design ( if you type upper case and lower case of the same thing, it would still give you the same thing) 
    # Then we include a password parameter and give it an attribute of hash_password(user.password), remember that hash_password is the function we created to hash our user passwords , so we hash the user password and save the hashed password in the database 

    db_session.add(new_user)
    await db_session.commit()
    await db_session.refresh(new_user)

    return new_user


# We used status code 201 because we are creating a new object 
# We used UserResponsePublic as the response_model because that what the API would respond with 
# We used user : UserCreate because the user must be of type UserCreate

# So basically, we the request must pass the UserCreate pydantic schema while the API responds with UserResponsePublic 

# db_session : Annotated[Session, Depends(get_db_session)]

# db_session is a database object that must be of type Annotated, Annotated in this context means the db must be of type Session and it is gotten from Depends(get_db_session).

# Depends is a fastAPI function ,that runs the function put inside it and gives back the output 

# the create_user function takes 2 parameters user which is of type hint UserCreate (Pydantic Validation) and db_session, which is the database session, which must be of type Session and will be gotten from the Depends (get_db_session)

#  ??? Why did we use result.scalars().first() instead of result.scalar(), because I think result.scalar().

# we then create an instance of the User class by doing  models.User(username=user.username, email = user.email) and pass that into a variable , (ln 113) , check your obsidian classes note too

# Still baffled about the concept of db_session.add(new_user), db_session.commit() and db_session.refresh(new_user)


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data : Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[AsyncSession, Depends(get_db_session)]):
    result = await db.execute(select(models.User).where(func.lower(models.User.email) == form_data.username.lower()))
    existing_user = result.scalars().first()
    # NOTE that we call form_data.username because the username of the form is used as the general name used to verify the user.
    # For example, if we used username to verify, good but if we used email to verify, we would still be pulling the email from the form_data username field
    # The form_data password field is used for passwords only 

    if not existing_user or not verify_password(form_data.password, existing_user.password_hash):
        raise FastapiHttpException(status.HTTP_401_UNAUTHORIZED,"Incorrect email or password", headers= {"WWW-Authenticate" : "Bearer"})
    # Anytime we have a 401 or non-authorized error, we must send back headers of {"WWW-Authenticate" :"Bearer"} 

    # so we create our time for access token to expire and create the access token itself, 
    # the sub means subject and just refers to the payload being used, which in this case is the User.id
    # Return Token, so that it follows the schemas convention 
    # token_type is of bearer, because that is what we are using and verifying for 

    # This is a tutorial but later on, I could create helper functions, that contains all this , including the data of sub and others so instead of typing out all this code, I could use a single line of code (the function) to set all up
    # You can check gemini for the helper function chat (https://share.gemini.google/QsRHihnTTjtX)
    access_token_expiry = timedelta(minutes = settings.jwt_token_expiry_mins)
    access_token = create_access_token({"sub" : str(existing_user.id)}, access_token_expiry)

    return Token(access_token=access_token, token_type= "bearer")





# Now this endpoint , uses the oauth2scheme to extract the current user from the jwt_token if they are the owner of the token
@router.get("/me", response_model=UserResponsePrivate)
async def get_current_user(jwt_token : Annotated[str, Depends(Oauth2_scheme)], db : Annotated[AsyncSession, Depends(get_db_session)]):
    
    user_id = verify_access_token(jwt_token)
    if user_id is None:
        raise FastapiHttpException(
            status_code= status.HTTP_401_UNAUTHORIZED,
            detail= "Invalid or expired token", 
            headers= {"WWW-Authenticate" : "Bearer"},
        )
    
    # Then we check validate if the User ID can be converted to integer

    # NOTE Now I think we are only checking for integer because we are using integers for our ID, but in projects I have seen UUID was used, so for those projects, we would have to convert from str to UUID instead of int as we are doing here 

    try :
        int(user_id)
    except (TypeError, ValueError):
        raise FastapiHttpException(
            status_code= status.HTTP_401_UNAUTHORIZED,
            detail= "Invalid or expired token", 
            headers= {"WWW-Authenticate" : "Bearer"},
        )
    
    result = await db.execute(select(models.User).where(models.User.id == int(user_id)))
    current_user_exists = result.scalars().first()

    if not current_user_exists:
        raise FastapiHttpException(
            status_code= status.HTTP_401_UNAUTHORIZED,
            detail= "User not found", 
            headers= {"WWW-Authenticate" : "Bearer"},
        )
    
    return current_user_exists

# Here, we use UserResponsePublic as the response_model 
@router.get("/{user_id}", response_model=UserResponsePublic)
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


# Now we might be confused about this route, as to why our response_model is UserResponsePrivate instead of UserResponsePublic
# We only return UserResponsePrivate for the user if he is logged in, if he isn't we return Public response, if someone wan't to update a post, they would have to be logged in so we return the private since only the user is seeing it
@router.patch("/{user_id}",response_model=UserResponsePrivate, name = 'update_user_partial')
async def update_user_partial(user_id :int, updated_user : UserUpdate, db: Annotated[AsyncSession, Depends(get_db_session)]):
   

    # We keep this line of code because we want it to check if the user trying to change exist, we can't change a user that doesn't exist 

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "User not found")
    

    # def update_post_full and def update_post_partial are the same , just that we removed the check for user_id.
    # We do not want someone changing ownership of a post through partial update (patch)


    # We then check if the username changed, if it changed we check if that username already exists so we won't override another person email or cause the database to return an error as every username would have to be unique 
    if updated_user.username is not None and updated_user.username.lower() != func.lower(existing_user.username) : 
        result = await db.execute(select(models.User).where(func.lower(models.User.username) == updated_user.username.lower()))
        existing_username = result.scalars().first()

        if existing_username:
            raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail = "Username already exists")
        
        # I came back to this function to change the database queries and results using func.lower() and strings to using lower(), so anywhere you see that, I changed that a bit, You can check git history to see what has been changed 




    # We then check if the email changed, if it changed we check if that email already exists so we won't override another person email or cause the database to return an error as every email would have to be unique 
    if updated_user.email is not None and updated_user.email.lower() != func.lower(existing_user.email) : 
        result = await db.execute(select(models.User).where(func.lower(models.User.email) == updated_user.email.lower()))
        existing_email = result.scalars().first()

        if existing_email:
            raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail = "Email already registered")
        

    # using the model_dump(exclude_unset = True) is just saying remap the values , remap the attributes with None (wasn't filled because it's optional) to it's former values and the remap the attributes with the new values to the new values 
    # Basically, only the title of the post got changed, it would change the title attribute to the new value and the remaining attributes would remain the same instead of becoming None
    # Note that it's exclude_unset that does that, model_dump is just like json dumps, we are dumping the attributes and their values into a dictionary but exclude_unset does the mroutering of attributes to new values and if new values not exist, mroutering to old values
    updated_user_dict = updated_user.model_dump(exclude_unset= True)

    # 1. Intercept and transform specific keys if they exist
    if "email" in updated_user_dict and updated_user_dict["email"]:
        updated_user_dict["email"] = updated_user_dict["email"].lower()
        # NOTE that this change is not from corey tutorial, just something implemented on my own after checking around

    # the `updated_post_dict` is going to be of type hint dict

    # setattr sets the named attribute on the given object to the specified value.
    # setattr(x, 'y', v) is equivalent to x.y = v

    # Just noticed a new issue here, if we are using set_attr ,we can't perform any operation on the user details, for example, I would like to store the email of the user in lowercase but I can't because everything is mapped automatically.
    # Now a fix for the above issue, is to go up and fix the dictionary data from the model dump
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


