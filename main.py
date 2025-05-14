import os
import uuid
import cv2
import asyncio
import logging
import numpy as np
import multiprocessing
from contextlib import contextmanager
from typing import Any, Dict

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from models import Violation
from db import SessionLocal

# --- Настройка приложения FastAPI ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешить все источники
    allow_credentials=True, # Разрешить учетные данные
    allow_methods=["*"],  # Разрешить все методы
    allow_headers=["*"],  # Разрешить все заголовки
)

UPLOAD_DIR = "uploaded_videos"  # Директория для загруженных видео
os.makedirs(UPLOAD_DIR, exist_ok=True) # Создать директорию, если она не существует

# --- Состояние многопроцессорной обработки ---
processes: Dict[int, Any] = {} # Словарь для хранения активных процессов обработки видео

# --- Вспомогательные функции ---
def get_file_path(directory: str, filename: str) -> str:
    """Формирует полный путь к файлу."""
    return os.path.join(directory, filename)

def to_python_type(obj: Any) -> Any:
    """Рекурсивно преобразует типы NumPy в нативные типы Python для JSON-сериализации."""
    if isinstance(obj, dict):
        return {k: to_python_type(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_python_type(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

@contextmanager
def get_session():
    """Контекстный менеджер для получения сессии базы данных."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

# --- Воркер для обработки видео/камеры в отдельном процессе ---
def camera_worker(video_path, queue, stop_event):
    """
    Обрабатывает кадры видео/камеры и отправляет результаты через очередь (queue)
    до тех пор, пока не будет установлено событие остановки (stop_event).
    """
    from yolo8_video import process_video # Импорт внутри функции для корректной работы multiprocessing
    for frame_data, frame in process_video(video_path, return_frame=True, stop_event=stop_event):
        if stop_event.is_set(): # Проверка флага остановки
            break
        ret, jpeg = cv2.imencode('.jpg', frame) # Кодирование кадра в JPEG
        if not ret:
            continue
        queue.put((frame_data, jpeg.tobytes())) # Отправка данных кадра и байтов JPEG в очередь
    queue.put(None)  # Сигнал о завершении обработки

# --- Эндпоинты API ---
@app.post("/process_video_file")
async def upload_video(file: UploadFile = File(...)):
    """Загружает видеофайл и возвращает путь к нему на сервере."""
    file_id = str(uuid.uuid4()) # Генерация уникального ID для файла
    file_path = get_file_path(UPLOAD_DIR, f"{file_id}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(await file.read()) # Сохранение файла на диск
    return {"file_id": file_id, "file_path": file_path}

@app.websocket("/ws/video_feed")
async def video_feed(websocket: WebSocket):
    """
    Осуществляет потоковую передачу обработанных видеокадров через WebSocket,
    используя отдельный процесс для обработки видео/камеры.
    """
    await websocket.accept()
    ws_id = id(websocket) # Уникальный идентификатор для WebSocket соединения
    queue = multiprocessing.Queue() # Очередь для обмена данными с процессом-воркером
    stop_event = multiprocessing.Event() # Событие для сигнализации об остановке воркера
    processes[ws_id] = (queue, stop_event) # Сохранение очереди и события в глобальном словаре
    try:
        data = await websocket.receive_json() # Получение JSON-сообщения от клиента
        video_path = data.get("file_path")

        # Проверка и установка источника видео (файл или веб-камера)
        if video_path in ("webcam", "0"):
            video_path = 0 # 0 обычно означает веб-камеру для OpenCV
        if video_path is None or (not isinstance(video_path, int) and not os.path.exists(video_path)):
            await websocket.send_json({"error": "Неверный или отсутствующий file_path"})
            return

        # Запуск процесса обработки видео
        process = multiprocessing.Process(target=camera_worker, args=(video_path, queue, stop_event))
        process.start()
        try:
            # Цикл получения и отправки данных клиенту
            while True:
                item = await asyncio.get_event_loop().run_in_executor(None, queue.get) # Асинхронное получение из очереди
                if item is None: # Сигнал о завершении от воркера
                    break
                frame_data, jpeg_bytes = item
                # Отправка метаданных кадра
                await websocket.send_json({
                    "type": "frame_data",
                    "data": to_python_type(frame_data) # Конвертация NumPy типов
                })
                # Отправка байтов изображения кадра
                await websocket.send_bytes(jpeg_bytes)
        except (WebSocketDisconnect, Exception):
            # Обработка отключения WebSocket или других исключений во внутреннем цикле
            stop_event.set() # Сигнализировать воркеру об остановке
        finally:
            # Гарантированная остановка и очистка ресурсов
            stop_event.set()
            process.join() # Ожидание завершения процесса-воркера
            queue.close()
            processes.pop(ws_id, None) # Удаление информации о процессе из словаря
    except WebSocketDisconnect:
        stop_event.set() # Установка события остановки при отключении клиента
        logging.info("WebSocket отключен")
    except Exception as e:
        stop_event.set() # Установка события остановки при других исключениях
        logging.exception("Ошибка WebSocket")
    finally:
        # Гарантированная очистка, если соединение было установлено, но произошла ошибка до основного try/finally
        stop_event.set()
        processes.pop(ws_id, None)

@app.get("/violations")
async def get_violations():
    """Возвращает список всех зарегистрированных нарушений."""
    with get_session() as session:
        violations = session.query(Violation).order_by(Violation.id.desc()).all()
        result = [
            {
                "id": v.id,
                "vehicle_id": v.vehicle_id,
                "timestamp": v.timestamp.isoformat() if v.timestamp else None,
                "video_second": v.video_second,
                "processed_video_path": v.processed_video_path,
                "original_video_path": v.original_video_path
            }
            for v in violations
        ]
    return JSONResponse(content=result)

@app.get("/uploaded_videos/{filename}")
async def get_uploaded_video(filename: str):
    """Предоставляет доступ к загруженному видеофайлу."""
    file_path = get_file_path("uploaded_videos", filename)
    return FileResponse(path=file_path, filename=filename, media_type='video/mp4')

@app.get("/download_processed_video")
async def download_processed_video(filename: str):
    """Предоставляет доступ к обработанному видеофайлу для скачивания."""
    file_path = get_file_path("output", filename)
    return FileResponse(path=file_path, filename=filename, media_type='video/x-msvideo')
