import os
import cv2
import numpy as np
import logging
import datetime
from typing import Any, Dict, Generator, Optional, Tuple
from ultralytics import YOLO
from db import SessionLocal
from models import Violation
from utils import detect_crosswalk, intersection_area

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# --- Инициализация модели YOLO ---
model = YOLO("yolo-coco/best.pt") # Загрузка предварительно обученной модели YOLO


def draw_box(frame: np.ndarray, box: Tuple[int, int, int, int], color: Tuple[int, int, int], label: Optional[str] = None) -> None:
    """Отрисовывает ограничительную рамку с необязательной меткой на кадре."""
    x, y, w, h = box
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
    if label:
        cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def process_video(
    input_video: Any, # Источник видео (путь к файлу или 0 для веб-камеры)
    show_windows: bool = False, # Флаг для отображения окон OpenCV в процессе обработки
    return_frame: bool = False, # Флаг, указывающий, нужно ли возвращать сам кадр помимо данных
    save_output: bool = True, # Флаг для сохранения обработанного видео в файл
    stop_event: Any = None # Событие для прерывания обработки извне (например, от WebSocket)
) -> Generator:
    """
    Генератор, возвращающий результаты детекции и кадры для каждого кадра видео.
    Обрабатывает как видеофайлы, так и потоки с веб-камеры.
    Поддерживает внешнее прерывание через stop_event.
    """
    try:
        logging.info(f"Начало обработки видео: {input_video}")
        # --- Настройка источника видео ---
        if input_video == 0: # Если источник - веб-камера
            results = model.track(
                source=input_video,
                tracker="botsort.yaml", # Используемый трекер объектов
                show=False, # Не отображать стандартные окна Ultralytics
                verbose=False, # Уменьшить количество выводимой информации
                stream=True # Потоковая обработка для веб-камеры
            )
            fps = 30 # Предполагаемый FPS для веб-камеры
        else: # Если источник - видеофайл
            results = model.track(
                source=input_video,
                tracker="botsort.yaml",
                show=False,
                verbose=False
            )
            fps = None
            cap = cv2.VideoCapture(input_video)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS) # Получение FPS из видеофайла
            cap.release()
        if not fps or fps <= 0: # Проверка и установка FPS по умолчанию, если не удалось определить
            logging.warning("FPS не определён или равен 0! Используется 30 FPS.")
            fps = 30

        # --- Инициализация состояния ---
        crosswalk_detected = False # Флаг, обнаружен ли пешеходный переход
        crosswalk_position = None # Координаты обнаруженного пешеходного перехода (x, y, w, h)
        vehicle_states: Dict[int, Dict[str, bool]] = {} # Словарь для отслеживания состояния ТС (id: {crossed, crossed_on_red})
        total_cross_count = 0 # Общее количество пересечений ТС пешеходного перехода
        session = SessionLocal() # Сессия базы данных SQLAlchemy
        frame_idx = 0 # Счетчик обработанных кадров
        out = None # Объект VideoWriter для записи видео
        output_path = None # Путь к сохраняемому обработанному видео

        # --- Основной цикл обработки кадров ---
        for result in results: # Итерация по результатам детекции/трекинга от YOLO
            if stop_event is not None and stop_event.is_set(): # Проверка сигнала остановки
                logging.info("Получен сигнал остановки обработки видео.")
                break
            frame = result.orig_img # Получение оригинального кадра

            # Инициализация VideoWriter для сохранения видео, если это еще не сделано
            if out is None and save_output:
                os.makedirs('output', exist_ok=True) # Создание директории output, если ее нет
                if isinstance(input_video, int) and input_video == 0: # Для веб-камеры
                    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_path = f"output/processed_webcam_{ts}.avi"
                else: # Для видеофайла
                    base = os.path.basename(str(input_video))
                    output_path = f"output/processed_{base}.avi"
                fourcc = cv2.VideoWriter_fourcc(*"MJPG") # Кодек для записи видео
                out = cv2.VideoWriter(output_path, fourcc, fps, (frame.shape[1], frame.shape[0]))

            # --- Разбор результатов детекции --- 
            green_lights, red_lights, yellow_lights = [], [], [] # Списки для хранения рамок светофоров
            vehicle_boxes, vehicles, traffic_lights = [], [], [] # Списки для хранения информации об ТС и светофорах

            for box in result.boxes: # Итерация по обнаруженным объектам (bounding boxes)
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int) # Координаты рамки
                cls = int(box.cls[0]) # ID класса объекта
                track_id = int(box.id[0]) if box.id is not None else -1 # ID объекта от трекера
                label = model.names[cls] # Метка класса (например, 'car', 'red_light')

                # Фильтрация и сохранение транспортных средств
                if label in ['bus', 'car', 'motorcycle', 'truck', 'van']:
                    vehicle_boxes.append((x1, y1, x2 - x1, y2 - y1, label, track_id))
                    vehicles.append({
                        'id': track_id,
                        'label': label,
                        'bbox': [x1, y1, x2, y2]
                    })
                # Фильтрация и сохранение светофоров
                if label in ['green_light', 'red_light', 'yellow_light']:
                    traffic_lights.append({
                        'label': label,
                        'bbox': [x1, y1, x2, y2]
                    })
                    if label == 'green_light':
                        green_lights.append((x1, y1, x2 - x1, y2 - y1))
                    elif label == 'red_light':
                        red_lights.append((x1, y1, x2 - x1, y2 - y1))
                    elif label == 'yellow_light':
                        yellow_lights.append((x1, y1, x2 - x1, y2 - y1))
            
            is_red = bool(red_lights) # Флаг, горит ли красный свет

            # --- Детекция пешеходного перехода (выполняется один раз или до успешного обнаружения) ---
            if not crosswalk_detected:
                # Выбираем любой обнаруженный светофор как ориентир для поиска перехода
                any_light = green_lights[0] if green_lights else (red_lights[0] if red_lights else (yellow_lights[0] if yellow_lights else None))
                if any_light is not None:
                    lx, ly, lw, lh = any_light
                    crosswalk_position = detect_crosswalk(frame, (lx, ly, lw, lh))
                    if crosswalk_position is not None:
                        crosswalk_detected = True
            
            crosswalk_bbox = None # Bbox перехода для отправки клиенту
            if crosswalk_position:
                cx, cy, cw, ch = crosswalk_position
                crosswalk_bbox = [cx, cy, cw, ch]

            # --- Детекция нарушений (проезд на красный по пешеходному переходу) ---
            if crosswalk_position: # Если пешеходный переход обнаружен
                cx, cy, cw, ch = crosswalk_position
                crosswalk_box = (cx, cy, cw, ch) # Рамка пешеходного перехода

                for (vx, vy, vw, vh, vlabel, tid) in vehicle_boxes: # Итерация по ТС
                    veh_box = (vx, vy, vw, vh) # Рамка ТС
                    inter_area = intersection_area(veh_box, crosswalk_box) # Площадь пересечения ТС и перехода
                    veh_area = vw * vh # Площадь ТС

                    if veh_area > 0 and inter_area > 0: # Если есть пересечение
                        if tid not in vehicle_states: # Инициализация состояния для нового ТС
                            vehicle_states[tid] = {'crossed': False, 'crossed_on_red': False}
                        
                        if not vehicle_states[tid]['crossed']: # Если ТС еще не было отмечено как пересекшее
                            vehicle_states[tid]['crossed'] = True
                            total_cross_count += 1

                            if is_red: # Если ТС пересекает на красный свет
                                vehicle_states[tid]['crossed_on_red'] = True
                                violation_time = None
                                video_second = None

                                # Определение времени/секунды нарушения
                                if isinstance(input_video, int) and input_video == 0: # Для веб-камеры
                                    violation_time = datetime.datetime.now()
                                else: # Для видеофайла
                                    if fps and fps > 0:
                                        video_second = int((frame_idx + 1) / fps)
                                        logging.info(f"Кадр={frame_idx}, секунда видео={video_second}")
                                
                                # Создание и сохранение записи о нарушении в БД
                                violation = Violation(
                                    vehicle_id=str(tid),
                                    timestamp=violation_time,
                                    video_second=video_second,
                                    processed_video_path=output_path, # Путь к видео, где зафиксировано нарушение
                                    original_video_path=str(input_video) if isinstance(input_video, str) else None # Путь к исходному видео
                                )
                                session.add(violation)
                                session.commit()
            
            red_light_cross_count = sum(1 for v in vehicle_states.values() if v['crossed_on_red']) # Подсчет нарушений на красный

            # --- Отрисовка информации на кадре ---
            if crosswalk_position: # Отрисовка рамки пешеходного перехода
                cx, cy, cw, ch = crosswalk_position
                draw_box(frame, (cx, cy, cw, ch), (255, 0, 0), "Пешеходный переход")
            
            # Отрисовка рамок светофоров
            for (lx, ly, lw, lh) in green_lights:
                draw_box(frame, (lx, ly, lw, lh), (0, 255, 0), "Зеленый")
            for (lx, ly, lw, lh) in red_lights:
                draw_box(frame, (lx, ly, lw, lh), (0, 0, 255), "Красный")
            for (lx, ly, lw, lh) in yellow_lights:
                draw_box(frame, (lx, ly, lw, lh), (0, 255, 255), "Желтый")
            
            # Отрисовка рамок ТС
            for (vx, vy, vw, vh, vlabel, tid) in vehicle_boxes:
                label = f"{vlabel} ID:{tid}" if tid != -1 else vlabel
                draw_box(frame, (vx, vy, vw, vh), (255, 255, 0), label)
            
            # Отображение счетчиков на кадре
            cv2.putText(frame, f"Пересекло: {total_cross_count}", (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.putText(frame, f"На красный: {red_light_cross_count}", (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # --- Подготовка данных для вывода/отправки ---
            frame_data = {
                'vehicles': vehicles, # Список ТС с их параметрами
                'traffic_lights': traffic_lights, # Список светофоров
                'crosswalk_bbox': crosswalk_bbox, # Рамка пешеходного перехода
                'total_crossings': total_cross_count, # Общее число пересечений
                'red_light_violations': red_light_cross_count, # Число нарушений на красный
                'frame_width': frame.shape[1],
                'frame_height': frame.shape[0],
                'vehicle_states': vehicle_states, # Состояния ТС (кто пересек на красный)
                'output_path': output_path # Путь к сохраненному видео (если сохраняется)
            }

            if out is not None: # Запись кадра в файл, если включено сохранение
                out.write(frame)
            
            # Возврат данных генератором
            if return_frame: # Если нужно вернуть и кадр
                yield frame_data, frame
            else:
                yield frame_data # По умолчанию только метаданные

            if show_windows: # Отображение окна OpenCV, если включено
                cv2.imshow("Текущий кадр", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"): # Выход по нажатию 'q'
                    break
            frame_idx += 1 # Инкремент счетчика кадров
        
        # --- Завершение обработки ---
        if out is not None:
            out.release() # Освобождение объекта VideoWriter
        if show_windows:
            cv2.destroyAllWindows() # Закрытие окон OpenCV
        logging.info(f"Обработка видео завершена: {input_video}")
        session.close() # Закрытие сессии БД
    except Exception as e:
        logging.error(f"Ошибка при обработке видео: {e}")
        if show_windows: # Гарантированное закрытие окон при ошибке
            cv2.destroyAllWindows()

# Пример запуска обработки видео (для отладки или прямого вызова скрипта)
if __name__ == "__main__":
    # process_video("videos/1d.mp4", show_windows=False) # Пример с файлом
    pass # В текущей конфигурации запуск предполагается через FastAPI
