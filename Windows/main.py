import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTreeView, QFileSystemModel,QVBoxLayout, QWidget, QLineEdit, QPushButton, QMessageBox, QHBoxLayout, QLabel, QDockWidget, QListWidget)
from PyQt5.QtCore import QDir, QSize, QTimer, Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon
import ftplib
import os
import socket
import sqlite3
from serv_FM import FTPFileModel
from Actions import Actions, Logger
import tempfile
import xlwt, xlrd
from datetime import datetime
import subprocess 

class FTPClient(QMainWindow):
    def __init__(self):
        super().__init__()
        # Инициализация переменных
        self.ftp = None
        self.current_directory = '/'
        self.local_directory = QDir.homePath()
        self.database = sqlite3.connect("main_data.db")
        self.ftp_file_model = None
        self.upload_thread = None
        self.is_double_click_processing = False
        self.user = None
        self.host = None
        self.passw = None
        self.is_admin = False
        self.physical_ftp_path = '/'
        self.connection_attempts = 0
        self.max_retries = 3
        self.user_dock = None
        self.setup_user_panel()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('FTPWidget')
        self.setGeometry(400, 100, 1300, 800)

        # Создание виджетов
        # Верхняя панель подключения
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText('IP хоста')
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('Имя пользователя')
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('Пароль')
        self.password_input.setEchoMode(QLineEdit.Password)
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText('Порт')

        self.highbox = QHBoxLayout()
        self.connect_button = QPushButton('Подключиться')
        self.connect_button.clicked.connect(self.connect_to_ftp)
        self.disconnect_button = QPushButton('Отключиться')
        self.disconnect_button.clicked.connect(self.ftp_disconnect)
        self.highbox.addWidget(self.connect_button)
        self.highbox.addWidget(self.disconnect_button)

        # Кнопка назад на сервере
        self.back_button = QPushButton()
        self.back_button.clicked.connect(self.go_back)
        back_button_icon = QIcon('pictures/back.png')
        self.back_button.setIcon(back_button_icon)
        self.back_button.setIconSize(QSize(20, 20))
        self.back_button.setFixedSize(25, 25)

        # Кнопка назад на локальном компьютере
        self.back_button_loc = QPushButton()
        self.back_button_loc.clicked.connect(self.go_back_loc)
        self.back_button_loc.setIcon(back_button_icon)
        self.back_button_loc.setIconSize(QSize(20, 20))
        self.back_button_loc.setFixedSize(25, 25)

        # Поля для отображения директорий
        self.local_location = QLineEdit(self.local_directory)
        self.local_location.setReadOnly(True)
        self.serv_location = QLineEdit()
        self.serv_location.setReadOnly(True)
        self.local_label = QLabel("Локальный компьютер:")
        self.serv_label = QLabel("FTP Сервер:")

        # Дерево файлов локального компьютера
        self.file_tree = QTreeView()
        self.file_model = QFileSystemModel()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.setRootPath(QDir.homePath()))

        # Дерево файлов сервера
        self.serv_file_tree = QTreeView()

        # Создаем контейнеры для кнопок
        local_buttons_container = QWidget()
        local_buttons_layout = QHBoxLayout(local_buttons_container)

        server_buttons_container = QWidget()
        server_buttons_layout = QHBoxLayout(server_buttons_container)

        # Кнопки для локального компьютера
        self.button_delete_local = QPushButton('Удалить')
        self.button_delete_local.clicked.connect(
            lambda: Actions.Delete_Loc(self, self.local_location, self.file_tree, self.file_model)())
        self.button_record = QPushButton('Записать на сервер')
        self.button_record.clicked.connect(lambda: Actions.Record(self, self.local_location, self.serv_location)())
        local_buttons_layout.addWidget(self.button_delete_local)
        local_buttons_layout.addWidget(self.button_record)

        # Кнопки для сервера
        self.button_delete_server = QPushButton('Удалить')
        self.button_delete_server.clicked.connect(lambda: Actions.Delete_Serv(self, self.serv_location, self)())
        self.button_download = QPushButton('Скачать')
        self.button_download.clicked.connect(lambda: Actions.Download(self, self.serv_location)())
        server_buttons_layout.addWidget(self.button_delete_server)
        server_buttons_layout.addWidget(self.button_download)

        # Дополнительные кнопки
        self.button_report_history = QPushButton('Отчёт истории')
        self.button_report = QPushButton('Активные пользователи')
        self.button_report.clicked.connect(self.show_active_users)
        self.button_report_history.setVisible(False)
        self.button_report.setVisible(False)
        self.button_report_history.clicked.connect(self.show_history_report)

        # Основной layout
        main_layout = QVBoxLayout()

        # Панель подключения
        connection_layout = QHBoxLayout()
        connection_layout.addWidget(self.host_input)
        connection_layout.addWidget(self.username_input)
        connection_layout.addWidget(self.password_input)
        connection_layout.addWidget(self.port_input)
        main_layout.addLayout(connection_layout)
        main_layout.addLayout(self.highbox)

        # Панель путей
        paths_layout = QHBoxLayout()
        paths_layout.addWidget(self.local_label)
        paths_layout.addWidget(self.local_location)
        paths_layout.addWidget(self.back_button_loc)
        paths_layout.addWidget(self.serv_label)
        paths_layout.addWidget(self.serv_location)
        paths_layout.addWidget(self.back_button)
        main_layout.addLayout(paths_layout)

        # Панель файловых деревьев
        files_layout = QHBoxLayout()
        files_layout.addWidget(self.file_tree)
        files_layout.addWidget(self.serv_file_tree)
        main_layout.addLayout(files_layout)

        # Панель кнопок действий
        actions_layout = QHBoxLayout()

        # Локальные кнопки (под левым деревом)
        local_actions = QVBoxLayout()
        local_actions.addWidget(QLabel("Действия с локальными файлами:"))
        local_actions.addWidget(local_buttons_container)

        # Серверные кнопки (под правым деревом)
        server_actions = QVBoxLayout()
        server_actions.addWidget(QLabel("Действия с файлами сервера:"))
        server_actions.addWidget(server_buttons_container)

        actions_layout.addLayout(local_actions)
        actions_layout.addLayout(server_actions)
        main_layout.addLayout(actions_layout)

        # Дополнительные кнопки
        other_buttons_layout = QHBoxLayout()
        other_buttons_layout.addWidget(self.button_report)
        other_buttons_layout.addWidget(self.button_report_history)
        main_layout.addLayout(other_buttons_layout)

        # Установка главного виджета
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Подключение сигналов
        self.serv_file_tree.doubleClicked.connect(self.item_double_clicked_in_serv)
        self.file_tree.doubleClicked.connect(self.item_double_clicked_in_local)

    def connect_to_ftp(self):
        admin_data = []
        try:
            with self.database as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT ad_serv_host, admin_log, admin_psw FROM admin")
                admin_data = [list(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка БД", f"Ошибка при чтении данных из БД: {e}")
            return

        self.host = self.host_input.text().strip()
        self.user = self.username_input.text().strip()
        self.passw = self.password_input.text().strip()
        port_text = self.port_input.text().strip()

        if not all([self.host, self.user, self.passw]):
            QMessageBox.warning(self, "Ошибка", "Заполните все обязательные поля")
            return

        try:
            port = int(port_text) if port_text else 21
        except ValueError:
            QMessageBox.critical(self, "Ошибка", "Неверный формат порта")
            return

        if self.ftp:
            self.ftp_disconnect()

        # Проверка прав администратора
        self.is_admin = any(
            self.host == host and self.user == user and self.passw == psw
            for host, user, psw in admin_data
        )

        try:
            self.ftp = ftplib.FTP(timeout=30)
            self.ftp.connect(self.host, port, timeout=15)
            
            # Проверка приветственного сообщения сервера
            if not self.ftp.welcome.startswith('220'):
                raise ConnectionError("Неверный ответ сервера")

            self.ftp.login(user=self.user, passwd=self.passw)
            
            # Усиленная проверка соединения
            try:
                self.ftp.voidcmd("NOOP")
                self.ftp.sendcmd("PWD")
            except Exception as e:
                raise ConnectionError(f"Соединение нестабильно: {str(e)}")

            # Настройка сокета
            if self.ftp.sock:
                sock = self.ftp.sock
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            else:
                raise ConnectionError("Не удалось получить сокет FTP")

            # Инициализация модели файлов
            self.ftp_file_model = FTPFileModel(self, '/', self.ftp)
            self.serv_file_tree.setModel(self.ftp_file_model)
            self.button_report.setVisible(self.is_admin)
            self.button_report_history.setVisible(self.is_admin)
            self.update_server_tree()
            self.serv_location.setText('/')

            # Определение корневого пути
            try:
                original_dir = self.ftp.pwd()
                test_dir = "test_dir_123"
                try:
                    self.ftp.mkd(test_dir)
                    self.ftp.rmd(test_dir)
                    self.physical_ftp_path = original_dir
                except:
                    self.physical_ftp_path = '/'
                self.ftp.cwd(original_dir)
            except Exception as e:
                print(f"Определение корня: {e}")
                self.physical_ftp_path = '/'

            QMessageBox.information(self, 'Успех', 'Подключение установлено')
            Logger.loging(self, "Подключение", f"Сервер: {self.host}")

        except ftplib.error_perm as e:
            error_code = e.args[0].split()[0]
            if error_code == '530':
                QMessageBox.critical(self, 'Ошибка', 'Неверные учетные данные')
            else:
                QMessageBox.critical(self, 'Ошибка', f"Код ошибки: {error_code}")
            self.ftp_disconnect()
            
        except (socket.timeout, ConnectionRefusedError) as e:
            QMessageBox.critical(self, 'Ошибка', 'Таймаут подключения')
            self.ftp_disconnect()
            
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f"{type(e).__name__}: {str(e)}")
            self.ftp_disconnect()
            
        finally:
            QApplication.processEvents()


    def ftp_disconnect(self):
        if self.ftp:
            Logger.loging(self, "Отключение", "От сервера FTP")
            try:
                try:
                    self.ftp.quit()
                except:
                    try:
                        self.ftp.close()
                    except:
                        pass
                
                QMessageBox.information(self, 'Отключение', 'Отключение произошло успешно')
            except Exception as e:
                QMessageBox.warning(self, 'Ошибка отключения', f'Ошибка при отключении: {str(e)}')
            finally:
                self.ftp = None
                self.current_directory = '/'
                self.serv_location.setText('')
                self.serv_file_tree.setModel(None)
                self.button_report_history.setVisible(False)
                self.button_report.setVisible(False)
                
                # Очищаем список пользователей при отключении
                self.user_list.clear()

    def update_server_tree(self):
        """Полное обновление дерева сервера"""
        if not self.ftp or not self.ftp_file_model:
            return

        try:
            current_path = self.ftp.pwd()
            self.ftp_file_model.root_path = current_path
            self.ftp_file_model.load_data()
            self.serv_location.setText(current_path)
            self.serv_file_tree.viewport().update()
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', f'Ошибка обновления: {str(e)}')

    def force_refresh_server_tree(self):
        """Принудительное обновление с задержкой"""
        QTimer.singleShot(100, self.update_server_tree)

    def setup_upload_thread(self, thread):
        """Настройка обработчиков для потока загрузки"""
        thread.finished.connect(lambda msg: QMessageBox.information(self, "Успех", msg))
        thread.error.connect(lambda err: QMessageBox.critical(self, "Ошибка", err))
        thread.update_needed.connect(self.force_refresh_server_tree)
        self.upload_thread = thread

    def _load_ftp_data(self):
        if self.ftp and self.ftp_file_model:
            self.ftp_file_model.root_path = self.current_directory
            self.ftp_file_model.load_data()
            self.serv_file_tree.viewport().update()

    def item_double_clicked_in_local(self, index):
        path = self.file_model.filePath(index)

        if os.path.isfile(path):
            self.local_location.setText(path)
            self.local_directory = os.path.dirname(path)
        elif os.path.isdir(path):
            self.local_directory = path
            self.local_location.setText(path)
        else:
            QMessageBox.warning(self, "Ошибка", "Неизвестный тип файла.")

        self.file_tree.setRootIndex(self.file_model.setRootPath(self.local_directory))

    def item_double_clicked_in_serv(self, index):
        if self.is_double_click_processing:
            return

        self.is_double_click_processing = True

        try:
            if not self.ftp or not self.ftp_file_model or not index.isValid():
                return

            item = self.ftp_file_model.file_list[index.row()]
            item_name = item['name']
            is_dir = item['is_dir']

            if item_name == '..':
                self.go_back()
                return

            if is_dir:
                new_path = os.path.join(self.current_directory, item_name).replace('\\', '/')
                try:
                    # Сохраняем текущий путь перед изменением
                    old_path = self.ftp.pwd()

                    # Переходим в новую директорию
                    self.ftp.cwd(new_path)
                    self.current_directory = new_path

                    # Полностью перезагружаем модель
                    self.ftp_file_model.root_path = new_path
                    self.ftp_file_model.load_data()

                    # Обновляем интерфейс
                    self.serv_location.setText(new_path)
                    self.serv_file_tree.viewport().update()

                except ftplib.error_perm as e:
                    QMessageBox.warning(self, 'Ошибка', f'Нет доступа: {e}')
                    # Восстанавливаем предыдущий путь
                    try:
                        self.ftp.cwd(old_path)
                    except:
                        pass
            else:
                full_path = os.path.join(self.current_directory, item_name).replace('\\', '/')
                self.serv_location.setText(full_path)

        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при обработке: {str(e)}')
        finally:
            self.is_double_click_processing = False

    def reset_double_click_flag(self):
        self.is_double_click_processing = False

    def go_back_loc(self):
        current_path = self.local_directory
        parent_path = os.path.dirname(current_path)

        if parent_path:
            self.local_directory = parent_path
            self.local_location.setText(parent_path)
            self.file_tree.setRootIndex(self.file_model.setRootPath(parent_path))

    def go_back(self):
        if self.current_directory != '/':
            parent_directory = '/'.join(self.current_directory.split('/')[:-1]) or '/'
            try:
                self.ftp.cwd(parent_directory)
                self.current_directory = self.ftp.pwd()
                self.update_server_tree()
                self.serv_location.setText(self.current_directory)
            except ftplib.error_perm as e:
                QMessageBox.warning(self, 'Ошибка', f'Нет доступа к родительской директории: {str(e)}')
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', f'Не удалось перейти в родительскую директорию: {str(e)}')
        else:
            QMessageBox.information(self, 'Информация', 'Вы уже находитесь в корневой директории.')

    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.ftp:
            self.ftp_disconnect()
        if hasattr(self, 'upload_thread') and self.upload_thread and self.upload_thread.isRunning():
            self.upload_thread.quit()
            self.upload_thread.wait()
        event.accept()

    def open_history_report(self):
        try:
            history_file = "history_adv.xls"
            if os.path.exists(history_file):
                os.startfile(history_file)
            else:
                QMessageBox.information(self, "Информация", "Файл с историей действий не создан ")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл истории: {str(e)}")

    def file_exists(self, path):
        try:
            self.ftp.size(path)
            return True
        except:
            return False

    def setup_user_panel(self):
        self.user_dock = QDockWidget("Активные пользователи", self)
        self.user_list = QListWidget()
        self.user_dock.setWidget(self.user_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.user_dock)
        self.user_dock.hide()

    def show_active_users(self):
        if not self.ftp:
            QMessageBox.warning(self, "Ошибка", "Сначала подключитесь к серверу")
            return

        try:
            # Альтернативный способ для серверов, не поддерживающих SITE WHO
            self.user_list.clear()
            
            # Попробуем получить список файлов в специальной директории
            try:
                self.ftp.cwd('/active_users')  # Может не существовать
                files = []
                self.ftp.retrlines('LIST', files.append)
                
                for line in files:
                    if line.startswith('d'):
                        continue  # Пропускаем директории
                    username = line.split()[-1]
                    self.user_list.addItem(username)
                    
            except ftplib.error_perm:
                # Если директории нет, используем альтернативный метод
                self.user_list.addItem("Сервер не поддерживает просмотр активных пользователей")
                self.user_list.addItem(f"Текущий пользователь: {self.user}")
                
            self.user_dock.show()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось получить информацию: {str(e)}")

    def show_history_report(self):
        """Открытие отчета истории - скачивает all_logs.xls и открывает его"""
        if not self.ftp:
            QMessageBox.warning(self, "Ошибка", "Нет подключения к FTP серверу")
            return

        try:
            # Создаем уникальное имя временного файла
            temp_dir = tempfile.gettempdir()
            temp_filename = os.path.join(temp_dir, f"ftp_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls")            
            # Скачиваем файл с сервера
            try:
                with open(temp_filename, 'wb') as tmp_file:
                    self.ftp.retrbinary('RETR /all_logs.xls', tmp_file.write)
            except ftplib.error_perm:
                QMessageBox.information(self, "Информация", "Файл с историей действий пока не создан")
                return
            
            # Открываем файл
            try:
                # Для Windows
                if os.name == 'nt':
                    os.startfile(temp_filename)
                else:
                    # Для Linux/Mac
                    opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                    subprocess.call([opener, temp_filename])
                
                # Удаляем файл через 30 секунд (даем время на работу с файлом)
                QTimer.singleShot(30000, lambda: self._safe_delete_file(temp_filename))
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл: {str(e)}")
                self._safe_delete_file(temp_filename)
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось обработать запрос: {str(e)}")
            self._safe_delete_file(temp_filename)

    def _safe_delete_file(self, filename):
        """Безопасное удаление файла с обработкой ошибок"""
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except Exception as e:
            print(f"Не удалось удалить временный файл {filename}: {str(e)}")
            # Пробуем еще раз через минуту
            QTimer.singleShot(60000, lambda: self._safe_delete_file(filename))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    client = FTPClient()
    client.show()
    sys.exit(app.exec_())
