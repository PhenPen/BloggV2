from datetime import datetime, timezone, timedelta
from pwdlib import PasswordHash
from fastapi.security import OAuth2PasswordBearer
from config import settings
import jwt


password_hash = PasswordHash.recommended()
Oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/users/token")

# In programming , a scheme is a set of rules or blueprint in which something should be handled, oauth2scheme is scheme that is set of rules or blueprint which states how the users should prove themselves to your API

def hash_password(password):
    return password_hash.hash(password)


def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)


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
            algorithms=settings.jwt_algorithm,
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    else:
        return payload.get("sub")
