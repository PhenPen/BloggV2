from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import HTTPException as FastapiHttpException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHttpException


# from posts import posts as pst  # Commented this line out because we don't need it again as we are using a database to store posts not just a list
from schemas import PostCreate, PostResponse, PostUpdate, UserCreate, UserResponse, UserUpdate 

# Importing PostUpdate for PATCH CRUD

from typing import Annotated # Now what is Annotated 
from sqlalchemy.orm import Session
from sqlalchemy import select

import models  # We import all our database models   
from database import Base, database_engine, get_db_session  # We import Base which is just Declarative Base in a nutshell, database_engine which is our engine for database connections and get_db_session, which is our function for returning database sessions 



Base.metadata.create_all(bind=database_engine) # here before we run the app, we are telling FastAPI to create all the tables in the database before the app starts, Now this is idempotent so it can be run multiple times 



app = FastAPI() 

template = Jinja2Templates(directory="templates")

app.mount('/static',StaticFiles(directory="static"),name="static") #Mounting files for static files 
app.mount('/media',StaticFiles(directory="media"),name="media")  # Mounting files for media


# I'm still a bit confused as to why the names for the endpoints are posts and home, I think it has to do with displaying it in the schema documentation.
# I will check it later 

#Home / Posts
@app.get('/', include_in_schema=False,name='home')
@app.get('/posts', include_in_schema=False,name='posts')
def posts_page(request: Request,db: Annotated[Session, Depends(get_db_session)]):
    #return template.TemplateResponse(request,'home_finished.html',{"posts" : pst,"title" : "Home"})
    result = db.execute(select(models.Post))
    posts = result.scalars().all()
    return template.TemplateResponse(request,'home_finished.html',{"posts" : posts,"title" : "Home"})
    



# Posts
@app.get("/posts/{post_id}",include_in_schema=False)
def post_page(request: Request, post_id :int, db: Annotated[Session, Depends(get_db_session)]):

    result = db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()


    if not post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND,detail="Post not found")
    
    return template.TemplateResponse(request,"post_finished.html",{"post":post, "title":post.title})  # I also changed the title here from title to post.title

    #for post in pst:
    #    if post['id'] == post_id:
    #        title = post["title"][:50]
    #        return template.TemplateResponse(request,"post_finished.html",{"post":post, "title":title})

    #commented former code 


    #for post in posts:
    #    if post.id == post_id:
    #        title = post.title [:50]
    #        return template.TemplateResponse(request,"post_finished.html",{"post":post, "title":title})

    # commented second former code too, Made mistakes on my part as I was writing out, I found all posts first and used a for loop to check over it which wrong, I should have used a database query instead. I will do all that up
    

# User 
@app.get('/users/{user_id}/posts',include_in_schema=False,name='user_posts')
def get_user_posts_page(request : Request, user_id : int, db: Annotated[Session, Depends(get_db_session)]):

    result = db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    
    result = db.execute(select(models.Post).where(models.Post.user_id == existing_user.id))
    # result = db.execute(select(models.Post).where(models.Post.user_id == user_id))

    #Note that both ln 190 and 191 both give the same result
    # the second line is from corey schafer, why the first is from me, I used the first because it is what I have learnt on my own

    # Why do we use name = 'user_posts' 

    posts = result.scalars().all()

    return template.TemplateResponse(request,"users_posts_finished.html",{'posts' : posts, "user" : existing_user, "title" :f'{existing_user.username} posts'})








#  API  Home /Posts
@app.get("/api/posts",response_model=list[PostResponse],name= 'posts')
def posts(db: Annotated[Session, Depends(get_db_session)]):
    # return {'posts' : pst}
    result = db.execute(select(models.Post))
    posts = result.scalars().all()

    # since this return all posts , like an algorithm, can I at best just randomize it ?
    # Like lets say use the random library to randomize the final post
    return posts


# API Posts
@app.get("/api/posts/{post_id}",response_model=PostResponse, name = 'post')
def get_post(post_id :int, db: Annotated[Session, Depends(get_db_session)]):
    #for post in pst:
     #   if post['id'] == post_id:
      #      return {'posts' : post}
    # raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND,detail="Post not found")

    result = db.execute(select(models.Post).where(models.Post.id == post_id))
    existing_post = result.scalars().first()

    if not existing_post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "Post not found")
    return existing_post




