from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account
from app.security import decode_token


def get_current_account(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> Account:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        account_id = decode_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "account not found")
    if account.is_banned:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"account is banned: {account.banned_reason or 'no reason given'}",
        )
    return account


def get_current_admin(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    if not account.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    return account
