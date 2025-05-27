import socket
import pickle
import threading
import time

class NetworkManager:
    def __init__(self, host, is_host, story_screen):
        self.host = host
        self.is_host = is_host
        self.story_screen = story_screen
        self.connection_established = False
        self.other_player_connected = False
        self.connection_attempts = 0
        self.max_connection_attempts = 30
        self.connection_timeout = 5.0
        self.last_connection_attempt = time.time()
        self.last_sync_time = time.time()
        self.sync_interval = 0.05

        # Настройка сети
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.settimeout(0.1)
            
            # Настройка портов
            host_port = 5000
            client_port = 5001
            
            if is_host:
                self.socket.bind(('0.0.0.0', host_port))
                self.other_address = (host, client_port)
                print(f"Хост: Сервер запущен на порту {host_port}")
            else:
                self.socket.bind(('0.0.0.0', client_port))
                self.other_address = (host, host_port)
                print(f"Клиент: Подключение к хосту на порт {host_port}")
                # Клиент сразу отправляет сообщение о подключении
                self.send_connection_message()
            
            # Запуск потока для приема данных
            self.receive_thread = threading.Thread(target=self.receive_data)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            
        except Exception as e:
            print(f"Критическая ошибка при инициализации сети: {e}")
            raise

    def send_connection_message(self):
        """Отправляет сообщение о подключении"""
        try:
            data = pickle.dumps({
                "type": "connection",
                "connected": True,
                "story": {
                    "stage": self.story_screen.current_stage,
                    "text_index": self.story_screen.current_text_index,
                    "timer": self.story_screen.story_timer
                },
                "timestamp": time.time(),
                "is_host": self.is_host
            })
            print(f"{'Хост' if self.is_host else 'Клиент'}: Отправка сообщения о подключении на {self.other_address}")
            self.socket.sendto(data, self.other_address)
            self.connection_attempts += 1
            self.last_connection_attempt = time.time()
        except Exception as e:
            print(f"Ошибка при отправке сообщения о подключении: {e}")

    def handle_connection(self, received_data):
        """Обрабатывает подключение второго игрока"""
        if received_data.get("type") == "connection" and received_data.get("connected", False):
            print(f"{'Хост' if self.is_host else 'Клиент'}: Получено сообщение о подключении")
            
            # Если мы хост и получили сообщение от клиента
            if self.is_host and not self.connection_established:
                try:
                    # Отправляем подтверждение клиенту с текущим состоянием
                    confirm_data = pickle.dumps({
                        "type": "connection_confirm",
                        "connected": True,
                        "story": {
                            "stage": "ready",
                            "text_index": 0,
                            "timer": 0
                        }
                    })
                    self.socket.sendto(confirm_data, self.other_address)
                    print("Хост: Отправлено подтверждение подключения")
                    
                    # Устанавливаем состояние подключения
                    self.connection_established = True
                    self.other_player_connected = True
                    
                    # Переводим хоста в состояние ready
                    self.story_screen.current_stage = "ready"
                    self.story_screen.ready_timer = 0
                    self.story_screen.lobby_text_progress = 0
                    
                except Exception as e:
                    print(f"Ошибка при отправке подтверждения подключения: {e}")

            # Если мы клиент и получили подтверждение от хоста
            elif not self.is_host and not self.connection_established:
                self.connection_established = True
                self.other_player_connected = True
                print("Клиент: Соединение установлено!")
                
                # Переводим клиента в состояние ready
                self.story_screen.current_stage = "ready"
                self.story_screen.ready_timer = 0
                self.story_screen.lobby_text_progress = 0

    def receive_data(self):
        """Получение данных от другого игрока"""
        while True:
            try:
                data, addr = self.socket.recvfrom(4096)
                received_data = pickle.loads(data)
                
                # Обработка сообщений о подключении
                if received_data.get("type") == "connection":
                    self.handle_connection(received_data)
                    
                elif received_data.get("type") == "connection_confirm":
                    print(f"{'Хост' if self.is_host else 'Клиент'}: Получено подтверждение подключения")
                    self.connection_established = True
                    self.other_player_connected = True
                    
                    # Клиент переходит в ready при получении подтверждения
                    if not self.is_host:
                        print("Клиент: Переход в ready")
                        self.story_screen.current_stage = "ready"
                        self.story_screen.ready_timer = 0
                        self.story_screen.lobby_text_progress = 0
                
                # Синхронизация состояния истории
                elif received_data.get("type") == "story_sync":
                    story_data = received_data.get("story", {})
                    self.sync_story_state(story_data)
                    
            except socket.timeout:
                if not self.connection_established:
                    current_time = time.time()
                    if (current_time - self.last_connection_attempt >= 1.0 and 
                        self.connection_attempts < self.max_connection_attempts):
                        self.send_connection_message()
                continue
            except Exception as e:
                print(f"Ошибка при получении данных: {e}")
                continue

    def sync_story_state(self, story_data):
        """Синхронизирует состояние истории"""
        if not story_data:
            return
            
        stage = story_data.get("stage", "waiting")
        if stage != self.story_screen.current_stage:
            print(f"StoryScreen: Синхронизация - переход из {self.story_screen.current_stage} в {stage}")
            self.story_screen.current_stage = stage
            
            if stage == "ready":
                self.story_screen.ready_timer = story_data.get("timer", 0)
                self.story_screen.lobby_text_progress = 0
            elif stage == "story":
                self.story_screen.current_text_index = story_data.get("text_index", 0)
                self.story_screen.story_timer = story_data.get("timer", 0)
            elif stage == "game":
                print("StoryScreen: Синхронизация - переход в игру")
                self.story_screen.current_text_index = len(self.story_screen.story_texts)

    def close(self):
        """Закрывает сетевое соединение"""
        try:
            self.socket.close()
        except:
            pass

    def send_data(self, data):
        """Отправляет данные другому игроку"""
        try:
            self.socket.sendto(data, self.other_address)
        except Exception as e:
            print(f"Ошибка при отправке данных: {e}") 