@app.put("/api/posts/{post_id}",response_model=PostResponse, name = 'update_post_full')
def update_post_full(post_id :int, updated_post : PostCreate, db: Annotated[Session, Depends(get_db_session)]):
    #for post in pst:
     #   if post['id'] == post_id:
      #      return {'posts' : post}
    # raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND,detail="Post not found")

    result = db.execute(select(models.Post).where(models.Post.id == post_id))
    existing_post = result.scalars().first()

    # We keep this line of code because we want it to check if the post trying to change exist, we can't change a post that doesn't exist 
    if not existing_post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "Post not found")
    

    # We will also check if the updated post has the same the user id, that is whether we are trying to change it from a user to another user.
    # if it is the same user, then no issue. But if it is a different user, we would have to check if that different user exists in the database before changing the post to that user
    if updated_post.user_id != existing_post.user_id :
        result = db.execute(select(models.User).where(models.User.id == updated_post.user_id))
        existing_user = result.scalars().first()

        # Then we check for if the new user exists in the database already, else we return an error 
        if not existing_user:
            raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "User not found")


    existing_post.title = updated_post.title
    existing_post.content= updated_post.content
    existing_post.user_id = updated_post.user_id

    # db.add(existing_post) # We didn't do db.add, why ? Because it already exists ? 
    db.commit() # Also, just committing, won't it clash with the posts that already had the same values
    # don't forget brackets for the commit (db.commit())
    db.refresh(existing_post)
    return existing_post




@app.patch("/api/posts/{post_id}",response_model=PostResponse, name = 'update_post_partial')
def update_post_partial(post_id :int, updated_post : PostUpdate, db: Annotated[Session, Depends(get_db_session)]):
   

    result = db.execute(select(models.Post).where(models.Post.id == post_id))
    existing_post = result.scalars().first()

    # We keep this line of code because we want it to check if the post trying to change exist, we can't change a post that doesn't exist 
    if not existing_post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "Post not found")
    

    # def update_post_full and def update_post_partial are the same , just that we removed the check for user_id.
    # We do not want someone changing ownership of a post through partial update (patch)


    # using the model_dump(exclude_unset = True) is just saying remap the values , remap the attributes with None (wasn't filled because it's optional) to it's former values and the remap the attributes with the new values to the new values 
    # Basically, only the title of the post got changed, it would change the title attribute to the new value and the remaining attributes would remain the same instead of becoming None
    # Note that it's exclude_unset that does that, model_dump is just like json dumps, we are dumping the attributes and their values into a dictionary but exclude_unset does the mapping of attributes to new values and if new values not exist, mapping to old values
    updated_post_dict = updated_post.model_dump(exclude_unset= True)

    # the `updated_post_dict` is going to be of type hint dict

    # setattr sets the named attribute on the given object to the specified value.
    # setattr(x, 'y', v) is equivalent to x.y = v


    for field, value in updated_post_dict.items():
        setattr(existing_post, field, value)

    # No need for db.add as the post already exists in the database, we are just changing it , so we just commit and refresh



    db.commit() # Also, just committing, won't it clash with the posts that already had the same values
    # don't forget brackets for the commit (db.commit())
    db.refresh(existing_post)
    return existing_post


# Note that we used a status code of 204, 204 is often used with delete and returns no content, so I don't think we are expecting a return for this function
@app.delete("/api/posts/{post_id}",status_code=status.HTTP_204_NO_CONTENT, name = 'delete_post')
def delete_post(post_id :int, db: Annotated[Session, Depends(get_db_session)]):

    result = db.execute(select(models.Post).where(models.Post.id == post_id))
    existing_post = result.scalars().first()

    if not existing_post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "Post not found")
    
    db.delete(existing_post)
    db.commit()
    





    




@app.post("/api/posts",response_model=PostResponse,status_code=status.HTTP_201_CREATED)
def create_post(post:PostCreate, db: Annotated[Session, Depends(get_db_session)]):

    # new_id = max([p["id"] for p in pst]) + 1 if pst else 1 

    # commented the line above because there is no need to manually increment ids since the database handles that for us


    #new_post = {
        # "id" : new_id,
        #"author" : post.author,
       # "content" : post.content,
        # "date_posted" : "April 23, 2025" # commented this out so it uses our database default that we set using a lambda model, check models,py
   # }

   # At first I didn't check if the owner of the post exists which is wrong, this causes issues because if I pass a user of lets say 9999, which doesn't exist , instead of checking if user 9999 exists first, it instead just create a post with that ID
   # Moreover, if that user doesn't exist in the database, Using user 9999 as example again, the database would throw an error but if we check for it, we can silently generate our own error , instead of the database generating an unfriendly error 
   # I think this is also a foreign key check, as in the models table, Post.user_id is a foreign key from id attribute of the users table (class User)

   result = db.execute(select(models.User).where(models.User.id == post.user_id))
   existing_user = result.scalars().first()

   if not existing_user:
       raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
   
   new_post = models.Post(title = post.title, content = post.content, user_id = post.user_id)
   
   db.add(new_post)
   db.commit()
   db.refresh(new_post)
   
   
   return new_post




