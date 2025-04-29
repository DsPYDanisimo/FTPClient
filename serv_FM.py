from PyQt5.QtCore import QAbstractItemModel, QModelIndex, Qt, QVariant
from PyQt5.QtGui import QIcon
import ftplib
import os

class FTPFileModel(QAbstractItemModel):
    def __init__(self, ftp_client, root_path="/", ftp=None):
        super().__init__()
        self.ftp_client = ftp_client
        self.root_path = root_path
        self.file_list = []
        self.columns = ["Имя", "Размер", "Дата изменения", "Тип"]
        self.ftp = ftp
        self.parent_path = None

        # Загрузка иконок
        self.folder_icon = QIcon("pictures/folder.png")  # Убедитесь, что пути к иконкам верны
        self.config_icon = QIcon("pictures/config.png")
        self.excel_icon = QIcon("pictures/excel.png")
        self.newfile_icon = QIcon("pictures/Newfile.png")
        self.png_icon = QIcon("pictures/png.png")
        self.txt_icon = QIcon("pictures/txt.png")
        self.word_icon = QIcon("pictures/word.png")

        self.load_data()

    def load_data(self):
        #print(f"load_data() вызвана для: {self.root_path}")
        if self.ftp is None:
            print("Соединение с FTP-сервером потеряно.")
            return  # Или вызовите функцию переподключения
        self.beginResetModel()
        self.file_list = []
        temp_list = []  # Временный список для хранения необработанных данных

        try:
            self.ftp.retrlines("LIST " + self.root_path, lambda line: temp_list.append(line)) # Собираем строки в temp_list
            #print("Содержимое temp_list после retrlines:", temp_list)
        except ftplib.error_perm as e:
            print(f"Ошибка доступа к директории: {e}")
        except Exception as e:
            print(f"Ошибка при получении списка файлов: {e}")

        # В serv_FM.py, внутри FTPFileModel.load_data() перед циклом for line in temp_list:
        print("Полный вывод LIST:")
        for line in temp_list:
            print(line)

        # Обрабатываем строки из temp_list
        for line in temp_list:
            self.process_ftp_line(line)

        # Сортировка: сначала директории, потом файлы, по имени
        self.file_list.sort(key=lambda x: (not x['is_dir'], x['name'].lower())) # Сортировка по директориям, а затем по имени файла

        # Добавляем элемент ".." для возврата на уровень выше, если это не корневая директория
        if self.root_path != '/':
            self.file_list.insert(0, {'name': '..', 'size': 0, 'last_modified': '', 'is_dir': True})

        #print("Содержимое file_list после сортировки:", self.file_list)
        self.endResetModel()

    def process_ftp_line(self, line):
        print("Получена строка LIST:", line)
        parts = line.split(None, 8)  # Разделяем на 9 частей (включая права доступа)
        if len(parts) < 9:
            print("Неверный формат строки LIST:", line)
            return

        permissions, _, owner, group, size, month, day, time, name = parts
        is_dir = permissions.startswith('d')  # Проверяем, начинается ли строка прав с 'd'
        try:
            size = int(size)
        except ValueError:
            print("Неверный формат размера файла:", size)
            size = 0

        last_modified = f"{month} {day} {time}"

        self.file_list.append({
            'name': name,
            'size': size,
            'last_modified': last_modified,
            'is_dir': is_dir
        })


    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.file_list)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()

        row = index.row()
        col = index.column()

        if row < 0 or row >= len(self.file_list):
            print("Неверный индекс строки:", row)
            return QVariant()

        file_info = self.file_list[row]
        name = file_info['name']
        is_dir = file_info['is_dir']

        if role == Qt.DisplayRole:
            if col == 0:  # Имя
                return name
            elif col == 1:  # Размер
                if is_dir:
                    return "<DIR>"
                else:
                    return str(file_info['size']) + " bytes"
            elif col == 2:  # Дата изменения
                return file_info['last_modified']
            elif col == 3:  # Тип
                return "Directory" if is_dir else "File"
        elif role == Qt.DecorationRole and col == 0:  # Иконка
            if name == '..':
                # Возвращаем иконку для возврата на уровень выше
                return QIcon('pictures/back.png')
            if is_dir:
                return self.folder_icon
            else:
                ext = os.path.splitext(name)[1].lower()  # Получаем расширение файла

                if ext in (".dll", ".ini"):
                    return self.config_icon
                elif ext == ".xlsx":
                    return self.excel_icon
                elif ext == ".png":
                    return self.png_icon
                elif ext in (".txt"):
                    return self.txt_icon
                elif ext in (".doc", ".docx"):
                    return self.word_icon
                else:
                    return self.newfile_icon

        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.columns[section]
        return QVariant()

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        return self.createIndex(row, column, None)

    def parent(self, index):
        return QModelIndex()

    def change_root(self, path):
        print(f"change_root вызвана с: {path}")
        self.root_path = path
        self.load_data()
