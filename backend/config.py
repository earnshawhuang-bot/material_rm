"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


class Settings:
    """集中管理后端运行时配置。"""

    app_name: str = os.getenv("APP_NAME", "RM Inventory Platform")

    database_dialect: str = os.getenv("SQL_DIALECT", "sqlite").strip().lower()
    database_url: str = os.getenv("DATABASE_URL", "").strip()

    sql_server: str = os.getenv("SQL_SERVER", "172.18.164.9")
    sql_port: str = os.getenv("SQL_PORT", "1433")
    sql_database: str = os.getenv("SQL_DATABASE", "rm_inventory_db")
    sql_user: str = os.getenv("SQL_USER", "sa")
    sql_password: str = os.getenv("SQL_PASSWORD", "")
    sql_driver: str = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")

    sqlite_path: str = os.getenv("SQLITE_PATH", "backend/rm_inventory_demo.db")
    seed_sqlite_demo: bool = _to_bool(os.getenv("SEED_SQLITE_DEMO", "1"), default=True)

    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "please-change-this-key")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_hours: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "8"))

    upload_max_file_size_mb: int = int(os.getenv("UPLOAD_MAX_FILE_SIZE_MB", "20"))
    default_admin_username: str = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    default_admin_password: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "123456")

    def get_database_url(self) -> str:
        """Return SQLAlchemy 连接字符串（ODBC）."""
        if self.database_dialect == "sqlite":
            if self.database_url:
                return self.database_url
            db_path = Path(self.sqlite_path).as_posix()
            return f"sqlite:///{db_path}"
        if self.database_url:
            return self.database_url

        password_part = self.sql_password or ""
        connect_str = (
            f"DRIVER={{{self.sql_driver}}};"
            f"SERVER={self.sql_server},{self.sql_port};"
            f"DATABASE={self.sql_database};"
            f"UID={self.sql_user};"
            f"PWD={password_part};"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
        )
        return f"mssql+pyodbc:///?odbc_connect={quote_plus(connect_str)}"


settings = Settings()
