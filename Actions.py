import os
import ftplib
from PyQt5.QtWidgets import QMessageBox, QInputDialog
import shutil
from PyQt5.QtCore import QThread, pyqtSignal


# Класс для выполнения FTP операций в отдельном потоке
class FTPUploadThread(QThread):
    finished = pyqtSignal(str)  # Сигнал об окончании загрузки
    error = pyqtSignal(str)     # Сигнал об ошибке

    def __init__(self, main_window, local_filepath, server_filepath):
        super().__init__()
        self.main_window = main_window
        self.local_filepath = local_filepath
        self.server_filepath = server_filepath

    def run(self):
        try:
            with open(self.local_filepath, 'rb') as local_file:
                self.main_window.ftp.storbinary(f'STOR {self.server_filepath}', local_file)
                response = self.main_window.ftp.getresp()  # Get server response
                if response.startswith('2'):
                    self.finished.emit(f"Файл успешно загружен: {self.server_filepath}")
                else:
                    self.error.emit(f"Ошибка записи на сервер: {response}")
        except Exception as e:
            self.error.emit(str(e))


class Actions:

    @staticmethod
    def Download(main_window, serv_location):
        def download_action():
            filename = serv_location.text()

            if not filename:
                QMessageBox.warning(main_window, "Внимание", "Не выбран файл для скачивания.")
                return

            filepath_on_server = os.path.join(main_window.current_directory, filename)

            file_name = os.path.basename(filename)

            if not file_name:
                QMessageBox.warning(main_window, "Внимание", "Не удалось получить имя файла.")
                return

            local_filepath = os.path.join(main_window.local_directory, file_name)

            try:
                with open(local_filepath, 'wb') as local_file:
                    main_window.ftp.retrbinary(f'RETR {filepath_on_server}', local_file.write)
                QMessageBox.information(main_window, "Успех", f"Файл '{file_name}' успешно скачан в '{main_window.local_directory}'.")
                main_window.update_server_tree()

            except ftplib.error_perm as e:
                QMessageBox.critical(main_window, 'Ошибка скачивания', f'Ошибка доступа к файлу: {str(e)}')
            except ftplib.error_temp as e:
                QMessageBox.critical(main_window, 'Ошибка скачивания', f'Временная ошибка при скачивании файла: {str(e)}')
            except ftplib.error_proto as e:
                QMessageBox.critical(main_window, 'Ошибка скачивания', f'Протокольная ошибка при скачивании файла: {str(e)}')
            except Exception as e:
                QMessageBox.critical(main_window, 'Ошибка', f'Не удалось скачать файл: {str(e)}')

        return download_action

    @staticmethod
    def Record(main_window, local_location, server_location):
        def recording():
            local_filepath = local_location.text()

            if not local_filepath:
                QMessageBox.warning(main_window, "Внимание", "Не выбран локальный файл для записи.")
                return

            # Запрашиваем имя файла у пользователя
            file_name, ok = QInputDialog.getText(main_window, "Имя файла", "Введите имя файла для сохранения на сервере:", text=os.path.basename(local_filepath))
            if not ok or not file_name:
                return  # Пользователь отменил или не ввел имя

            server_filepath = os.path.join(main_window.current_directory, file_name)

            # Создаем и запускаем поток
            main_window.upload_thread = FTPUploadThread(main_window, local_filepath, server_filepath)
            main_window.upload_thread.finished.connect(lambda message: (QMessageBox.information(main_window, "Успех", message), main_window.update_server_tree()))
            main_window.upload_thread.error.connect(lambda message: QMessageBox.critical(main_window, "Ошибка", message))
            main_window.upload_thread.start()

        return recording

    @staticmethod
    def Delete_Serv(main_window, serv_location):
        def delete_action_serv():
            filename = serv_location.text()

            if not filename:
                QMessageBox.warning(main_window, "Внимание", "Не выбран файл для удаления на сервере.")
                return

            filepath_on_server = os.path.join(main_window.current_directory, filename)

            try:
                main_window.ftp.delete(filepath_on_server)
                QMessageBox.information(main_window, "Успех", f"Файл '{os.path.basename(filepath_on_server)}' успешно удален с сервера.")
                # Обновляем дерево
                main_window.update_server_tree()
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

            if not filepath_on_local:
                QMessageBox.warning(main_window, "Внимание", 'Не выбран путь для удаления на локальной машине.')
                return

            if not os.path.exists(filepath_on_local):
                QMessageBox.warning(main_window, 'Ошибка', f"Файл не существует: {filepath_on_local}")
                return

            try:
                if os.path.isfile(filepath_on_local):
                    os.remove(filepath_on_local)
                    QMessageBox.information(main_window, "Успех", f"Файл '{os.path.basename(filepath_on_local)}', успешно удалён с локальной машины.")
                elif os.path.isdir(filepath_on_local):
                    shutil.rmtree(filepath_on_local)
                    QMessageBox.information(main_window, 'Успех', f"Директория '{filepath_on_local}' успешно удалёна с локальной машины.")
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
