"""
认证与用户管理服务
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.db.models import User
from app.utils.logger import get_logger

logger = get_logger("auth_service")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
auth_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """验证密码"""
    try:
        return pwd_context.verify(plain_password, password_hash)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def read_initial_password(path: str) -> str:
    """
    从配置文件读取初始密码
    - 如果文件不存在或为空，则回退到默认值 'admin123'
    - 文件仅读取第一行内容
    """
    try:
        pwd_path = Path(path)
        if pwd_path.exists():
            content = pwd_path.read_text(encoding="utf-8").splitlines()
            if content:
                password = content[0].strip()
                if password:
                    return password
        logger.warning(f"初始密码文件缺失或为空，已使用默认密码 'admin123' ({path})")
    except Exception as e:
        logger.warning(f"读取初始密码文件失败，使用默认密码: {e}")
    return "admin123"


def ensure_initial_admin(db: Session) -> User:
    """
    确保默认管理员账户存在
    - 用户名由 settings.default_admin_username 指定
    - 密码从 settings.initial_admin_password_file 读取
    """
    username = settings.default_admin_username
    user = db.query(User).filter(User.username == username).first()
    if user:
        return user

    password = read_initial_password(settings.initial_admin_password_file)
    password_hash = get_password_hash(password)
    user = User(
        username=username,
        password_hash=password_hash,
        is_admin=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"默认管理员已创建: {username}")
    return user


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """校验用户名和密码"""
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def change_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    """
    更新用户密码（需提供当前密码）
    """
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")

    user.password_hash = get_password_hash(new_password)
    db.add(user)
    db.commit()


def create_user(db: Session, username: str, password: str, is_admin: bool = False) -> User:
    """创建新用户"""
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    password_hash = get_password_hash(password)
    user = User(
        username=username,
        password_hash=password_hash,
        is_admin=is_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    target: User,
    password: Optional[str] = None,
    is_admin: Optional[bool] = None,
    is_active: Optional[bool] = None,
) -> User:
    """更新用户信息"""
    if password:
        target.password_hash = get_password_hash(password)
    if is_admin is not None:
        target.is_admin = is_admin
    if is_active is not None:
        target.is_active = is_active

    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def delete_user(db: Session, target: User):
    """删除用户"""
    db.delete(target)
    db.commit()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> User:
    """获取当前用户（验证 JWT）"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效令牌")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效令牌")

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已被禁用")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """仅管理员可访问的依赖"""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
