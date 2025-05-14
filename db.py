from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- Конфигурация базы данных ---
# Строка подключения к базе данных MySQL.
# Формат: "mysql+драйвер://пользователь:пароль@хост:порт/имя_базы_данных"
DATABASE_URL: str = "mysql+pymysql://root:root@localhost:3306/traffic_violations"

# Создание движка SQLAlchemy, который будет управлять соединениями с БД.
engine = create_engine(DATABASE_URL)

# Создание фабрики сессий.
# autocommit=False: изменения не будут автоматически фиксироваться в БД.
# autoflush=False: изменения не будут автоматически отправляться в БД перед каждым запросом.
# bind=engine: привязка фабрики сессий к созданному движку.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
