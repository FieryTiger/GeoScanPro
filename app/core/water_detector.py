import numpy as np
import cv2
from skimage import morphology
from scipy.ndimage import binary_fill_holes


class WaterDetector:
    def __init__(self):
        self.thresholds = {
            'NDWI': 0.3,
            'MNDWI': 0.2,
            'AWEI_nsh': 0.0,
            'LSWI': 0.3
        }
        self.min_object_size = 100
        self.apply_morphology = True
        self.voting_threshold = 3
        self.merge_gap_px = 0      # радиус closing для слияния близких объектов (0 = выкл)
        self.spatial_fill = False  # заполнять облачные пиксели окружённые водой
        self.mask_shadows = True   # исключать тени облаков из детектирования

    def set_parameters(self, thresholds=None, min_object_size=None,
                       apply_morphology=None, merge_gap_px=None, spatial_fill=None,
                       mask_shadows=None):
        if thresholds:
            self.thresholds.update(thresholds)
        if min_object_size is not None:
            self.min_object_size = min_object_size
        if apply_morphology is not None:
            self.apply_morphology = apply_morphology
        if merge_gap_px is not None:
            self.merge_gap_px = merge_gap_px
        if spatial_fill is not None:
            self.spatial_fill = spatial_fill
        if mask_shadows is not None:
            self.mask_shadows = mask_shadows

    def detect_water(self, data):
        """Основной метод детектирования водных объектов"""
        try:
            indices = self._calculate_water_indices(data)

            binary_masks = {}
            for name, values in indices.items():
                if name in self.thresholds:
                    binary_masks[name] = values > self.thresholds[name]
            del indices
            indices = {}

            if self.mask_shadows:
                detect_mask = data.get('exclude_mask')        # облака + тени + снег + цирус
            else:
                detect_mask = data.get('cloud_only_mask')     # только облака + снег + цирус
            water_mask = self._ensemble_voting(binary_masks, detect_mask)

            if self.apply_morphology:
                water_mask = self._apply_morphological_operations(water_mask)

            water_mask = self._remove_small_objects(water_mask)

            # Слияние близких объектов через дополнительное closing
            if self.merge_gap_px > 0:
                water_mask = self._merge_nearby_objects(water_mask, self.merge_gap_px)

            # Заполнение облачных пикселей, окружённых водой
            if self.spatial_fill:
                water_mask = self._fill_cloud_gaps(water_mask, data.get('exclude_mask'))

            analysis_results = self._analyze_water_objects(water_mask, data)

            visualizations = self._create_visualizations(
                water_mask, data, contours=analysis_results.get('contours')
            )

            return {
                'water_mask': water_mask,
                'indices': indices,
                'binary_masks': binary_masks,
                **analysis_results,
                **visualizations
            }

        except Exception as e:
            print(f"Ошибка детектирования: {e}")
            return None

    def _calculate_water_indices(self, data):
        green = data['SR_B3']
        red   = data['SR_B4']
        nir   = data['SR_B5']
        swir1 = data['SR_B6']
        swir2 = data['SR_B7']

        def safe_ratio(a, b):
            return np.where((a + b) != 0, (a - b) / (a + b), 0)

        return {
            'NDWI':     safe_ratio(green, nir),
            'MNDWI':    safe_ratio(green, swir1),
            'AWEI_nsh': 4 * (green - swir1) - (0.25 * nir + 2.75 * swir2),
            'LSWI':     safe_ratio(nir, swir1),
            'WI':       1.7204 + 171 * green + 3 * red - 70 * nir - 45 * swir1 - 71 * swir2,
        }

    def _ensemble_voting(self, binary_masks, exclude_mask=None):
        if not binary_masks:
            return None
        vote_count = np.zeros_like(list(binary_masks.values())[0], dtype=int)
        for mask in binary_masks.values():
            vote_count += mask.astype(int)
        water_mask = vote_count >= self.voting_threshold
        if exclude_mask is not None:
            water_mask = water_mask & (~exclude_mask)
        return water_mask.astype(np.uint8)

    def _apply_morphological_operations(self, water_mask):
        try:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, kernel)
            water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_OPEN, kernel)
            cleaned = morphology.remove_small_holes(water_mask.astype(bool), area_threshold=100)
            return cleaned.astype(np.uint8)
        except Exception as e:
            print(f"Ошибка морфологических операций: {e}")
            return water_mask

    def _remove_small_objects(self, water_mask):
        try:
            cleaned = morphology.remove_small_objects(water_mask.astype(bool), min_size=self.min_object_size)
            return cleaned.astype(np.uint8)
        except Exception as e:
            print(f"Ошибка удаления мелких объектов: {e}")
            return water_mask

    def _analyze_water_objects(self, water_mask, data):
        try:
            pixel_size_km = abs(data['meta']['transform'][0]) / 1000 if 'meta' in data else 0.03
            pixel_area_km2 = pixel_size_km ** 2

            total_water_pixels = int(np.sum(water_mask))
            total_area_km2 = total_water_pixels * pixel_area_km2
            water_percentage = (total_water_pixels / water_mask.size) * 100

            contours, _ = cv2.findContours(water_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            objects_data = []
            total_perimeter_km = 0

            for i, contour in enumerate(contours):
                area_pixels = cv2.contourArea(contour)
                area_km2 = area_pixels * pixel_area_km2
                perimeter_pixels = cv2.arcLength(contour, True)
                perimeter_km = perimeter_pixels * pixel_size_km
                total_perimeter_km += perimeter_km
                shape_factor = (4 * np.pi * area_pixels / perimeter_pixels ** 2) if perimeter_pixels > 0 else 0

                objects_data.append({
                    'id': i,
                    'area_pixels': int(area_pixels),
                    'area_km2': area_km2,
                    'perimeter_km': perimeter_km,
                    'shape_factor': shape_factor,
                    'contour': contour
                })

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
            print(f"Ошибка анализа объектов: {e}")
            return {}

    def _merge_nearby_objects(self, water_mask, gap_px: int):
        """Closing с большим ядром - сшивает объекты ближе gap_px пикселей."""
        size = gap_px * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        return cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, kernel)

    def _fill_cloud_gaps(self, water_mask, cloud_mask):
        """Заполняет облачные пиксели, полностью окружённые водой."""
        if cloud_mask is None:
            return water_mask
        filled = binary_fill_holes(water_mask.astype(bool))
        cloud_enclosed = filled & ~water_mask.astype(bool) & cloud_mask
        result = water_mask.copy()
        result[cloud_enclosed] = 1
        return result

    def _create_visualizations(self, water_mask, data, contours=None):
        """
        Создаёт визуализации для отображения.
        Оптимизации:
        - одна нормализация RGB, без лишних копий массивов
        - overlay через np.where (без copy)
        - contours переиспользуются из _analyze_water_objects
        """
        try:
            vis = {}
            if not all(b in data for b in ['SR_B4', 'SR_B3', 'SR_B2']):
                return vis

            # RGB нормализация - per-channel stretch
            # Исключаем из расчёта:
            #   - nodata (ch <= 0.001)
            #   - пересвет (ch >= 0.990)
            #   - облака/тени/снег (exclude_mask) - иначе яркие облака
            #     доминируют в p98 и делают остальную сцену тёмной
            rgb = np.stack([data['SR_B4'], data['SR_B3'], data['SR_B2']], axis=-1)
            cloud_mask = data.get('display_exclude_mask', data.get('exclude_mask'))
            for c in range(3):
                ch = rgb[:, :, c]
                good = (ch > 0.001) & (ch < 0.990)
                if cloud_mask is not None:
                    good &= ~cloud_mask
                valid = ch[good]
                if valid.size > 1000:
                    p2, p98 = np.percentile(valid, [2, 98])
                else:
                    p2, p98 = float(ch.min()), float(ch.max())
                denom = p98 - p2
                if denom > 1e-10:
                    rgb[:, :, c] = np.clip((ch - p2) / denom, 0, 1)
                else:
                    rgb[:, :, c] = 0.0

            # Гамма-коррекция: поднимает тёмные пиксели (стандарт ДЗЗ)
            # gamma=2.0 -> sqrt(x), хорошо для зимних и водных сцен
            GAMMA = 2.0
            np.power(rgb, 1.0 / GAMMA, out=rgb)
            np.clip(rgb, 0, 1, out=rgb)
            vis['rgb_image'] = rgb

            # Overlay - без copy(), через np.where
            water_px = (water_mask == 1)[:, :, np.newaxis]
            water_color = np.array([0.2, 0.5, 1.0], dtype=np.float32)
            vis['overlay_image'] = np.where(water_px, rgb * 0.6 + water_color * 0.4, rgb)

            # Контуры - переиспользуем уже найденные
            if contours is None:
                contours, _ = cv2.findContours(water_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contour_img = (rgb * 255).astype(np.uint8)
            # Наш массив в RGB-порядке, cv2 ожидает BGR → цвет контура (R=255,G=80,B=0)
            cv2.drawContours(contour_img, contours, -1, (255, 80, 0), 2)
            vis['contour_image'] = contour_img.astype(np.float32) / 255.0

            return vis

        except Exception as e:
            print(f"Ошибка создания визуализаций: {e}")
            return {}
