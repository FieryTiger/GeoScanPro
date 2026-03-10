import numpy as np
import cv2
from PIL import Image
import pandas as pd
import json
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

    def export_to_pdf(self, results: dict, export_path: str) -> bool:
        try:
            from matplotlib.backends.backend_pdf import PdfPages
            from matplotlib.figure import Figure
            from matplotlib.gridspec import GridSpec
            from app.gui.charts import _draw_area_histogram, _draw_composition_pie

            with PdfPages(export_path) as pdf:
                fig = Figure(figsize=(8.27, 11.69))  # A4 книжная
                gs = GridSpec(
                    3, 3, figure=fig,
                    height_ratios=[2.4, 1.6, 1.0],
                    hspace=0.40, wspace=0.28,
                    left=0.05, right=0.97, top=0.93, bottom=0.05,
                )

                fig.suptitle(
                    f'Отчёт по анализу водных объектов — GeoScanPro\n'
                    f'{datetime.now().strftime("%d.%m.%Y %H:%M:%S")}',
                    fontsize=12, fontweight='bold',
                )

                for col, (key, title) in enumerate([
                    ('rgb_image',       'RGB'),
                    ('overlay_image',   'Overlay (вода)'),
                    ('cloud_image_plain', 'Облачность'),
                ]):
                    ax = fig.add_subplot(gs[0, col])
                    arr = results.get(key)
                    if arr is not None:
                        arr = np.clip(arr, 0, 1)
                        h, w = arr.shape[:2]
                        scale = 600 / max(h, w)
                        small = cv2.resize(
                            (arr * 255).astype(np.uint8),
                            (int(w * scale), int(h * scale)),
                            interpolation=cv2.INTER_AREA,
                        )
                        ax.imshow(small)
                    ax.set_title(title, fontsize=8)
                    ax.axis('off')

                _draw_area_histogram(fig.add_subplot(gs[1, 0]), results)
                _draw_composition_pie(fig.add_subplot(gs[1, 1]), results)
                fig.add_subplot(gs[1, 2]).set_visible(False)

                ax_tbl = fig.add_subplot(gs[2, :])
                ax_tbl.axis('off')

                rows = [
                    ['Площадь воды, км²',    f"{results.get('total_water_area_km2', 0):.4f}",
                     '% воды',               f"{results.get('water_percentage', 0):.2f}%",
                     '% облаков',            f"{results.get('cloud_percentage', 0):.2f}%"],
                    ['% суши',               f"{results.get('land_percentage', 0):.2f}%",
                     'Объектов',             str(results.get('object_count', 0)),
                     'Крупнейший объект, км²', f"{results.get('largest_object_area', 0):.4f}"],
                    ['Средний объект, км²',  f"{results.get('average_object_size', 0):.4f}",
                     'Общий периметр, км',   f"{results.get('total_perimeter_km', 0):.2f}",
                     '', ''],
                ]
                tbl = ax_tbl.table(
                    cellText=rows,
                    colLabels=['Показатель', 'Значение', 'Показатель', 'Значение', 'Показатель', 'Значение'],
                    loc='center', cellLoc='left',
                )
                tbl.auto_set_font_size(False)
                tbl.set_fontsize(8.5)
                tbl.scale(1, 1.8)
                for (r, c), cell in tbl.get_celld().items():
                    if r == 0:
                        cell.set_facecolor('#dbeafe')
                    elif c in (0, 2, 4):
                        cell.set_facecolor('#f8fafc')
                    cell.set_edgecolor('#e2e8f0')

                pdf.savefig(fig)

            return True
        except Exception as e:
            print(f'Ошибка экспорта PDF: {e}')
            return False

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
