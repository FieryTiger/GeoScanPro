# app_core.py
"""
GeoScanPro - Ядро приложения для обработки данных и детектирования воды
"""

import numpy as np
import rasterio
from rasterio.plot import show
import cv2
from pathlib import Path
import os
from scipy import ndimage
from skimage import morphology, measure
import json

class DataProcessor:
    """Класс для загрузки и предобработки данных Landsat 9"""
    
    def __init__(self):
        self.required_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
        self.required_qa = 'QA_PIXEL'
        self.data_cache = {}
        self.metadata = {}
    
    def load_landsat_data(self, file_paths):
        """
        Загрузка данных Landsat 9 из списка файлов
        
        Args:
            file_paths (list): Список путей к файлам .tif
            
        Returns:
            dict: Словарь с загруженными массивами данных
        """
        try:
            # Поиск и классификация файлов по типам
            band_files = {}
            qa_file = None
            
            for file_path in file_paths:
                filename = Path(file_path).name.upper()
                
                # Поиск спектральных каналов
                for band in self.required_bands:
                    if band in filename:
                        band_files[band] = file_path
                        break
                
                # Поиск файла качества
                if self.required_qa in filename:
                    qa_file = file_path
            
            # Проверка наличия всех необходимых файлов
            missing_bands = set(self.required_bands) - set(band_files.keys())
            if missing_bands:
                print(f"Отсутствуют каналы: {missing_bands}")
                return None
            
            if not qa_file:
                print(f"Отсутствует файл качества: {self.required_qa}")
                return None
            
            # Загрузка данных
            loaded_data = {}
            
            # Загрузка спектральных каналов
            for band, file_path in band_files.items():
                with rasterio.open(file_path) as src:
                    data = src.read(1).astype(np.float32)
                    loaded_data[band] = data
                    
                    # Сохранение метаданных из первого файла
                    if not self.metadata:
                        self.metadata = {
                            'crs': src.crs,
                            'transform': src.transform,
                            'width': src.width,
                            'height': src.height,
                            'bounds': src.bounds
                        }
            
            # Загрузка канала качества
            with rasterio.open(qa_file) as src:
                qa_data = src.read(1)
                loaded_data[self.required_qa] = qa_data
            
            # Предобработка данных
            loaded_data = self._preprocess_data(loaded_data)
            
            loaded_data['meta'] = self.metadata
            
            # Кэширование данных
            self.data_cache = loaded_data
            
            print(f"✅ Успешно загружено {len(loaded_data)} каналов")
            return loaded_data
            
        except Exception as e:
            print(f"❌ Ошибка загрузки данных: {str(e)}")
            return None
    
    def _preprocess_data(self, data):
        """
        Предобработка загруженных данных
        
        Args:
            data (dict): Словарь с сырыми данными
            
        Returns:
            dict: Предобработанные данные
        """
        try:
            # Масштабирование спектральных данных Landsat Collection 2 Level-2
            scale_factor = 0.0000275
            add_offset = -0.2
            
            for band in self.required_bands:
                if band in data:
                    # Применение коэффициентов масштабирования
                    data[band] = data[band] * scale_factor + add_offset
                    
                    # Обрезка значений до разумного диапазона
                    data[band] = np.clip(data[band], 0, 1)
            
            # Создание маски облаков из QA_PIXEL
            if self.required_qa in data:
                qa_data = data[self.required_qa]
                
                # Биты для облаков, теней и снега в Landsat Collection 2
                cloud_mask = self._extract_qa_bits(qa_data, [1, 3])  # Dilated cloud and Cloud
                shadow_mask = self._extract_qa_bits(qa_data, [4])    # Cloud Shadow
                snow_mask = self._extract_qa_bits(qa_data, [5])      # Snow
                cirrus_mask = self._extract_qa_bits(qa_data, [2])    # Cirrus
                
                # Объединенная маска исключения
                exclude_mask = cloud_mask | shadow_mask | snow_mask | cirrus_mask
                data['exclude_mask'] = exclude_mask
            
            return data
            
        except Exception as e:
            print(f"❌ Ошибка предобработки: {str(e)}")
            return data
    
    def _extract_qa_bits(self, qa_array, bit_positions):
        """
        Извлечение значений конкретных битов из QA канала
        
        Args:
            qa_array (np.array): Массив QA данных
            bit_positions (list): Список позиций битов для извлечения
            
        Returns:
            np.array: Булева маска
        """
        result = np.zeros_like(qa_array, dtype=bool)
        
        for bit_pos in bit_positions:
            bit_mask = 1 << bit_pos
            result |= (qa_array & bit_mask) != 0
        
        return result
    
    def get_pixel_size_km(self):
        """Получить размер пикселя в км"""
        if self.metadata and 'transform' in self.metadata:
            transform = self.metadata['transform']
            pixel_size_m = abs(transform[0])  # Размер пикселя в метрах
            return pixel_size_m / 1000.0  # Конвертация в км
        return 0.03  # Значение по умолчанию для Landsat (30м = 0.03км)