# Api Users
@app.post("/api/users",response_model=UserResponse,status_code=status.HTTP_201_CREATED)
def create_user(user :UserCreate, db_session : Annotated[Session,Depends(get_db_session)]):
    result = db_session.execute(select(models.User).where(models.User.username == user.username))

    existing_user = result.scalars().first()

    if existing_user:
        raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail='User already exists')
    
    result = db_session.execute(select(models.User).where(models.User.email == user.email))

    existing_email = result.scalars().first()

    if existing_email:
        raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail='Email already exists')
    
    new_user = models.User(username = user.username, email = user.email)
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)

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







@app.get("/api/users/{user_id}", response_model=UserResponse)
def user(user_id : int, db:Annotated[Session, Depends(get_db_session)]):

    result = db.execute(select(models.User).where(models.User.id == user_id))

    existing_user  = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return existing_user


@app.get('/api/users/{user_id}/posts',response_model= list[PostResponse])
def user_post_page(user_id : int, db: Annotated[Session, Depends(get_db_session)]):

    result = db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    
    result = db.execute(select(models.Post).where(models.Post.user_id == existing_user.id))
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



@app.patch("/api/user/{user_id}",response_model=UserResponse, name = 'update_user_partial')
def update_user_partial(user_id :int, updated_user : UserUpdate, db: Annotated[Session, Depends(get_db_session)]):
   

    # We keep this line of code because we want it to check if the user trying to change exist, we can't change a user that doesn't exist 

    result = db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "User not found")
    

    # def update_post_full and def update_post_partial are the same , just that we removed the check for user_id.
    # We do not want someone changing ownership of a post through partial update (patch)


    # We then check if the username changed, if it changed we check if that username already exists so we won't override another person email or cause the database to return an error as every username would have to be unique 
    if updated_user.username is not None and updated_user.username != existing_user.username : 
        result = db.execute(select(models.User).where(models.User.username == updated_user.username))
        existing_username = result.scalars().first()

        if existing_username:
            raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail = "Username already exists")
        

    # We then check if the email changed, if it changed we check if that email already exists so we won't override another person email or cause the database to return an error as every email would have to be unique 
    if updated_user.email is not None and updated_user.email != existing_user.email : 
        result = db.execute(select(models.User).where(models.User.email == updated_user.email))
        existing_email = result.scalars().first()

        if existing_email:
            raise FastapiHttpException(status_code=status.HTTP_400_BAD_REQUEST, detail = "Email already registered")
        

    # using the model_dump(exclude_unset = True) is just saying remap the values , remap the attributes with None (wasn't filled because it's optional) to it's former values and the remap the attributes with the new values to the new values 
    # Basically, only the title of the post got changed, it would change the title attribute to the new value and the remaining attributes would remain the same instead of becoming None
    # Note that it's exclude_unset that does that, model_dump is just like json dumps, we are dumping the attributes and their values into a dictionary but exclude_unset does the mapping of attributes to new values and if new values not exist, mapping to old values
    updated_user_dict = updated_user.model_dump(exclude_unset= True)

    # the `updated_post_dict` is going to be of type hint dict

    # setattr sets the named attribute on the given object to the specified value.
    # setattr(x, 'y', v) is equivalent to x.y = v


    for field, value in updated_user_dict.items():
        setattr(existing_user, field, value)

    # No need for db.add as the post already exists in the database, we are just changing it , so we just commit and refresh



    db.commit() # Also, just committing, won't it clash with the posts that already had the same values
    # don't forget brackets for the commit (db.commit())
    db.refresh(existing_user)
    return existing_user


@app.delete('/api/user/{user_id}',status_code=status.HTTP_204_NO_CONTENT,name = 'delete_user')
def delete_user(user_id : int, db: Annotated[Session, Depends(get_db_session)]):

    # check for if user exists
    result = db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "User not found")
    
    db.delete(existing_user)
    db.commit()



# Error Handling 
@app.exception_handler(StarletteHttpException)
def general_Http_Exception_Handler(request:Request, exception:StarletteHttpException):
    message = (exception.detail if exception.detail else "An error occured. Please check your request and try again.")

    if request.url.path.startswith('/api'):
        return JSONResponse(content={"detail":message},status_code=exception.status_code)
    return template.TemplateResponse(request,'error_finished.html',{"status_code":exception.status_code,'message':message,"title":exception.status_code},status_code=exception.status_code)


@app.exception_handler(RequestValidationError)
def request_validation_error_handler(request:Request, exception:RequestValidationError):
    if request.url.path.startswith('/api'):
        return JSONResponse(content={"detail":exception.errors()},status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    return template.TemplateResponse(request, "error_finished.html",context={"status_code":status.HTTP_422_UNPROCESSABLE_CONTENT,'message':"Invalid request.Please check your input and try again","title":status.HTTP_422_UNPROCESSABLE_CONTENT},status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
