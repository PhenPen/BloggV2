from datetime import datetime, timezone, timedelta
from pwdlib import PasswordHash
from fastapi.security import OAuth2PasswordBearer
from config import settings
import jwt
from fastapi import Depends, status
from main import FastapiHttpException
from sqlalchemy import select
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
import models
from database import get_db_session
import hashlib
import secrets



password_hash = PasswordHash.recommended()
Oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/users/token")

# In programming , a scheme is a set of rules or blueprint in which something should be handled, oauth2scheme is scheme that is set of rules or blueprint which states how the users should prove themselves to your API

def hash_password(password):
    return password_hash.hash(password)


def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)  # Why is it url_safe, it seems that every hash stuff seems to be multiplied by 2 to get the actual number

def hash_reset_token(token : str) -> str :
    return hashlib.sha256(token.encode()).hexdigest()   # token encode, coverts it to bytes and hexdigests gives back a hexadecimal string


def create_access_token(data: dict, minutes: timedelta | None = None):
    data_to_encode = data.copy()

    if minutes:
        access_token_expiry = datetime.now() + minutes
    else:
        access_token_expiry = datetime.now() + timedelta(
            minutes=settings.jwt_token_expiry_mins
        )

    data_to_encode.update({"exp": access_token_expiry})

    return jwt.encode(
        data_to_encode,
        key=settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


# We used get secret values because remember we gave our secret key type SecretStr from pydantic so calling it normally will just display asterisks


def verify_access_token(token):
    """ Verifies if a jwt token is valid and then extracts the subject of the token
    
    Args:
        token (str): JWT Token
    
    Returns:
        str | None : The subject of the token or None if subject can't be extracted
    """
    try:
        payload = jwt.decode(
            token,
            key=settings.jwt_secret_key.get_secret_value(), #Since the in our settings, the secret key is of type SecretStr, calling secretkey, without the get_secret_value() function won't return a string but asterisk, which can't be converted to string and will cause a traceback.
            # Check obsidian for the traceback caused and whatsapp
            algorithms=[settings.jwt_algorithm], # Note that this is a list instead of a string because decoding uses algorithms and not just a single algorithm.
            # We can also see it from the create_access_token , it uses a parameter of algorithm while the decode uses algorithms
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    else:
        return payload.get("sub")
 

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

CurrentUser = Annotated[models.User,Depends(get_current_user)]  # We create a variable that already contains annotated , so we can just call that variable instead of typing Annotated every time