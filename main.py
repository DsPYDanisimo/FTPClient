import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeView, QFileSystemModel, QVBoxLayout, QWidget, QLineEdit, QPushButton, QMessageBox, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import QDir, QSize
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon
import ftplib
import os
import sqlite3
from serv_FM import FTPFileModel
from Actions import Actions  

class FTPClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ftp = None
        self.current_directory = '/'
        self.local_directory = QDir.homePath()
        self.database = sqlite3.connect("main_data.db")
        self.ftp_file_model = None
        self.upload_thread = None
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
        self.button_delete_local.clicked.connect(lambda: Actions.Delete_Loc(self, self.local_location, self.file_tree, self.file_model)())  # <--- Вызываем возвращенную функцию
        self.button_record = QPushButton('Записать на сервер')
        self.button_record.clicked.connect(lambda: Actions.Record(self, self.local_location, self.serv_location)())  # <--- Вызываем возвращенную функцию
        local_buttons_layout.addWidget(self.button_delete_local)
        local_buttons_layout.addWidget(self.button_record)

        # Кнопки для сервера
        self.button_delete_server = QPushButton('Удалить')
        self.button_delete_server.clicked.connect(lambda: Actions.Delete_Serv(self, self.serv_location)())  # <--- Вызываем возвращенную функцию
        self.button_download = QPushButton('Скачать')
        self.button_download.clicked.connect(lambda: Actions.Download(self, self.serv_location)())  # <--- Вызываем возвращенную функцию
        server_buttons_layout.addWidget(self.button_delete_server)
        server_buttons_layout.addWidget(self.button_download)

        # Дополнительные кнопки
        self.button_report_history = QPushButton('Отчёт истории')
        self.button_report = QPushButton('Отчёт')
        self.button_report_history.setVisible(False)
        self.button_report.setVisible(False)
        self.button_chat = QPushButton('Чат')

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
        other_buttons_layout.addWidget(self.button_chat)
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
                rows = cursor.fetchall()
                for row in rows:
                    hosts = row[0]
                    logins = row[1]
                    passwords = row[2]
                    full_data = [hosts, logins, passwords]
                    admin_data.append(full_data)
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка БД", f"Ошибка при чтении данных из БД admin: {e}")
            return

        host = self.host_input.text()
        username = self.username_input.text()
        password = self.password_input.text()
        port_text = self.port_input.text()
        is_admin = False

        try:
            for value_host in admin_data:
                if host == value_host[0] and username == value_host[1] and password == value_host[2]:
                    is_admin = True
                    break
            try:
                port = int(port_text) if port_text else 21
            except ValueError:
                QMessageBox.critical(self, "Ошибка", "Неверный формат порта.  Используется порт 21 по умолчанию.")
                port = 21

            self.ftp = ftplib.FTP(timeout=30) 
            self.ftp.connect(host, port, timeout=30)
            self.ftp.login(user=username, passwd=password)
            self.ftp.set_pasv(True)
            print(f"Пассивный режим включён: {self.ftp.passiveserver}")
            QMessageBox.information(self, 'Подключение к серверу', 'Успешное подключение!')


            self.ftp_file_model = FTPFileModel(self, self.current_directory, self.ftp)
            self.serv_file_tree.setModel(self.ftp_file_model)
            self.update_server_tree()
            self.serv_location.setText(self.current_directory)

            self.button_report_history.setVisible(is_admin)
            self.button_report.setVisible(is_admin)
            self.update()

        except ftplib.all_errors as e:
            QMessageBox.critical(self, 'Ошибка FTP', f'Ошибка FTP: {str(e)}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка 1', f'Не удалось подключиться к FTP-серверу: {str(e)}, Host: {host}, User: {username}, Port: {port_text}') #Более информативное сообщение

    def ftp_disconnect(self):
        if self.ftp:
            try:
                self.ftp.quit()
                QMessageBox.information(self, 'Отключение', 'Отключение произошло успешно')
            except ftplib.all_errors as e:
                QMessageBox.warning(self, 'Ошибка отключения', f'Ошибка при отключении: {str(e)}')
            finally:
                self.ftp = None
                self.current_directory = '/'
                self.serv_location.setText('')  # Очищаем поле отображения пути
                self.ftp_file_model = FTPFileModel(self, self.current_directory, self.ftp)
                self.serv_file_tree.setModel(self.ftp_file_model)
                self.host_input.setText('')
                self.username_input.setText('')
                self.port_input.setText('')
                self.password_input.setText('')
                self.update_server_tree()
                self.button_report_history.setVisible(False)
                self.button_report.setVisible(False)
                self.update()
        return

    def update_server_tree(self):
        if self.ftp is None:
            self.serv_file_tree.setModel(QStandardItemModel())
            self.serv_location.setText('')
            return
        try:
            if self.ftp_file_model:
                self.ftp_file_model.change_root(self.current_directory)

            self.serv_location.setText(self.current_directory)
        except ftplib.error_perm as e:
            QMessageBox.warning(self, 'Ошибка 3', f'Не удалось получить список файлов: {str(e)}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка 4', f'Не удалось обновить дерево файлов: {str(e)}')


    def item_double_clicked_in_local(self, index):
        path = self.file_model.filePath(index)

        if os.path.isfile(path):
            self.local_location.setText(path)
            self.local_directory = os.path.dirname(path)
            self.file_tree.setRootIndex(self.file_model.setRootPath(self.local_directory))
        elif os.path.isdir(path):
            self.local_directory = path
            self.local_location.setText(path)
            self.file_tree.setRootIndex(self.file_model.setRootPath(path))
        else:
            QMessageBox.warning(self, "Ошибка 5", "Неизвестный тип файла.")


    def item_double_clicked_in_serv(self, index):
        if not index.isValid():
            return

        try:
            item_name = self.ftp_file_model.file_list[index.row()]['name']
            is_dir = self.ftp_file_model.file_list[index.row()]['is_dir']
            print(f"Выбран элемент: {item_name}, является директорией: {is_dir}") #Отладка
        except IndexError:
            QMessageBox.warning(self, "Ошибка", "Не удалось получить информацию о файле.")
            return

        if item_name == '..':
            print("Переход к родительской директории") # Отладка
            self.go_back()
            return

        new_directory = os.path.join(self.current_directory, item_name)
        print(f"Новая директория: {new_directory}") # Отладка

        if is_dir:
            try:
                self.ftp.cwd(new_directory)
                self.current_directory = new_directory
                print(f"Текущая директория изменена на: {self.current_directory}")#Отладка
                self.update_server_tree()
                self.serv_location.setText(self.current_directory)  # Отображаем текущий путь
            except ftplib.error_perm as e:
                QMessageBox.warning(self, 'Ошибка 6', f'Нет доступа к директории: {item_name}. Ошибка: {e}')
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка 7', f'Не удалось открыть: {str(e)}')
        else:
            # Вместо полного пути, передаем только имя файла
            self.serv_location.setText(item_name)

    def go_back_loc(self):
        current_path = self.local_directory
        parent_path = os.path.dirname(current_path) #Более простой способ получить родительский каталог

        if parent_path: #Проверяем, что родительский каталог существует
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
            except ftplib.error_perm as e:
                 QMessageBox.warning(self, 'Ошибка', f'Нет доступа к родительской директории: {str(e)}') #Сообщение об ошибке
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', f'Не удалось перейти в родительскую директорию: {str(e)}') #Сообщение об ошибке
        else:
            QMessageBox.information(self, 'Информация', 'Вы уже находитесь в корневой директории.')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    client = FTPClient()
    client.show()
    sys.exit(app.exec_())
