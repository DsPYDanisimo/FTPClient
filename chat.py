import socket
import threading
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QLineEdit, 
                            QPushButton, QMessageBox)
from PyQt5.QtCore import pyqtSignal, QObject

class ChatClient(QObject):
    message_received = pyqtSignal(str)
    connection_error = pyqtSignal(str)

    def __init__(self, host, port, username):
        super().__init__()
        self.host = host
        self.port = port
        self.username = username
        self.socket = None
        self.running = False

    def connect_to_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.running = True
            
            # Отправляем серверу имя пользователя
            self.send_message({
                'type': 'connect',
                'username': self.username
            })
            
            # Запускаем поток для получения сообщений
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            return True
        except Exception as e:
            self.connection_error.emit(f"Ошибка подключения к чату: {str(e)}")
            return False

    def receive_messages(self):
        while self.running:
            try:
                message = self.socket.recv(1024).decode('utf-8')
                if not message:
                    break
                    
                data = json.loads(message)
                if data['type'] == 'message':
                    formatted_msg = f"{data['sender']}: {data['content']}"
                    self.message_received.emit(formatted_msg)
                    
            except Exception as e:
                self.connection_error.emit(f"Ошибка получения сообщения: {str(e)}")
                break

    def send_message(self, message_dict):
        try:
            message_str = json.dumps(message_dict)
            self.socket.sendall(message_str.encode('utf-8'))
        except Exception as e:
            self.connection_error.emit(f"Ошибка отправки сообщения: {str(e)}")

    def send_text_message(self, text):
        self.send_message({
            'type': 'message',
            'sender': self.username,
            'content': text
        })

    def disconnect(self):
        self.running = False
        try:
            if self.socket:
                self.socket.close()
        except:
            pass

class ChatWindow(QWidget):
    def __init__(self, chat_client):
        super().__init__()
        self.chat_client = chat_client
        self.init_ui()
        self.setup_signals()

    def init_ui(self):
        self.setWindowTitle(f'Чат - {self.chat_client.username}')
        self.setGeometry(300, 300, 400, 500)
        
        layout = QVBoxLayout()
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите сообщение...")
        
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_message)
        
        layout.addWidget(self.chat_display)
        layout.addWidget(self.message_input)
        layout.addWidget(self.send_button)
        
        self.setLayout(layout)

    def setup_signals(self):
        self.chat_client.message_received.connect(self.display_message)
        self.chat_client.connection_error.connect(self.show_error)

    def display_message(self, message):
        self.chat_display.append(message)

    def show_error(self, error_msg):
        QMessageBox.warning(self, "Ошибка чата", error_msg)

    def send_message(self):
        message = self.message_input.text().strip()
        if message:
            self.chat_client.send_text_message(message)
            self.message_input.clear()

    def closeEvent(self, event):
        self.chat_client.disconnect()
        event.accept()

class ChatServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = {}
        self.running = False

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"Сервер чата запущен на {self.host}:{self.port}")
        
        accept_thread = threading.Thread(target=self.accept_connections)
        accept_thread.daemon = True
        accept_thread.start()

    def accept_connections(self):
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()
            except:
                break

    def handle_client(self, client_socket):
        username = None
        try:
            while True:
                message = client_socket.recv(1024).decode('utf-8')
                if not message:
                    break
                    
                data = json.loads(message)
                
                if data['type'] == 'connect':
                    username = data['username']
                    self.clients[username] = client_socket
                    self.broadcast({
                        'type': 'notification',
                        'content': f"{username} присоединился к чату"
                    })
                    
                elif data['type'] == 'message':
                    self.broadcast({
                        'type': 'message',
                        'sender': username,
                        'content': data['content']
                    })
                    
        except:
            pass
        finally:
            if username and username in self.clients:
                del self.clients[username]
                self.broadcast({
                    'type': 'notification',
                    'content': f"{username} покинул чат"
                })
            client_socket.close()

    def broadcast(self, message_dict):
        message_str = json.dumps(message_dict)
        for client in list(self.clients.values()):
            try:
                client.sendall(message_str.encode('utf-8'))
            except:
                continue

    def stop(self):
        self.running = False
        try:
            if self.server_socket:
                self.server_socket.close()
        except:
            pass

def start_chat_server():
    server = ChatServer()
    server.start()
    return server