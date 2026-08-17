from fastapi import Depends, FastAPI, Request, status, Query
from fastapi.exceptions import HTTPException as FastapiHttpException
from fastapi.exceptions import RequestValidationError
# from fastapi.responses import JSONResponse   # I commented this since we were using it for our own exception handlers but since we imported the default exception handlers , we don't need the response

# Note that we can still import it to use JSON or HTML responses from here

from routers import posts as posts_router # import for the routers
from routers import users as users_router # import for the routers

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHttpException


from fastapi.exception_handlers import request_validation_exception_handler, http_exception_handler # We are importing default handlers now instead of our code own ? 

from sqlalchemy.orm import selectinload # I dunno what this does  
# Corey said that selectinload was for eager loading but I don't even know what that does 

from contextlib import asynccontextmanager  # I dunno what this does


# from posts import posts as pst  # Commented this line out because we don't need it again as we are using a database to store posts not just a list
from schemas import PostCreate, PostResponse, PostUpdate, UserCreate, UserResponsePublic, UserUpdate 

# Importing PostUpdate for PATCH CRUD

from typing import Annotated # Now what is Annotated 
# from sqlalchemy.orm import Session  # Since we are converting to async, we don't need sync sessions, so we comment that our and import Async session instead

from sqlalchemy.ext.asyncio import AsyncSession # Imported async session to use instead of normal sessions as sync would normally use


from sqlalchemy import select, func

import models  # We import all our database models   
from database import Base, database_engine, get_db_session  # We import Base which is just Declarative Base in a nutshell, database_engine which is our engine for database connections and get_db_session, which is our function for returning database sessions 

from config import settings  # We import settings because we want to using the post_per_page setting


# We can no longer use the line below since we are converting to async , that is because the line below is used for synchronous functions
# Base.metadata.create_all(bind=database_engine) # here before we run the app, we are telling FastAPI to create all the tables in the database before the app starts, Now this is idempotent so it can be run multiple times 

@asynccontextmanager     # What does this do ? 
async def lifespan(_app: FastAPI):    #Life span function, will check what that means later
    # Startup
    async with database_engine.begin() as connection:   # what does .begin() do though ? # Probably begins an async connection 
        await connection.run_sync(Base.metadata.create_all)  # This seems to use the connection to await the result of running a sync function , which is the Base.metadata.create_all that was meant to be just run in sync
    yield  # Not sure what the yield does but maybe it hands the awaited result ? but it is outside the await connection.run_sync()
    # However, I do know that in this type of function, everything above yield is the startup and everything below yield inside the function is the shutdown
    # Shutdown
    await database_engine.dispose()

# The function above is also idempotent like the sync one , so it runs multiple times 

# app = FastAPI() 
app = FastAPI(lifespan=lifespan)  # Then inside the instance of the FastAPI class, we pass in our lifespan function for async, and do lifespan=lifespan 

template = Jinja2Templates(directory="templates")

app.mount('/static',StaticFiles(directory="static"),name="static") #Mounting files for static files 
app.mount('/media',StaticFiles(directory="media"),name="media")  # Mounting files for media

# Adding routers from routers and to main.py for organization
app.include_router(posts_router.router,prefix= "/api/posts" , tags= ['Posts'])
app.include_router(users_router.router,prefix= "/api/users" , tags= ['Users'])

# changed router tags to Title case (Pascal case perharps > )

# I'm still a bit confused as to why the names for the endpoints are posts and home, I think it has to do with displaying it in the schema documentation.
# I will check it later  # Checked this , the reason why the name exists is so that if we change the name of the function, it's reference name would still be the name we gave it in the decorator.

# For example, if I'm using url_for(), if the name argument exists in the decorator, FastAPI would use it first else it uses the function name

#Home / Posts
#@app.get('/', include_in_schema=False,name='home')
#@app.get('/posts', include_in_schema=False,name='posts')
#def posts_page(request: Request,db: Annotated[Session, Depends(get_db_session)]):
    #return template.TemplateResponse(request,'home_finished.html',{"posts" : pst,"title" : "Home"})
#    result = db.execute(select(models.Post))
#    posts = result.scalars().all()
#    return template.TemplateResponse(request,'home_finished.html',{"posts" : posts,"title" : "Home"})

# Updated async home route
@app.get('/', include_in_schema=False,name='home')
@app.get('/posts', include_in_schema=False,name='posts')
async def posts_page(request: Request,db: Annotated[AsyncSession, Depends(get_db_session)]):


    total_post_count_query = await db.execute(select(func.count()).select_from(models.Post))
    total_post_count = total_post_count_query.scalar() or 0

    # we would also await our db query as we are now in co-routine function
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).order_by (models. Post.date_posted.desc()).limit(settings.posts_per_page))    # Compared to our API route, there is no offset because this is home page , so we would return all posts without skipping 
    # added order by so we our posts could be returned from new to old instead of old to new, I did this for every place that a group or list of posts would be sent 

    # Now options is like a adding settings to an sql query, just like saying , do burgers the normal way but without onions

    # so we are telling sql alchemy, to run the query "db.execute(select(models.Post)", and include a setting of selectinload(models.Post.author)

    # Still don't get what selectinload does though # Eager loading ? 

    # So apparently, there is eager and lazy loading 
    posts = result.scalars().all()

    has_more = len(posts) < total_post_count

    return template.TemplateResponse(request,'home_finished.html',{"posts" : posts,"title" : "Home", "limit" : settings.posts_per_page, "has_more" : has_more})




