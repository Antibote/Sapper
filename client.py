import socket
import threading

# Определяем адрес и порт сервера
HOST = '127.0.0.1'
PORT = 65432

# Создаем сокет и подключаемся к серверу
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

def receive_messages():
    """
    Функция для приёма сообщений от сервера и их вывода на экран.
    
    Эта функция выполняется в отдельном потоке, что позволяет клиенту непрерывно получать
    обновления (например, комментарии игры или уведомления) от сервера.
    """
    while True:
        try:
            data = client.recv(1024).decode()
            if not data:
                break
            print(data)
            # Если получено сообщение о выигрыше или проигрыше, прекращаем приём сообщений
            if "lose" in data or "win" in data:
                break
        except Exception as e:
            print("Ошибка приёма:", e)
            break

# Запускаем отдельный поток для приёма сообщений от сервера
threading.Thread(target=receive_messages, daemon=True).start()

# Основной цикл: считываем ввод пользователя и отправляем его на сервер
while True:
    message = input("-> ")
    try:
        client.send(message.encode())
    except Exception as e:
        print("Ошибка отправки сообщения:", e)
        break