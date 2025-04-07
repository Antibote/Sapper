import socket
import threading

# Определяем адрес и порт сервера
HOST = '127.0.0.1'
PORT = 65432

# Глобальные переменные для управления клиентскими соединениями и игровыми данными:
clients = []               # Список для хранения клиентских сокетов
player_mines = {}          # Словарь, сопоставляющий клиентский сокет с множеством координат мин
player_names = {}          # Словарь, сопоставляющий клиентский сокет с именем игрока 
start_game_event = threading.Event()  # Событие, сигнализирующее о начале игры
lock = threading.Lock()    # Блокировка для синхронизации доступа к общим данным между потоками

def broadcast(message):
    """
    Функция для отправки сообщения всем подключённым клиентам.
    
    Перебирает все клиентские сокеты и отправляет указанное сообщение.
    Использование блокировки гарантирует, что потоки не будут одновременно пытаться отправить данные.
    """
    with lock:
        for client in clients:
            try:
                client.send(message.encode())
            except Exception as e:
                print("Ошибка отправки сообщения:", e)

def handle_client(client_socket):
    """
    Функция для обработки взаимодействия с подключённым клиентом.
    
    Эта функция выполняется в отдельном потоке для каждого клиента. 
    Сначала запрашиваются координаты мин у игрока, затем происходит ожидание подключения второго игрока,
    после чего начинается игровой цикл, где клиент отправляет свои ходы.
    При каждом ходе сервер рассылает комментарии всем игрокам.
    """
    # Получаем адрес подключённого клиента для логирования
    addr = client_socket.getpeername()
    
    # Назначаем имя игрока в зависимости от порядка подключения
    with lock:
        player_id = f"Player {len(clients)}"
        player_names[client_socket] = player_id

    # Запрашиваем у игрока ввод 5 координат мин через пробел
    client_socket.send("Enter 5 mine coordinates separated by space:".encode())
    data = client_socket.recv(1024).decode().strip().split()
    
    # Проверяем корректность ввода
    if len(data) != 5:
        client_socket.send("Invalid input. Closing connection.".encode())
        client_socket.close()
        return

    # Сохраняем координаты мин для текущего игрока
    with lock:
        player_mines[client_socket] = set(data)
    print(f"{player_id} {addr} set mines: {data}")
    
    # Уведомляем всех игроков об установке мин
    broadcast(f"{player_id} has set mines.")

    # Ожидание второго игрока
    if not start_game_event.is_set():
        client_socket.send("Waiting for second player...".encode())
        start_game_event.wait()

    # Старт игры
    client_socket.send("Game start!".encode())

    # Счётчик попаданий по минам противника
    exploded_mines = 0
    while exploded_mines < 5:
        try:
            # Получаем ход игрока
            move = client_socket.recv(1024).decode().strip()
            if not move:
                break
        except Exception as e:
            print("Ошибка приёма данных от", player_id, ":", e)
            break

        # Поиск мин противника
        with lock:
            opponent_socket = None
            for c in clients:
                if c != client_socket:
                    opponent_socket = c
                    break
            opponent_mines = player_mines.get(opponent_socket, set())

        # Формируем комментарий
        commentary = f"{player_names[client_socket]} chooses coordinate: {move}. "
        if move in opponent_mines:
            exploded_mines += 1
            commentary += f"BOOM! {exploded_mines}/5"
        else:
            commentary += "No hit."
        
        # Рассылаем комментарий
        broadcast(commentary)
        
        # Проверка условия победы
        if exploded_mines >= 5:
            client_socket.send("You lose.".encode())
            if opponent_socket:
                try:
                    opponent_socket.send("You win!".encode())
                except Exception as e:
                    print("Ошибка при уведомлении оппонента:", e)
            break

    # Завершение соединения
    client_socket.close()

# Создаём серверный сокет (IPv4, TCP)
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(2)  # Прослушиваем до 2 подключений
print(f"Server started on {HOST}:{PORT}")

# Основной цикл принятия подключений
while True:
    client_socket, addr = server.accept()
    with lock:
        clients.append(client_socket)
    print(f"Player {addr} connected.")
    
    # Запуск обработчика клиента
    threading.Thread(target=handle_client, args=(client_socket,)).start()
    
    # Активация игры при подключении двух игроков
    with lock:
        if len(clients) == 2:
            start_game_event.set()