# Posts
#@app.get("/posts/{post_id}",include_in_schema=False)
#def post_page(request: Request, post_id :int, db: Annotated[Session, Depends(get_db_session)]):

#    result = db.execute(select(models.Post).where(models.Post.id == post_id))
#    post = result.scalars().first()


#    if not post:
#        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND,detail="Post not found")
    
#    return template.TemplateResponse(request,"post_finished.html",{"post":post, "title":post.title})  # I also changed the title here from title to post.title

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
    
@app.get("/posts/{post_id}",include_in_schema=False, name = 'post_page')
async def post_page(request: Request, post_id :int, db: Annotated[AsyncSession, Depends(get_db_session)]):

    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))

    # Notice that .options came before the .where chaining for the sql
    post = result.scalars().first()


    if not post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND,detail="Post not found")
    
    return template.TemplateResponse(request,"post_finished.html",{"post":post, "title":post.title}) 





# User 
@app.get('/users/{user_id}/posts',include_in_schema=False,name='user_posts')
async def get_user_posts_page(request : Request, user_id : int, db: Annotated[AsyncSession, Depends(get_db_session)], skip : Annotated[int, Query(ge=0)] = 0, limit : Annotated[int, Query(ge=1, le=100)] = 10):

    result = await db.execute(select(models.User).where(models.User.id == user_id)) 

    # Now you would see that we didn't call options or selectinload in this query, that is because we aren't accessing the relationship object
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')


    count_result = await db.execute(select(func.count()).select_from(models.Post).where(models.Post.user_id == user_id))
    total = count_result.scalar() or 0


    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.user_id == existing_user.id).order_by (models.Post.date_posted.desc()).offset(skip).limit(limit))
    # result = db.execute(select(models.Post).where(models.Post.user_id == user_id))

    # I think the post author is the user id ?? 

    #Note that both ln 190 and 191 both give the same result
    # the second line is from corey schafer, why the first is from me, I used the first because it is what I have learnt on my own

    # Why do we use name = 'user_posts' 


    posts = result.scalars().all()

    has_more = (skip + len(posts)) < total

    return template.TemplateResponse(request,"users_posts_finished.html",{'posts' : posts, "user" : existing_user, "title" :f'{existing_user.username} posts', "limit" : settings.posts_per_page, "has_more": has_more})


# I copied this from snippets of corey scafer and it's just more endpoints with templates for the register and login


@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return template.TemplateResponse(
        request,
        "login.html",
        {"title": "Login"},
    )


@app.get("/register", include_in_schema=False)
async def register_page(request: Request):
    return template.TemplateResponse(
        request,
        "register.html",
        {"title": "Register"},
    )


@app.get("/account", include_in_schema=False)
async def account_page(request: Request):
    return template.TemplateResponse(
        request,
        "account_finished.html",
        {"title": "Account"},
    )


@app.get("/forgot-password", include_in_schema=False)  # We then added endpoints for forgot-password
async def forgot_password_page(request: Request):
    return template.TemplateResponse(
        request,
        "forgot_password.html",
        {"title": "Forgot Password"},
    )


@app.get("/reset-password", include_in_schema=False) # We then added endpoints for reset-password, the reset-password route is called after when the user clicks on the link inside the email
async def reset_password_page(request: Request):
    response = template.TemplateResponse(
        request,
        "reset_password.html",
        {"title": "Reset Password"},
    )
    response.headers["Referrer-Policy"] = "no-referrer"   # we also added this in this route for security, normally when a page is opened from another page or a link is sent, the browser sends a referrer header from the previous page to the new site, to show what page you came from.
    # While this is good, this can cause security issues, if you remember, our previous page or link contained our token as a query parameter, so it sends the token along with the link to the new website via the referral header. Setting this to no-referrer, stops that from being sent
    return response



#  API  Home /Posts




# Api Users



# We would also change our exception handlers to fastapi default handlers which is async by default

# Error Handling 
@app.exception_handler(StarletteHttpException)
async def general_Http_Exception_Handler(request:Request, exception:StarletteHttpException):
    # message = (exception.detail if exception.detail else "An error occured. Please check your request and try again.")  # Now I commented this out because we don't need it for api route, the fastapi async exception handler, handles it already and you can see this in the api route below, However, it is still needed for template routing, so we move the message below

    if request.url.path.startswith('/api'):
        # return JSONResponse(content={"detail":message},status_code=exception.status_code)
        return await http_exception_handler(request, exception)
    

    message = (exception.detail if exception.detail else "An error occured. Please check your request and try again.")

    return template.TemplateResponse(request,'error_finished.html',{"status_code":exception.status_code,'message':message,"title":exception.status_code},status_code=exception.status_code)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request:Request, exception:RequestValidationError):
    if request.url.path.startswith('/api'):
        # return JSONResponse(content={"detail":exception.errors()},status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
        return await request_validation_exception_handler(request, exception)  # the fastapi default exception handler , handles this too 
    

    return template.TemplateResponse(request, "error_finished.html",context={"status_code":status.HTTP_422_UNPROCESSABLE_CONTENT,'message':"Invalid request.Please check your input and try again","title":status.HTTP_422_UNPROCESSABLE_CONTENT},status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
