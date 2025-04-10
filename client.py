"""
Клиент для подключения к игре "Сапёр"
Обеспечивает взаимодействие с сервером и интерфейс пользователя
"""

import socket
import threading
import logging
import re

# Настройка вывода сообщений
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

class GameClient:
    def __init__(self, host: str = '127.0.0.1', port: int = 65432):
        """Инициализация клиента с параметрами подключения"""
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = False  # Флаг работы клиента
        # Регулярка для проверки формата A1-J9
        self.pattern = re.compile(r'^[A-Ja-j][1-9]$')  

    def _receive_handler(self) -> None:
        """Обработчик входящих сообщений от сервера"""
        try:
            while self.running:
                data = self.sock.recv(1024).decode()
                if not data:
                    break
                # Разделение сообщений по переносам строк
                for msg in data.split('\n'):
                    if msg:
                        logging.info(msg.strip())
                        # Завершение при получении итогов игры
                        if "VICTORY" in msg or "DEFEAT" in msg:
                            self.running = False
                            return
        except (ConnectionResetError, TimeoutError):
            logging.info("Connection lost")

    def _validate_input(self, text: str) -> bool:
        """Проверка корректности ввода пользователя"""
        return self.pattern.match(text.upper()) is not None

    def start(self) -> None:
        """Основной цикл работы клиента"""
        try:
            self.sock.connect((self.host, self.port))
            self.running = True
            # Запуск потока для приема сообщений
            threading.Thread(target=self._receive_handler, daemon=True).start()
            logging.info("Connected to server\n")
            
            # Цикл ввода ходов
            while self.running:
                try:
                    move = input("Your move (e.g. A5): ").strip().upper()
                    if not self._validate_input(move):
                        logging.info("Invalid input! Use format A1-J9")
                        continue
                    
                    self.sock.send(move.encode())
                except (KeyboardInterrupt, EOFError):
                    logging.info("\nQuitting...")
                    break
        except ConnectionRefusedError:
            logging.info("Server unavailable")
        finally:
            self.running = False
            self.sock.close()

if __name__ == "__main__":
    GameClient().start()