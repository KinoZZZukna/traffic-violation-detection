# Документация по системе видеоаналитики нарушений ПДД

## Оглавление
1. [Введение](#введение)
2. [Архитектура системы](#архитектура-системы)
3. [Пользовательский интерфейс (Frontend)](#пользовательский-интерфейс-frontend)
    3.1. [Обзор интерфейса](#обзор-интерфейса)
    3.2. [Загрузка и выбор видеофайла](#загрузка-и-выбор-видеофайла)
    3.3. [Запуск обработки видео](#запуск-обработки-видео)
    3.4. [Обработка с веб-камеры](#обработка-с-веб-камеры)
    3.5. [Отображение процесса обработки](#отображение-процесса-обработки)
    3.6. [Просмотр и скачивание результатов](#просмотр-и-скачивание-результатов)
    3.7. [История нарушений](#история-нарушений)
4. [Серверная часть (Backend)](#серверная-часть-backend)
    4.1. [Обзор API](#обзор-api)
    4.2. [Обработка загрузки видеофайлов](#обработка-загрузки-видеофайлов)
    4.3. [WebSocket для потоковой передачи данных](#websocket-для-потоковой-передачи-данных)
    4.4. [Взаимодействие с базой данных](#взаимодействие-с-базой-данных)
    4.5. [Многопроцессорная обработка видео](#многопроцессорная-обработка-видео)
5. [Модуль обработки видео (`yolo8_video.py`)](#модуль-обработки-видео-yolo8_videopy)
    5.1. [Инициализация модели YOLO](#инициализация-модели-yolo)
    5.2. [Основной цикл обработки кадров (`process_video`)](#основной-цикл-обработки-кадров-process_video)
    5.3. [Детекция объектов](#детекция-объектов)
    5.4. [Трекинг объектов](#трекинг-объектов)
    5.5. [Детекция пешеходного перехода (`utils.detect_crosswalk`)](#детекция-пешеходного-перехода-utilsdetect_crosswalk)
    5.6. [Логика определения нарушений](#логика-определения-нарушений)
    5.7. [Запись результатов в БД](#запись-результатов-в-бд)
    5.8. [Формирование обработанного видео](#формирование-обработанного-видео)
6. [Вспомогательные утилиты (`utils.py`)](#вспомогательные-утилиты-utilspy)
    6.1. [Алгоритм детекции пешеходного перехода](#алгоритм-детекции-пешеходного-перехода)
    6.2. [Расчет области пересечения](#расчет-области-пересечения)
7. [База данных](#база-данных)
    7.1. [Схема данных (модель `Violation`)](#схема-данных-модель-violation)
    7.2. [Настройка подключения](#настройка-подключения)
    7.3. [Миграции Alembic](#миграции-alembic)
8. [Модель YOLO: Детекция и трекинг](#модель-yolo-детекция-и-трекинг)
    8.1. [Принцип работы YOLO](#принцип-работы-yolo)
    8.2. [Используемая модель (`best.pt`)](#используемая-модель-bestpt)
    8.3. [Классы объектов](#классы-объектов)
    8.4. [Механизм трекинга (BoT-SORT)](#механизм-трекинга-bot-sort)
9. [Развертывание и запуск](#развертывание-и-запуск)
10. [Возможные доработки](#возможные-доработки)

## 1. Введение
Данный документ описывает работу системы видеоаналитики нарушений правил дорожного движения (ПДД), в частности, проезда на запрещающий сигнал светофора по пешеходному переходу. Система состоит из веб-интерфейса для загрузки видео и просмотра результатов, серверной части для обработки видео и управления данными, а также модуля машинного зрения на базе YOLO для детекции и отслеживания объектов.

## 2. Архитектура системы
Система имеет трехуровневую архитектуру:
1.  **Клиентская часть (Frontend)**: Разработана на Angular. Позволяет пользователю загружать видеофайлы или инициировать обработку с веб-камеры, отображает поток обрабатываемого видео с результатами детекции в реальном времени, а также предоставляет доступ к истории зафиксированных нарушений.
2.  **Серверная часть (Backend)**: Реализована на FastAPI (Python). Обрабатывает HTTP-запросы от клиента (загрузка файлов, запросы к истории нарушений), управляет WebSocket-соединениями для потоковой передачи данных обработки видео. Запускает и контролирует процессы анализа видео. Взаимодействует с базой данных для сохранения и извлечения информации о нарушениях.
3.  **Модуль обработки видео**: Основная логика реализована в Python с использованием библиотеки `ultralytics` для модели YOLOv8 и `OpenCV` для обработки изображений. Этот модуль отвечает за детекцию транспортных средств, светофоров, пешеходных переходов, отслеживание объектов и фиксацию нарушений.

Взаимодействие компонентов:
- Пользователь через Frontend загружает видеофайл или выбирает обработку с веб-камеры.
- Frontend отправляет запрос на Backend.
- Backend инициирует процесс обработки видео, используя модуль `yolo8_video.py`. Для обработки файлов, не блокирующей основной поток, используется `multiprocessing`.
- Модуль обработки видео кадр за кадром анализирует видеопоток, детектирует объекты, определяет нарушения и сохраняет информацию о нарушениях в базу данных MySQL.
- Backend через WebSocket транслирует обработанные кадры и метаданные детекции обратно на Frontend.
- Frontend отображает видеопоток и информацию о нарушениях. Пользователь также может запросить историю нарушений, которая извлекается Backend'ом из БД.

## 3. Пользовательский интерфейс (Frontend)
Компонент: `video-detection-frontend/src/app/video-stream/video-stream.component.ts`
Шаблон: `video-detection-frontend/src/app/video-stream/video-stream.component.html`
Стили: `video-detection-frontend/src/app/video-stream/video-stream.component.scss`

### 3.1. Обзор интерфейса
Интерфейс предоставляет следующие элементы управления и отображения:
-   Кнопка "Выберите файл" для загрузки видео.
-   Отображение имени выбранного файла.
-   Кнопка "Скачать обработанное видео" (появляется после обработки).
-   Кнопка "Старт обработки" для запуска анализа выбранного файла.
-   Кнопка "Обработка с камеры" для запуска анализа с веб-камеры.
-   Кнопка "Остановить" для прекращения текущей обработки.
-   Область для отображения видеопотока (`<img #videoImage>`).
-   Карточка с информацией о текущих нарушениях на красный свет (общее количество, ID нарушителей).
-   Раскрывающаяся панель "Показать raw-логи" для просмотра JSON-данных детекции.
-   Секция "История нарушений" с таблицей, отображающей ранее зафиксированные нарушения, и кнопкой "Обновить".

### 3.2. Загрузка и выбор видеофайла
Метод: `async onFileSelected(event: Event)`
1.  Пользователь нажимает кнопку "Выберите файл", что активирует скрытый элемент `<input type="file" #fileInput>`.
2.  После выбора файла срабатывает событие `(change)`, которое вызывает метод `onFileSelected`.
3.  Метод получает выбранный файл (`input.files?.[0]`).
4.  Устанавливается флаг `this.uploading = true`.
5.  Создается объект `FormData`, и файл добавляется в него (`formData.append('file', file)`).
6.  Выполняется асинхронный POST-запрос на эндпоинт `http://localhost:8000/process_video_file` с `FormData` в теле запроса.
7.  Сервер сохраняет файл и возвращает JSON с путем к файлу на сервере (`data.file_path`). Этот путь сохраняется в `this.filePath`.
8.  Флаг `this.uploading` снимается.

### 3.3. Запуск обработки видео
Метод: `startProcessing()`
1.  Этот метод доступен, если `this.filePath` (путь к загруженному файлу) существует и обработка не запущена (`!processing`).
2.  Вызывается `this.prepareForProcessing()`, который сбрасывает `this.processedVideoFilename` и `this.detectionData` в `null`.
3.  Вызывается `this.openWebSocket(this.filePath)`, который инициирует WebSocket-соединение и отправляет серверу путь к файлу для начала обработки.

### 3.4. Обработка с веб-камеры
Метод: `startWebcam()`
1.  Метод доступен, если обработка не запущена (`!processing`).
2.  Вызывается `this.prepareForProcessing()` для сброса состояния.
3.  Вызывается `this.openWebSocket('0')`. Строка `'0'` является специальным значением, которое сервер интерпретирует как команду использовать веб-камеру в качестве источника видео.

### 3.5. Отображение процесса обработки
Метод: `private handleWebSocketMessage(event: MessageEvent)`
1.  WebSocket (`this.ws`) получает сообщения от сервера в ходе обработки.
2.  **Если тип сообщения - строка (JSON)**:
    *   Строка парсится как JSON (`JSON.parse(event.data)`).
    *   Если `msg.type === 'frame_data'`, то `this.detectionData` обновляется данными из `msg.data`. Эти данные включают информацию о детекциях (координаты рамок, классы объектов, ID), счетчики нарушений и т.д.
    *   Если в `msg.data.output_path` есть путь к обработанному видео, его имя извлекается и сохраняется в `this.processedVideoFilename`.
3.  **Если тип сообщения - `ArrayBuffer` (бинарные данные кадра видео)**:
    *   Данные преобразуются в `Blob` типа `image/jpeg`.
    *   Создается URL для этого Blob (`URL.createObjectURL(blob)`).
    *   Этот URL присваивается атрибуту `src` элемента `<img #videoImage>`, что приводит к отображению кадра в интерфейсе.
    *   После загрузки изображения URL отзывается (`URL.revokeObjectURL(url)`) для освобождения ресурсов.

Метод `private drawBoundingBoxes()` является устаревшим (`@deprecated`). Ранее он использовался для отрисовки рамок детектированных объектов на `overlayCanvas` на стороне клиента. Теперь отрисовка рамок выполняется на стороне бэкенда, и клиент получает уже готовое изображение.

### 3.6. Просмотр и скачивание результатов
-   **Скачивание обработанного видео**:
    Метод: `downloadProcessedVideo()`
    *   Если `this.processedVideoFilename` (имя файла, полученное через WebSocket) существует, открывается новое окно браузера со ссылкой вида `http://localhost:8000/download_processed_video?filename=${this.processedVideoFilename}`. Это инициирует скачивание файла через соответствующий эндпоинт бэкенда.
-   **Ссылки в истории нарушений**:
    Методы `getOriginalVideoUrl(v: Violation)` и `getProcessedVideoUrl(v: Violation)` формируют URL для скачивания оригинального и обработанного видео для конкретного нарушения из истории.
    *   `getOriginalVideoUrl`: Формирует ссылку вида `http://localhost:8000/uploaded_videos/${filename}`.
    *   `getProcessedVideoUrl`: Формирует ссылку вида `http://localhost:8000/download_processed_video?filename=${filename}`.
    Эти ссылки используются в шаблоне для атрибутов `href` тегов `<a>`.

### 3.7. История нарушений
Метод: `async loadViolations()`
1.  Вызывается при инициализации компонента (`ngOnInit()`) и при нажатии кнопки "Обновить" (иконка `refresh`).
2.  Выполняет асинхронный GET-запрос на эндпоинт `http://localhost:8000/violations`.
3.  Полученный JSON-ответ (массив объектов нарушений) парсится и присваивается свойству `this.violations`.
4.  Данные из `this.violations` отображаются в таблице (`<table mat-table [dataSource]="violations">`) на странице. Колонки таблицы включают ID нарушения, ID транспортного средства, временную метку, секунду видео, а также ссылки на оригинальное и обработанное видео.

## 4. Серверная часть (Backend)
Файл: `main.py`

### 4.1. Обзор API
Backend построен с использованием FastAPI и предоставляет следующие основные эндпоинты:
-   **`POST /process_video_file`**: Принимает загружаемый видеофайл, сохраняет его на сервере и возвращает путь к файлу.
-   **`WebSocket /ws/video_feed`**: Основной эндпоинт для интерактивной обработки видео. Клиент подключается, отправляет путь к файлу (или '0' для веб-камеры), и сервер начинает потоковую передачу обработанных кадров и данных детекции.
-   **`GET /violations`**: Возвращает список всех зафиксированных нарушений из базы данных.
-   **`GET /uploaded_videos/{filename}`**: Предоставляет доступ к оригинальным загруженным видеофайлам.
-   **`GET /download_processed_video`**: Предоставляет доступ к видеофайлам, которые были обработаны системой.

### 4.2. Обработка загрузки видеофайлов
Эндпоинт: `async def upload_video(file: UploadFile = File(...))`
1.  Функция вызывается при POST-запросе на `/process_video_file`.
2.  Параметр `file: UploadFile` содержит загружаемый файл.
3.  Генерируется уникальный идентификатор файла (`file_id = str(uuid.uuid4())`).
4.  Формируется путь для сохранения файла: `UPLOAD_DIR` (константа `"uploaded_videos"`) + `/{file_id}_{file.filename}`.
5.  Файл считывается (`await file.read()`) и записывается на диск в бинарном режиме.
6.  Клиенту возвращается JSON-ответ, содержащий `file_id` и `file_path` (полный путь к сохраненному файлу на сервере).

### 4.3. WebSocket для потоковой передачи данных
Эндпоинт: `async def video_feed(websocket: WebSocket)`
1.  Принимает новое WebSocket-соединение (`await websocket.accept()`).
2.  Каждому соединению присваивается уникальный `ws_id` (на основе `id(websocket)`).
3.  Создаются `multiprocessing.Queue()` для передачи данных из дочернего процесса и `multiprocessing.Event()` (`stop_event`) для сигнализации об остановке. Они сохраняются в глобальный словарь `processes` по `ws_id`.
4.  Ожидается JSON-сообщение от клиента с путем к видео: `data = await websocket.receive_json()`. `video_path = data.get("file_path")`.
5.  Если `video_path` это "webcam" или "0", он заменяется на целочисленное `0`.
6.  Проверяется, что `video_path` существует (если это не `0`). В случае ошибки клиенту отправляется сообщение.
7.  Создается новый процесс `multiprocessing.Process` с целевой функцией `camera_worker`. В `camera_worker` передаются `video_path`, `queue` и `stop_event`. Процесс запускается (`process.start()`).
8.  **Основной цикл обработки сообщений из очереди**:
    *   Асинхронно ожидаются элементы из `queue` (`await asyncio.get_event_loop().run_in_executor(None, queue.get)`). Это позволяет не блокировать основной поток FastAPI.
    *   Если получен `None`, это сигнал о завершении обработки в `camera_worker`, цикл прерывается.
    *   Иначе, из элемента извлекаются `frame_data` (метаданные) и `jpeg_bytes` (кадр).
    *   `frame_data` (может содержать типы NumPy) конвертируется в нативные типы Python с помощью `to_python_type` для корректной JSON-сериализации.
    *   Клиенту отправляются два сообщения:
        *   JSON: `{"type": "frame_data", "data": to_python_type(frame_data)}`
        *   Бинарные данные: `jpeg_bytes`
9.  **Обработка завершения и ошибок**:
    *   В блоках `except (WebSocketDisconnect, Exception)` и `finally` устанавливается `stop_event.set()`, чтобы сигнализировать `camera_worker` о необходимости завершения.
    *   Вызывается `process.join()` для ожидания завершения дочернего процесса.
    *   Очередь закрывается (`queue.close()`).
    *   Запись о процессе удаляется из `processes`.

### 4.4. Взаимодействие с базой данных
-   **Настройка**: Файл `db.py` определяет `DATABASE_URL` для подключения к MySQL, создает `engine` SQLAlchemy и `SessionLocal` (фабрику сессий).
-   **Модели**: Файл `models.py` определяет модель `Violation` с помощью SQLAlchemy ORM, которая соответствует таблице `violations` в БД.
-   **Получение сессии**: Контекстный менеджер `get_session()` в `main.py` используется для удобного получения и закрытия сессий БД:
    ```python
    @contextmanager
    def get_session():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
    ```
-   **Чтение нарушений**: Эндпоинт `@app.get("/violations")` использует `get_session()` для получения сессии и выполнения запроса:
    `session.query(Violation).order_by(Violation.id.desc()).all()`
    Результаты преобразуются в список словарей и возвращаются как `JSONResponse`.
-   **Запись нарушений**: Происходит в модуле `yolo8_video.py` (см. раздел 5.7).

### 4.5. Многопроцессорная обработка видео
-   Для предотвращения блокировки основного асинхронного цикла FastAPI при выполнении ресурсоемкой задачи обработки видео, используется модуль `multiprocessing`.
-   Функция `camera_worker(video_path, queue, stop_event)` выполняется в отдельном процессе:
    1.  Импортирует `process_video` из `yolo8_video.py` (импорт внутри функции, чтобы избежать проблем с сериализацией при создании процесса).
    2.  Итерирует по генератору `process_video`, получая `frame_data` и `frame`.
    3.  Проверяет `stop_event.is_set()` на каждой итерации для возможности прерывания.
    4.  Кодирует `frame` в JPEG (`cv2.imencode('.jpg', frame)`).
    5.  Помещает кортеж `(frame_data, jpeg.tobytes())` в `queue`.
    6.  После завершения цикла (или при срабатывании `stop_event`) помещает `None` в `queue` как сигнал о завершении.
-   Словарь `processes: Dict[int, Any]` в `main.py` хранит кортежи `(queue, stop_event)` для каждого активного WebSocket-соединения (и, соответственно, для каждого дочернего процесса обработки видео). Это позволяет управлять жизненным циклом процессов и их коммуникацией.

## 5. Модуль обработки видео (`yolo8_video.py`)

### 5.1. Инициализация модели YOLO
-   `model = YOLO("yolo-coco/best.pt")`
-   Загружается предварительно обученная модель YOLO. Файл `best.pt` (находится в директории `yolo-coco/`) содержит веса модели, вероятно, дообученной на специфическом наборе данных для улучшения детекции транспортных средств и элементов дорожной инфраструктуры. Предположительно, используется одна из версий YOLOv8 от Ultralytics.

### 5.2. Основной цикл обработки кадров (`process_video`)
Функция-генератор `process_video(input_video, show_windows=False, return_frame=False, save_output=True, stop_event=None)`:
1.  **Источник видео**:
    *   Если `input_video == 0` (веб-камера), используется `model.track(source=0, stream=True, ...)` для потоковой обработки. FPS устанавливается в 30.
    *   Если `input_video` - путь к файлу, используется `model.track(source=input_video, ...)` . FPS извлекается из видеофайла с помощью `cv2.VideoCapture`. Если FPS не удается определить, используется значение по умолчанию 30.
2.  **Инициализация состояния**:
    *   `crosswalk_detected = False`, `crosswalk_position = None`: для детекции пешеходного перехода.
    *   `vehicle_states: Dict[int, Dict[str, bool]] = {}`: словарь для отслеживания состояния ТС (пересек ли переход, пересек ли на красный).
    *   `total_cross_count = 0`: общий счетчик пересечений.
    *   `session = SessionLocal()`: создается сессия для работы с БД.
    *   `frame_idx = 0`: счетчик кадров.
    *   `out = None`, `output_path = None`: для сохранения обработанного видео.
3.  **Цикл по кадрам**: Итерация по `results` (результатам `model.track()`):
    *   **Проверка `stop_event`**: Если событие установлено, обработка прерывается.
    *   `frame = result.orig_img`: получение оригинального кадра.
    *   **Инициализация `VideoWriter`**: Если `save_output` истинно и `out` еще не создан, создается объект `cv2.VideoWriter` для записи обработанного видео в директорию `output/`. Имя файла генерируется на основе текущей даты/времени для веб-камеры или имени исходного файла.
    *   **Парсинг детекций**: (см. 5.3)
    *   **Детекция пешеходного перехода**: (см. 5.5)
    *   **Логика определения нарушений**: (см. 5.6)
    *   **Отрисовка на кадре**: На кадр наносятся рамки для ТС, светофоров, пешеходного перехода, а также текстовая информация о счетчиках (`draw_box`, `cv2.putText`).
    *   **Формирование `frame_data`**: Словарь с данными о детекциях, нарушениях, размерах кадра и т.д., который будет отправлен клиенту.
    *   **Запись кадра**: Если `out` существует, кадр `frame` записывается в видеофайл.
    *   **Yield результата**: Генератор возвращает `frame_data` (и `frame`, если `return_frame=True`).
    *   **Отображение (опционально)**: Если `show_windows=True`, кадр отображается в окне OpenCV.
    *   Инкремент `frame_idx`.
4.  **Завершение**:
    *   Если `out` был создан, он освобождается (`out.release()`).
    *   Если окна отображались, они закрываются.
    *   Сессия БД закрывается (`session.close()`).
5.  **Обработка ошибок**: Обернуто в `try...except` для логирования ошибок.

### 5.3. Детекция объектов
Внутри цикла по кадрам, для каждого `result` из `model.track()`:
1.  Инициализируются списки: `green_lights, red_lights, yellow_lights, vehicle_boxes, vehicles, traffic_lights`.
2.  Итерация по `result.boxes` (обнаруженные объекты в текущем кадре):
    *   Из `box.xyxy[0]` извлекаются координаты рамки `(x1, y1, x2, y2)`.
    *   Из `box.cls[0]` извлекается ID класса, а из `model.names[cls]` - имя класса (метка).
    *   Из `box.id[0]` извлекается трекинговый ID объекта (если трекер активен).
    *   **Фильтрация ТС**: Если `label` принадлежит списку `['bus', 'car', 'motorcycle', 'truck', 'van']`:
        *   Информация о ТС добавляется в `vehicle_boxes` (в формате `(x1, y1, width, height, label, track_id)`) и `vehicles` (в формате словаря для `frame_data`).
    *   **Фильтрация светофоров**: Если `label` принадлежит списку `['green_light', 'red_light', 'yellow_light']`:
        *   Информация о светофоре добавляется в `traffic_lights` (в формате словаря для `frame_data`).
        *   В зависимости от типа светофора, его рамка добавляется в соответствующий список (`green_lights`, `red_lights`, `yellow_lights`).
3.  Устанавливается флаг `is_red = bool(red_lights)`, указывающий на наличие активного красного сигнала.

### 5.4. Трекинг объектов
-   Трекинг обеспечивается вызовом `model.track(tracker="botsort.yaml", ...)` при инициализации обработки видео.
-   `botsort.yaml` - это конфигурационный файл для трекера BoT-SORT.
-   Для каждого обнаруженного объекта, который успешно отслеживается, `box.id` будет содержать уникальный целочисленный идентификатор (`track_id`). Этот ID сохраняется для объекта на протяжении нескольких кадров, пока трекер может его сопоставлять.
-   `track_id` используется для ведения `vehicle_states` и корректной фиксации нарушений для конкретных ТС.

### 5.5. Детекция пешеходного перехода (`utils.detect_crosswalk`)
1.  Выполняется только если `crosswalk_detected == False` (т.е. один раз за сеанс обработки или пока переход не будет успешно найден).
2.  Для вызова `detect_crosswalk` требуется рамка какого-либо светофора (`any_light`). Берется первый попавшийся из `green_lights`, `red_lights` или `yellow_lights`.
3.  Если светофор найден, вызывается `crosswalk_position = detect_crosswalk(frame, (lx, ly, lw, lh))` из `utils.py`. Эта функция пытается найти область пешеходного перехода на кадре `frame`, используя позицию светофора `(lx, ly, lw, lh)` как ориентир.
4.  Если переход найден, `crosswalk_detected` устанавливается в `True`, и `crosswalk_position` (кортеж `(x, y, w, h)`) сохраняется для использования в последующих кадрах.
5.  `crosswalk_bbox` (список `[x, y, w, h]`) формируется для `frame_data`.

### 5.6. Логика определения нарушений
Выполняется на каждом кадре, если `crosswalk_position` был ранее определен:
1.  Из `crosswalk_position` извлекаются координаты `(cx, cy, cw, ch)`.
2.  Итерация по всем обнаруженным ТС (`vehicle_boxes`):
    *   Для каждого ТС (`(vx, vy, vw, vh, vlabel, tid)`), его рамка `veh_box` сравнивается с рамкой перехода `crosswalk_box` с помощью `intersection_area(veh_box, crosswalk_box)`.
    *   Если площадь пересечения (`inter_area`) больше нуля (т.е. ТС находится на переходе):
        *   Если `tid` (ID ТС) еще нет в `vehicle_states`, он добавляется с начальным состоянием `{'crossed': False, 'crossed_on_red': False}`.
        *   Если ТС ранее не было отмечено как пересекшее переход (`not vehicle_states[tid]['crossed']`):
            *   `vehicle_states[tid]['crossed'] = True`.
            *   `total_cross_count` инкрементируется.
            *   **Проверка на красный свет**: Если `is_red` (красный светофор активен в данный момент):
                *   `vehicle_states[tid]['crossed_on_red'] = True`.
                *   **Фиксация нарушения**:
                    *   `violation_time` (текущее время для веб-камеры) или `video_second` (рассчитанная секунда видео для файла) определяется.
                    *   Создается объект `Violation` из `models.py`.
                    *   Поля `vehicle_id`, `timestamp`/`video_second`, `processed_video_path`, `original_video_path` заполняются.
                    *   Запись добавляется в сессию БД (`session.add(violation)`) и сохраняется (`session.commit()`).
3.  Обновляется `red_light_cross_count` на основе `vehicle_states`.

### 5.7. Запись результатов в БД
-   Как описано в п. 5.6, при каждом выявлении факта проезда ТС на красный свет по пешеходному переходу, создается экземпляр модели `Violation`.
-   Эта модель содержит информацию о нарушителе (`vehicle_id`), времени/секунде нарушения, путях к видеофайлам.
-   `session.add(violation)` добавляет объект в текущую сессию SQLAlchemy.
-   `session.commit()` фиксирует изменения в базе данных. Сессия (`session = SessionLocal()`) создается в начале функции `process_video` и закрывается в конце.

### 5.8. Формирование обработанного видео
1.  Если `save_output=True`, то при первом кадре (или когда `out is None`):
    *   Создается директория `output/`, если она не существует.
    *   Определяется `output_path` для сохраняемого видео. Для веб-камеры имя генерируется с временной меткой (e.g., `output/processed_webcam_YYYYMMDD_HHMMSS.avi`). Для файла используется имя исходного файла с префиксом `processed_` (e.g., `output/processed_myvideo.mp4.avi`).
    *   Создается объект `cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))`. `fourcc` установлен в `"MJPG"`.
2.  На каждом кадре (`frame`):
    *   Вызывается функция `draw_box` для отрисовки рамок вокруг обнаруженных пешеходных переходов, светофоров (разными цветами в зависимости от сигнала) и транспортных средств (с меткой класса и ID).
    *   `cv2.putText` используется для отображения счетчиков `Crossed` и `Red Crossed` на кадре.
    *   Модифицированный кадр `frame` записывается в видеофайл с помощью `out.write(frame)`.
3.  После завершения обработки всех кадров (или при прерывании), если `out` был создан, вызывается `out.release()` для корректного завершения записи файла.

## 6. Вспомогательные утилиты (`utils.py`)

### 6.1. Алгоритм детекции пешеходного перехода (`detect_crosswalk`)
Функция `detect_crosswalk(frame: np.ndarray, light_box: Tuple[int, int, int, int]) -> Optional[Tuple[int, int, int, int]]`:
1.  **Входные данные**: Оригинальный кадр (`frame`) и кортеж с координатами рамки светофора (`light_box = (xlight, ylight, wlight, hlight)`).
2.  **Преобразование в серое**: Кадр конвертируется в оттенки серого (`gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)`).
3.  **Адаптивная бинаризация**: Применяется `cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 115, 1)` для получения бинарного изображения, где белые пиксели соответствуют возможным линиям разметки.
4.  **Морфологические операции**:
    *   Эрозия (`cv2.erode`) с ядром 3x3 для удаления мелкого шума.
    *   Дилатация (`cv2.dilate`) с ядром 3x3 (2 итерации) для соединения разорванных линий разметки.
5.  **Поиск контуров**: `cv2.findContours(th, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)` находит все замкнутые контуры на бинарном изображении.
6.  **Фильтрация контуров**:
    *   Отбираются контуры с площадью (`cv2.contourArea(contour)`) больше 800 пикселей.
    *   Периметр контура аппроксимируется полигоном (`cv2.approxPolyDP`). Отбираются те, что имеют 4 вершины (похожи на прямоугольники).
    *   `x, y, w, h = cv2.boundingRect(contour)`: получается описанный прямоугольник.
    *   Отбираются только те прямоугольники, которые находятся ниже светофора (`y > ylight + hlight`). Они добавляются в `potential_crosswalks`.
7.  **Кластеризация (если найдены потенциальные переходы)**:
    *   Если `potential_crosswalks` не пуст, прямоугольники кластеризуются. Предполагается, что линии одного пешеходного перехода будут расположены близко друг к другу.
    *   Центр каждого прямоугольника `(x + w // 2, y + h // 2)` добавляется в существующий кластер, если он достаточно близок (евклидово расстояние < 100) ко всем центрам в этом кластере. Иначе создается новый кластер.
    *   Выбирается самый большой кластер (`largest_cluster`).
    *   Определяются минимальная и максимальная Y-координаты центров в этом кластере (`min_y`, `max_y`).
    *   Возвращается кортеж `(0, min_y, frame.shape[1], max_y - min_y)`, представляющий собой горизонтальную полосу по всей ширине кадра, охватывающую кластер линий зебры.
8.  **Возврат `None`**: Если переходы не найдены или кластеризация не дала результатов, возвращается `None`.

### 6.2. Расчет области пересечения (`intersection_area`)
Функция `intersection_area(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float`:
1.  **Входные данные**: Два кортежа, представляющие рамки `boxA = (Ax, Ay, Aw, Ah)` и `boxB = (Bx, By, Bw, Bh)`, где `x, y` - координаты верхнего левого угла, `w, h` - ширина и высота.
2.  **Расчет координат пересечения**:
    *   `x1 = max(Ax, Bx)`
    *   `y1 = max(Ay, By)`
    *   `x2 = min(Ax + Aw, Bx + Bw)`
    *   `y2 = min(Ay + Ah, By + Bh)`
3.  **Проверка наличия пересечения**: Если `x2 < x1` или `y2 < y1`, рамки не пересекаются, и функция возвращает `0.0`.
4.  **Расчет площади**: Иначе, площадь пересечения рассчитывается как `(x2 - x1) * (y2 - y1)` и возвращается.

## 7. База данных
Файлы: `db.py`, `models.py`, `alembic.ini`, `alembic/env.py`.

### 7.1. Схема данных (модель `Violation`)
Определена в `models.py` с использованием SQLAlchemy Declarative Base:
```python
class Violation(Base):
    __tablename__ = 'violations'
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: str = Column(String(64))
    timestamp: Optional[datetime] = Column(DateTime) # Для веб-камеры
    video_second: Optional[int] = Column(Integer, nullable=True) # Для видеофайла
    processed_video_path: Optional[str] = Column(String(256), nullable=True)
    original_video_path: Optional[str] = Column(String(256), nullable=True)
```
-   `id`: Уникальный идентификатор записи о нарушении.
-   `vehicle_id`: Идентификатор транспортного средства, полученный от трекера YOLO.
-   `timestamp`: Дата и время нарушения (используется, когда источник - веб-камера).
-   `video_second`: Секунда видеофайла, на которой зафиксировано нарушение.
-   `processed_video_path`: Путь к сохраненному обработанному видеофайлу с визуализацией нарушения.
-   `original_video_path`: Путь к оригинальному видеофайлу, на котором было зафиксировано нарушение (если применимо).

### 7.2. Настройка подключения
Определена в `db.py`:
-   `DATABASE_URL: str = "mysql+pymysql://root:root@localhost:3306/traffic_violations"`: Строка подключения к базе данных MySQL. "root:root" - имя пользователя и пароль, "localhost:3306" - хост и порт, "traffic_violations" - имя БД.
-   `engine = create_engine(DATABASE_URL)`: Создает движок SQLAlchemy, который управляет соединениями с БД.
-   `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`: Создает фабрику сессий. Сессии используются для выполнения CRUD-операций с БД.

### 7.3. Миграции Alembic
Alembic используется для управления изменениями схемы базы данных.
-   **`alembic.ini`**: Основной конфигурационный файл Alembic.
    *   `script_location = alembic`: Указывает директорию со скриптами миграций.
    *   `sqlalchemy.url = mysql+pymysql://root:root@localhost:3306/traffic_violations`: Строка подключения к БД, используемая Alembic.
    *   `prepend_sys_path = .`: Добавляет корень проекта в `sys.path` для корректного импорта моделей.
-   **`alembic/env.py`**: Скрипт, который запускается Alembic для выполнения команд миграции.
    *   `sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))`: Добавление корневой директории проекта в `sys.path`.
    *   `from models import Base`: Импорт `Base` из `models.py`.
    *   `target_metadata = Base.metadata`: Указывает Alembic на метаданные моделей SQLAlchemy для автогенерации миграций.
-   **Типичные команды Alembic** (выполняются в терминале из корневой директории проекта):
    *   `alembic init alembic`: (Если не инициализировано) Создает структуру Alembic.
    *   `alembic revision -m "create_violations_table"`: Создает новый файл миграции (например, для создания таблицы `violations`). Нужно отредактировать сгенерированный файл, добавив код для создания таблицы на основе модели `Violation`.
    *   `alembic upgrade head`: Применяет все непримененные миграции к базе данных.
    *   `alembic downgrade -1`: Откатывает последнюю примененную миграцию.

## 8. Модель YOLO: Детекция и трекинг

### 8.1. Принцип работы YOLO (You Only Look Once)
YOLO — это семейство алгоритмов обнаружения объектов в реальном времени. Основная идея YOLO заключается в том, что вся задача обнаружения объектов рассматривается как единая задача регрессии.
1.  **Единый проход**: Изображение передается через нейронную сеть только один раз.
2.  **Сетка**: Сеть делит входное изображение на сетку ячеек (например, S x S).
3.  **Предсказания на ячейку**: Каждая ячейка сетки отвечает за предсказание:
    *   Нескольких ограничивающих рамок (bounding boxes) для объектов, центры которых попадают в эту ячейку.
    *   Оценки уверенности (confidence score) для каждой рамки, отражающей, насколько вероятно, что рамка содержит объект, и насколько точно она его описывает.
    *   Вероятностей принадлежности к каждому классу для объекта внутри рамки.
4.  **Объединение предсказаний**: Предсказания всех ячеек объединяются.
5.  **Non-Maximum Suppression (NMS)**: Применяется для устранения избыточных рамок, которые сильно пересекаются и указывают на один и тот же объект, оставляя только рамку с наивысшей уверенностью.

### 8.2. Используемая модель (`best.pt`)
-   В проекте используется `model = YOLO("yolo-coco/best.pt")`.
-   Это означает, что применяется модель из семейства YOLOv8.
-   Файл `best.pt` представляет собой сохраненные веса модели. "best" означает, что эти веса были получены в результате процесса дообучения и показали наилучшие метрики на валидационном наборе данных.
-   Модель, была дообучена на датасете, содержащим изображения различных транспортных средств и светофоров, показывающих один из трех цветов (красный, желтый, зеленый).

### 8.3. Классы объектов
Исходя из кода `yolo8_video.py`, модель используется для детекции следующих классов объектов, которые затем обрабатываются логикой приложения:
-   **Транспортные средства**: 'bus', 'car', 'motorcycle', 'truck', 'van'.
-   **Светофоры**: 'green_light', 'red_light', 'yellow_light'.
Хотя базовая модель YOLO, обученная на COCO, может распознавать больше классов, для логики фиксации нарушений в данном проекте используются только перечисленные.

### 8.4. Механизм трекинга (BoT-SORT)
-   Для отслеживания объектов во времени (присвоения им уникальных ID и поддержания этих ID между кадрами) используется трекер, указанный в `model.track(tracker="botsort.yaml", ...)`.
-   **BoT-SORT** (Bag of Tricks for SORT) - это усовершенствованный алгоритм многообъектного трекинга, основанный на SORT (Simple Online and Realtime Tracking).
-   Ключевые особенности BoT-SORT:
    *   **ByteTrack**: Использует детекции с низкой уверенностью (обычно отбрасываемые) для восстановления треков объектов, которые временно перекрыты или плохо детектируются. Это улучшает обработку окклюзий.
    *   **Re-ID (Re-identification)**: Часто включает в себя модели повторной идентификации для сопоставления объектов, которые были потеряны трекером на длительное время.
    *   **Фильтр Калмана**: Используется для предсказания следующего положения объекта и сглаживания траекторий.
    *   **Сопоставление**: Использует метрики, такие как IoU (Intersection over Union) и/или сходство признаков (из Re-ID модели), для сопоставления текущих детекций с существующими треками.
-   Конфигурация трекера (параметры, пороги и т.д.) задается в файле `botsort.yaml`.
-   В результате работы трекера каждому отслеживаемому объекту присваивается `track_id` (доступный через `box.id` в коде), который используется для идентификации конкретного транспортного средства при фиксации нарушений.

## 9. Развертывание и запуск
1.  **Клонирование репозитория.**
2.  **Настройка базы данных MySQL**:
    *   Установить MySQL сервер.
    *   Создать базу данных `traffic_violations`.
    *   Убедиться, что пользователь `root` с паролем `root` имеет доступ (или изменить `DATABASE_URL` в `db.py` и `alembic.ini`).
3.  **Установка зависимостей Python (Backend)**:
    *   Создать и активировать виртуальное окружение (python 3.9.21).
    *   `pip install -r requirements.txt`.
4.  **Применение миграций Alembic**:
    *   `alembic upgrade head`
5.  **Запуск Backend сервера**:
    *   `uvicorn main:app --reload` (из корневой директории проекта).
6.  **Установка зависимостей Node.js (Frontend)**:
    *   Перейти в директорию `video-detection-frontend`.
    *   `npm install`
7.  **Запуск Frontend сервера**:
    *   `ng serve` (из директории `video-detection-frontend`).
8.  **Доступ к приложению**: Открыть в браузере `http://localhost:4200`.

## 10. Возможные доработки
-   Улучшение точности детекции пешеходного перехода (например, использование семантической сегментации).
-   Детекция других типов нарушений (например, пересечение стоп-линии, превышение скорости).
-   Более продвинутый интерфейс для анализа нарушений (например, с возможностью покадрового просмотра видео нарушения).
-   Аутентификация и авторизация пользователей.
-   Оптимизация производительности для обработки видео высокого разрешения или нескольких потоков одновременно.
-   Интеграция с системами распознавания номерных знаков.
-   Сбор и анализ статистики по нарушениям. 