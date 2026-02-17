import numpy as np
import cv2
from PIL import Image
import pandas as pd
import json
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime


class ImageExporter:
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def export_results(self, detection_results, original_data, export_dir) -> bool:
        try:
            results_dir = Path(export_dir) / f"GeoScanPro_Results_{self.timestamp}"
            results_dir.mkdir(exist_ok=True)

            self._export_images(detection_results, results_dir)
            self._export_metadata(detection_results, results_dir)
            self._create_summary_report(detection_results, results_dir)

            return True
        except Exception as e:
            print(f"Ошибка экспорта: {e}")
            return False

    def export_to_excel(self, results, export_path) -> bool:
        try:
            summary_data = {
                'Общая площадь воды (кв.км)':      [round(results.get('total_water_area_km2', 0), 4)],
                'Общая площадь воды (пикселей)':   [results.get('total_water_area_pixels', 0)],
                'Общий периметр воды (км)':         [round(results.get('total_perimeter_km', 0), 4)],
                'Процент водной поверхности (%)':   [round(results.get('water_percentage', 0), 4)],
                'Количество водных объектов':       [results.get('object_count', 0)],
                'Крупнейший объект (кв.км)':        [round(results.get('largest_object_area', 0), 4)],
            }

            objects_rows = []
            for obj in results.get('objects_data', []):
                objects_rows.append({
                    'ID объекта':          obj['id'] + 1,
                    'Площадь (кв.км)':    round(obj['area_km2'], 4),
                    'Площадь (пикс.)':    obj['area_pixels'],
                    'Периметр (км)':      round(obj['perimeter_km'], 4),
                    'Коэф. формы':        round(obj['shape_factor'], 4),
                })

            with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='Общая статистика', index=False)

                if objects_rows:
                    df_objects = pd.DataFrame(objects_rows)
                    df_objects.to_excel(writer, sheet_name='Водные объекты', index=False)

                    ws = writer.sheets['Водные объекты']
                    for col in ws.columns:
                        ws.column_dimensions[col[0].column_letter].width = 18

                ws_summary = writer.sheets['Общая статистика']
                for col in ws_summary.columns:
                    ws_summary.column_dimensions[col[0].column_letter].width = 30

            return True
        except Exception as e:
            print(f"Ошибка экспорта Excel: {e}")
            return False

    def _export_images(self, results, export_dir):
        images_dir = export_dir / "images"
        images_dir.mkdir(exist_ok=True)

        saves = {
            '01_original_rgb.png':        results.get('rgb_image'),
            '03_overlay_visualization.png': results.get('overlay_image'),
            '04_contours.png':             results.get('contour_image'),
        }
        for filename, img_data in saves.items():
            if img_data is not None:
                img_uint8 = (img_data * 255).astype(np.uint8)
                Image.fromarray(img_uint8).save(images_dir / filename)

        if 'water_mask' in results:
            mask_img = results['water_mask'] * 255
            Image.fromarray(mask_img.astype(np.uint8)).save(images_dir / '02_water_mask.png')

        if results.get('indices'):
            indices_dir = images_dir / "water_indices"
            indices_dir.mkdir(exist_ok=True)
            for name, index_data in results['indices'].items():
                normalized = self._normalize_for_display(index_data)
                index_uint8 = (normalized * 255).astype(np.uint8)
                colored = cv2.applyColorMap(index_uint8, cv2.COLORMAP_JET)
                colored_rgb = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)
                Image.fromarray(colored_rgb).save(indices_dir / f"{name}_index.png")

    def _export_metadata(self, results, export_dir):
        metadata_dir = export_dir / "metadata"
        metadata_dir.mkdir(exist_ok=True)
        metadata = {
            "analysis_info": {
                "timestamp": self.timestamp,
                "software": "GeoScanPro v2.0",
                "algorithm": "Ensemble voting with water indices"
            },
            "results_summary": {
                "total_water_area_km2": results.get('total_water_area_km2', 0),
                "water_percentage": results.get('water_percentage', 0),
                "object_count": results.get('object_count', 0)
            }
        }
        with open(metadata_dir / "analysis_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _create_summary_report(self, results, export_dir):
        report = f"""ОТЧЕТ ПО АНАЛИЗУ ВОДНЫХ ОБЪЕКТОВ
GeoScanPro v2.0
{'=' * 48}

Дата и время: {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}

РЕЗУЛЬТАТЫ
{'=' * 48}
Общая площадь воды:        {results.get('total_water_area_km2', 0):.4f} кв.км
Общий периметр:            {results.get('total_perimeter_km', 0):.4f} км
Процент водной поверхности:{results.get('water_percentage', 0):.2f}%
Количество объектов:       {results.get('object_count', 0)}
Крупнейший объект:         {results.get('largest_object_area', 0):.4f} кв.км
Средний размер объекта:    {results.get('average_object_size', 0):.4f} кв.км

МЕТОДОЛОГИЯ
{'=' * 48}
1. Предобработка данных Landsat 9 Collection 2
2. Вычисление водных индексов (NDWI, MNDWI, AWEI, LSWI)
3. Ансамбль с голосованием (минимум 3 голоса из 4)
4. Исключение облаков/теней/снега по QA каналу
5. Морфологическая постобработка
6. Удаление объектов < 100 пикселей
"""
        with open(export_dir / "ОТЧЕТ_АНАЛИЗА.txt", 'w', encoding='utf-8') as f:
            f.write(report)

    def _normalize_for_display(self, data):
        try:
            finite = data[np.isfinite(data)]
            p1, p99 = np.percentile(finite, [1, 99])
            normalized = np.clip(data, p1, p99)
            if p99 != p1:
                normalized = (normalized - p1) / (p99 - p1)
            return np.nan_to_num(normalized, 0)
        except Exception:
            return np.zeros_like(data)
