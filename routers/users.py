from typing import Annotated

from fastapi import APIRouter,Depends,status, UploadFile, Query, BackgroundTasks
from fastapi import HTTPException as FastapiHttpException
from sqlalchemy import select, func 
# we imported func so we can write queries that are case insensitive ,basically queries that check for both cases of letters (uppercase and lowercase) ; In a blog or social media website, we would want our usernames to be unique, but while displaying the username in the way the user passed it to us, we would want to convert it to lowercase

from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from PIL import UnidentifiedImageError # This error is raised when an image cannot be opened or any errors for the image occurs 
# UploadFile is a library from fastAPI used to upload files 

from image_utils import process_profile_image, delete_profile_image # we import our functions used for processing the image and deleting the image in case a user wants upload a picture or delete a profile image too 
from email_utils import send_password_reset_email

from starlette.concurrency import run_in_threadpool # Not sure of what this does 


import models
from database import get_db_session
from schemas import PostResponse, UserCreate, UserResponsePublic, UserResponsePrivate, UserUpdate, Token, PaginatedPostResponse, ResetPasswordRequest, ChangePasswordRequest, ForgotPasswordRequest
# Imported UserResponsePublic and UserResponsePrivate instead UserResponse as I changed that 

# Change the response from UserResponse to UserResponsePublic


from datetime import timedelta, UTC, datetime # import timedelta so we could add our jwt expiry time here
from fastapi.security import OAuth2PasswordRequestForm 
# OAuth2PasswordRequestForm is used as the input so it could extract the password and username /email for checking 
from auth import hash_password, CurrentUser, create_access_token, verify_password, generate_reset_token, hash_reset_token
# we import our functions for hashing, creating , verifying.
# We also import our oauth scheme 

from config import settings
from sqlalchemy import delete as sql_delete


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
async def get_current_user(current_user : CurrentUser):
    return current_user

# Note that we are returning 202, instead of 200 here, we also didn't use a response model
@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)  # I think we used 202, because we accepted the user request to change password as the user forgot it, but what of 200_ok, isn't that the same for all ?
# I was also told that it is not 200_ok, because the request hasn't gone fully as it doesn't check if the email exists or not, but just tells the user that they have seen their request 
async def forgot_password(
    request_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):  # Note that there is no current user dependency so there is no need for the user to be logged in
    result = await db.execute(
        select(models.User).where(
            func.lower(models.User.email) == request_data.email.lower(),
        ),
    )
    user = result.scalars().first()

    if user:
        await db.execute(
            sql_delete(models.PasswordResetToken).where(
                models.PasswordResetToken.user_id == user.id,
            ),
        ) # Why sql_delete instead of db.delete() ?
        # We used sql_delete, because we are trying to delete every single existing token, though db.delete and delete does the same thing technically, for db.delete, we are using a query to fetch a specific row as a result before deleting, for sql_delete, we just delete the entire table, and in the case about, we delete the table for the user that matches that user_id

        token = generate_reset_token()
        token_hash = hash_reset_token(token)
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.reset_expire_token_mins
        )

        reset_token = models.PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(reset_token)
        await db.commit()

        background_tasks.add_task(
            send_password_reset_email,
            to_email=user.email,  # Also notice that we're passing simple data, just like strings here. We're not passing the database session. Background tasks run after the response is sent, so the session may be closed by then. ???
 
            username=user.username,
            token=token,
        ) # Also notice that we are passing the token not the token hash here, that is what is sent to the user and not the token hash, while the token_hash is just meant for the database only

    return {
        "message": "If an account exists with this email, you will receive password reset instructions."
    }  # we returned a normal message, why ?
# Now this part here is important for security, so when we return, we're just returning this message here, we always return the same 202 response with the same generic message, whether or not the email exists. We don't say anything like email not found or anything like that. that prevents email enumeration attacks where an attacker tries a bunch of emails to see which ones get a different response so that they know what emails exist on your system. 


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request_data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):    # Note that there is no current user dependency so there is no need for the user to be logged in
    token_hash = hash_reset_token(request_data.token)  # we first convert it to hash to see if it exists in database 

    result = await db.execute(
        select(models.PasswordResetToken).where(
            models.PasswordResetToken.token_hash == token_hash,
        ),
    )
    reset_token = result.scalars().first()

    if not reset_token:
        raise FastapiHttpException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if reset_token.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):  # why .replace ? # We are using replace because, sqlite by default removes timezones, so after it removes it , we can't just compare that with the database own that has it, so we would replace the sqlite database time with the timezone version, before comparing it, this issue however doesn't exist in postgresql
        await db.delete(reset_token)
        await db.commit()
        raise FastapiHttpException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    result = await db.execute(
        select(models.User).where(models.User.id == reset_token.user_id),
    )
    user = result.scalars().first()

    if not user:
        raise FastapiHttpException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.password_hash = hash_password(request_data.new_password) #if user, then we hash the password and save it

    # However, after we change the password, we then delete all the request tokens in the database, as shown below
    await db.execute(
        sql_delete(models.PasswordResetToken).where(
            models.PasswordResetToken.user_id == user.id,
        ),
    )

    await db.commit()
    return {
        "message": "Password reset successfully. You can now log in with your new password."
    }  # we return the a generic message and we do not log the user in, but rather prompt the user to login in themselves

