# utils.py
"""
GeoScanPro - Вспомогательные функции и утилиты
"""

import numpy as np
import cv2
from PIL import Image
import pandas as pd
import json
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
import os

def create_default_settings():
    """Создание настроек по умолчанию"""
    return {
        "water_color": "#FF0000",
        "contour_thickness": 2,
        "theme": "system",
        "font_size": 12,
        "font_family": "Segoe UI",
        "export_format": "PNG",
        "save_metadata": True,
        "thresholds": {
            "NDWI": 0.3,
            "MNDWI": 0.2,
            "AWEI_nsh": 0.0,
            "LSWI": 0.3
        }
    }

class ImageExporter:
    """Класс для экспорта результатов анализа"""
    
    def __init__(self):
        self.export_formats = ['PNG', 'JPEG', 'TIFF']
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def export_results(self, detection_results, original_data, export_dir):
        """
        Экспорт всех результатов анализа
        
        Args:
            detection_results (dict): Результаты детектирования
            original_data (dict): Исходные данные
            export_dir (str): Директория для экспорта
            
        Returns:
            bool: Успешность экспорта
        """
        try:
            export_path = Path(export_dir)
            
            # Создание поддиректории с timestamp
            results_dir = export_path / f"GeoScanPro_Results_{self.timestamp}"
            results_dir.mkdir(exist_ok=True)
            
            print(f"📁 Экспорт в директорию: {results_dir}")
            
            # Экспорт изображений
            self._export_images(detection_results, original_data, results_dir)

            
            # Экспорт метаданных
            self._export_metadata(detection_results, original_data, results_dir)
            
            # Создание отчета
            self._create_summary_report(detection_results, results_dir)
            
            print("✅ Экспорт завершен успешно")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка экспорта: {str(e)}")
            return False
    
    def _export_images(self, results, original_data, export_dir):
        """Экспорт изображений"""
        try:
            images_dir = export_dir / "images"
            images_dir.mkdir(exist_ok=True)
            
            # 1. Исходный RGB композит
            if 'rgb_image' in results:
                rgb_img = (results['rgb_image'] * 255).astype(np.uint8)
                rgb_pil = Image.fromarray(rgb_img)
                rgb_pil.save(images_dir / "01_original_rgb.png")
            
            # 2. Бинарная маска воды
            if 'water_mask' in results:
                mask_img = results['water_mask'] * 255
                mask_pil = Image.fromarray(mask_img.astype(np.uint8))
                mask_pil.save(images_dir / "02_water_mask.png")
            
            # 3. Наложение маски
            if 'overlay_image' in results:
                overlay_img = (results['overlay_image'] * 255).astype(np.uint8)
                overlay_pil = Image.fromarray(overlay_img)
                overlay_pil.save(images_dir / "03_overlay_visualization.png")
            
            # 4. Контуры объектов
            if 'contour_image' in results:
                contour_img = (results['contour_image'] * 255).astype(np.uint8)
                contour_pil = Image.fromarray(contour_img)
                contour_pil.save(images_dir / "04_contours.png")
            
            # 5. Индивидуальные индексы
            if 'indices' in results:
                indices_dir = images_dir / "water_indices"
                indices_dir.mkdir(exist_ok=True)
                
                for name, index_data in results['indices'].items():
                    # Нормализация для отображения
                    normalized = self._normalize_for_display(index_data)
                    index_img = (normalized * 255).astype(np.uint8)
                    
                    # Применение цветовой карты
                    colored = cv2.applyColorMap(index_img, cv2.COLORMAP_JET)
                    colored_rgb = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)
                    
                    index_pil = Image.fromarray(colored_rgb)
                    index_pil.save(indices_dir / f"{name}_index.png")
            
            # 6. Бинарные маски для каждого индекса
            if 'binary_masks' in results:
                masks_dir = images_dir / "binary_masks"
                masks_dir.mkdir(exist_ok=True)
                
                for name, mask in results['binary_masks'].items():
                    mask_img = mask.astype(np.uint8) * 255
                    mask_pil = Image.fromarray(mask_img)
                    mask_pil.save(masks_dir / f"{name}_binary_mask.png")
            
            print("📸 Изображения экспортированы")
            
        except Exception as e:
            print(f"❌ Ошибка экспорта изображений: {str(e)}")
    


    def export_to_excel(self, results, export_path):
        """Экспорт статистики в Excel файл с одним листом"""
        try:
            # Создаем DataFrame с нужными столбцами
            excel_data = {
                'Общая площадь воды (кв.км)': [float(results.get('total_water_area_km2', 0))],
                'Общая площадь воды (пикселей)': [int(results.get('total_water_area_pixels', 0))],
                'Общий периметр воды (км)': [float(results.get('total_perimeter_km', 0))],
                'Процент водной поверхности (%)': [float(results.get('water_percentage', 0))],
                'Количество водных объектов': [int(results.get('object_count', 0))],
                'Крупнейший объект (кв.км)': [float(results.get('largest_object_area', 0))]
            }
            
            df = pd.DataFrame(excel_data)
            
            # Настройка ширины столбцов
            with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Статистика', index=False)
                
                # Получаем объект листа для настройки ширины столбцов
                worksheet = writer.sheets['Статистика']
                
                # Устанавливаем ширину столбцов, чтобы все слова были видны
                column_widths = {
                    'A': 25,  # Общая площадь воды (кв.км)
                    'B': 30,  # Общая площадь воды (пикселей)
                    'C': 25,  # Общий периметр воды (км)
                    'D': 25,  # Процент водной поверхности (%)
                    'E': 25,  # Количество водных объектов
                    'F': 25   # Крупнейший объект (кв.км)
                }
                
                for col, width in column_widths.items():
                    worksheet.column_dimensions[col].width = width
            
            print(f"✅ Excel файл сохранен: {export_path}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка экспорта в Excel: {str(e)}")
            return False
    
    def _export_metadata(self, results, original_data, export_dir):
        """Экспорт метаданных"""
        try:
            metadata_dir = export_dir / "metadata"
            metadata_dir.mkdir(exist_ok=True)
            
            # Сбор метаданных
            metadata = {
                "analysis_info": {
                    "timestamp": self.timestamp,
                    "software": "GeoScanPro v1.0",
                    "algorithm": "Ensemble voting with water indices"
                },
                "data_source": {
                    "satellite": "Landsat 9",
                    "processing_level": "Level-2 Surface Reflectance",
                    "bands_used": ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
                },
                "indices_used": {
                    "NDWI": "Normalized Difference Water Index",
                    "MNDWI": "Modified Normalized Difference Water Index", 
                    "AWEI_nsh": "Automated Water Extraction Index (no shadows)",
                    "LSWI": "Land Surface Water Index"
                },
                "analysis_parameters": {
                    "voting_threshold": 3,
                    "min_object_size_pixels": 100,
                    "morphological_processing": True,
                    "pixel_size_km": 0.03
                },
                "results_summary": {
                    "total_water_area_km2": results.get('total_water_area_km2', 0),
                    "water_percentage": results.get('water_percentage', 0),
                    "object_count": results.get('object_count', 0)
                }
            }
            
            # Сохранение в JSON
            with open(metadata_dir / "analysis_metadata.json", 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            print("📋 Метаданные экспортированы")
            
        except Exception as e:
            print(f"❌ Ошибка экспорта метаданных: {str(e)}")
    
    def _create_summary_report(self, results, export_dir):
        """Создание сводного отчета"""
        try:
            report_content = f"""
ОТЧЕТ ПО АНАЛИЗУ ВОДНЫХ ОБЪЕКТОВ
GeoScanPro v1.0
===============================================

Дата и время анализа: {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}

ОБЩАЯ ИНФОРМАЦИЯ
▪ Спутник: Landsat 9
▪ Уровень обработки: Level-2 Surface Reflectance  
▪ Алгоритм: Ансамбль водных индексов с голосованием
▪ Используемые индексы: NDWI, MNDWI, AWEI, LSWI

РЕЗУЛЬТАТЫ АНАЛИЗА
===============================================
▪ Общая площадь воды: {results.get('total_water_area_km2', 0):.2f} кв.км
▪ Общая площадь воды: {results.get('total_water_area_pixels', 0):,} пикселей
▪ Общий периметр: {results.get('total_perimeter_km', 0):.2f} км
▪ Процент водной поверхности: {results.get('water_percentage', 0):.2f}%

СТАТИСТИКА ПО ОБЪЕКТАМ
===============================================
▪ Количество водных объектов: {results.get('object_count', 0)}
▪ Крупнейший объект: {results.get('largest_object_area', 0):.2f} кв.км
▪ Средний размер объекта: {results.get('average_object_size', 0):.2f} кв.км

МЕТОДОЛОГИЯ
===============================================
1. Предобработка данных Landsat 9 Collection 2
2. Вычисление водных индексов (NDWI, MNDWI, AWEI, LSWI)
3. Создание бинарных масок для каждого индекса
4. Ансамбль с голосованием (минимум 3 голоса из 4)
5. Исключение облаков, теней и снега по QA каналу
6. Морфологическая постобработка
7. Удаление объектов менее 100 пикселей
8. Анализ геометрических параметров объектов

СТРУКТУРА ЭКСПОРТИРОВАННЫХ ФАЙЛОВ
===============================================
📁 images/
  ├── 01_original_rgb.png          - Исходный RGB снимок
  ├── 02_water_mask.png            - Бинарная маска воды
  ├── 03_overlay_visualization.png - Наложение маски
  ├── 04_contours.png              - Контуры объектов
  ├── 📁 water_indices/            - Индивидуальные индексы
  └── 📁 binary_masks/             - Бинарные маски индексов

📁 statistics/
  ├── general_statistics.csv       - Общая статистика
  └── water_objects_detailed.csv   - Детализация по объектам

📁 metadata/
  └── analysis_metadata.json      - Метаданные анализа

Этот отчет создан автоматически программой GeoScanPro.
Для получения дополнительной информации обратитесь к документации.
"""
            
            with open(export_dir / "ОТЧЕТ_АНАЛИЗА.txt", 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            print("📄 Сводный отчет создан")
            
        except Exception as e:
            print(f"❌ Ошибка создания отчета: {str(e)}")
    
    def _normalize_for_display(self, data):
        """Нормализация данных для отображения"""
        try:
            # Удаление выбросов (1% и 99% перцентили)
            p1, p99 = np.percentile(data[np.isfinite(data)], [1, 99])
            
            # Обрезка и нормализация
            normalized = np.clip(data, p1, p99)
            normalized = (normalized - p1) / (p99 - p1)
            
            # Замена NaN и inf на 0
            normalized = np.nan_to_num(normalized, 0)
            
            return normalized
            
        except Exception as e:
            print(f"❌ Ошибка нормализации: {str(e)}")
            return np.zeros_like(data)

class GeospatialAnalyzer:
    """Дополнительные геопространственные анализы"""
    
    def __init__(self):
        self.pixel_size_m = 30  # Landsat pixel size in meters
        self.pixel_area_m2 = self.pixel_size_m ** 2
        self.pixel_area_km2 = (self.pixel_size_m / 1000) ** 2
    
    def calculate_shape_metrics(self, contour):
        """Расчет метрик формы объекта"""
        try:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            
            if perimeter == 0:
                return {'compactness': 0, 'circularity': 0, 'elongation': 0}
            
            # Компактность (чем ближе к 1, тем компактнее)
            compactness = 4 * np.pi * area / (perimeter ** 2)
            
            # Цикличность (отношение площади к площади окружности того же периметра)
            circularity = area / ((perimeter / (2 * np.pi)) ** 2 * np.pi)
            
            # Вытянутость (отношение главных осей эллипса)
            if len(contour) >= 5:
                ellipse = cv2.fitEllipse(contour)
                major_axis = max(ellipse[1])
                minor_axis = min(ellipse[1])
                elongation = major_axis / minor_axis if minor_axis > 0 else 0
            else:
                elongation = 0
            
            return {
                'compactness': compactness,
                'circularity': circularity, 
                'elongation': elongation
            }
            
        except Exception as e:
            print(f"❌ Ошибка расчета метрик формы: {str(e)}")
            return {'compactness': 0, 'circularity': 0, 'elongation': 0}
    
    def create_size_distribution_chart(self, objects_data, save_path):
        """Создание графика распределения объектов по размерам"""
        try:
            if not objects_data:
                return False
            
            # Извлечение данных о площадях
            areas = [obj['area_km2'] for obj in objects_data]
            
            # Создание гистограммы
            plt.figure(figsize=(10, 6))
            plt.hist(areas, bins=20, alpha=0.7, color='blue', edgecolor='black')
            plt.xlabel('Площадь объекта (кв.км)')
            plt.ylabel('Количество объектов')
            plt.title('Распределение водных объектов по размерам')
            plt.grid(True, alpha=0.3)
            
            # Добавление статистики
            plt.axvline(np.mean(areas), color='red', linestyle='--', 
                       label=f'Среднее: {np.mean(areas):.3f} кв.км')
            plt.axvline(np.median(areas), color='green', linestyle='--',
                       label=f'Медиана: {np.median(areas):.3f} кв.км')
            
            plt.legend()
            plt.tight_layout()
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка создания графика: {str(e)}")
            return False
    
    def create_pie_chart(self, results, save_path):
        """Создание круговой диаграммы соотношения вода/суша"""
        try:
            water_percentage = results.get('water_percentage', 0)
            land_percentage = 100 - water_percentage
            
            labels = ['Вода', 'Суша']
            sizes = [water_percentage, land_percentage]
            colors = ['#4472C4', '#E7E6E6']
            explode = (0.1, 0)  # Выделение сектора воды
            
            plt.figure(figsize=(8, 8))
            plt.pie(sizes, explode=explode, labels=labels, colors=colors,
                   autopct='%1.2f%%', shadow=True, startangle=90)
            
            plt.title('Соотношение водной поверхности и суши', 
                     fontsize=14, fontweight='bold')
            plt.axis('equal')
            
            plt.tight_layout()
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка создания круговой диаграммы: {str(e)}")
            return False

def validate_landsat_files(file_paths):
    """
    Валидация файлов Landsat 9
    
    Args:
        file_paths (list): Список путей к файлам
        
    Returns:
        dict: Результат валидации
    """
    required_patterns = [
        'SR_B2.TIF', 'SR_B3.TIF', 'SR_B4.TIF', 
        'SR_B5.TIF', 'SR_B6.TIF', 'SR_B7.TIF',
        'QA_PIXEL.TIF'
    ]
    
    found_files = {pattern: False for pattern in required_patterns}
    file_info = {}
    
    for file_path in file_paths:
        filename = Path(file_path).name.upper()
        
        for pattern in required_patterns:
            if pattern in filename:
                found_files[pattern] = True
                file_info[pattern] = file_path
                break
    
    missing_files = [pattern for pattern, found in found_files.items() if not found]
    
    return {
        'is_valid': len(missing_files) == 0,
        'missing_files': missing_files,
        'found_files': file_info,
        'validation_message': "✅ Все необходимые файлы найдены" if len(missing_files) == 0 
                            else f"❌ Отсутствуют файлы: {', '.join(missing_files)}"
    }

def hex_to_rgb(hex_color):
    """Конвертация HEX цвета в RGB"""
    try:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except:
        return (255, 0, 0)  # Красный по умолчанию

def create_legend_image(water_color="#FF0000", save_path=None):
    """Создание изображения легенды"""
    try:
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.axis('off')
        
        # Элементы легенды
        legend_elements = [
            plt.Rectangle((0, 0), 1, 1, facecolor=water_color, alpha=0.7, label='Водные объекты'),
            plt.Rectangle((0, 0), 1, 1, facecolor='gray', alpha=0.3, label='Суша')
        ]
        
        ax.legend(handles=legend_elements, loc='center', ncol=2, fontsize=12)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            return True
        else:
            return fig
            
    except Exception as e:
        print(f"❌ Ошибка создания легенды: {str(e)}")
        return False