class WaterDetector:
    """Класс для детектирования водных объектов"""
    
    def __init__(self):
        self.thresholds = {
            'NDWI': 0.3,
            'MNDWI': 0.2, 
            'AWEI_nsh': 0.0,
            'LSWI': 0.3
        }
        self.min_object_size = 100  # Минимальный размер объекта в пикселях
        self.apply_morphology = True
        self.voting_threshold = 3  # Минимум голосов для классификации как вода
    
    def set_parameters(self, thresholds=None, min_object_size=None, apply_morphology=None):
        """Установка параметров детектирования"""
        if thresholds:
            self.thresholds.update(thresholds)
        if min_object_size is not None:
            self.min_object_size = min_object_size
        if apply_morphology is not None:
            self.apply_morphology = apply_morphology
    
    def detect_water(self, data):
        """
        Основной метод детектирования водных объектов
        
        Args:
            data (dict): Предобработанные данные Landsat
            
        Returns:
            dict: Результаты детектирования
        """
        try:
            print("🚀 Запуск детектирования водных объектов...")
            
            # Вычисление водных индексов
            indices = self._calculate_water_indices(data)
            
            # Создание бинарных масок для каждого индекса
            binary_masks = {}
            for name, values in indices.items():
                if name in self.thresholds:
                    threshold = self.thresholds[name]
                    binary_masks[name] = values > threshold
            
            # Ансамбль с голосованием
            water_mask = self._ensemble_voting(binary_masks, data.get('exclude_mask'))
            
            # Постобработка
            if self.apply_morphology:
                water_mask = self._apply_morphological_operations(water_mask)
            
            # Удаление мелких объектов
            water_mask = self._remove_small_objects(water_mask)
            
            # Анализ объектов
            analysis_results = self._analyze_water_objects(water_mask, data)
            
            # Создание визуализаций
            visualizations = self._create_visualizations(water_mask, data)
            
            # Формирование итоговых результатов
            results = {
                'water_mask': water_mask,
                'indices': indices,
                'binary_masks': binary_masks,
                **analysis_results,
                **visualizations
            }
            
            print("✅ Детектирование завершено успешно")
            return results
            
        except Exception as e:
            print(f"❌ Ошибка детектирования: {str(e)}")
            return None
    
    def _calculate_water_indices(self, data):
        """Вычисление водных индексов"""
        try:
            indices = {}
            
            # Извлечение каналов
            blue = data['SR_B2']    # Blue
            green = data['SR_B3']   # Green  
            red = data['SR_B4']     # Red
            nir = data['SR_B5']     # NIR
            swir1 = data['SR_B6']   # SWIR1
            swir2 = data['SR_B7']   # SWIR2
            
            # NDWI = (Green - NIR) / (Green + NIR)
            indices['NDWI'] = np.where(
                (green + nir) != 0,
                (green - nir) / (green + nir),
                0
            )
            
            # MNDWI = (Green - SWIR1) / (Green + SWIR1)  
            indices['MNDWI'] = np.where(
                (green + swir1) != 0,
                (green - swir1) / (green + swir1),
                0
            )
            
            # AWEI_nsh = 4 * (Green - SWIR1) - (0.25 * NIR + 2.75 * SWIR2)
            indices['AWEI_nsh'] = 4 * (green - swir1) - (0.25 * nir + 2.75 * swir2)
            
            # LSWI = (NIR - SWIR1) / (NIR + SWIR1)
            indices['LSWI'] = np.where(
                (nir + swir1) != 0,
                (nir - swir1) / (nir + swir1),
                0
            )
            
            # Дополнительные индексы (опционально)
            # WI = 1.7204 + 171 * green + 3 * red - 70 * nir - 45 * swir1 - 71 * swir2
            indices['WI'] = (1.7204 + 171 * green + 3 * red - 
                           70 * nir - 45 * swir1 - 71 * swir2)
            
            return indices
            
        except Exception as e:
            print(f"❌ Ошибка вычисления индексов: {str(e)}")
            return {}
    
    def _ensemble_voting(self, binary_masks, exclude_mask=None):
        """Ансамбль с голосованием"""
        try:
            if not binary_masks:
                return None
            
            # Подсчет голосов
            vote_count = np.zeros_like(list(binary_masks.values())[0], dtype=int)
            
            for mask in binary_masks.values():
                vote_count += mask.astype(int)
            
            # Пиксели с достаточным количеством голосов классифицируются как вода
            water_mask = vote_count >= self.voting_threshold
            
            # Исключение облаков, теней и снега
            if exclude_mask is not None:
                water_mask = water_mask & (~exclude_mask)
            
            return water_mask.astype(np.uint8)
            
        except Exception as e:
            print(f"❌ Ошибка голосования: {str(e)}")
            return None
    
    def _apply_morphological_operations(self, water_mask):
        """Применение морфологических операций для очистки маски"""
        try:
            # Структурирующий элемент
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            
            # Закрытие (closing) - заполнение дырок
            water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, kernel)
            
            # Открытие (opening) - удаление шума
            water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_OPEN, kernel)
            
            # Удаление мелких дырок
            cleaned_mask = morphology.remove_small_holes(water_mask.astype(bool), area_threshold=100)
            water_mask = cleaned_mask.astype(np.uint8)
            
            return water_mask
            
        except Exception as e:
            print(f"❌ Ошибка морфологических операций: {str(e)}")
            return water_mask
    
    def _remove_small_objects(self, water_mask):
        """Удаление мелких объектов"""
        try:
            # Используем skimage для удаления мелких объектов
            cleaned_mask = morphology.remove_small_objects(
                water_mask.astype(bool), 
                min_size=self.min_object_size
            )
            
            return cleaned_mask.astype(np.uint8)
            
        except Exception as e:
            print(f"❌ Ошибка удаления мелких объектов: {str(e)}")
            return water_mask
    
    def _analyze_water_objects(self, water_mask, data):
        """Анализ водных объектов"""
        try:
            # Размер пикселя в км
            pixel_size_km = abs(data['meta']['transform'][0]) / 1000 if 'meta' in data else 0.03
            pixel_area_km2 = pixel_size_km ** 2
            
            # Общая статистика
            total_water_pixels = np.sum(water_mask)
            total_area_km2 = total_water_pixels * pixel_area_km2
            total_pixels = water_mask.size
            water_percentage = (total_water_pixels / total_pixels) * 100
            
            # Поиск контуров объектов
            contours, _ = cv2.findContours(water_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Анализ каждого объекта
            objects_data = []
            total_perimeter_km = 0
            
            for i, contour in enumerate(contours):
                # Площадь объекта
                area_pixels = cv2.contourArea(contour)
                area_km2 = area_pixels * pixel_area_km2
                
                # Периметр объекта
                perimeter_pixels = cv2.arcLength(contour, True)
                perimeter_km = perimeter_pixels * pixel_size_km
                total_perimeter_km += perimeter_km
                
                # Коэффициент формы (чем ближе к 1, тем более круглый объект)
                if perimeter_pixels > 0:
                    shape_factor = 4 * np.pi * area_pixels / (perimeter_pixels ** 2)
                else:
                    shape_factor = 0
                
                objects_data.append({
                    'id': i,
                    'area_pixels': int(area_pixels),
                    'area_km2': area_km2,
                    'perimeter_km': perimeter_km,
                    'shape_factor': shape_factor,
                    'contour': contour
                })
            
            # Сортировка объектов по площади (от большего к меньшему)
            objects_data.sort(key=lambda x: x['area_km2'], reverse=True)
            
            return {
                'total_water_area_pixels': total_water_pixels,
                'total_water_area_km2': total_area_km2,
                'total_perimeter_km': total_perimeter_km,
                'water_percentage': water_percentage,
                'object_count': len(objects_data),
                'objects_data': objects_data,
                'largest_object_area': objects_data[0]['area_km2'] if objects_data else 0,
                'average_object_size': total_area_km2 / len(objects_data) if objects_data else 0,
                'contours': contours
            }
            
        except Exception as e:
            print(f"❌ Ошибка анализа объектов: {str(e)}")
            return {}
    
    def _create_visualizations(self, water_mask, data):
        """Создание изображений для визуализации"""
        try:
            visualizations = {}
            
            # 1. RGB композит для основы
            if all(band in data for band in ['SR_B4', 'SR_B3', 'SR_B2']):
                rgb = np.stack([
                    data['SR_B4'],  # Red
                    data['SR_B3'],  # Green
                    data['SR_B2']   # Blue
                ], axis=-1)
                
                # Нормализация для отображения
                rgb_norm = np.clip(rgb / np.percentile(rgb, 98), 0, 1)
                visualizations['rgb_image'] = rgb_norm
            
            # 2. Наложение маски
            if 'rgb_image' in visualizations:
                overlay = visualizations['rgb_image'].copy()
                water_pixels = water_mask == 1
                
                # Красное наложение для воды (полупрозрачное)
                overlay[water_pixels] = overlay[water_pixels] * 0.6 + np.array([1, 0, 0]) * 0.4
                visualizations['overlay_image'] = overlay
            
            # 3. Контуры объектов
            if 'rgb_image' in visualizations:
                contour_image = visualizations['rgb_image'].copy()
                
                # Поиск и отрисовка контуров
                contours, _ = cv2.findContours(water_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Конвертация в uint8 для cv2.drawContours
                contour_image_uint8 = (contour_image * 255).astype(np.uint8)
                cv2.drawContours(contour_image_uint8, contours, -1, (255, 0, 0), 2)
                
                visualizations['contour_image'] = contour_image_uint8.astype(np.float32) / 255.0
            
            return visualizations
            
        except Exception as e:
            print(f"❌ Ошибка создания визуализаций: {str(e)}")
            return {} 