# NOte that we are using /me/password as the endpoint, instead of something like user_id/password, a change of password is a personal something and cannot be done by another person, so we can just do that since we already know the current user
@router.patch("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):  # Note that there is current user dependency as you must be logged in before you can change you r password as compared to the other two routes 
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise FastapiHttpException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(password_data.new_password)

    # we would delete the table which all our reset tokens exist too 
    await db.execute(
        sql_delete(models.PasswordResetToken).where(
            models.PasswordResetToken.user_id == current_user.id,
        ),
    )

    await db.commit()

    return {"message" : "Password changed successfully"}


# Here, we use UserResponsePublic as the response_model 
@router.get("/{user_id}", response_model=UserResponsePublic)
async def user(user_id : int, db:Annotated[AsyncSession, Depends(get_db_session)]):

    result = await db.execute(select(models.User).where(models.User.id == user_id))

    existing_user  = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return existing_user


@router.get('/{user_id}/posts',response_model= PaginatedPostResponse)
async def user_post_page(user_id : int, db: Annotated[AsyncSession, Depends(get_db_session)],skip : Annotated[int, Query(ge=0)] = 0, limit : Annotated[int, Query(ge=1, le=100)] = 10):

    result = await db.execute(select(models.User).where(models.User.id == user_id).offset(skip).limit(limit))
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    count_result = await db.execute(
        select(func.count())       # We would add this query for counting the posts in the database
        .select_from(models.Post)
        .where(models.Post.user_id == user_id),
    )
    total = count_result.scalar() or 0

    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.user_id == existing_user.id).order_by (models. Post.date_posted.desc()).offset(skip).limit(limit))  # We would add offset and limit to our database query for posts
    # result = db.execute(select(models.Post).where(models.Post.user_id == user_id))

    # Note that lines above (commented and not commented ) both give the same result
    # the second line is from corey schafer, why the first is from me, I used the first because it is what I have learnt on my own

    posts = result.scalars().all()


    has_more = skip + len(posts) < total

    return PaginatedPostResponse(
        posts = [PostResponse.model_validate(post) for post in posts],
        total = total,
        skip = skip,
        limit = limit,
        has_more = has_more,
    )

    

# Note that after updating routes, we need to update some templates
# I changed how we display the date and author, recall that we set our API to return ISO 8601 date format .
# We would also change src="{{ url_for('static', path='profile_pics/default.jpg') }}" in the route as you can see that is hard coded, to the dynamic way of retrieving images.  
# Since post is an object with attributes, instead of using url_for, we can just call it directly, see home.html and check the difference between the commented out src and the current main src 


# Also I some of the content dictionary is a different across functions, so I check and found out I used posts when I was returning a list of posts , Example , returning all posts and post for a single post, Example , returning a single post


# Now we might be confused about this route, as to why our response_model is UserResponsePrivate instead of UserResponsePublic
# We only return UserResponsePrivate for the user if he is logged in, if he isn't we return Public response, if someone wan't to update a post, they would have to be logged in so we return the private since only the user is seeing it
@router.patch("/{user_id}",response_model=UserResponsePrivate, name = 'update_user_partial')
async def update_user_partial(user_id :int, updated_user : UserUpdate, current_user : CurrentUser, db: Annotated[AsyncSession, Depends(get_db_session)]):

    # Note that authorization should always be first 
    if user_id != current_user.id:
        raise FastapiHttpException(status.HTTP_403_FORBIDDEN, "Not authorized to update user") 
    

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
async def delete_user(user_id : int, current_user : CurrentUser, db: Annotated[AsyncSession, Depends(get_db_session)]):

    # Note that authorization should always be first 
    if user_id != current_user.id:
        raise FastapiHttpException(status.HTTP_403_FORBIDDEN, "Not authorized to delete user") 

    # check for if user exists
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "User not found")

    # Now when deleting the user, we would want to delete any file associated with it, else we would be leaving orphaned files on disk, when we say orphaned files, we mean files that are not linked to anything. For example, if we delete the user, we would an image file that is not linked to anyone, so we would have to take care of that here

    old_filename = existing_user.image_file # And like delete_users_picture, we would set the file name to a variable first, as we would want to only delete the profile picture only when the commit was successful

    await db.delete(existing_user)
    await db.commit()

    if old_filename:
        delete_profile_image(old_filename)

        # We then delete it after a successful commit # Also note that we are deleting the file or file path, not deleting from the database so we aren't meant to use db.delete, the only thing stored in the database is the filename, and that would change after committing 



