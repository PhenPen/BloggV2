from typing import Annotated

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession


from fastapi import HTTPException as FastapiHttpException
import models
from database import get_db_session
from schemas import PostCreate, PostResponse, PostUpdate, PaginatedPostResponse
from auth import CurrentUser  

router = APIRouter()

@router.get("",response_model=PaginatedPostResponse, name= 'posts')
async def posts(db: Annotated[AsyncSession, Depends(get_db_session)], 
                skip : Annotated[int, Query(ge=0)] = 0, 
                limit : Annotated[int, Query(ge=1, le=100)] = 10,
                ):

    # return {'posts' : pst}

    # Now instead of sending all the posts first, we would first count the number of posts that exists and we would this with a count query
    total_post_count_query = await db.execute(select(func.count()).select_from(models.Post)) # I used where here before, I need to learn the difference between selectfrom and where as well as other SQL commands
    total_post_count = total_post_count_query.scalar() or 0   # Interesting case here but we added or 0 here so if there is no Post yet, .scalar() would give None and then python will pick 0 as None is a non truthy value

    # Now we would just add .offset and .limit to our SQLAlchemy query, Learn about OFFSET and LIMIT in SQL
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).order_by (models.Post.date_posted.desc()).offset(skip).limit(limit))
    posts = result.scalars().all()
    # Also note that in the result of our query about, we also have order_by, though we included it before, it is actually very important for Pagination, without order_by, our posts can be returned either ascending or descending and we won't be sure, so in order to be exact, we set it ourselves

    # Now remember our has_more bool from our schema, we would create it here
    # To create the bool, we would calculate if the sum of our OFFSET and number of posts currently displayed (basically the LIMIT for the page) is equal to or more that the total number of posts, if it is more than or equal to the number of posts, our has_more would be false because there is no more posts to load but if it is less than the total number of posts then, has_more would be true because it has more posts to load

    has_more = (skip + len(posts)) < total_post_count



    # since this return all posts , like an algorithm, can I at best just randomize it ?
    # Like lets say use the random library to randomize the final post
    # return posts   # Now instead of returning all posts , we return the paginated response schema, with the posts and other fields
    return PaginatedPostResponse(
        posts = [PostResponse.model_validate(post) for post in posts],
        total = total_post_count,
        skip = skip,
        limit = limit,
        has_more = has_more
    )
    # for posts, we would use the model_validate attribute of the schema class to validate each individual post as we loop through it, and with all the posts validated, that becomes our set of posts 
    # When FastAPI handles the response model, FastAPI handles that automatically but now are constructing the object ourselves as we want to pass the response in the schema not the response only for FastAPI to validate against


# API Posts
@router.get("/{post_id}",response_model=PostResponse, name = 'post')
async def get_post(post_id :int, db: Annotated[AsyncSession, Depends(get_db_session)]):
    #for post in pst:
     #   if post['id'] == post_id:
      #      return {'posts' : post}
    # raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND,detail="Post not found")

    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    existing_post = result.scalars().first()

    if not existing_post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "Post not found")
    return existing_post




@router.put("/{post_id}",response_model=PostResponse, name = 'update_post_full')
async def update_post_full(post_id :int, updated_post : PostCreate,current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db_session)]):
    #for post in pst:
     #   if post['id'] == post_id:
      #      return {'posts' : post}
    # raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND,detail="Post not found")

    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    existing_post = result.scalars().first()

    # We keep this line of code because we want it to check if the post trying to change exist, we can't change a post that doesn't exist 
    if not existing_post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "Post not found")
    

    # We will also check if the updated post has the same the user id, that is whether we are trying to change it from a user to another user.
    # if it is the same user, then no issue. But if it is a different user, we would have to check if that different user exists in the database before changing the post to that user
    
    # We comment out this check because, we only want the owner of the post , which is the current user to edit and the CurrentUser Dependency already checks if the user exists 

    #if updated_post.user_id != existing_post.user_id :
    #    result = await db.execute(select(models.User).where(models.User.id == updated_post.user_id))
    #    existing_user = result.scalars().first()

        # Then we check for if the new user exists in the database already, else we return an error 
    #    if not existing_user:
    #        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "User not found")



    if existing_post.user_id != current_user.id:
        raise FastapiHttpException(status.HTTP_403_FORBIDDEN, "Not authorized to update post")


    existing_post.title = updated_post.title
    existing_post.content= updated_post.content
    #existing_post.user_id = updated_post.user_id  # We comment out this line because we aren't using it

    # db.add(existing_post) # We didn't do db.add, why ? Because it already exists ? 
    await db.commit() # Also, just committing, won't it clash with the posts that already had the same values
    # don't forget brackets for the commit (db.commit())
    await db.refresh(existing_post,attribute_names = ['author'])  # We added attribute names so that when refreshing the post, the refresh keeps the author object ready to be sent quickly I think ??? I think I would still have to verify this 

    # Also, I think attribute_names is added every time we are creating a new resource (POST CRUD) or when we are updating a resource (PUT or PATCH CRUD)  
    return existing_post




