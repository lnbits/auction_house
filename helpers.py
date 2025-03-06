from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException
from lnbits.decorators import optional_user_id


async def check_user_id(user_id: Annotated[str, Depends(optional_user_id)]) -> str:
    if not user_id:
        raise HTTPException(HTTPStatus.UNAUTHORIZED)
    return user_id