@router.patch("/{user_id}/picture", response_model= UserResponsePrivate)
async def upload_profile_picture(file : UploadFile, user_id : int, current_user : CurrentUser, db : Annotated[AsyncSession, Depends(get_db_session)]):

    #Authorization check
    if current_user.id != user_id:
        raise FastapiHttpException(status_code= status.HTTP_403_FORBIDDEN, detail= "Not authorized to update this user's profile picture")

    #  ??? Looking at this, I feel it's kinda weird that we are still inputting the user_id , when we could have just gotten it from the current_user id or in twitter I know you could view other people profile picture, so I'm guessing this check could be for that 

    content = await file.read() # reading the file or the uploaded profile picture in this case # Note that here, it isn't opened as an Image yet but rather it is just opened as a normal file, same way an image could be opened as binary instead of the default image format

    if len(content) > settings.max_upload_size_bytes :
        raise FastapiHttpException(status_code = status.HTTP_400_BAD_REQUEST, detail=f"File size too large. Maximum size is {settings.max_upload_size_bytes // (1024 *1024)} MB")
    # A bit baffled as to why we could not set the MB directly in the settings file configuration but it is okay though, I understand this too 

    # Remember we just opened the image as a file to read the content size, now in the try statement condition below, we would attempt to open the content as an Image instead of just a file, now if PIL (which is pillow) can't open it then it returns an error, this is method is much better that assuming the content file type or getting the file type from the user which can pass mischievous file format instead of the usual default image format types
    try : 
        new_filename = await run_in_threadpool(process_profile_image, content) # What is a threadpool

        # It seems the reason for the threadpool stuff is that we are trying to run a sync function in an async endpoint , which would block the endpoint, so instead of doing that we run the sync function in a separate thread , while the async loop runs ? 

    except UnidentifiedImageError as err:  # If file is not an image or file can't be opened, then this error is raised 
        raise FastapiHttpException(status_code= status.HTTP_400_BAD_REQUEST, detail = "Invalid image file.  Please upload a valid image (JPEG, PNG, GIF, WebP).",) from err
    # I don't get the from err

    old_filename = current_user.image_file # we get the current user image file name or profile picture name, if the user hasn't set a profile picture before it should still remain the static default profile picture

    current_user.image_file = new_filename
    # Then we change the user profile picture to the new profile picture

    await db.commit()
    await db.refresh(current_user) # we commit (save) and refresh the user

    if old_filename:
        delete_profile_image(old_filename) # here we delete the old file name if it exists, notice we didn't run this in a separate threadpool, this is because we are just removing the file and not running a full cpu bound operation, unlike the process_profile_image

    # Now if you notice, we are committing first before before deleting the old file name, this is because if we have any weird scenario whereby the database commit fails , we instead of deleting the old file name already , we would still have the file name.
    # In this case, we would make sure the database is committed first, and only then can we delete the old file name 
    return current_user


@router.delete("/{user_id}/picture", response_model= UserResponsePrivate)
async def delete_user_picture(user_id : int, current_user : CurrentUser, db : Annotated[AsyncSession, Depends(get_db_session)]):

    #Authorization check
    if current_user.id != user_id:
        raise FastapiHttpException(status_code=status.HTTP_403_FORBIDDEN, detail= "Not authorized to delete this user's profile picture")

    old_file_name = current_user.image_file   # Then before do anything, we save the old file name so in case there are issues such as error while committing , we would still have the file location instead of losing it all

    if old_file_name is None:  # If no profile picture, it returns this 
        raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail = "No profile picture to delete")

    current_user.image_file = None  # Then if it deletes , it then sets the image_file of the user to None, which is the file name of the profile picture
    await db.commit()
    await db.refresh(current_user)

    delete_profile_image(old_file_name)  # we then commit and refresh and only after doing those things successfully, we delete the old file name 

    return current_user
