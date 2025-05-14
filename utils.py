import cv2
import numpy as np
from scipy.spatial import distance
from typing import Optional, Tuple

def detect_crosswalk(frame: np.ndarray, light_box: Tuple[int, int, int, int]) -> Optional[Tuple[int, int, int, int]]:
    """
    Обнаруживает область пешеходного перехода под указанной ограничительной рамкой светофора.
    Возвращает ограничительную рамку (x, y, w, h) или None, если переход не найден.
    """
    xlight, ylight, wlight, hlight = light_box # Координаты рамки светофора

    # Преобразование в оттенки серого
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Адаптивная бинаризация для выделения линий разметки
    th = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 115, 1
    )
    
    # Морфологические операции для улучшения бинарного изображения
    kernel = np.ones((3, 3), np.uint8) # Ядро для морфологических операций
    th = cv2.erode(th, kernel, iterations=1) # Эрозия для удаления шума
    th = cv2.dilate(th, kernel, iterations=2) # Дилатация для соединения разрывов
    
    # Поиск контуров на бинарном изображении
    contours, _ = cv2.findContours(th, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    potential_crosswalks = [] # Список для потенциальных прямоугольников зебры
    for contour in contours:
        # Фильтрация контуров по площади
        if cv2.contourArea(contour) > 800:
            peri = cv2.arcLength(contour, True) # Периметр контура
            approx = cv2.approxPolyDP(contour, 0.04 * peri, True) # Аппроксимация контура полигоном
            
            # Рассматриваем только четырехугольные контуры
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(contour) # Описанный прямоугольник
                # Учитываем только прямоугольники, расположенные ниже светофора
                if y > ylight + hlight:
                    potential_crosswalks.append((x, y, w, h))
    
    if potential_crosswalks:
        # Кластеризация найденных прямоугольников для объединения линий одной зебры
        clusters = []
        for rect in potential_crosswalks:
            x, y, w, h = rect
            center = (x + w // 2, y + h // 2) # Центр прямоугольника
            found_cluster = False
            for cluster in clusters:
                # Проверка, достаточно ли близок текущий прямоугольник к существующему кластеру
                if all(distance.euclidean(center, (cx, cy)) < 100 for cx, cy in cluster):
                    cluster.append(center)
                    found_cluster = True
                    break
            if not found_cluster:
                clusters.append([center]) # Создание нового кластера
        
        if not clusters: # Если кластеры не образовались
            return None

        # Выбор наибольшего кластера (предполагается, что это и есть пешеходный переход)
        largest_cluster = max(clusters, key=len)
        
        # Определение вертикальных границ пешеходного перехода по крайним точкам кластера
        min_y = min(cy for cx, cy in largest_cluster)
        max_y = max(cy for cx, cy in largest_cluster)
        
        # Возвращаем рамку перехода: по всей ширине кадра, с вычисленными y-координатами
        return (0, min_y, frame.shape[1], max_y - min_y)
    
    return None # Пешеходный переход не найден

def intersection_area(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """
    Рассчитывает площадь пересечения двух ограничительных рамок.
    Рамки задаются как (x, y, ширина, высота).
    """
    Ax, Ay, Aw, Ah = boxA
    Bx, By, Bw, Bh = boxB

    # Определение координат прямоугольника пересечения
    x1 = max(Ax, Bx)
    y1 = max(Ay, By)
    x2 = min(Ax + Aw, Bx + Bw)
    y2 = min(Ay + Ah, By + Bh)

    # Если рамки не пересекаются, площадь пересечения равна 0
    if x2 < x1 or y2 < y1:
        return 0.0
    
    # Расчет и возврат площади пересечения
    return (x2 - x1) * (y2 - y1)
