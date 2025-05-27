import pygame
import socket
import pickle
import threading
import sys
import os
import time

# Константы
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

class StoryScreen:
    def __init__(self):
        self.font = None
        self.story_timer = 0
        self.current_stage = "waiting"
        self.story_images = []
        self.story_texts = [
            "Алиса сидела со старшей сестрой на берегу и маялась от безделья...",
            "Вдруг мимо пробежал Белый Кролик с часами...",
            "Алиса, недолго думая, побежала за ним...",
            "И упала в глубокую-преглубокую нору..."
        ]
        self.current_text_index = 0
        self.text_alpha = 0
        self.lobby_text = "Ожидание второго игрока..."
        self.ready_text = "Вот-вот начнется ваша история..."
        self.lobby_text_progress = 0
        self.dots_count = 0
        self.dots_timer = 0
        self.text_speed = 0.3
        self.scene_duration = 8.0
        self.ready_timer = 0
        self.ready_duration = 3.0
        self.text_box_width = SCREEN_WIDTH - 100
        self.text_box_height = 150
        self.transition_delay = 1.0
        self.load_resources()

    def update(self, dt):
        """Обновляет состояние истории"""
        if self.current_stage == "waiting":
            # Анимация точек в ожидании
            self.dots_timer += dt
            if self.dots_timer >= 0.7:
                self.dots_timer = 0
                self.dots_count = (self.dots_count + 1) % 4
            
            # Анимация появления текста
            self.lobby_text_progress = min(1.0, self.lobby_text_progress + dt * self.text_speed)
            
        elif self.current_stage == "ready":
            self.ready_timer += dt
            self.lobby_text_progress = min(1.0, self.lobby_text_progress + dt * self.text_speed)
            if self.ready_timer >= self.ready_duration:
                print("StoryScreen: Переход из ready в story")
                self.current_stage = "story"
                self.story_timer = 0
                self.current_text_index = 0
                self.text_alpha = 0
                
        elif self.current_stage == "story":
            self.story_timer += dt
            
            if self.story_timer >= self.scene_duration:
                print(f"StoryScreen: Следующая сцена {self.current_text_index + 1}/{len(self.story_texts)}")
                self.story_timer = 0
                self.current_text_index += 1
                self.text_alpha = 0
                
                # Проверяем, закончились ли все сцены
                if self.current_text_index >= len(self.story_texts):
                    print("StoryScreen: Все сцены показаны, ожидаем перед переходом в игру")
                    self.story_timer = 0
                    self.current_stage = "transition"
            else:
                self.text_alpha = min(255, int((self.story_timer / 2) * 255))
                
        elif self.current_stage == "transition":
            self.story_timer += dt
            if self.story_timer >= self.transition_delay:
                print("StoryScreen: Переход в game")
                self.current_stage = "game"

    def draw(self, screen):
        """Отрисовывает экран истории"""
        if self.current_stage in ["waiting", "ready"]:
            screen.fill((0, 0, 0))
            
            # Выбираем текст в зависимости от стадии
            current_text = self.ready_text if self.current_stage == "ready" else self.lobby_text
            
            # Вычисляем видимую часть текста
            visible_chars = int(len(current_text) * self.lobby_text_progress)
            display_text = current_text[:visible_chars]
            
            # Добавляем анимированные точки только для waiting
            if self.current_stage == "waiting":
                display_text += "." * self.dots_count
            
            # Разбиваем текст на строки
            lines = self.wrap_text(display_text, self.text_box_width)
            
            # Отрисовываем каждую строку
            y = SCREEN_HEIGHT//2 - (len(lines) * 30)//2
            for line in lines:
                text = self.font.render(line, True, (255, 255, 255))
                text_rect = text.get_rect(center=(SCREEN_WIDTH//2, y))
                screen.blit(text, text_rect)
                y += 30
            
        elif self.current_stage in ["story", "transition"]:
            if self.current_text_index < len(self.story_images):
                screen.blit(self.story_images[self.current_text_index], (0, 0))
                
            if self.current_text_index < len(self.story_texts):
                full_text = self.story_texts[self.current_text_index]
                text_progress = min(1.0, (self.story_timer * self.text_speed))
                visible_chars = int(len(full_text) * text_progress)
                current_text = full_text[:visible_chars]
                
                if current_text:
                    # Создаем полупрозрачный фон для текста
                    bg_rect = pygame.Rect(
                        (SCREEN_WIDTH - self.text_box_width)//2,
                        SCREEN_HEIGHT - self.text_box_height - 20,
                        self.text_box_width,
                        self.text_box_height
                    )
                    bg_surface = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                    bg_surface.fill((0, 0, 0, 180))
                    screen.blit(bg_surface, bg_rect)
                    
                    # Разбиваем текст на строки
                    lines = self.wrap_text(current_text, self.text_box_width - 40)
                    
                    # Отрисовываем каждую строку
                    y = bg_rect.y + 20
                    for line in lines:
                        text = self.font.render(line, True, (255, 255, 255))
                        text.set_alpha(self.text_alpha)
                        text_rect = text.get_rect(center=(SCREEN_WIDTH//2, y))
                        screen.blit(text, text_rect)
                        y += 30

    def load_resources(self):
        """Загружает шрифт и картинки для истории"""
        try:
            self.font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), 36)
        except:
            self.font = pygame.font.Font(None, 36)
            
        # Загружаем картинки для истории
        try:
            for i in range(1, 5):  # 4 картинки для истории
                # Пробуем загрузить jpg файл
                try:
                    image_path = os.path.join("assets", "story", f"story_{i}.jpg")
                    image = pygame.image.load(image_path).convert()
                except:
                    # Если jpg не найден, пробуем png
                    image_path = os.path.join("assets", "story", f"story_{i}.png")
                    image = pygame.image.load(image_path).convert_alpha()
                
                image = pygame.transform.scale(image, (SCREEN_WIDTH, SCREEN_HEIGHT))
                self.story_images.append(image)
                print(f"Загружена картинка истории {i}: {image_path}")
                
        except Exception as e:
            print(f"Ошибка загрузки картинок истории: {e}")
            print("Проверьте наличие файлов .jpg или .png в папке assets/story/")
            # Создаем пустые поверхности если картинки не найдены
            for _ in range(4):
                surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                surface.fill((0, 0, 0))
                self.story_images.append(surface)

    def wrap_text(self, text, max_width):
        """Разбивает текст на строки, чтобы он помещался в заданную ширину"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            # Пробуем добавить следующее слово
            test_line = ' '.join(current_line + [word])
            test_surface = self.font.render(test_line, True, (255, 255, 255))
            
            # Если текст не помещается, начинаем новую строку
            if test_surface.get_width() > max_width:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
            else:
                current_line.append(word)
        
        # Добавляем последнюю строку
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines

    def set_initial_stage(self, is_host):
        """Устанавливает начальное состояние в зависимости от роли"""
        self.current_stage = "waiting"  # Всегда начинаем с waiting
        self.ready_timer = 0
        self.lobby_text_progress = 0
        self.story_timer = 0
        self.current_text_index = 0
        self.text_alpha = 0

class NetworkManager:
    def __init__(self, host, is_host, story_screen):
        self.host = host
        self.is_host = is_host
        self.story_screen = story_screen
        # Добавляем обратную ссылку на NetworkManager в StoryScreen
        self.story_screen.network_manager = self
        
        self.connection_established = False
        self.other_player_connected = False
        self.connection_attempts = 0
        self.max_connection_attempts = 30
        self.connection_timeout = 5.0
        self.last_connection_attempt = time.time()
        self.last_sync_time = time.time()
        self.sync_interval = 0.05

        # Устанавливаем начальное состояние
        self.story_screen.set_initial_stage(is_host)

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
                    # Отправляем подтверждение клиенту
                    confirm_data = pickle.dumps({
                        "type": "connection_confirm",
                        "connected": True,
                        "story": {
                            "stage": "ready",  # Начинаем с ready
                            "text_index": 0,
                            "timer": 0
                        }
                    })
                    self.socket.sendto(confirm_data, self.other_address)
                    print("Хост: Отправлено подтверждение подключения")
                    
                    # Устанавливаем состояние подключения
                    self.connection_established = True
                    self.other_player_connected = True
                    
                except Exception as e:
                    print(f"Ошибка при отправке подтверждения подключения: {e}")

            if not self.connection_established:
                self.connection_established = True
                self.other_player_connected = True
                print(f"{'Хост' if self.is_host else 'Клиент'}: Соединение установлено!")
                
                # Если мы клиент, переходим в ready
                if not self.is_host:
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
                    
                    # Клиент тоже переходит в ready при получении подтверждения
                    if not self.is_host:
                        print("Клиент: Переход в ready")
                        self.story_screen.current_stage = "ready"
                        self.story_screen.ready_timer = 0
                        self.story_screen.lobby_text_progress = 0
                        
                        # Отправляем ответное подтверждение
                        confirm_data = pickle.dumps({
                            "type": "connection_confirm",
                            "connected": True,
                            "story": {
                                "stage": "ready",
                                "text_index": self.story_screen.current_text_index,
                                "timer": self.story_screen.story_timer
                            }
                        })
                        self.socket.sendto(confirm_data, self.other_address)
                
                # Синхронизация состояния истории
                if "story" in received_data:
                    story_data = received_data["story"]
                    if story_data.get("stage") == "ready":
                        # Принудительно переходим в ready при получении этого состояния
                        self.story_screen.current_stage = "ready"
                        self.story_screen.ready_timer = story_data.get("timer", 0)
                        self.story_screen.lobby_text_progress = 0
                    else:
                        self.story_screen.sync_state(
                            story_data.get("stage", "waiting"),
                            story_data.get("text_index", 0),
                            story_data.get("timer", 0)
                        )
                    
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