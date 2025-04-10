"""
Многопоточный сервер для онлайн-игры "Сапёр"
Обрабатывает до 2 подключений, синхронизирует игровой процесс
"""

import socket
import threading
import logging
from typing import Dict, Set, List

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class GameServer:
    def __init__(self, host: str = '127.0.0.1', port: int = 65432):
        """Инициализация сервера с параметрами подключения"""
        self.host = host
        self.port = port
        self.connections: List[socket.socket] = []  # Активные соединения
        self.mines: Dict[socket.socket, Set[str]] = {}  # Мины игроков
        self.players: Dict[socket.socket, str] = {}  # Имена игроков
        self.lock = threading.Lock()  # Для потокобезопасности
        self.game_start = threading.Event()  # Флаг старта игры
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
    def broadcast(self, message: str) -> None:
        """Рассылка сообщения всем активным клиентам"""
        with self.lock:
            disconnected = []
            for conn in self.connections:
                try:
                    # Отправка с добавлением переноса строки
                    conn.send(f"{message}\n".encode())
                except (ConnectionError, OSError):
                    disconnected.append(conn)
            
            # Очистка отключенных клиентов
            for conn in disconnected:
                self._cleanup_client(conn)

    def _cleanup_client(self, conn: socket.socket) -> None:
        """Безопасное удаление клиента из системы"""
        with self.lock:
            if conn in self.connections:
                self.connections.remove(conn)
            self.mines.pop(conn, None)  # Удаление мин игрока
            self.players.pop(conn, None)  # Удаление имени
            try:
                conn.close()
            except OSError:
                pass
            logging.info("Client %s disconnected", conn.getpeername())

    def _validate_coordinates(self, coords: List[str]) -> bool:
        """Проверка формата координат (A1-J9)"""
        return len(coords) == 5 and all(len(c) == 2 for c in coords)

    def _handle_client(self, conn: socket.socket) -> None:
        """Основная логика взаимодействия с клиентом"""
        addr = conn.getpeername()
        with self.lock:
            player_id = f"Player-{len(self.connections)}"
            self.players[conn] = player_id
        
        try:
            # Этап установки мин
            conn.send("SET MINES (5 coordinates, e.g. A1 B2): ".encode())
            coords = conn.recv(1024).decode().strip().upper().split()
            
            if not self._validate_coordinates(coords):
                conn.send("INVALID_INPUT\n".encode())
                return

            with self.lock:
                self.mines[conn] = set(coords)
            
            logging.info("%s set mines: %s", player_id, coords)
            self.broadcast(f"{player_id} READY")

            # Ожидание второго игрока
            if not self.game_start.is_set():
                conn.send("WAITING_FOR_OPPONENT\n".encode())
                self.game_start.wait()

            # Старт игры
            conn.send("GAME_START\n".encode())
            hits = 0  # Счетчик попаданий
            
            # Игровой цикл
            while hits < 5:
                try:
                    move = conn.recv(1024).decode().strip().upper()
                    if not move:
                        break
                except (ConnectionResetError, TimeoutError):
                    break

                # Поиск противника
                with self.lock:
                    opponent = next((c for c in self.connections if c != conn), None)
                    target = self.mines.get(opponent, set()) if opponent else set()

                # Проверка попадания
                response = f"{player_id} -> {move}: "
                if move in target:
                    hits += 1
                    response += f"HIT ({hits}/5)"
                else:
                    response += "MISS"
                
                self.broadcast(response)

                # Условие победы
                if hits >= 5:
                    self.broadcast(f"{player_id} VICTORY")
                    if opponent:
                        try:
                            opponent.send("DEFEAT\n".encode())
                        except OSError:
                            pass
                    break
        finally:
            self._cleanup_client(conn)

    def start(self) -> None:
        """Запуск сервера и обработка подключений"""
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(2)  # Максимум 2 игрока
        logging.info("Server started on %s:%d", self.host, self.port)

        try:
            while True:
                conn, addr = self.server_socket.accept()
                with self.lock:
                    self.connections.append(conn)
                logging.info("New connection from %s", addr)
                # Запуск обработчика для каждого клиента в отдельном потоке
                threading.Thread(target=self._handle_client, args=(conn,)).start()
                
                # Активация игры при 2 подключениях
                with self.lock:
                    if len(self.connections) >= 2:
                        self.game_start.set()
        except KeyboardInterrupt:
            logging.info("Shutting down server")
        finally:
            self.server_socket.close()

if __name__ == "__main__":
    GameServer().start()