import numpy as np
import rasterio
from pathlib import Path


class DataProcessor:
    def __init__(self):
        self.required_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
        self.required_qa = 'QA_PIXEL'
        self.data_cache = {}
        self.metadata = {}

    def load_landsat_data(self, file_paths):
        """Загрузка данных Landsat 9 из списка файлов .tif"""
        try:
            band_files = {}
            qa_file = None

            for file_path in file_paths:
                filename = Path(file_path).name.upper()
                for band in self.required_bands:
                    if band in filename:
                        band_files[band] = file_path
                        break
                if self.required_qa in filename:
                    qa_file = file_path

            missing_bands = set(self.required_bands) - set(band_files.keys())
            if missing_bands:
                print(f"Отсутствуют каналы: {missing_bands}")
                return None

            if not qa_file:
                print(f"Отсутствует файл качества: {self.required_qa}")
                return None

            loaded_data = {}
            self.metadata = {}

            for band, file_path in band_files.items():
                with rasterio.open(file_path) as src:
                    data = src.read(1).astype(np.float32)
                    loaded_data[band] = data
                    if not self.metadata:
                        self.metadata = {
                            'crs': src.crs,
                            'transform': src.transform,
                            'width': src.width,
                            'height': src.height,
                            'bounds': src.bounds
                        }

            with rasterio.open(qa_file) as src:
                loaded_data[self.required_qa] = src.read(1)

            loaded_data = self._preprocess_data(loaded_data)
            loaded_data['meta'] = self.metadata
            self.data_cache = loaded_data

            print(f"Успешно загружено {len(loaded_data)} каналов")
            return loaded_data

        except Exception as e:
            print(f"Ошибка загрузки данных: {e}")
            return None

    def _preprocess_data(self, data):
        """Масштабирование Landsat Collection 2 Level-2 + маска облаков"""
        try:
            scale_factor = 0.0000275
            add_offset = -0.2

            for band in self.required_bands:
                if band in data:
                    data[band] = np.clip(data[band] * scale_factor + add_offset, 0, 1)

            if self.required_qa in data:
                qa_data = data[self.required_qa]
                cloud_mask   = self._extract_qa_bits(qa_data, [1, 3])
                shadow_mask  = self._extract_qa_bits(qa_data, [4])
                snow_mask    = self._extract_qa_bits(qa_data, [5])
                cirrus_mask  = self._extract_qa_bits(qa_data, [2])
                # Для детектирования: тени включаем по умолчанию.
                # mask_shadows управляется из UI через set_shadow_masking().
                data['exclude_mask'] = cloud_mask | shadow_mask | snow_mask | cirrus_mask
                data['shadow_mask']  = shadow_mask  # отдельно - для опционального включения
                data['cloud_only_mask'] = cloud_mask | snow_mask | cirrus_mask
                # Для RGB-отображения: всегда исключаем тени из перцентильного стретча.
                data['display_exclude_mask'] = cloud_mask | shadow_mask | snow_mask | cirrus_mask

            return data

        except Exception as e:
            print(f"Ошибка предобработки: {e}")
            return data

    def _extract_qa_bits(self, qa_array, bit_positions):
        result = np.zeros_like(qa_array, dtype=bool)
        for bit_pos in bit_positions:
            result |= (qa_array & (1 << bit_pos)) != 0
        return result

    def get_pixel_size_km(self):
        if self.metadata and 'transform' in self.metadata:
            return abs(self.metadata['transform'][0]) / 1000.0
        return 0.03