@router.patch("/{post_id}",response_model=PostResponse, name = 'update_post_partial')
async def update_post_partial(post_id :int, updated_post : PostUpdate,current_user : CurrentUser, db: Annotated[AsyncSession, Depends(get_db_session)]):
   

    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    existing_post = result.scalars().first()

    # We keep this line of code because we want it to check if the post trying to change exist, we can't change a post that doesn't exist 
    if not existing_post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "Post not found")
    
    # Added the check below because we are checking if current user id is the same as the post we are attempting to update
    if existing_post.user_id != current_user.id:
        raise FastapiHttpException(status.HTTP_403_FORBIDDEN, "Not authorized to update post")

    # def update_post_full and def update_post_partial are the same , just that we removed the check for user_id.
    # We do not want someone changing ownership of a post through partial update (patch)


    # using the model_dump(exclude_unset = True) is just saying remap the values , remap the attributes with None (wasn't filled because it's optional) to it's former values and the remap the attributes with the new values to the new values 
    # Basically, only the title of the post got changed, it would change the title attribute to the new value and the remaining attributes would remain the same instead of becoming None
    # Note that it's exclude_unset that does that, model_dump is just like json dumps, we are dumping the attributes and their values into a dictionary but exclude_unset does the mroutering of attributes to new values and if new values not exist, mroutering to old values
    updated_post_dict = updated_post.model_dump(exclude_unset= True)

    # the `updated_post_dict` is going to be of type hint dict

    # setattr sets the named attribute on the given object to the specified value.
    # setattr(x, 'y', v) is equivalent to x.y = v


    for field, value in updated_post_dict.items():
        setattr(existing_post, field, value)

    # No need for db.add as the post already exists in the database, we are just changing it , so we just commit and refresh



    await db.commit() # Also, just committing, won't it clash with the posts that already had the same values
    # don't forget brackets for the commit (db.commit())
    await db.refresh(existing_post, attribute_names= ['author'])
    return existing_post


# Note that we used a status code of 204, 204 is often used with delete and returns no content, so I don't think we are expecting a return for this function
@router.delete("/{post_id}",status_code=status.HTTP_204_NO_CONTENT, name = 'delete_post')
async def delete_post(post_id :int,current_user : CurrentUser, db: Annotated[AsyncSession, Depends(get_db_session)]):

    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    existing_post = result.scalars().first()

    if not existing_post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "Post not found")
    
    # Added the code below to only allow the current user to be able to delete his post
    if existing_post.user_id != current_user.id:
        raise FastapiHttpException(status.HTTP_403_FORBIDDEN, "Not authorized to delete post")
    
    await db.delete(existing_post)   # Remember in db.add, we didn't await but in db.delete, we had to await, this because db.delete is actually an I/O task 
    await db.commit()
    





    




@router.post("",response_model=PostResponse,status_code=status.HTTP_201_CREATED)
async def create_post(post:PostCreate, current_user : CurrentUser, db: Annotated[AsyncSession, Depends(get_db_session)]):

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


# Now below we comment this out, because since we passed CurrentUser as the type hint for current_user and f you remember from auth.py that CurrentUser has a dependency So when the function runs, the Depends runs and authentication is ran before authorization is ran. So if authentication is failed, authorization won't even run at all  
   #result = await db.execute(select(models.User).where(models.User.id == post.user_id))
   #existing_user = result.scalars().first()

   #if not existing_user:
    #   raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
   
   #new_post = models.Post(title = post.title, content = post.content, user_id = post.user_id)
   new_post = models.Post(title = post.title, content = post.content, user_id = current_user.id) # Now instead of post.user_id for the user_id, we use the current_user which uses the Depends to get the current user id automatically, so it becomes current_user.id (it is also .id because it uses the User Schema) 

   
   db.add(new_post)  # I didn't add await here because 1) db.add returns None , and None is not awaitable and 2) db.add doesn't actually do any I/O, it just adds the object memory for it to wait to be committed 
   await db.commit()
   await db.refresh(new_post, attribute_names= ['author'])
   
   
   return new_post
