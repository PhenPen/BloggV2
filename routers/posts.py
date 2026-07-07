from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession


from fastapi import HTTPException as FastapiHttpException
import models
from database import get_db_session
from schemas import PostCreate, PostResponse, PostUpdate

router = APIRouter()

@router.get("",response_model=list[PostResponse],name= 'posts')
async def posts(db: Annotated[AsyncSession, Depends(get_db_session)]):
    # return {'posts' : pst}
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).order_by (models. Post.date_posted.desc()))
    posts = result.scalars().all()

    # since this return all posts , like an algorithm, can I at best just randomize it ?
    # Like lets say use the random library to randomize the final post
    return posts


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
async def update_post_full(post_id :int, updated_post : PostCreate, db: Annotated[AsyncSession, Depends(get_db_session)]):
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
    if updated_post.user_id != existing_post.user_id :
        result = await db.execute(select(models.User).where(models.User.id == updated_post.user_id))
        existing_user = result.scalars().first()

        # Then we check for if the new user exists in the database already, else we return an error 
        if not existing_user:
            raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "User not found")


    existing_post.title = updated_post.title
    existing_post.content= updated_post.content
    existing_post.user_id = updated_post.user_id

    # db.add(existing_post) # We didn't do db.add, why ? Because it already exists ? 
    await db.commit() # Also, just committing, won't it clash with the posts that already had the same values
    # don't forget brackets for the commit (db.commit())
    await db.refresh(existing_post,attribute_names = ['author'])  # We added attribute names so that when refreshing the post, the refresh keeps the author object ready to be sent quickly I think ??? I think I would still have to verify this 

    # Also, I think attribute_names is added every time we are creating a new resource (POST CRUD) or when we are updating a resource (PUT or PATCH CRUD)  
    return existing_post




@router.patch("/{post_id}",response_model=PostResponse, name = 'update_post_partial')
async def update_post_partial(post_id :int, updated_post : PostUpdate, db: Annotated[AsyncSession, Depends(get_db_session)]):
   

    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    existing_post = result.scalars().first()

    # We keep this line of code because we want it to check if the post trying to change exist, we can't change a post that doesn't exist 
    if not existing_post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "Post not found")
    

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
async def delete_post(post_id :int, db: Annotated[AsyncSession, Depends(get_db_session)]):

    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    existing_post = result.scalars().first()

    if not existing_post:
        raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail = "Post not found")
    
    await db.delete(existing_post)   # Remember in db.add, we didn't await but in db.delete, we had to await, this because db.delete is actually an I/O task 
    await db.commit()
    





    




@router.post("",response_model=PostResponse,status_code=status.HTTP_201_CREATED)
async def create_post(post:PostCreate, db: Annotated[AsyncSession, Depends(get_db_session)]):

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

   result = await db.execute(select(models.User).where(models.User.id == post.user_id))
   existing_user = result.scalars().first()

   if not existing_user:
       raise FastapiHttpException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
   
   new_post = models.Post(title = post.title, content = post.content, user_id = post.user_id)
   
   db.add(new_post)  # I didn't add await here because 1) db.add returns None , and None is not awaitable and 2) db.add doesn't actually do any I/O, it just adds the object memory for it to wait to be committed 
   await db.commit()
   await db.refresh(new_post, attribute_names= ['author'])
   
   
   return new_post
