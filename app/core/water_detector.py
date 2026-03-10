import numpy as np
import cv2

from app.core.cloud_filler import CloudFiller


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
        self.merge_gap_px = 0
        self.spatial_fill = True
        self.min_fill_area = 20
        self.fill_water_frac = 0.50
        self.mask_shadows = True
        self.use_thermal_mask = False
        self.thermal_temp_c = 5.0
        self.thermal_bright_threshold = 0.12
        self.use_cdist_buffer = False
        self.cdist_buffer_km = 0.3
        self.cloud_buffer_px = 0
        self.use_hot_mask = False
        self.hot_threshold = 0.05

        self._filler = CloudFiller()

    def set_parameters(self, thresholds=None, min_object_size=None,
                       apply_morphology=None, merge_gap_px=None, spatial_fill=None,
                       min_fill_area=None, fill_water_frac=None, mask_shadows=None,
                       use_thermal_mask=None, thermal_temp_c=None,
                       thermal_bright_threshold=None,
                       use_cdist_buffer=None, cdist_buffer_km=None,
                       cloud_buffer_px=None, use_hot_mask=None, hot_threshold=None):
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
        if min_fill_area is not None:
            self.min_fill_area = min_fill_area
        if fill_water_frac is not None:
            self.fill_water_frac = fill_water_frac
        if mask_shadows is not None:
            self.mask_shadows = mask_shadows
        if use_thermal_mask is not None:
            self.use_thermal_mask = use_thermal_mask
        if thermal_temp_c is not None:
            self.thermal_temp_c = thermal_temp_c
        if thermal_bright_threshold is not None:
            self.thermal_bright_threshold = thermal_bright_threshold
        if use_cdist_buffer is not None:
            self.use_cdist_buffer = use_cdist_buffer
        if cdist_buffer_km is not None:
            self.cdist_buffer_km = cdist_buffer_km
        if cloud_buffer_px is not None:
            self.cloud_buffer_px = cloud_buffer_px
        if use_hot_mask is not None:
            self.use_hot_mask = use_hot_mask
        if hot_threshold is not None:
            self.hot_threshold = hot_threshold

        # Синхронизируем параметры с CloudFiller
        self._filler.min_fill_area    = self.min_fill_area
        self._filler.fill_water_frac  = self.fill_water_frac
        self._filler.use_thermal_mask = self.use_thermal_mask
        self._filler.thermal_temp_c = self.thermal_temp_c
        self._filler.thermal_bright_threshold = self.thermal_bright_threshold
        self._filler.use_cdist_buffer = self.use_cdist_buffer
        self._filler.cdist_buffer_km = self.cdist_buffer_km
        self._filler.use_hot_mask = self.use_hot_mask
        self._filler.hot_threshold = self.hot_threshold

    def detect_water(self, data, progress_callback=None):
        """Основной метод детектирования водных объектов."""
        def _prog(msg):
            if progress_callback:
                progress_callback(msg)

        try:
            _prog('Вычисление водных индексов...')
            indices = self._calculate_water_indices(data)

            binary_masks = {}
            for name, values in indices.items():
                if name in self.thresholds:
                    binary_masks[name] = values > self.thresholds[name]
            del indices
            indices = {}

            _prog('Применение облачной маски...')
            if self.mask_shadows:
                detect_mask = data.get('exclude_mask')
            else:
                detect_mask = data.get('cloud_only_mask')
            detect_mask = self._filler.enhance_mask(detect_mask, data)

            # Буфер QA: расширяем маску на N пикселей — захватывает cloud adjacency effect
            # Расширенные пиксели попадают и в fill_cloud_mask → spatial fill их восстановит
            if self.cloud_buffer_px > 0 and detect_mask is not None:
                k = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE,
                    (self.cloud_buffer_px * 2 + 1, self.cloud_buffer_px * 2 + 1)
                )
                detect_mask = cv2.dilate(detect_mask.astype(np.uint8), k).astype(bool)
            fill_cloud_mask = detect_mask  # fill видит ту же расширенную маску

            _prog('Ансамблевое голосование...')
            water_mask = self._ensemble_voting(binary_masks, detect_mask)

            # Close/open до fill: соединяет фрагменты воды у краёв облаков,
            # что улучшает расчёт border_water_frac при заполнении.
            if self.apply_morphology:
                _prog('Морфологическая обработка...')
                water_mask = self._apply_morphological_operations(water_mask)

            if self.merge_gap_px > 0:
                water_mask = self._merge_nearby_objects(water_mask, self.merge_gap_px)

            if self.spatial_fill:
                _prog('Заполнение под облаками...')
                before_fill = water_mask.copy()

                water_mask = self._filler.fill(
                    water_mask, fill_cloud_mask,
                    nodata_mask=data.get('nodata_mask'),
                )
                water_mask = self._smooth_filled_edges(
                    water_mask, before_fill, fill_cloud_mask
                )

            # remove_small_objects после fill: чистит как шум индексов,
            # так и артефакты краёв заполненных облаков за один проход.
            water_mask = self._remove_small_objects(water_mask)

            _prog('Анализ водных объектов...')
            analysis_results = self._analyze_water_objects(water_mask, data)

            _prog('Создание визуализаций...')
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
            print(f'Ошибка детектирования: {e}')
            import traceback; traceback.print_exc()
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
            return water_mask
        except Exception as e:
            print(f'Ошибка морфологических операций: {e}')
            return water_mask

    def _remove_small_objects(self, water_mask):
        """Удаляет компоненты меньше min_object_size через cv2 (быстрее skimage в 3-5х)."""
        try:
            n, labels, stats, _ = cv2.connectedComponentsWithStats(water_mask, connectivity=8)
            areas = stats[:, cv2.CC_STAT_AREA]
            keep  = np.zeros(n, dtype=bool)
            keep[1:] = areas[1:] >= self.min_object_size  # 0 = фон, пропускаем
            return keep[labels].astype(np.uint8)
        except Exception as e:
            print(f'Ошибка удаления мелких объектов: {e}')
            return water_mask

    def _merge_nearby_objects(self, water_mask, gap_px: int):
        size = gap_px * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        return cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, kernel)

    def _smooth_filled_edges(self, water_mask, original_mask, cloud_mask=None):
        """
        Убирает аутлайн на QA-границе облаков после spatial fill.

        QA-маска немного не дотягивает до реального края облака, получается 1-2px кольцо
        с испорченной яркостью остаётся снаружи cloud_mask и не заполняется fill.
        MORPH_CLOSE с ядром 7px, ограниченный расширенным cloud_mask, замыкает
        этот зазор между заполненной зоной и исходной водой.
        """

        newly_filled = water_mask.astype(bool) & ~original_mask.astype(bool)
        if not newly_filled.any() or cloud_mask is None:
            return water_mask

        # Расширяем cloud_mask на 3px - захватываем пиксели снаружи QA-границы
        k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        expanded_cloud = cv2.dilate(cloud_mask.astype(np.uint8), k3).astype(bool)

        # MORPH_CLOSE замыкает зазоры в водной маске в пределах облачной зоны
        closed = cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, k7)
        return np.where(expanded_cloud, closed, water_mask).astype(np.uint8)

    def _analyze_water_objects(self, water_mask, data):
        try:
            pixel_size_km = abs(data['meta']['transform'][0]) / 1000 if 'meta' in data else 0.03
            pixel_area_km2 = pixel_size_km ** 2

            total_water_pixels = int(np.sum(water_mask))
            total_area_km2 = total_water_pixels * pixel_area_km2
            total_pixels = water_mask.size
            water_percentage = (total_water_pixels / total_pixels) * 100

            exclude_mask = data.get('exclude_mask')
            nodata_mask  = data.get('nodata_mask')
            cloud_pixels = int(np.sum(exclude_mask)) if exclude_mask is not None else 0
            nodata_pixels = int(np.sum(nodata_mask)) if nodata_mask is not None else 0
            valid_pixels = total_pixels - nodata_pixels
            cloud_percentage  = (cloud_pixels / valid_pixels * 100) if valid_pixels > 0 else 0.0
            land_percentage   = max(0.0, 100.0 - water_percentage - cloud_percentage)

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
                'cloud_percentage': cloud_percentage,
                'land_percentage': land_percentage,
                'object_count': len(objects_data),
                'objects_data': objects_data,
                'largest_object_area': objects_data[0]['area_km2'] if objects_data else 0,
                'average_object_size': total_area_km2 / len(objects_data) if objects_data else 0,
                'contours': contours
            }

        except Exception as e:
            print(f'Ошибка анализа объектов: {e}')
            return {}

    def _create_visualizations(self, water_mask, data, contours=None):
        try:
            vis = {}
            if not all(b in data for b in ['SR_B4', 'SR_B3', 'SR_B2']):
                return vis

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

            GAMMA = 2.0
            np.power(rgb, 1.0 / GAMMA, out=rgb)
            np.clip(rgb, 0, 1, out=rgb)
            vis['rgb_image'] = rgb

            water_px = (water_mask == 1)[:, :, np.newaxis]
            water_color = np.array([0.2, 0.5, 1.0], dtype=np.float32)
            vis['overlay_image'] = np.where(water_px, rgb * 0.6 + water_color * 0.4, rgb)

            if contours is None:
                contours, _ = cv2.findContours(water_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contour_img = (rgb * 255).astype(np.uint8)
            cv2.drawContours(contour_img, contours, -1, (255, 80, 0), 2)
            vis['contour_image'] = contour_img.astype(np.float32) / 255.0

            cloud_vis = rgb * 0.55
            shadow = data.get('shadow_mask')
            if shadow is not None:
                px = shadow[:, :, np.newaxis]
                cloud_vis = np.where(px, rgb * 0.2 + np.array([0.1, 0.25, 0.9]) * 0.8, cloud_vis)
            clouds = data.get('cloud_only_mask')
            if clouds is not None:
                px = clouds[:, :, np.newaxis]
                cloud_vis = np.where(px, rgb * 0.2 + np.array([1.0, 0.5, 0.05]) * 0.8, cloud_vis)
            cloud_vis = np.clip(cloud_vis, 0, 1)
            vis['cloud_image_plain'] = cloud_vis  # без отладочных боксов
            vis['cloud_mask_image'] = self._filler.annotate_bboxes(
                cloud_vis, water_mask.astype(bool),
                data.get('exclude_mask'), data.get('nodata_mask')
            )

            return vis

        except Exception as e:
            print(f'Ошибка создания визуализаций: {e}')
            return {}
