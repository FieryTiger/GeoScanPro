import os
import sys
import shutil
import winreg
import threading
import time
import subprocess
from tkinter import Tk, filedialog, messagebox, Checkbutton, IntVar, Button, Label
from tkinter import ttk

class Installer:
    def __init__(self):
        self.root = Tk()
        self.root.title("Установка GeoScanPro")
        self.root.geometry("600x650")
        self.root.resizable(False, False)
        
        # Центрирование окна
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 600) // 2
        y = (screen_height - 650) // 2
        self.root.geometry(f"600x650+{x}+{y}")
        
        # Переменные
        self.install_path = os.path.join(os.environ.get('LOCALAPPDATA', 'C:\\'), 'GeoScanPro')
        self.create_desktop_shortcut = IntVar(value=1)
        self.create_start_menu_shortcut = IntVar(value=1)
        self.run_after_install = IntVar(value=1)
        self.total_files = 0
        self.copied_files = 0
        self.install_in_progress = False
        self.cancel_requested = False
        
        # Проверяем наличие собранного приложения
        self.app_exe = os.path.abspath("dist/GeoScanPro.exe")
        self.resources_dir = os.path.abspath("resources")
        
        if not os.path.exists(self.app_exe):
            messagebox.showerror("Ошибка", 
                               "Собранное приложение не найдено!\n\n"
                               "Ожидаемый путь: dist/GeoScanPro.exe\n"
                               "Убедитесь, что вы выполнили сборку через PyInstaller.")
            sys.exit(1)
        
        if not os.path.exists(self.resources_dir):
            messagebox.showerror("Ошибка", 
                               "Папка ресурсов не найдена!\n\n"
                               "Ожидаемый путь: resources/")
            sys.exit(1)
        
        self.create_widgets()

    def create_widgets(self):
        # Заголовок
        header_frame = ttk.Frame(self.root)
        header_frame.pack(pady=20, padx=20, fill="x")
        
        Label(header_frame, text="Установка GeoScanPro", 
              font=("Arial", 20, "bold"), foreground="#2c3e50").pack()
        Label(header_frame, text="Профессиональное приложение для детектирования водных объектов", 
              font=("Arial", 11), foreground="#7f8c8d").pack(pady=(5, 0))
        
        # Выбор пути установки
        path_frame = ttk.LabelFrame(self.root, text="Выбор папки установки", padding=15)
        path_frame.pack(pady=10, padx=20, fill="x")
        
        Label(path_frame, text="Программа будет установлена в следующую папку:", 
              font=("Arial", 10)).pack(anchor="w")
        
        path_entry_frame = ttk.Frame(path_frame)
        path_entry_frame.pack(fill="x", pady=10)
        
        self.path_entry = ttk.Entry(path_entry_frame, font=("Arial", 10))
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.path_entry.insert(0, self.install_path)
        
        ttk.Button(path_entry_frame, text="Обзор...", command=self.browse_path, 
                  width=10).pack(side="right", padx=(10, 0))
        
        # Информация о диске
        self.disk_info_label = Label(path_frame, text="", font=("Arial", 9), foreground="#7f8c8d")
        self.disk_info_label.pack(anchor="w", pady=(5, 0))
        self.update_disk_info()
        
        # Опции установки
        options_frame = ttk.LabelFrame(self.root, text="Опции установки", padding=15)
        options_frame.pack(pady=10, padx=20, fill="x")
        
        Checkbutton(options_frame, text="Создать ярлык на рабочем столе", 
                   variable=self.create_desktop_shortcut, font=("Arial", 10),
                   anchor="w").pack(fill="x", pady=5)
        Checkbutton(options_frame, text="Создать ярлык в меню Пуск", 
                   variable=self.create_start_menu_shortcut, font=("Arial", 10),
                   anchor="w").pack(fill="x", pady=5)
        Checkbutton(options_frame, text="Запустить программу после установки", 
                   variable=self.run_after_install, font=("Arial", 10),
                   anchor="w").pack(fill="x", pady=5)
        
        # Область прогресса (изначально скрыта)
        self.progress_frame = ttk.LabelFrame(self.root, text="Ход установки", padding=15)
        
        # Текущее действие
        self.current_action_label = Label(self.progress_frame, text="Готов к установке...", 
                                         font=("Arial", 11, "bold"))
        self.current_action_label.pack(anchor="w", pady=(0, 10))
        
        # Прогресс-бар
        self.progress_bar = ttk.Progressbar(self.progress_frame, length=500, mode='determinate')
        self.progress_bar.pack(fill="x", pady=5)
        
        # Процент выполнения
        progress_frame_inner = ttk.Frame(self.progress_frame)
        progress_frame_inner.pack(fill="x", pady=5)
        
        self.progress_percent_label = Label(progress_frame_inner, text="0%", 
                                           font=("Arial", 12, "bold"))
        self.progress_percent_label.pack(side="left")
        
        # Оставшееся время
        self.time_remaining_label = Label(progress_frame_inner, text="", 
                                         font=("Arial", 9), foreground="#7f8c8d")
        self.time_remaining_label.pack(side="right")
        
        # Детали процесса
        self.progress_details_label = Label(self.progress_frame, text="", 
                                           font=("Arial", 9), foreground="#7f8c8d",
                                           wraplength=500, justify="left")
        self.progress_details_label.pack(anchor="w", pady=(10, 0))
        
        # Фрейм для кнопок
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=20)
        
        # Кнопка установки
        self.install_button = ttk.Button(button_frame, text="Установить", 
                                        command=self.start_installation, width=20)
        self.install_button.pack(side="left", padx=5)
        
        # Кнопка отмены
        self.cancel_button = ttk.Button(button_frame, text="Отмена", 
                                       command=self.cancel_installation, width=20)
        self.cancel_button.pack(side="left", padx=5)
        
        self.start_time = None

    def update_disk_info(self):
        try:
            path = self.path_entry.get()
            if not path: return
            drive = os.path.splitdrive(path)[0] + "\\"
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(drive), None, ctypes.byref(total_bytes), ctypes.byref(free_bytes)
            )
            free_gb = free_bytes.value / (1024**3)
            total_gb = total_bytes.value / (1024**3)
            used_percent = ((total_bytes.value - free_bytes.value) / total_bytes.value) * 100
            self.disk_info_label.config(
                text=f"Диск {drive}: {free_gb:.1f} ГБ свободно из {total_gb:.1f} ГБ ({used_percent:.1f}% занято)"
            )
        except Exception as e:
            self.disk_info_label.config(text="Не удалось получить информацию о диске")

    def browse_path(self):
        path = filedialog.askdirectory(
            title="Выберите папку для установки",
            initialdir=os.path.dirname(self.install_path) if os.path.exists(os.path.dirname(self.install_path)) else "C:\\"
        )
        if path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, path)
            self.install_path = path
            self.update_disk_info()

    def start_installation(self):
        if self.install_in_progress: return
        self.install_path = self.path_entry.get().strip()
        if not self.install_path:
            messagebox.showerror("Ошибка", "Пожалуйста, укажите путь установки")
            return
        try:
            test_file = os.path.join(self.install_path, "test_write.tmp")
            with open(test_file, 'w') as f: f.write("test")
            os.remove(test_file)
        except PermissionError:
            fallback = os.path.join(os.environ.get('LOCALAPPDATA', 'C:\\'), 'GeoScanPro')
            if not messagebox.askyesno("Нет прав доступа", 
                                     f"У вас нет прав на запись в папку:\n{self.install_path}\n\n"
                                     f"Хотите установить в папку пользователя?\n{fallback}"):
                return
            self.install_path = fallback
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, self.install_path)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Недопустимый путь: {str(e)}")
            return

        self.progress_frame.pack(pady=15, padx=20, fill="x", before=self.install_button.master)
        self.install_button.config(state="disabled", text="Установка...")
        self.cancel_button.config(state="normal")
        self.path_entry.config(state="disabled")
        self.install_in_progress = True
        self.cancel_requested = False
        self.start_time = time.time()

        thread = threading.Thread(target=self.install, daemon=True)
        thread.start()
        self.root.after(100, self.update_progress_ui)

    def update_progress_ui(self):
        if self.install_in_progress and not self.cancel_requested:
            if self.total_files > 0:
                progress = (self.copied_files / self.total_files) * 100
                self.progress_bar['value'] = progress
                self.progress_percent_label.config(text=f"{progress:.1f}%")
                if self.copied_files > 0 and progress < 100:
                    elapsed = time.time() - self.start_time
                    estimated_total = elapsed / (progress / 100)
                    remaining = estimated_total - elapsed
                    if remaining > 60:
                        self.time_remaining_label.config(text=f"Осталось: {int(remaining/60)} мин {int(remaining%60)} сек")
                    else:
                        self.time_remaining_label.config(text=f"Осталось: {int(remaining)} сек")
                elif progress >= 100:
                    self.time_remaining_label.config(text="Завершено!")
            self.root.after(100, self.update_progress_ui)

    def update_progress(self, action, details, current=0, total=0):
        if not self.cancel_requested:
            self.current_action_label.config(text=action)
            self.progress_details_label.config(text=details)
            if total > 0: self.total_files = total
            if current >= 0: self.copied_files = current

    def install(self):
        try:
            self.update_progress("Подготовка...", "Проверка и создание директории")
            os.makedirs(self.install_path, exist_ok=True)
            time.sleep(0.2)

            # Файлы для копирования: exe + папка resources
            files_to_copy = [
                ("GeoScanPro.exe", self.app_exe),
            ]
            # Добавляем все файлы из resources/
            for root_dir, _, files in os.walk(self.resources_dir):
                for f in files:
                    src = os.path.join(root_dir, f)
                    rel = os.path.relpath(src, self.resources_dir)
                    dst_rel = os.path.join("resources", rel)
                    files_to_copy.append((dst_rel, src))

            total = len(files_to_copy)
            self.total_files = total
            self.update_progress("Копирование файлов...", f"Найдено {total} элементов", 0, total)

            for i, (rel_path, src) in enumerate(files_to_copy):
                if self.cancel_requested: return
                dst = os.path.join(self.install_path, rel_path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                self.copied_files = i + 1
                if (i + 1) % 5 == 0 or i + 1 == total:
                    self.update_progress(
                        "Копирование файлов...",
                        f"Скопировано {i + 1} из {total}",
                        i + 1, total
                    )
                if os.path.getsize(src) > 10 * 1024 * 1024:  # >10 MB
                    time.sleep(0.01)

            exe_path = os.path.join(self.install_path, "GeoScanPro.exe")

            if self.create_desktop_shortcut.get() and not self.cancel_requested:
                self.update_progress("Ярлыки", "Создание ярлыка на рабочем столе")
                self.create_shortcut(exe_path, "desktop")

            if self.create_start_menu_shortcut.get() and not self.cancel_requested:
                self.update_progress("Ярлыки", "Создание ярлыка в меню Пуск")
                self.create_shortcut(exe_path, "startmenu")

            if not self.cancel_requested:
                self.update_progress("Реестр", "Добавление в список программ")
                self.add_uninstall_info()

            if not self.cancel_requested:
                self.update_progress("Завершение", "Установка успешно завершена!", total, total)
                time.sleep(1)
                self.root.after(0, self.installation_complete)

        except Exception as e:
            print(f"Ошибка установки: {e}")
            self.update_progress("Ошибка", f"Произошла ошибка: {str(e)}")
            time.sleep(2)
            self.root.after(0, self.installation_error)

    def installation_complete(self):
        self.install_in_progress = False
        self.progress_bar['value'] = 100
        self.progress_percent_label.config(text="100%")
        self.time_remaining_label.config(text="Завершено!")
        messagebox.showinfo("Установка завершена", 
                          f"GeoScanPro успешно установлен в:\n{self.install_path}")
        if self.run_after_install.get():
            exe_path = os.path.join(self.install_path, "GeoScanPro.exe")
            try:
                subprocess.Popen([exe_path], cwd=self.install_path)
            except Exception as e:
                print(f"Ошибка запуска: {e}")
        self.root.quit()

    def installation_error(self):
        self.install_in_progress = False
        self.install_button.config(state="normal", text="Установить")
        self.cancel_button.config(state="normal")
        self.path_entry.config(state="normal")
        self.progress_frame.pack_forget()

    def cancel_installation(self):
        if self.install_in_progress:
            if messagebox.askyesno("Отмена установки", 
                                 "Установка в процессе. Отменить?\nВсе файлы будут удалены."):
                self.cancel_requested = True
                self.install_in_progress = False
                if os.path.exists(self.install_path):
                    shutil.rmtree(self.install_path, ignore_errors=True)
                self.install_button.config(state="normal", text="Установить")
                self.cancel_button.config(state="normal")
                self.path_entry.config(state="normal")
                self.progress_frame.pack_forget()
        else:
            self.root.quit()

    def create_shortcut(self, target_path, location="desktop"):
        try:
            try:
                import winshell
                if location == "desktop":
                    shortcut_path = os.path.join(winshell.desktop(), "GeoScanPro.lnk")
                else:
                    start_menu = winshell.start_menu()
                    programs_dir = os.path.join(start_menu, "Programs", "GeoScanPro")
                    os.makedirs(programs_dir, exist_ok=True)
                    shortcut_path = os.path.join(programs_dir, "GeoScanPro.lnk")
                with winshell.shortcut(shortcut_path) as link:
                    link.path = target_path
                    link.working_directory = os.path.dirname(target_path)
                    link.description = "GeoScanPro - Детектирование водных объектов"
                    icon = os.path.join(os.path.dirname(target_path), "resources", "GeoScanPro.ico")
                    if os.path.exists(icon):
                        link.icon_location = (icon, 0)
                    else:
                        link.icon_location = (target_path, 0)
                return
            except ImportError:
                pass

            # Fallback: VBScript
            if location == "desktop":
                shortcut_path = os.path.join(os.path.expanduser("~"), "Desktop", "GeoScanPro.lnk")
            else:
                start_menu = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "GeoScanPro")
                os.makedirs(start_menu, exist_ok=True)
                shortcut_path = os.path.join(start_menu, "GeoScanPro.lnk")

            vbs = os.path.join(os.environ["TEMP"], "mklink.vbs")
            icon_path = os.path.join(os.path.dirname(target_path), "resources", "GeoScanPro.ico")
            icon_arg = f'"{icon_path}"' if os.path.exists(icon_path) else '""'
            with open(vbs, "w", encoding="utf-8") as f:
                f.write(f'''
Set sh = CreateObject("WScript.Shell")
Set shortcut = sh.CreateShortcut("{shortcut_path}")
shortcut.TargetPath = "{target_path}"
shortcut.WorkingDirectory = "{os.path.dirname(target_path)}"
shortcut.Description = "GeoScanPro - Детектирование водных объектов"
shortcut.IconLocation = {icon_arg}
shortcut.Save
''')
            subprocess.run(['cscript', '//nologo', vbs], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.remove(vbs)
        except Exception as e:
            print(f"Не удалось создать ярлык: {e}")

    def add_uninstall_info(self):
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\GeoScanPro"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "GeoScanPro")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "1.0.0")
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "GeoScanPro Team")
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, self.install_path)
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, 
                            f'"{sys.executable}" "{os.path.abspath(__file__)}" --uninstall')
            winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, 
                            f'"{sys.executable}" "{os.path.abspath(__file__)}" --uninstall --quiet')
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Ошибка записи в реестр: {e}")

    def run(self):
        self.root.mainloop()

