import os
import ftplib
from PyQt5.QtWidgets import QMessageBox, QInputDialog, QApplication
import shutil
from PyQt5.QtCore import QThread, pyqtSignal
import socket
import xlrd
import xlwt
from datetime import datetime
import os



class FTPUploadThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    update_needed = pyqtSignal()

    def __init__(self, main_window, local_filepath, server_filepath):
        super().__init__()
        self.main_window = main_window
        self.local_filepath = local_filepath
        self.server_filepath = server_filepath
        self.block_size = 32768
        self.timeout = 30
        self.ftp = None  # Добавляем ссылку на объект FTP

    def run(self):
        try:
            self.ftp = self.main_window.ftp
            if not self.ftp or not self.ftp.sock:
                self.error.emit("Нет соединения с FTP")
                return

            # Явно устанавливаем бинарный режим
            self.ftp.voidcmd('TYPE I')
            
            with open(self.local_filepath, 'rb') as f:
                # Устанавливаем таймауты
                self.ftp.sock.settimeout(30)
                
                # Загружаем файл
                self.ftp.storbinary(f'STOR {self.server_filepath}', f, blocksize=32768)
                
                # Явно ждём завершения
                response = self.ftp.getresp()
                if response.startswith(('226', '250')):
                    self.finished.emit(f"Файл загружен: {self.server_filepath}")
                    # Даём время серверу обработать
                    QThread.msleep(200)
                    self.update_needed.emit()
                else:
                    self.error.emit(f"Ошибка сервера: {response}")
                    
        except Exception as e:
            self.error.emit(f"Ошибка загрузки: {str(e)}")

        except socket.timeout:
            self.error.emit("Таймаут операции")
        except ftplib.Error as e:
            self.error.emit(f"FTP ошибка: {str(e)}")
        except Exception as e:
            self.error.emit(f"Неизвестная ошибка: {str(e)}")


class Actions:

    @staticmethod
    def Download(main_window, serv_location):
        def download_action():
            filename = serv_location.text()
            Logger.loging("Скачивание", f"Файл: {filename}")

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
        def recording():
            local_filepath = local_location.text()
            server_filepath = server_location.text()

            if not local_filepath:
                QMessageBox.warning(main_window, "Внимание", "Не выбран локальный файл для записи.")
                return

            default_filename = os.path.basename(local_filepath)

            file_name, ok = QInputDialog.getText(main_window, "Имя файла","Введите имя файла для сохранения на сервере:",text=default_filename)
            if not ok or not file_name:
                return

            Logger.loging(main_window.user, "Загрузка на сервер", f"Локальный файл. {file_name} загружен в {server_filepath}")

            server_filepath = os.path.join(main_window.current_directory, file_name).replace('\\', '/')

            # Создаем и настраиваем поток
            upload_thread = FTPUploadThread(main_window, local_filepath, server_filepath)
            main_window.setup_upload_thread(upload_thread)
            upload_thread.start()

        return recording

    @staticmethod
    def Delete_Serv(main_window, serv_location, parent):
        def delete_action_serv():
            filename = serv_location.text()
            Logger.loging(main_window.user,"Удаление с сервера", f"Файл: {filename}")

            if not filename:
                QMessageBox.warning(main_window, "Внимание", "Не выбран файл для удаления на сервере.")
                return

            filepath_on_server = filename  # Используем полный путь

            try:
                main_window.ftp.delete(filepath_on_server)
                QMessageBox.information(main_window, "Успех",
                                          f"Файл '{os.path.basename(filepath_on_server)}' успешно удален с сервера.")
                main_window.update_server_tree()
                serv_location.setText(main_window.current_directory)

            except ftplib.error_perm as e:
                QMessageBox.critical(main_window, 'Ошибка удаления', f'Ошибка доступа при удалении файла: {str(e)}')
            except ftplib.error_temp as e:
                QMessageBox.critical(main_window, 'Ошибка удаления', f'Временная ошибка при удалении файла: {str(e)}')
            except ftplib.error_proto as e:
                QMessageBox.critical(main_window, 'Ошибка удаления', f'Протокольная ошибка при удалении файла: {str(e)}')
            except Exception as e:
                QMessageBox.critical(main_window, 'Ошибка', f'Не удалось удалить файл: {str(e)}')

        return delete_action_serv

    @staticmethod
    def Delete_Loc(main_window, local_location, file_tree, file_model):
        def delete_action_loc():
            filepath_on_local = local_location.text()
            Logger.loging(main_window.user,"Удаление локального файла", f"Путь: {os.path.basename(filepath_on_local)}")

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
    @staticmethod
    def loging(username, action, details, filename='history_adv.xls'):
        try:
            # Создаем Excel файла
            workbook = xlwt.Workbook()
            sheet = workbook.add_sheet("History")
            
            # Заголовки
            headers = ["Дата и время", "Пользователь", "Действие", "Детали"]
            for col, header in enumerate(headers):
                sheet.write(0, col, header)
            
            # Проверяем существование файла и читаем старые данные
            if os.path.exists(filename):
                try:
                    old_workbook = xlrd.open_workbook(filename)
                    old_sheet = old_workbook.sheet_by_index(0)
                    
                    for row in range(1, old_sheet.nrows):
                        for col in range(old_sheet.ncols):
                            sheet.write(row, col, old_sheet.cell_value(row, col))
                    
                    next_row = old_sheet.nrows
                except:
                    # Если ошибка чтения, начинаем новую историю
                    next_row = 1
            else:
                next_row = 1
            
            # Добавляем новую запись (4 колонки)
            sheet.write(next_row, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            sheet.write(next_row, 1, username)
            sheet.write(next_row, 2, action)
            sheet.write(next_row, 3, details)
            
            workbook.save(filename)
            
        except Exception as e:
            print(f"Ошибка при логировании: {str(e)}")
            # Резервное логирование в текстовый файл
            try:
                with open('history_fallback.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now()}|{username}|{action}|{details}\n")
            except Exception as e:
                print(f"Ошибка резервного логирования: {str(e)}")