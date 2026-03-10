import os
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor, as_completed


class CloudFiller:
    def __init__(self):
        self.use_thermal_mask = False
        self.thermal_temp_c = 5.0
        self.thermal_bright_threshold = 0.12
        self.use_cdist_buffer = False
        self.cdist_buffer_km = 0.3
        self.use_hot_mask = False
        self.hot_threshold = 0.05
        self.min_fill_area = 20
        self.fill_water_frac = 0.50

    def enhance_mask(self, base_mask, data):
        """Дополняет базовую QA-маску температурной и/или CDIST-буферной маской."""
        enhanced = base_mask
        if self.use_thermal_mask and 'st_celsius' in data:
            thermal = self._build_thermal_mask(data)
            if thermal is not None:
                enhanced = thermal if enhanced is None else (enhanced | thermal)
        if self.use_cdist_buffer and 'cdist_km' in data:
            cdist = self._build_cdist_mask(data)
            if cdist is not None:
                enhanced = cdist if enhanced is None else (enhanced | cdist)
        if self.use_hot_mask:
            hot = self._build_hot_mask(data)
            if hot is not None:
                enhanced = hot if enhanced is None else (enhanced | hot)
        return enhanced

    def _build_thermal_mask(self, data):
        st = data.get('st_celsius')
        green = data.get('SR_B3')
        if st is None or green is None:
            return None
        return (st < self.thermal_temp_c) & (green > self.thermal_bright_threshold)

    def _build_cdist_mask(self, data):
        cdist = data.get('cdist_km')
        if cdist is None:
            return None
        return (cdist > 0) & (cdist < self.cdist_buffer_km)

    def _build_hot_mask(self, data):
        """
        Haze Optimized Transform: HOT = Blue - 0.5 * Red.
        Высокий HOT -> дымка / полупрозрачное облако / cloud adjacency effect.
        Вода имеет низкий HOT (синий, но тёмный), поэтому ложных срабатываний мало.
        """
        blue = data.get('SR_B2')
        red  = data.get('SR_B4')
        if blue is None or red is None:
            return None
        return (blue - 0.5 * red) > self.hot_threshold

    def build_components(self, cloud_mask, merge_radius=3):
        """
        Строит именованные компоненты облаков/теней через cv2 (быстрее scipy.label в 3-5х).
        Возвращает (n_components, labeled_array, slices_list).
        """
        if merge_radius > 0:
            k = merge_radius * 2 + 1
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
            merged = cv2.dilate(cloud_mask.astype(np.uint8), kernel)
        else:
            merged = cloud_mask.astype(np.uint8)

        n, labeled, stats, _ = cv2.connectedComponentsWithStats(merged, connectivity=8)
        # n включает фон (label 0), компоненты: 1..n-1
        n_comp = n - 1
        if n_comp == 0:
            return 0, labeled, []

        # Bounding boxes из stats — быстрее ndimage.find_objects
        slices = []
        for i in range(1, n):
            top  = int(stats[i, cv2.CC_STAT_TOP])
            left = int(stats[i, cv2.CC_STAT_LEFT])
            h    = int(stats[i, cv2.CC_STAT_HEIGHT])
            w    = int(stats[i, cv2.CC_STAT_WIDTH])
            slices.append((slice(top, top + h), slice(left, left + w)))

        return n_comp, labeled, slices

    def fill(self, water_mask, cloud_mask, nodata_mask=None, merge_radius=5):
        if cloud_mask is None:
            return water_mask

        result = water_mask.copy()

        n, labeled, slices = self.build_components(cloud_mask, merge_radius)
        if n == 0:
            return result

        h, w = result.shape
        BORDER_PAD = 8
        DILATE_K = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))

        for _ in range(8):
            prev_sum = int(result.sum())
            water_bool = result.astype(bool)
            self._fill_pass(
                cloud_mask, water_bool, nodata_mask, result,
                self.min_fill_area, self.fill_water_frac,
                labeled, slices, h, w, BORDER_PAD, DILATE_K,
            )
            if int(result.sum()) == prev_sum:
                break

        return result

    def _fill_pass(self, cloud_mask, water_bool, nodata_mask, result,
                   min_area_px, water_border_frac,
                   labeled, slices, h, w, BORDER_PAD, DILATE_K):
        def check_comp(comp_id, sl):
            orig_local = cloud_mask[sl] & (labeled[sl] == comp_id)
            if int(orig_local.sum()) < min_area_px:
                return None

            r0 = max(0, sl[0].start - BORDER_PAD)
            r1 = min(h, sl[0].stop  + BORDER_PAD)
            c0 = max(0, sl[1].start - BORDER_PAD)
            c1 = min(w, sl[1].stop  + BORDER_PAD)
            sl_ext = (slice(r0, r1), slice(c0, c1))

            comp_u8 = (labeled[sl_ext] == comp_id).astype(np.uint8)
            border  = cv2.dilate(comp_u8, DILATE_K).astype(bool) & ~comp_u8.astype(bool)
            if nodata_mask is not None:
                border &= ~nodata_mask[sl_ext]
            bsum = int(border.sum())
            if bsum == 0:
                return None

            water_on_border = int(water_bool[sl_ext][border].sum())
            if water_on_border == 0:
                return None

            if water_on_border / bsum >= water_border_frac:
                return (sl, orig_local)
            return None

        n_workers = min(os.cpu_count() or 4, 8)
        fills = []
        with ThreadPoolExecutor(max_workers=n_workers) as ex:
            futures = {ex.submit(check_comp, i + 1, sl): i for i, sl in enumerate(slices)}
            for fut in as_completed(futures):
                res = fut.result()
                if res is not None:
                    fills.append(res)

        for sl, orig_local in fills:
            result[sl][orig_local] = 1

    def annotate_bboxes(self, cloud_vis, water_bool, cloud_mask, nodata_mask=None):
        if cloud_mask is None or not water_bool.any():
            return cloud_vis.astype(np.float32)

        MAX_DRAW = 200
        n, labeled, slices = self.build_components(cloud_mask)
        if n == 0:
            return cloud_vis.astype(np.float32)

        img = (cloud_vis * 255).astype(np.uint8)

        comp_info = []
        for comp_id, sl in enumerate(slices, start=1):
            orig_area = int((cloud_mask[sl] & (labeled[sl] == comp_id)).sum())
            if orig_area >= 10:
                comp_info.append((orig_area, comp_id, sl))
        comp_info.sort(reverse=True)
        comp_info = comp_info[:MAX_DRAW]

        DILATE_K3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

        def calc_comp(orig_area, comp_id, sl):
            comp_u8 = (labeled[sl] == comp_id).astype(np.uint8)
            border  = cv2.dilate(comp_u8, DILATE_K3).astype(bool) & ~comp_u8.astype(bool)
            if nodata_mask is not None:
                border &= ~nodata_mask[sl]
            if border.sum() == 0:
                return None
            frac   = float(water_bool[sl][border].mean())
            passes = frac >= self.fill_water_frac and orig_area >= self.min_fill_area
            return (orig_area, sl, frac, passes)

        n_workers = min(os.cpu_count() or 4, 8)
        draw_data = []
        with ThreadPoolExecutor(max_workers=n_workers) as ex:
            futures = [ex.submit(calc_comp, a, c, s) for a, c, s in comp_info]
            for fut in as_completed(futures):
                res = fut.result()
                if res is not None:
                    draw_data.append(res)

        for orig_area, sl, frac, passes in draw_data:
            y0, y1 = sl[0].start, sl[0].stop
            x0, x1 = sl[1].start, sl[1].stop
            color     = (50, 210, 50) if passes else (60, 60, 220)
            thickness = max(1, min(4, orig_area // 1000))
            cv2.rectangle(img, (x0, y0), (x1, y1), color[::-1], thickness)

            text       = f'{frac * 100:.0f}%'
            font_scale = max(0.4, min(1.4, orig_area / 4000))
            tx, ty     = x0 + 3, max(y0 + int(16 * font_scale), 14)
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
            cv2.rectangle(img, (tx - 1, ty - th - 2), (tx + tw + 1, ty + 2), (15, 15, 15), -1)
            cv2.putText(img, text, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                        font_scale, color[::-1], 1, cv2.LINE_AA)

        return img.astype(np.float32) / 255.0