def uninstall(quiet=False):
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\GeoScanPro"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
            install_loc = winreg.QueryValueEx(key, "InstallLocation")[0]
            winreg.CloseKey(key)
        except:
            if not quiet:
                messagebox.showerror("Ошибка", "GeoScanPro не найден в системе.")
            return

        if not quiet:
            if not messagebox.askyesno("Удаление", f"Удалить GeoScanPro?\n\n{install_loc}"):
                return

        shutil.rmtree(install_loc, ignore_errors=True)

        # Удалить ярлыки
        desktop_lnk = os.path.join(os.path.expanduser("~"), "Desktop", "GeoScanPro.lnk")
        start_lnk = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "GeoScanPro", "GeoScanPro.lnk")
        start_dir = os.path.dirname(start_lnk)
        for p in [desktop_lnk, start_lnk]:
            if os.path.exists(p):
                os.remove(p)
        if os.path.exists(start_dir) and not os.listdir(start_dir):
            os.rmdir(start_dir)

        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        except:
            pass

        if not quiet:
            messagebox.showinfo("Готово", "GeoScanPro удалён.")
    except Exception as e:
        if not quiet:
            messagebox.showerror("Ошибка", str(e))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if "--uninstall" in sys.argv:
            uninstall("--quiet" in sys.argv)
        else:
            print("Неизвестный аргумент. Используйте --uninstall или без аргументов.")
    else:
        app = Installer()
        app.run()