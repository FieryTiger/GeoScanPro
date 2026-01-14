# main.py
#!/usr/bin/env python3
"""
GeoScanPro - Приложение для детектирования водных объектов на спутниковых снимках Landsat 9
Главный файл приложения
"""

import sys
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from gui import GeoScanProGUI
from tkinterdnd2 import TkinterDnD

# Настройка customtkinter
ctk.set_appearance_mode("system")  # Режимы: "system", "dark", "light"
ctk.set_default_color_theme("blue")  # Темы: "blue", "green", "dark-blue"

class GeoScanProApp:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.setup_main_window()
        self.gui = GeoScanProGUI(self.root)
    
    def setup_main_window(self):
        """Настройка главного окна приложения"""
        self.root.title("GeoScanPro - Детектирование водных объектов")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)
        
        # Установка иконки приложения
        icon_path = Path("resources/GeoScanPro.png")
        if icon_path.exists():
            try:
                # Для Windows
                self.root.iconbitmap(str(icon_path))
            except:
                # Альтернативный способ для других ОС
                try:
                    photo = tk.PhotoImage(file=str(icon_path))
                    self.root.iconphoto(False, photo)
                except Exception as e:
                    print(f"Не удалось загрузить иконку: {e}")
        
        # Центрирование окна на экране
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")
    
    def run(self):
        """Запуск приложения"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.close_app()
        except Exception as e:
            messagebox.showerror("Критическая ошибка", f"Произошла критическая ошибка:\n{str(e)}")
            self.close_app()
    
    def close_app(self):
        """Корректное закрытие приложения"""
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
        sys.exit(0)

def main():
    """Главная функция"""
    # Проверка зависимостей
    try:
        import numpy as np
        import cv2
        import rasterio
        import matplotlib.pyplot as plt
        import pandas as pd
        from PIL import Image, ImageTk
        from scipy import ndimage
        from skimage import morphology
    except ImportError as e:
        error_msg = f"""
Не удалось импортировать необходимые библиотеки:
{str(e)}

Пожалуйста, установите недостающие зависимости:
pip install numpy opencv-python rasterio matplotlib pandas pillow scipy scikit-image customtkinter
"""
        if 'tkinter' in sys.modules:
            messagebox.showerror("Ошибка зависимостей", error_msg)
        else:
            print(error_msg)
        sys.exit(1)
    
    # Создание необходимых директорий
    Path("resources").mkdir(exist_ok=True)
    Path("resources/icons").mkdir(exist_ok=True)
    Path("resources/styles").mkdir(exist_ok=True)
    Path("exports").mkdir(exist_ok=True)
    
    # Запуск приложения
    app = GeoScanProApp()
    app.run()

if __name__ == "__main__":
    main()