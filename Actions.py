import os
import ftplib
import shutil
import socket
import tempfile
from datetime import datetime
import xlrd
import xlwt
from xlrd import xldate_as_datetime
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QInputDialog


class FTPUploadThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    update_needed = pyqtSignal()

    def __init__(self, main_window, local_filepath, server_filepath):
        super().__init__()
        self.main_window = main_window
        self.local_filepath = local_filepath
        self.server_filepath = server_filepath
        self.ftp = None
        self.retries = 3

    def run(self):
        for attempt in range(self.retries):
            try:
                if not self.main_window.ftp:
                    self.main_window.connect_to_ftp()

                self.ftp = self.main_window.ftp
                if not self.ftp:
                    continue

                # Устанавливаем таймаут на сокете (если он существует)
                if hasattr(self.ftp, 'sock') and self.ftp.sock:
                    self.ftp.sock.settimeout(15)  # 15 секунд таймаут

                with open(self.local_filepath, 'rb') as f:
                    # Убираем параметр timeout из storbinary
                    self.ftp.storbinary(f'STOR {self.server_filepath}', f)

                self.finished.emit("Файл успешно загружен")
                self.update_needed.emit()
                return

            except (socket.timeout, ConnectionResetError):
                if attempt < self.retries - 1:
                    self.main_window.ftp_disconnect()
                    self.main_window.connect_to_ftp()
                continue

            except Exception as e:
                self.error.emit(f"Ошибка: {str(e)}")
                return

        self.error.emit("Не удалось загрузить файл после нескольких попыток")
        self.update_needed.emit()


class Actions:

    @staticmethod
    def Download(main_window, serv_location):
        """Скачивает файл с FTP-сервера."""
        def download_action():
            filename = serv_location.text()
            Logger.loging(main_window, "Скачивание", f"Файл: {filename}")

            if not filename:
                QMessageBox.warning(main_window, "Внимание", "Не выбран файл для скачивания.")
                return

            filepath_on_server = filename  # Используем уже полный путь
            file_name = os.path.basename(filename)

            if not file_name:
                QMessageBox.warning(main_window, "Внимание", "Не удалось получить имя файла.")
                return

            local_filepath = os.path.join(main_window.local_directory, file_name)

            try:
                with open(local_filepath, 'wb') as local_file:
                    main_window.ftp.retrbinary(f'RETR {filepath_on_server}', local_file.write)
                QMessageBox.information(main_window, "Успех",
                                          f"Файл '{file_name}' успешно скачан в '{main_window.local_directory}'.")
                main_window.update_server_tree()

            except ftplib.error_perm as e:
                QMessageBox.critical(main_window, 'Ошибка скачивания', f'Ошибка доступа к файлу: {str(e)}')
            except ftplib.error_temp as e:
                QMessageBox.critical(main_window, 'Ошибка скачивания',
                                       f'Временная ошибка при скачивании файла: {str(e)}')
            except ftplib.error_proto as e:
                QMessageBox.critical(main_window, 'Ошибка скачивания',
                                       f'Протокольная ошибка при скачивании файла: {str(e)}')
            except Exception as e:
                QMessageBox.critical(main_window, 'Ошибка', f'Не удалось скачать файл: {str(e)}')

        return download_action

    @staticmethod
    def Record(main_window, local_location, server_location):
        """Записывает файл на FTP-сервер."""
        def recording():
            local_filepath = local_location.text()
            server_filepath = server_location.text()

            if not local_filepath:
                QMessageBox.warning(main_window, "Внимание", "Не выбран локальный файл для записи.")
                return

            default_filename = os.path.basename(local_filepath)

            file_name, ok = QInputDialog.getText(main_window, "Имя файла",
                                                   "Введите имя файла для сохранения на сервере:",
                                                   text=default_filename)
            if not ok or not file_name:
                return

            Logger.loging(main_window, "Загрузка на сервер",
                          f"Локальный файл. {file_name} загружен в {server_filepath}")

            server_filepath = os.path.join(main_window.current_directory, file_name).replace('\\', '/')

            # Создаем и настраиваем поток
            upload_thread = FTPUploadThread(main_window, local_filepath, server_filepath)
            main_window.setup_upload_thread(upload_thread)
            upload_thread.start()

        return recording

    @staticmethod
    def Delete_Serv(main_window, serv_location, parent):
        """Удаляет файл с FTP-сервера."""
        def delete_action_serv():
            filename = serv_location.text()
            Logger.loging(main_window, "Удаление с сервера", f"Файл: {filename}")

            if not filename:
                QMessageBox.warning(main_window, "Внимание", "Не выбран файл для удаления на сервере.")
                return

            filepath_on_server = filename  # Используем полный путь

            try:
                main_window.ftp.delete(filepath_on_server)
                QMessageBox.information(main_window, "Успех",
                                          f"Файл '{os.path.basename(filepath_on_server)}' успешно удален с сервера.")
                main_window.update_server_tree()

            except ftplib.error_perm as e:
                QMessageBox.critical(main_window, 'Ошибка удаления', f'Ошибка доступа при удалении файла: {str(e)}')
            except ftplib.error_temp as e:
                QMessageBox.critical(main_window, 'Ошибка удаления', f'Временная ошибка при удалении файла: {str(e)}')
            except ftplib.error_proto as e:
                QMessageBox.critical(main_window, 'Ошибка удаления',
                                       f'Протокольная ошибка при удалении файла: {str(e)}')
            except Exception as e:
                QMessageBox.critical(main_window, 'Ошибка', f'Не удалось удалить файл: {str(e)}')

        return delete_action_serv

    @staticmethod
    def Delete_Loc(main_window, local_location, file_tree, file_model):
        """Удаляет файл с локального компьютера."""
        def delete_action_loc():
            filepath_on_local = local_location.text()
            Logger.loging(main_window, "Удаление локального файла", f"Путь: {os.path.basename(filepath_on_local)}")

            if not filepath_on_local:
                QMessageBox.warning(main_window, "Внимание", 'Не выбран путь для удаления на локальной машине.')
                return

            if not os.path.exists(filepath_on_local):
                QMessageBox.warning(main_window, 'Ошибка', f"Файл не существует: {filepath_on_local}")
                return

            try:
                if os.path.isfile(filepath_on_local):
                    os.remove(filepath_on_local)
                    QMessageBox.information(main_window, "Успех",
                                              f"Файл '{os.path.basename(filepath_on_local)}', успешно удалён с локальной машины.")
                elif os.path.isdir(filepath_on_local):
                    shutil.rmtree(filepath_on_local)
                    QMessageBox.information(main_window, 'Успех',
                                              f"Директория '{filepath_on_local}' успешно удалёна с локальной машины.")
                else:
                    QMessageBox.warning(main_window, "Ошибка", "Неизвестный тип объекта для удаления.")
                    return

                file_tree.setRootIndex(file_model.setRootPath(os.path.dirname(filepath_on_local)))

            except PermissionError as e:
                QMessageBox.critical(main_window, 'Ошибка прав', f'Нет прав для удаления: {str(e)}')
            except OSError as e:
                QMessageBox.critical(main_window, 'Ошибка системы', f'Ошибка при удалении: {str(e)}')
            except Exception as e:
                QMessageBox.critical(main_window, 'Ошибка', f'Не удалось удалить: {str(e)}')

        return delete_action_loc


