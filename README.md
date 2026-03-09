<p align="center">
  <img src="resources/GeoScanPro.png" width="96" alt="GeoScanPro">
</p>

<h1 align="center">GeoScanPro</h1>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python">
  <img src="https://img.shields.io/badge/PySide6-6.6+-green" alt="PySide6">
  <img src="https://img.shields.io/badge/Landsat-9%20L2C2-orange" alt="Landsat">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey" alt="Platform">
</p>

Десктопное приложение для автоматического детектирования водных объектов на снимках Landsat 9.

---

## Как это работает

1. **Загрузка** — импорт файлов Landsat 9 Level-2 Collection 2 `.tif` (каналы SR\_B2–SR\_B7 + QA\_PIXEL)
2. **Предобработка** — масштабирование отражательной способности (×0.0000275 − 0.2), построение масок облаков, теней, снега и цирусов из битовых флагов QA\_PIXEL
3. **Вычисление индексов** — расчёт пяти спектральных водных индексов: NDWI, MNDWI, AWEI\_nsh, LSWI, WI
4. **Ансамблевое голосование** — каждый индекс голосует; пиксели с ≥3 голосами классифицируются как вода, облачные пиксели исключаются
5. **Морфологическая обработка** — closing/opening для устранения шума, заполнение мелких дыр, удаление объектов ниже минимального размера
6. **Анализ** — детектирование контуров по каждому водному объекту: площадь (км²), периметр, коэффициент формы, количество объектов
7. **Визуализация** — истинноцветной RGB с гамма-коррекцией, оверлей воды, отрисовка контуров
8. **Экспорт** — результаты сохраняются в историю SQLite, доступен экспорт в CSV/Excel

## Установка

```bash
pip install -r requirements.txt
python main.py
```

## Зависимости

| Пакет | Версия |
|---|---|
| PySide6 | ≥ 6.6.0 |
| numpy | ≥ 1.24.0 |
| opencv-python | ≥ 4.8.0 |
| rasterio | ≥ 1.3.0 |
| scipy | ≥ 1.11.0 |
| scikit-image | ≥ 0.21.0 |
| matplotlib | ≥ 3.7.0 |
| pandas | ≥ 2.0.0 |
