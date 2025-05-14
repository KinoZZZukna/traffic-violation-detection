import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Добавляем корень проекта в sys.path для корректного импорта моделей SQLAlchemy.
# Это необходимо, чтобы Alembic мог найти файл models.py и класс Base.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models import Base # Импорт Base из вашего файла models.py

# Объект конфигурации Alembic, предоставляет доступ к значениям из файла alembic.ini.
config = context.config

# Интерпретация файла конфигурации для настройки логирования Python.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Здесь указывается объект MetaData ваших моделей для поддержки автогенерации миграций.
# Alembic будет сравнивать состояние таблиц в БД с метаданными, определенными в Base.
target_metadata = Base.metadata

# Другие значения из конфигурации, определяемые потребностями env.py,
# могут быть получены здесь:
# my_important_option = config.get_main_option("my_important_option")
# ... и т.д.


def run_migrations_offline() -> None:
    """Запуск миграций в 'оффлайн' режиме.

    В этом режиме контекст настраивается только с URL к БД,
    без создания объекта Engine. Это позволяет генерировать SQL-скрипты
    без фактического подключения к базе данных.

    Вызовы context.execute() здесь выводят переданную строку в выходной скрипт.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True, # Используется для генерации SQL с литеральными значениями вместо placeholders
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в 'онлайн' режиме.

    В этом сценарии необходимо создать Engine (движок SQLAlchemy)
    и связать соединение (connection) с контекстом Alembic.
    Миграции применяются непосредственно к базе данных.
    """
    # Получение конфигурации БД из alembic.ini для создания движка
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", # Префикс для опций SQLAlchemy в alembic.ini
        poolclass=pool.NullPool, # NullPool рекомендуется для Alembic, чтобы избежать проблем с соединениями
    )

    with connectable.connect() as connection: # Установка соединения с БД
        context.configure(
            connection=connection, # Передача активного соединения в контекст
            target_metadata=target_metadata # Передача метаданных моделей
        )

        with context.begin_transaction(): # Начало транзакции
            context.run_migrations() # Выполнение миграций


# Определение режима запуска миграций (оффлайн или онлайн)
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