class Logger:
    """Класс для логирования действий пользователей и администраторов."""
    @staticmethod
    def loging(ftp_client, action, details):
        """Основной метод логирования."""
        try:
            if not ftp_client.ftp:
                return

            if ftp_client.is_admin:
                Logger._admin_logging(ftp_client, action, details)
            else:
                Logger._user_logging(ftp_client, action, details)

        except Exception as e:
            print(f"Ошибка логирования: {str(e)}")

    @staticmethod
    def _user_logging(ftp_client, action, details):
        """Логирование для обычных пользователей."""
        log_filename = ".user_logs.xls"
        log_path = f"/{log_filename}"

        # Создаем уникальное имя временного файла
        temp_dir = tempfile.gettempdir()
        temp_filename = os.path.join(temp_dir, f"ftp_userlog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls")

        try:
            # Пытаемся скачать существующий файл логов
            try:
                with open(temp_filename, 'wb') as tmp_file:
                    ftp_client.ftp.retrbinary(f'RETR {log_path}', tmp_file.write)
            except ftplib.error_perm:
                pass  # Файла нет, создадим новый

            # Читаем существующие записи
            existing_entries = []
            if os.path.exists(temp_filename):
                try:
                    rb = xlrd.open_workbook(temp_filename, formatting_info=True)
                    sheet = rb.sheet_by_index(0)

                    for row in range(1, sheet.nrows):
                        try:
                            # Пробуем преобразовать дату из разных форматов
                            cell_value = sheet.cell_value(row, 0)
                            if sheet.cell_type(row, 0) == xlrd.XL_CELL_DATE:  # Cell type is a date
                                dt = xldate_as_datetime(cell_value, rb.datemode)
                            else:
                                dt = datetime.strptime(str(cell_value), "%Y-%m-%d %H:%M:%S")

                            existing_entries.append({
                                "datetime": dt,
                                "user": sheet.cell_value(row, 1),  # Получаем имя пользователя
                                "action": sheet.cell_value(row, 2),
                                "details": sheet.cell_value(row, 3)
                            })
                        except Exception as e:
                            print(f"Ошибка при чтении строки {row}: {e}")
                            continue

                except Exception as e:
                    print(f"Ошибка при открытии или чтении файла: {e}")
                    pass

            # Добавляем новую запись
            existing_entries.append({
                "datetime": datetime.now(),
                "user": ftp_client.user,  # Добавляем имя пользователя
                "action": action,
                "details": details
            })

            # Сортируем записи
            existing_entries.sort(key=lambda x: x["datetime"])

            # Создаем новый файл
            wb = xlwt.Workbook()
            ws = wb.add_sheet("Logs")

            # Заголовки
            headers = ["Дата и время", "Пользователь", "Действие", "Детали"]
            for col, header in enumerate(headers):
                ws.write(0, col, header)

            # Данные
            for row, entry in enumerate(existing_entries, 1):
                ws.write(row, 0, entry["datetime"].strftime("%Y-%m-%d %H:%M:%S"))
                ws.write(row, 1, entry["user"])  # Записываем имя пользователя
                ws.write(row, 2, entry["action"])
                ws.write(row, 3, entry["details"])

            # Сохраняем во временный файл
            try:
                wb.save(temp_filename)
            except Exception as e:
                print(f"Ошибка при сохранении файла: {e}")
                return


            # Загружаем на сервер
            try:
                with open(temp_filename, 'rb') as f:
                    ftp_client.ftp.storbinary(f'STOR {log_path}', f)
            except Exception as e:
                print(f"Ошибка при загрузке файла на сервер: {e}")

        except Exception as e:
            print(f"Ошибка при логировании пользователя: {str(e)}")
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except OSError:
                    pass

    @staticmethod
    def _admin_logging(ftp_client, action, details):
        """Логирование для администратора с дополнением существующего файла."""
        temp_name = None
        temp_download = None
        try:
            # 1. Сначала собираем все логи пользователей
            user_logs = Logger._collect_user_logs(ftp_client)

            # 2. Добавляем текущее действие администратора
            user_logs.append({
                "datetime": datetime.now(),
                "user": ftp_client.user,
                "action": action,
                "details": details
            })

            # 3. Проверяем, существует ли файл all_logs.xls на сервере
            existing_logs = []
            temp_download = os.path.join(tempfile.gettempdir(),
                                         f"ftp_alllogs_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls")

            try:
                # Пытаемся скачать существующий файл
                with open(temp_download, 'wb') as tmp_file:
                    ftp_client.ftp.retrbinary('RETR /all_logs.xls', tmp_file.write)

                # Читаем существующие записи
                rb = xlrd.open_workbook(temp_download, formatting_info=True)
                sheet = rb.sheet_by_index(0)

                for row in range(1, sheet.nrows):
                    try:
                        # Пробуем преобразовать дату из разных форматов
                        cell_value = sheet.cell_value(row, 0)
                        if sheet.cell_type(row, 0) == xlrd.XL_CELL_DATE:  # Cell type is a date
                            dt = xldate_as_datetime(cell_value, rb.datemode)
                        else:
                            dt = datetime.strptime(str(cell_value), "%Y-%m-%d %H:%M:%S")

                        existing_logs.append({
                            "datetime": dt,
                            "user": sheet.cell_value(row, 1),
                            "action": sheet.cell_value(row, 2),
                            "details": sheet.cell_value(row, 3)
                        })
                    except Exception as e:
                        print(f"Ошибка при чтении строки {row}: {e}")
                        continue

                # Добавляем существующие записи к новым
                user_logs.extend(existing_logs)

            except ftplib.error_perm:
                # Файла нет, это нормально - будем создавать новый
                pass
            except Exception as e:
                print(f"Ошибка при чтении существующего файла логов: {str(e)}")

            # 4. Сортируем все записи по времени
            user_logs.sort(key=lambda x: x["datetime"])

            # 5. Создаем новый файл с объединенными записями
            temp_name = os.path.join(tempfile.gettempdir(),
                                     f"ftp_adminlog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls")
            wb = xlwt.Workbook()
            ws = wb.add_sheet("Logs")

            # Заголовки
            headers = ["Дата и время", "Пользователь", "Действие", "Детали"]
            for col, header in enumerate(headers):
                ws.write(0, col, header)

            # Записи
            for row, log in enumerate(user_logs, 1):
                ws.write(row, 0, log["datetime"].strftime("%Y-%m-%d %H:%M:%S"))
                ws.write(row, 1, log["user"])
                ws.write(row, 2, log["action"])
                ws.write(row, 3, log["details"])

            try:
                wb.save(temp_name)
            except Exception as e:
                print(f"Ошибка при сохранении файла: {e}")
                return

            # Загружаем на сервер
            try:
                with open(temp_name, 'rb') as f:
                    ftp_client.ftp.storbinary('STOR /all_logs.xls', f)
            except Exception as e:
                print(f"Ошибка при загрузке файла на сервер: {e}")

        except Exception as e:
            print(f"Ошибка при логировании администратора: {str(e)}")
        finally:
            # Удаляем временные файлы
            for filename in [temp_name, temp_download]:
                if filename and os.path.exists(filename):
                    try:
                        os.remove(filename)
                    except OSError:
                        pass

            # 6. Удаляем файлы пользователей
            Logger._cleanup_user_logs(ftp_client)

    @staticmethod
    def _collect_user_logs(ftp_client):
        """Сбор всех логов пользователей с сервера."""
        user_logs = []

        try:
            # Сохраняем текущую директорию
            original_dir = ftp_client.ftp.pwd()

            # Рекурсивный поиск файлов .user_logs.xls
            def search_logs(path):
                try:
                    ftp_client.ftp.cwd(path)
                    items = []
                    ftp_client.ftp.retrlines('LIST', items.append)

                    for item in items:
                        parts = item.split()
                        if not parts:
                            continue

                        name = parts[-1]
                        is_dir = item.startswith('d')

                        if is_dir and name not in ('.', '..'):
                            # Рекурсивно проверяем поддиректории
                            search_logs(name)
                        elif name == '.user_logs.xls':
                            # Нашли файл логов
                            temp_name = os.path.join(tempfile.gettempdir(),
                                                   f"ftp_userlog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls")
                            try:
                                with open(temp_name, 'wb') as tmp:
                                    ftp_client.ftp.retrbinary(f'RETR {name}', tmp.write)

                                # Читаем логи из файла
                                rb = xlrd.open_workbook(temp_name, formatting_info=True)
                                sheet = rb.sheet_by_index(0)

                                for row in range(1, sheet.nrows):
                                    try:
                                        # Пробуем преобразовать дату из разных форматов
                                        cell_value = sheet.cell_value(row, 0)
                                        if sheet.cell_type(row, 0) == xlrd.XL_CELL_DATE:  # Cell type is a date
                                            dt = xldate_as_datetime(cell_value, rb.datemode)
                                        else:
                                            dt = datetime.strptime(str(cell_value), "%Y-%m-%d %H:%M:%S")

                                        user_logs.append({
                                            "datetime": dt,
                                            "user": sheet.cell_value(row, 1),  # Получаем имя пользователя
                                            "action": sheet.cell_value(row, 2),
                                            "details": sheet.cell_value(row, 3)
                                        })
                                    except Exception as e:
                                        print(f"Ошибка при чтении строки {row}: {e}")
                                        continue

                            except Exception as e:
                                print(f"Ошибка при обработке файла {name}: {str(e)}")
                            finally:
                                if os.path.exists(temp_name):
                                    try:
                                        os.remove(temp_name)
                                    except OSError:
                                        pass
                except ftplib.error_perm:
                    pass  # Нет доступа к директории

            # Начинаем поиск с корня
            search_logs('/')

            # Возвращаемся в исходную директорию
            try:
                ftp_client.ftp.cwd(original_dir)
            except Exception as e:
                print(f"Не удалось вернуться в исходную директорию: {e}")

        except Exception as e:
            print(f"Ошибка при сборе логов пользователей: {str(e)}")

        return user_logs

    @staticmethod
    def _cleanup_user_logs(ftp_client):
        """Удаление файлов логов пользователей после сбора."""
        try:
            file_list = []
            ftp_client.ftp.retrlines('LIST', file_list.append)

            for line in file_list:
                if line.strip().endswith('.user_logs.xls'):
                    filename = line.split()[-1]
                    try:
                        ftp_client.ftp.delete(f'/{filename}')
                    except Exception:
                        continue

        except Exception as e:
            print(f"Ошибка при удалении логов пользователей: {str(e)}")
