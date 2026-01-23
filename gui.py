# gui.py
"""
GeoScanPro - Графический интерфейс пользователя
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from tkinter import ttk
import threading
import os
from pathlib import Path
import zipfile
import rarfile
import tarfile
import json
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pandas as pd
from datetime import datetime
import os

from app_core import DataProcessor, WaterDetector
from utils import ImageExporter, create_default_settings

class GeoScanProGUI:
    def __init__(self, root):
        self.root = root
        self.data_processor = DataProcessor()
        self.water_detector = WaterDetector()
        self.image_exporter = ImageExporter()
        
        # Настройки по умолчанию
        self.settings = create_default_settings()
        self.load_settings()
        
        # Переменные для хранения результатов
        self.loaded_data = None
        self.water_mask = None
        self.detection_results = None
        
        self.create_widgets()
        self.setup_drag_drop()
    
    def load_settings(self):
        """Загрузка настроек из файла"""
        settings_file = Path("resources/settings.json")
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                self.settings.update(saved_settings)
            except Exception as e:
                print(f"Ошибка загрузки настроек: {e}")
    
    def save_settings(self):
        """Сохранение настроек в файл"""
        try:
            with open("resources/settings.json", 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
    
    def create_widgets(self):
        """Создание виджетов интерфейса"""
        # Главное меню
        self.create_menu()
        
        # Основной контейнер
        self.main_container = ctk.CTkFrame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Создание вкладок
        self.notebook = ctk.CTkTabview(self.main_container)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Вкладка загрузки данных
        self.create_data_tab()
        
        # Вкладка настроек детектирования
        self.create_detection_tab()
        
        # Вкладка результатов
        self.create_results_tab()
        
        # Вкладка статистики
        self.create_statistics_tab()
    
    def create_menu(self):
        """Создание главного меню"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Меню Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Открыть файлы", command=self.load_files)
        file_menu.add_command(label="Открыть архив", command=self.load_archive)
        file_menu.add_separator()
        file_menu.add_command(label="Экспорт результатов", command=self.export_results, state="disabled")
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.root.quit)
        
        # Меню Настройки
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Настройки", menu=settings_menu)
        settings_menu.add_command(label="Параметры детектирования", command=self.open_settings_window)
        settings_menu.add_separator()
        settings_menu.add_command(label="Светлая тема", command=lambda: self.change_theme("light"))
        settings_menu.add_command(label="Темная тема", command=lambda: self.change_theme("dark"))
        settings_menu.add_command(label="Системная тема", command=lambda: self.change_theme("system"))
        
        # Меню Справка
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self.show_about)
        
        self.menubar = menubar
    
    def create_data_tab(self):
        """Создание вкладки загрузки данных"""
        self.data_tab = self.notebook.add("Загрузка данных")
        
        # Заголовок
        title = ctk.CTkLabel(self.data_tab, text="Загрузка спутниковых данных Landsat 9", 
                           font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(pady=20)
        
        # Область для drag & drop
        self.drop_frame = ctk.CTkFrame(self.data_tab, height=200)
        self.drop_frame.pack(fill="x", padx=20, pady=10)
        
        drop_label = ctk.CTkLabel(self.drop_frame, 
                                text="Перетащите архив с данными Landsat 9 сюда\nили воспользуйтесь кнопками ниже",
                                font=ctk.CTkFont(size=14))
        drop_label.pack(pady=70)
        
        # Кнопки загрузки
        button_frame = ctk.CTkFrame(self.data_tab)
        button_frame.pack(pady=20)
        
        self.load_files_btn = ctk.CTkButton(button_frame, text="📁 Выбрать файлы", 
                                          command=self.load_files, width=150)
        self.load_files_btn.pack(side="left", padx=10)
        
        self.load_archive_btn = ctk.CTkButton(button_frame, text="📦 Загрузить архив", 
                                            command=self.load_archive, width=150)
        self.load_archive_btn.pack(side="left", padx=10)
        
        # Область информации о файлах
        self.info_frame = ctk.CTkScrollableFrame(self.data_tab, height=300)
        self.info_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.info_text = ctk.CTkTextbox(self.info_frame, height=250)
        self.info_text.pack(fill="both", expand=True)
        
        # Кнопка запуска анализа
        self.analyze_btn = ctk.CTkButton(self.data_tab, text="🚀 Запустить анализ", 
                                       command=self.start_analysis, state="disabled",
                                       font=ctk.CTkFont(size=16, weight="bold"))
        self.analyze_btn.pack(pady=20)
    
    def create_detection_tab(self):
        """Создание вкладки настроек детектирования"""
        self.detection_tab = self.notebook.add("Настройки детектирования")
        
        # Заголовок
        title = ctk.CTkLabel(self.detection_tab, text="Параметры детектирования водных объектов", 
                           font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(pady=10)
        
        # Скроллируемая область для настроек
        scroll_frame = ctk.CTkScrollableFrame(self.detection_tab)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Индексы и их пороги
        indices_frame = ctk.CTkFrame(scroll_frame)
        indices_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(indices_frame, text="Водные индексы и пороговые значения:", 
                   font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        
        self.thresholds = {}
        indices_info = [
            ("NDWI", "Нормализованный индекс воды", 0.3),
            ("MNDWI", "Модифицированный NDWI", 0.2),
            ("AWEI_nsh", "Автоматический индекс воды (без теней)", 0.0),
            ("LSWI", "Индекс поверхностной воды по землепользованию", 0.3)
        ]
        
        for idx, (name, desc, default_val) in enumerate(indices_info):
            frame = ctk.CTkFrame(indices_frame)
            frame.pack(fill="x", padx=10, pady=2)
            
            ctk.CTkLabel(frame, text=f"{name}:", width=80).pack(side="left", padx=5)
            ctk.CTkLabel(frame, text=desc, width=300).pack(side="left", padx=5)
            
            self.thresholds[name] = ctk.CTkEntry(frame, width=80)
            self.thresholds[name].pack(side="right", padx=5)
            self.thresholds[name].insert(0, str(default_val))
        
        # Постобработка
        post_frame = ctk.CTkFrame(scroll_frame)
        post_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(post_frame, text="Постобработка:", 
                   font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        
        self.apply_morphology = ctk.CTkCheckBox(post_frame, text="Применить морфологические операции")
        self.apply_morphology.pack(pady=2)
        self.apply_morphology.select()
        
        self.min_object_size = ctk.CTkEntry(post_frame, placeholder_text="Минимальный размер объекта (пикселей)")
        self.min_object_size.pack(pady=2)
        self.min_object_size.insert(0, "100")
        
        # Визуализация
        viz_frame = ctk.CTkFrame(scroll_frame)
        viz_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(viz_frame, text="Настройки визуализации:", 
                   font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        
        self.water_color = ctk.CTkEntry(viz_frame, placeholder_text="Цвет воды (hex, например #FF0000)")
        self.water_color.pack(pady=2)
        self.water_color.insert(0, self.settings.get("water_color", "#FF0000"))
        
        self.contour_thickness = ctk.CTkEntry(viz_frame, placeholder_text="Толщина контура (пиксели)")
        self.contour_thickness.pack(pady=2)
        self.contour_thickness.insert(0, str(self.settings.get("contour_thickness", 2)))
    
    def create_results_tab(self):
        """Создание вкладки результатов"""
        self.results_tab = self.notebook.add("Результаты анализа")
        
        # Панель инструментов
        toolbar = ctk.CTkFrame(self.results_tab, height=50)
        toolbar.pack(fill="x", padx=5, pady=5)
        
        self.export_btn = ctk.CTkButton(toolbar, text="💾 Экспорт", command=self.export_results)
        self.export_btn.pack(side="right", padx=5, pady=5)
        
        # Область для изображений
        self.image_frame = ctk.CTkFrame(self.results_tab)
        self.image_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Создание канваса для изображений
        self.canvas_frame = ctk.CTkFrame(self.image_frame)
        self.canvas_frame.pack(fill="both", expand=True)
        
        # Placeholder для результатов
        self.results_placeholder = ctk.CTkLabel(self.canvas_frame, 
                                              text="Результаты анализа будут отображены здесь после обработки данных",
                                              font=ctk.CTkFont(size=16))
        self.results_placeholder.pack(expand=True)
    
    def create_statistics_tab(self):
        """Создание вкладки статистики"""
        self.stats_tab = self.notebook.add("Статистика")
        
        # Общая статистика
        stats_frame = ctk.CTkFrame(self.stats_tab)
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(stats_frame, text="Общая статистика", 
                   font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        self.stats_text = ctk.CTkTextbox(stats_frame, height=150)
        self.stats_text.pack(fill="x", padx=10, pady=5)
        
        # Таблица объектов
        table_frame = ctk.CTkFrame(self.stats_tab)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkLabel(table_frame, text="Детализация по водным объектам", 
                   font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # Создание Treeview для таблицы
        self.tree_frame = tk.Frame(table_frame)
        self.tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("ID", "Площадь (кв.км)", "Площадь (пикс.)", "Периметр (км)", "Форма")
        self.object_tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings")
        
        for col in columns:
            self.object_tree.heading(col, text=col)
            self.object_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.object_tree.yview)
        self.object_tree.configure(yscrollcommand=scrollbar.set)
        
        self.object_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Привязка события клика по таблице
        self.object_tree.bind("<ButtonRelease-1>", self.on_object_select)
    
    def setup_drag_drop(self):
        """Настройка drag & drop функционality"""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind('<<Drop>>', self.on_drop)
        except ImportError:
            print("tkinterdnd2 не установлен. Drag & drop недоступен.")
    
    def on_drop(self, event):
        """Обработка события drop"""
        files = event.data.split()
        if files:
            file_path = files[0].strip('{}')
            if os.path.isfile(file_path) and file_path.lower().endswith(('.zip', '.rar', '.tar', '.gz')):
                self.process_archive(file_path)
            else:
                messagebox.showwarning("Неподдерживаемый файл", 
                                     "Пожалуйста, перетащите архив (.zip, .rar, .tar)")
    
    def load_files(self):
        """Загрузка отдельных файлов"""
        filetypes = [
            ("TIFF файлы", "*.tif *.TIF"),
            ("Все файлы", "*.*")
        ]
        files = filedialog.askopenfilenames(title="Выберите файлы Landsat 9", filetypes=filetypes)
        if files:
            self.process_files(list(files))
    
    def load_archive(self):
        """Загрузка архива"""
        filetypes = [
            ("Архивы", "*.zip *.rar *.tar *.gz"),
            ("ZIP архивы", "*.zip"),
            ("RAR архивы", "*.rar"),
            ("TAR архивы", "*.tar *.gz")
        ]
        archive_path = filedialog.askopenfilename(title="Выберите архив с данными", filetypes=filetypes)
        if archive_path:
            self.process_archive(archive_path)
    
    def process_archive(self, archive_path):
        """Обработка архива"""
        try:
            # Создание временной директории
            temp_dir = Path("temp_extracted")
            temp_dir.mkdir(exist_ok=True)
            
            # Извлечение архива
            if archive_path.lower().endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            elif archive_path.lower().endswith('.rar'):
                with rarfile.RarFile(archive_path, 'r') as rar_ref:
                    rar_ref.extractall(temp_dir)
            elif archive_path.lower().endswith(('.tar', '.gz')):
                with tarfile.open(archive_path, 'r') as tar_ref:
                    tar_ref.extractall(temp_dir)
            
            # Поиск .tif файлов
            tif_files = list(temp_dir.rglob("*.tif")) + list(temp_dir.rglob("*.TIF"))
            if tif_files:
                self.process_files([str(f) for f in tif_files])
            else:
                messagebox.showwarning("Файлы не найдены", "В архиве не найдены .tif файлы")
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось извлечь архив: {str(e)}")
    
    def process_files(self, files):
        """Обработка списка файлов"""
        self.loaded_data = self.data_processor.load_landsat_data(files)
        if self.loaded_data:
            self.update_file_info()
            self.analyze_btn.configure(state="normal")
            # Включение экспорта в меню
            self.menubar.entryconfig("Файл", state="normal")
        else:
            messagebox.showerror("Ошибка загрузки", "Не удалось загрузить необходимые файлы")
    
    def update_file_info(self):
        """Обновление информации о загруженных файлах"""
        if not self.loaded_data:
            return
            
        info = "✅ Загруженные файлы Landsat 9:\n\n"
        
        # Информация о спектральных каналах
        bands_info = {
            'SR_B2': 'Синий канал (0.45-0.51 мкм)',
            'SR_B3': 'Зеленый канал (0.53-0.59 мкм)', 
            'SR_B4': 'Красный канал (0.64-0.67 мкм)',
            'SR_B5': 'Ближний ИК (0.85-0.88 мкм)',
            'SR_B6': 'SWIR1 (1.57-1.65 мкм)',
            'SR_B7': 'SWIR2 (2.11-2.29 мкм)',
            'QA_PIXEL': 'Канал качества пикселей'
        }
        
        for band, data in self.loaded_data.items():
            if band in bands_info:
                info += f"📊 {band}: {bands_info[band]}\n"
                info += f"    Размер: {data.shape[1]} x {data.shape[0]} пикселей\n"
                info += f"    Тип данных: {data.dtype}\n\n"
        
        # Метаданные
        info += "📋 Метаданные:\n"
        if 'meta' in self.loaded_data:
            meta = self.loaded_data['meta']
            info += f"    Проекция: {meta.get('crs', 'Не указана')}\n"
            info += f"    Разрешение: {meta.get('transform', 'Не указано')}\n"
        
        info += f"\n🎯 Готов к анализу водных объектов!"
        
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", info)
    
    def start_analysis(self):
        """Запуск анализа в отдельном потоке"""
        if not self.loaded_data:
            messagebox.showwarning("Нет данных", "Сначала загрузите данные Landsat 9")
            return
        
        # Блокировка кнопки анализа
        self.analyze_btn.configure(state="disabled", text="🔄 Анализ...")
        
        # Запуск в отдельном потоке
        thread = threading.Thread(target=self.run_analysis, daemon=True)
        thread.start()
    
    def run_analysis(self):
        """Выполнение анализа водных объектов"""
        try:
            # Получение параметров из GUI
            thresholds = {}
            for name, entry in self.thresholds.items():
                try:
                    thresholds[name] = float(entry.get())
                except ValueError:
                    thresholds[name] = 0.0
            
            min_size = int(self.min_object_size.get()) if self.min_object_size.get().isdigit() else 100
            apply_morph = self.apply_morphology.get()
            
            # Выполнение детектирования
            self.water_detector.set_parameters(
                thresholds=thresholds,
                min_object_size=min_size,
                apply_morphology=apply_morph
            )
            
            results = self.water_detector.detect_water(self.loaded_data)
            
            if results:
                self.detection_results = results
                self.water_mask = results['water_mask']
                
                # Обновление GUI в главном потоке
                self.root.after(0, self.display_results)
            else:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось выполнить анализ"))
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка анализа", f"Произошла ошибка: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.analyze_btn.configure(state="normal", text="🚀 Запустить анализ"))
    
    def display_results(self):
        """Отображение результатов анализа"""
        if not self.detection_results:
            return
        
        # Переключение на вкладку результатов
        self.notebook.set("Результаты анализа")
        
        # Очистка предыдущих результатов
        for widget in self.canvas_frame.winfo_children():
            widget.destroy()
        
        # Создание изображений для отображения
        self.create_result_images()
        
        # Обновление статистики
        self.update_statistics()
        
        # Включение кнопки экспорта
        self.export_btn.configure(state="normal")
    
    def create_result_images(self):
        """Создание изображений результатов"""
        try:
            results = self.detection_results
            
            # Создание сетки для изображений 2x2
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            fig.suptitle('Результаты детектирования водных объектов', fontsize=16, fontweight='bold')
            
            # 1. Исходный снимок (Natural Color)
            if all(band in self.loaded_data for band in ['SR_B4', 'SR_B3', 'SR_B2']):
                rgb = np.stack([
                    self.loaded_data['SR_B4'],  # Red
                    self.loaded_data['SR_B3'],  # Green  
                    self.loaded_data['SR_B2']   # Blue
                ], axis=-1)
                
                # Нормализация для отображения
                rgb_norm = np.clip(rgb / np.percentile(rgb, 98), 0, 1)
                axes[0,0].imshow(rgb_norm)
                axes[0,0].set_title('Исходный снимок (Natural Color)')
                axes[0,0].axis('off')
            
            # 2. Бинарная маска воды
            axes[0,1].imshow(results['water_mask'], cmap='Blues')
            axes[0,1].set_title('Бинарная маска воды')
            axes[0,1].axis('off')
            
            # 3. Наложение маски
            if 'overlay_image' in results:
                axes[1,0].imshow(results['overlay_image'])
                axes[1,0].set_title('Наложение маски на исходник')
                axes[1,0].axis('off')
            
            # 4. Контуры водных объектов
            if 'contour_image' in results:
                axes[1,1].imshow(results['contour_image'])
                axes[1,1].set_title('Контуры водных объектов')
                axes[1,1].axis('off')
            
            plt.tight_layout()
            
            # Встраивание matplotlib в tkinter
            canvas = FigureCanvasTkAgg(fig, self.canvas_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
        except Exception as e:
            error_label = ctk.CTkLabel(self.canvas_frame, 
                                     text=f"Ошибка отображения результатов: {str(e)}")
            error_label.pack(expand=True)
    
    def update_statistics(self):
        """Обновление статистики"""
        if not self.detection_results:
            return
            
        results = self.detection_results
        
        # Общая статистика
        stats_text = f"""
🌊 ОБЩАЯ СТАТИСТИКА ВОДНЫХ ОБЪЕКТОВ

📊 Основные показатели:
• Общая площадь воды: {results['total_water_area_km2']:.2f} кв.км
• Общая площадь воды: {results['total_water_area_pixels']:,} пикселей
• Общий периметр: {results['total_perimeter_km']:.2f} км
• Процент водной поверхности: {results['water_percentage']:.2f}%

🎯 Детализация:
• Количество объектов: {results['object_count']}
• Крупнейший объект: {results['largest_object_area']:.2f} кв.км
• Средний размер объекта: {results['average_object_size']:.2f} кв.км

⚙️ Параметры анализа:
• Использованные индексы: NDWI, MNDWI, AWEI, LSWI
• Метод: Ансамбль с голосованием
• Постобработка: {"Включена" if self.apply_morphology.get() else "Отключена"}
"""
        
        self.stats_text.delete("1.0", "end")
        self.stats_text.insert("1.0", stats_text)
        
        # Обновление таблицы объектов
        # Очистка существующих данных
        for item in self.object_tree.get_children():
            self.object_tree.delete(item)
        
        # Заполнение таблицы
        if 'objects_data' in results:
            for i, obj_data in enumerate(results['objects_data']):
                self.object_tree.insert("", "end", values=(
                    i + 1,
                    f"{obj_data['area_km2']:.3f}",
                    f"{obj_data['area_pixels']:,}",
                    f"{obj_data['perimeter_km']:.3f}",
                    obj_data.get('shape_factor', 'N/A')
                ))
    
    def on_object_select(self, event):
        """Обработка выбора объекта в таблице"""
        selection = self.object_tree.selection()
        if selection:
            item = self.object_tree.item(selection[0])
            obj_id = int(item['values'][0]) - 1
            # Здесь можно добавить подсветку объекта на изображении
            print(f"Выбран объект #{obj_id}")
    
    def export_results(self):
        """Экспорт результатов"""
        if not self.detection_results:
            messagebox.showwarning("Нет результатов", "Сначала выполните анализ")
            return
        
        # Выбор папки для сохранения
        export_dir = filedialog.askdirectory(title="Выберите папку для экспорта")
        if not export_dir:
            return
        
        try:
            # Экспорт через ImageExporter
            success = self.image_exporter.export_results(
                self.detection_results, 
                self.loaded_data,
                export_dir
            )
            
            # Дополнительно экспортируем в Excel
            if success:
                # Создаем путь для Excel файла
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                excel_path = os.path.join(export_dir, f"Статистика_водных_объектов_{timestamp}.xlsx")
                
                # Экспортируем в Excel
                excel_success = self.image_exporter.export_to_excel(self.detection_results, excel_path)
                
                if excel_success:
                    messagebox.showinfo("Экспорт завершен", 
                                    f"Результаты сохранены в папку:\n{export_dir}\n\n"
                                    f"Excel файл со статистикой:\n{excel_path}")
                else:
                    messagebox.showwarning("Экспорт завершен с ограничениями", 
                                        f"Основные результаты сохранены, но Excel файл не создан.\n\n"
                                        f"Папка с результатами:\n{export_dir}")
            else:
                messagebox.showerror("Ошибка экспорта", "Не удалось экспортировать результаты")
                
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", f"Произошла ошибка: {str(e)}")
    
    def open_settings_window(self):
        """Открытие окна настроек"""
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("Настройки детектирования")
        settings_window.geometry("600x500")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # Центрирование окна
        settings_window.update_idletasks()
        x = (settings_window.winfo_screenwidth() - settings_window.winfo_width()) // 2
        y = (settings_window.winfo_screenheight() - settings_window.winfo_height()) // 2
        settings_window.geometry(f"+{x}+{y}")
        
        # Содержимое окна настроек
        notebook = ctk.CTkTabview(settings_window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Вкладка алгоритма
        algo_tab = notebook.add("Алгоритм")
        
        ctk.CTkLabel(algo_tab, text="Настройки алгоритма детектирования", 
                   font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # Дополнительные настройки можно добавить здесь
        
        # Вкладка визуализации  
        viz_tab = notebook.add("Визуализация")
        
        ctk.CTkLabel(viz_tab, text="Настройки отображения", 
                   font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # Цвет воды
        color_frame = ctk.CTkFrame(viz_tab)
        color_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(color_frame, text="Цвет выделения воды:").pack(side="left", padx=5)
        color_entry = ctk.CTkEntry(color_frame, width=100)
        color_entry.pack(side="right", padx=5)
        color_entry.insert(0, self.settings.get("water_color", "#FF0000"))
        
        # Кнопки
        button_frame = ctk.CTkFrame(settings_window)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        def save_and_close():
            # Сохранение настроек
            self.settings["water_color"] = color_entry.get()
            self.save_settings()
            settings_window.destroy()
        
        ctk.CTkButton(button_frame, text="Сохранить", command=save_and_close).pack(side="right", padx=5)
        ctk.CTkButton(button_frame, text="Отмена", command=settings_window.destroy).pack(side="right", padx=5)
    
    def change_theme(self, theme):
        """Изменение темы приложения"""
        ctk.set_appearance_mode(theme)
        self.settings["theme"] = theme
        self.save_settings()
    
    def show_about(self):
        """Показать информацию о программе"""
        about_text = """
GeoScanPro v1.0
Профессиональное приложение для детектирования водных объектов 
на спутниковых снимках Landsat 9

Возможности:
• Загрузка и обработка данных Landsat 9 Level-2
• Детектирование воды с использованием ансамбля индексов
• Точная статистика по площадям и периметрам
• Экспорт результатов в различных форматах
• Современный адаптивный интерфейс

Используемые алгоритмы:
- NDWI (Normalized Difference Water Index)  
- MNDWI (Modified NDWI)
- AWEI (Automated Water Extraction Index)
- LSWI (Land Surface Water Index)

Разработано для ихтиологов, экологов и специалистов по ДЗЗ
"""
        messagebox.showinfo("О программе", about_text)