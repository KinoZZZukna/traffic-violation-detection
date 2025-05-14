from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from typing import Optional

# Базовый класс для декларативных моделей SQLAlchemy
Base = declarative_base()

class Violation(Base):
    """
    Модель SQLAlchemy для записей о нарушениях правил проезда на красный свет.
    Отражает структуру таблицы 'violations' в базе данных.
    """
    __tablename__ = 'violations' # Имя таблицы в базе данных

    # Уникальный идентификатор записи о нарушении (первичный ключ, автоинкремент)
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    
    # Идентификатор транспортного средства, совершившего нарушение (полученный от трекера)
    vehicle_id: str = Column(String(64))
    
    # Временная метка нарушения (для случаев обработки с веб-камеры)
    timestamp: Optional[datetime] = Column(DateTime, nullable=True)
    
    # Секунда видеофайла, на которой зафиксировано нарушение (для случаев обработки видеофайлов)
    video_second: Optional[int] = Column(Integer, nullable=True)
    
    # Путь к сохраненному обработанному видеофайлу с визуализацией нарушения
    processed_video_path: Optional[str] = Column(String(256), nullable=True)
    
    # Путь к оригинальному видеофайлу, на котором было зафиксировано нарушение
    original_video_path: Optional[str] = Column(String(256), nullable=True)
