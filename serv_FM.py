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

        self.folder_icon = QIcon("pictures/folder.png")
        self.config_icon = QIcon("pictures/config.png")
        self.excel_icon = QIcon("pictures/excel.png")
        self.newfile_icon = QIcon("pictures/Newfile.png")
        self.png_icon = QIcon("pictures/png.png")
        self.txt_icon = QIcon("pictures/txt.png")
        self.word_icon = QIcon("pictures/word.png")

        self.load_data()

    def load_data(self):
        if self.ftp is None:
            return

        self.beginResetModel()
        self.file_list = []

        try:
            # Получаем текущую директорию
            current_dir = self.ftp.pwd()

            # Пытаемся перейти в целевую директорию
            try:
                if self.root_path != current_dir:
                    self.ftp.cwd(self.root_path)
            except ftplib.error_perm as e:
                print(f"Не удалось перейти в {self.root_path}: {e}")
                self.endResetModel()
                return

            lines = []
            try:
                # Используем LIST -a для админа, обычный LIST для пользователей
                if self.ftp_client.is_admin:
                    self.ftp.retrlines('LIST -a', lambda x: lines.append(x))
                else:
                    self.ftp.retrlines('LIST', lambda x: lines.append(x))
            except ftplib.error_perm as e:
                print(f"Ошибка LIST: {e}")
                self.endResetModel()
                return

            for line in lines:
                try:
                    # Пропускаем служебные строки и скрытые файлы для обычных пользователей
                    if not line.strip() or (not self.ftp_client.is_admin and
                                            any(part.startswith('.') for part in line.split()[-1:])):
                        continue

                    self.process_ftp_line(line)
                except Exception as e:
                    print(f"Ошибка обработки строки: {e}")
                    continue

            # Сортировка: сначала директории, потом файлы
            self.file_list.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))

            # Добавляем ".." если не в корне
            if self.root_path != '/':
                self.file_list.insert(0, {
                    'name': '..',
                    'size': 0,
                    'last_modified': '',
                    'is_dir': True
                })

        except Exception as e:
            print(f"Критическая ошибка при загрузке данных: {e}")
        finally:
            self.endResetModel()

    def process_ftp_line(self, line):
        # Пропускаем пустые строки и строки суммарного размера
        if not line.strip() or 'total ' in line.lower():
            return
            
        parts = line.split()
        if not parts:
            return
            
        # Windows-style LIST
        if line.startswith('d') or line.startswith('-'):
            is_dir = parts[0].startswith('d')
            try:
                size = int(parts[4]) if not is_dir else 0
            except (IndexError, ValueError):
                size = 0
            last_modified = ' '.join(parts[5:8]) if len(parts) >= 8 else ''
            name = ' '.join(parts[8:]) if len(parts) > 8 else parts[-1]
        # Unix-style LIST
        else:
            is_dir = len(parts) > 1 and parts[1].isdigit() and int(parts[1]) > 1
            size = 0 if is_dir else (int(parts[4]) if len(parts) > 4 else 0)
            last_modified = ' '.join(parts[5:8]) if len(parts) >= 8 else ''
            name = parts[-1]

        # Пропускаем текущий и родительский каталоги (они добавляются отдельно)
        if name in ('.', '..'):
            return

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
        if row < 0 or row >= len(self.file_list):
            return QVariant()

        file_info = self.file_list[row]
        name = file_info['name']
        is_dir = file_info['is_dir']

        if role == Qt.DisplayRole:
            col = index.column()
            if col == 0:
                return name
            elif col == 1:
                return "<DIR>" if is_dir else f"{file_info['size']} bytes"
            elif col == 2:
                return file_info['last_modified']
            elif col == 3:
                return "Directory" if is_dir else "File"
        elif role == Qt.DecorationRole and index.column() == 0:
            if name == '..':
                return QIcon('pictures/back.png')
            if is_dir:
                return self.folder_icon

            ext = os.path.splitext(name)[1].lower()
            if ext in (".dll", ".ini"):
                return self.config_icon
            elif ext == ".xlsx":
                return self.excel_icon
            elif ext == ".png":
                return self.png_icon
            elif ext == ".txt":
                return self.txt_icon
            elif ext in (".doc", ".docx"):
                return self.word_icon
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
        self.root_path = path
        self.load_data()

    def refresh(self):
        """Принудительное обновление списка файлов"""
        self.load_data()
