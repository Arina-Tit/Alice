import pygame
import socket
import pickle
import threading
import sys
import os
import time
import random
import json
import pygame.font

# Инициализация Pygame
pygame.init()

# Константы
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
WORLD_WIDTH = 3000
WORLD_HEIGHT = 1000

# Размеры персонажей
ALICE_WIDTH = 192
ALICE_HEIGHT = 192
RABBIT_WIDTH = 80
RABBIT_HEIGHT = 80
ALICE_OFFSET = 70
RABBIT_OFFSET = 10

# Физика
GRAVITY = 0.5
ALICE_JUMP_FORCE = -12
RABBIT_JUMP_FORCE = -20
ALICE_MOVE_SPEED = 6
RABBIT_MOVE_SPEED = 8

# Скорости анимации
ALICE_ANIMATION_SPEED = 0.04
RABBIT_IDLE_ANIMATION_SPEED = 0.15
RABBIT_WALK_ANIMATION_SPEED = 0.06

DIRT_BROWN = (65, 50, 35)  
DIRT_DARK = (55, 40, 25)   
DIRT_LIGHT = (75, 60, 45)  
PLATFORM_HEIGHT = 50  
SHADOW_HEIGHT = 400  
SHADOW_ALPHA = 200  

# Константы для диалогов
DIALOG_PADDING = 40
DIALOG_WIDTH = 700
DIALOG_HEIGHT = 200
CHOICE_HEIGHT = 40
CHOICE_PADDING = 10
FONT_SIZE = 24
TEXT_COLOR = (255, 255, 255)
CHOICE_COLOR = (200, 200, 200)
CHOICE_HOVER_COLOR = (255, 255, 100)
DIALOG_TRIGGER_DISTANCE = 150
DIALOG_PROMPT_COLOR = (255, 255, 100)
CHOICE_INDENT = 20
EXIT_HINT_DURATION = 3.0

# Константы для платформ и препятствий
PLATFORM_COLOR = (139, 69, 19)
ALICE_PLATFORM_COLOR = (100, 149, 237)
RABBIT_PLATFORM_COLOR = (255, 165, 0)
SWITCH_COLOR = (255, 215, 0)
DOOR_COLOR = (160, 82, 45)
COLLECTIBLE_COLOR = (255, 20, 147)

# Импортируем только необходимые классы из game.py
from game import (SpriteSheet, Camera, Player, DialogSystem, Platform, 
                 AnimatedKey, Potion, Lamp, Decoration, MovingPlatform, Flag, Sign)

class Game:
    def __init__(self, host, is_host):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("P2P Game - Level 2")
        self.clock = pygame.time.Clock()
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)
        
        # Флаг для контроля состояния сокета
        self.socket_active = True
        
        # Создаем фон и платформу
        self.background = self.create_background()
        self.platform = self.create_platform()
        self.shadow = self.create_shadow()
        
        # Загружаем диалоги для второго уровня
        dialog_file = os.path.join("assets", "dialogs", "level2_dialog.json")
        try:
            with open(dialog_file, 'r', encoding='utf-8') as f:
                self.dialogs = json.load(f)
                print(f"Загружен диалог для уровня 2: {dialog_file}")
        except Exception as e:
            print(f"Ошибка загрузки диалога level2_dialog.json: {e}")
            self.dialogs = {}
        
        # Создание игроков с соответствующими спрайтами
        platform_y = WORLD_HEIGHT - PLATFORM_HEIGHT
        if is_host:
            self.my_player = Player(100, platform_y - ALICE_HEIGHT + ALICE_OFFSET, "alice")
            self.other_player = Player(250, platform_y - RABBIT_HEIGHT + RABBIT_OFFSET, "rabbit")
        else:
            self.my_player = Player(250, platform_y - RABBIT_HEIGHT + RABBIT_OFFSET, "rabbit")
            self.other_player = Player(100, platform_y - ALICE_HEIGHT + ALICE_OFFSET, "alice")

        # Добавляем флаг для контроля завершения работы
        self.is_shutting_down = False
        
        # Настройка сети
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if is_host:
            self.socket.bind((host, 5000))
            self.other_address = (host, 5001)
        else:
            self.socket.bind((host, 5001))
            self.other_address = (host, 5000)

        # Устанавливаем таймаут для сокета
        self.socket.settimeout(0.1)

        # Запуск потока для приема данных
        self.receive_thread = threading.Thread(target=self.receive_data, daemon=False)
        self.receive_thread.start()

        # Добавляем систему диалогов с новым диалогом
        self.dialog_system = DialogSystem()
        self.dialog_system.dialogs = self.dialogs  # Устанавливаем диалоги из level2_dialog.json
        self.is_host = is_host
        
        # Инициализируем состояние диалога
        self.dialog_state = {
            "is_active": False,
            "current_dialog_id": None,
            "current_speaker": None,
            "dialog_completed": False
        }
        
        # Создаем игровые объекты
        self.platforms = self.create_platforms()
        self.animated_keys = self.create_animated_keys()
        self.potions = self.create_potions()
        self.lamps = self.create_lamps()
        self.decorations = self.create_decorations()
        self.signs = self.create_signs()
        self.collected_keys = 0
        self.collected_potions = 0
        self.moving_platforms = self.create_moving_platforms()
        
        # Состояние финала
        self.victory_achieved = False
        self.victory_timer = 0
        self.victory_duration = 5.0
        
        # Если мы хост, инициируем первый диалог после небольшой задержки
        if is_host:
            self.initial_dialog_timer = 2.0
        else:
            self.initial_dialog_timer = None

    def create_shadow(self):
        """Создает градиент затемнения сверху"""
        shadow = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        
        # Создаем градиент от темного к прозрачному
        for y in range(SHADOW_HEIGHT):
            # Нелинейный градиент для более плавного перехода
            progress = y / SHADOW_HEIGHT
            alpha = int(SHADOW_ALPHA * (1 - progress * progress))
            pygame.draw.line(shadow, (0, 0, 0, alpha), (0, y), (SCREEN_WIDTH, y))
            
        return shadow

    def create_platform(self):
        """Создает платформу для ходьбы"""
        platform = pygame.Surface((SCREEN_WIDTH, PLATFORM_HEIGHT))
        platform.fill(DIRT_BROWN)
        
        # Добавляем текстуру на платформу
        for _ in range(500):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, PLATFORM_HEIGHT)
            size = random.randint(2, 4)
            color = random.choice([DIRT_DARK, DIRT_LIGHT])
            pygame.draw.ellipse(platform, color, (x, y, size, size * 0.7))
        
        # Добавляем верхнюю границу платформы
        pygame.draw.line(platform, DIRT_LIGHT, (0, 0), (SCREEN_WIDTH, 0), 2)
        
        return platform

    def create_background(self):
        """Создает многослойный фон с параллаксом"""
        backgrounds = {}
        
        try:
            # Загружаем 3 слоя фона
            bg1 = pygame.image.load(os.path.join("assets", "tiles", "BG_3.png")).convert_alpha()
            bg2 = pygame.image.load(os.path.join("assets", "tiles", "BG_2.png")).convert_alpha()
            bg3 = pygame.image.load(os.path.join("assets", "tiles", "BG_1.png")).convert_alpha()
            
            # Сохраняем пропорции при масштабировании
            def scale_bg_preserve_ratio(bg):
                bg_ratio = bg.get_width() / bg.get_height()
                screen_ratio = SCREEN_WIDTH / SCREEN_HEIGHT
                
                if bg_ratio > screen_ratio:
                    new_height = SCREEN_HEIGHT
                    new_width = int(new_height * bg_ratio)
                else:
                    new_width = SCREEN_WIDTH
                    new_height = int(new_width / bg_ratio)
                
                return pygame.transform.scale(bg, (new_width, new_height))
            
            # Масштабируем фоны с сохранением пропорций
            backgrounds['layer1'] = scale_bg_preserve_ratio(bg1)
            backgrounds['layer2'] = scale_bg_preserve_ratio(bg2)
            backgrounds['layer3'] = scale_bg_preserve_ratio(bg3)
            
        except Exception as e:
            print(f"Ошибка загрузки фона: {e}")
            # Fallback - создаем простой градиентный фон
            background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            for y in range(SCREEN_HEIGHT):
                color_value = max(20, 80 - (y * 60 // SCREEN_HEIGHT))
                color = (color_value, color_value - 10, color_value - 5)
                pygame.draw.line(background, color, (0, y), (SCREEN_WIDTH, y))
            
            backgrounds['layer1'] = background
            backgrounds['layer2'] = background.copy()
            backgrounds['layer3'] = background.copy()
        
        return backgrounds

    def create_platforms(self):
        """Создает платформы и препятствия для кооперативного прохождения"""
        platforms = []
        
        # Обычные платформы для прыжков
        platforms.append(Platform(1000, 650, 100, 20))
        platforms.append(Platform(1300, 600, 100, 20))
        
        # Высокие платформы для зайца
        platforms.append(Platform(1600, 500, 120, 20))
        platforms.append(Platform(1900, 450, 100, 20))
        platforms.append(Platform(2200, 400, 100, 20))
        
        # Низкие платформы для Алисы
        platforms.append(Platform(1800, 820, 100, 20, "alice_trigger"))
        platforms.append(Platform(2000, 800, 100, 20, "alice_trigger"))
        
        # Специальные платформы
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT
        platforms.append(Platform(1100, ground_level - 80, 100, 20))
        platforms.append(Platform(1400, ground_level - 100, 120, 20))
        
        # Дополнительные платформы
        platforms.append(Platform(1750, ground_level - 100, 90, 20))
        platforms.append(Platform(2450, ground_level - 120, 100, 20))
        
        # Финальные платформы
        platforms.append(Platform(2800, 600, 150, 20))
        platforms.append(Platform(3000, 550, 150, 20))
        platforms.append(Platform(3200, 500, 200, 20))
        
        # Дополнительная платформа для доступа к предметам
        platforms.append(Platform(850, ground_level - 120, 80, 20))
        
        return platforms

    def create_animated_keys(self):
        """Создает анимированные ключи"""
        keys = []
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT
        
        keys.append(AnimatedKey(1120, ground_level - 112, "key2"))
        keys.append(AnimatedKey(1650, 470, "key5"))
        keys.append(AnimatedKey(770, WORLD_HEIGHT - PLATFORM_HEIGHT - 32, "key15"))
        
        return keys

    def create_potions(self):
        """Создает зелья"""
        potions = []
        
        potions.append(Potion(620, WORLD_HEIGHT - PLATFORM_HEIGHT - 92, "red"))
        potions.append(Potion(1750, 420, "green"))
        potions.append(Potion(1770, WORLD_HEIGHT - PLATFORM_HEIGHT - 132, "blue"))
        
        return potions

    def create_lamps(self):
        """Создает фонари"""
        lamps = []
        
        # Фонари на уровне земли
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT - 64  # На уровне земли
        lamps.append(Lamp(750, ground_level))   # У старта
        lamps.append(Lamp(1250, ground_level))  # На пути
        lamps.append(Lamp(1750, ground_level))  # У платформ Алисы
        lamps.append(Lamp(2150, ground_level))  # У высоких платформ зайца
        lamps.append(Lamp(2750, ground_level))  # У финала
        
        # Фонари на платформах (корректируем высоту)
        lamps.append(Lamp(1620, 436))  # На высокой платформе (500 - 64)
        lamps.append(Lamp(2820, 536))  # На финальной платформе (600 - 64)
        
        return lamps

    def create_decorations(self):
        """Создает декорации"""
        decorations = []
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT - 32
        
        decorations.append(Decoration(700, ground_level, "rock1"))
        decorations.append(Decoration(1500, ground_level, "grass2"))
        decorations.append(Decoration(2100, ground_level, "fence"))
        decorations.append(Decoration(2700, ground_level, "rock2"))
        
        decorations.append(Decoration(1020, 620, "grass2"))
        decorations.append(Decoration(1320, 570, "fence"))
        decorations.append(Decoration(1620, 470, "rock1"))
        decorations.append(Decoration(1920, 420, "grass3"))
        decorations.append(Decoration(2220, 370, "rock2"))
        
        decorations.append(Decoration(1770, ground_level - 100, "rock3"))
        decorations.append(Decoration(2470, ground_level - 120, "fence"))
        
        return decorations

    def create_signs(self):
        """Создает знаки"""
        signs = []
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT - 48
        
        signs.append(Sign(2850, 550))
        signs.append(Sign(2850, ground_level))
        
        return signs

    def create_moving_platforms(self):
        """Создает подвижные платформы"""
        moving_platforms = []
        
        moving_platforms.append(MovingPlatform(1500, 600, 100, 20, 0, 0, "moving", "horizontal"))
        moving_platforms.append(MovingPlatform(2100, 550, 100, 20, 0, 0, "moving", "horizontal"))
        moving_platforms.append(MovingPlatform(1700, 700, 100, 20, 0, 0, "moving", "vertical"))
        moving_platforms.append(MovingPlatform(2300, 650, 100, 20, 0, 0, "moving", "vertical"))
        
        for platform in moving_platforms:
            platform.activate()
        
        return moving_platforms

    def draw_ui(self, screen):
        """Отрисовка пользовательского интерфейса"""
        if not self.dialog_system.dialog_completed:
            return
            
        try:
            pixel_font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), 20)
        except:
            pixel_font = pygame.font.Font(None, 20)
        
        keys_text = pixel_font.render(f"Ключи: {self.collected_keys}/3", True, (255, 255, 255))
        screen.blit(keys_text, (10, 10))
        
        potions_text = pixel_font.render(f"Зелья: {self.collected_potions}/3", True, (255, 255, 255))
        screen.blit(potions_text, (10, 35))
        
        if self.collected_keys == 3 and self.collected_potions == 3:
            victory_text = pixel_font.render("Все предметы собраны! Найдите выход из сада!", True, (0, 255, 0))
            screen.blit(victory_text, (10, SCREEN_HEIGHT - 30))
        else:
            hint_text = pixel_font.render("Соберите все предметы, чтобы найти выход!", True, (255, 200, 0))
            screen.blit(hint_text, (10, SCREEN_HEIGHT - 30))

    def draw_background_with_parallax(self, screen):
        """Отрисовывает многослойный фон с эффектом параллакса"""
        parallax_factor_1 = 0.1
        parallax_factor_2 = 0.3
        parallax_factor_3 = 0.5
        parallax_factor_4 = 0.7
        
        offset_1 = int(self.camera.scroll_x * parallax_factor_1)
        offset_2 = int(self.camera.scroll_x * parallax_factor_2)
        offset_3 = int(self.camera.scroll_x * parallax_factor_3)
        offset_4 = int(self.camera.scroll_x * parallax_factor_4)
        
        screen.fill((0, 0, 0))
        
        if 'layer1' in self.background:
            screen.blit(self.background['layer1'], (-offset_1, 0))
            if offset_1 > 0:
                screen.blit(self.background['layer1'], (SCREEN_WIDTH - offset_1, 0))
        
        if 'layer2' in self.background:
            screen.blit(self.background['layer2'], (-offset_2, 0))
            if offset_2 > 0:
                screen.blit(self.background['layer2'], (SCREEN_WIDTH - offset_2, 0))
        
        if 'layer3' in self.background:
            screen.blit(self.background['layer3'], (-offset_3, 0))
            if offset_3 > 0:
                screen.blit(self.background['layer3'], (SCREEN_WIDTH - offset_3, 0))
        
        if 'layer4' in self.background:
            screen.blit(self.background['layer4'], (-offset_4, 0))
            if offset_4 > 0:
                screen.blit(self.background['layer4'], (SCREEN_WIDTH - offset_4, 0))

    def draw_victory_screen(self, screen):
        """Отрисовывает экран победы"""
        if not self.victory_achieved:
            return
            
        white_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        white_surface.fill((255, 255, 255))
        white_alpha = min(255, int(self.victory_timer * 255))
        white_surface.set_alpha(white_alpha)
        screen.blit(white_surface, (0, 0))
        
        if self.victory_timer > 1:
            try:
                font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), 48)
            except:
                font = pygame.font.Font(None, 48)
            
            full_text = "Новые приключения ждут!"
            text_progress = min(1.0, (self.victory_timer - 1) * 0.5)
            visible_chars = int(len(full_text) * text_progress)
            current_text = full_text[:visible_chars]
            
            if current_text:
                text = font.render(current_text, True, (0, 0, 0))
                text_rect = text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
                screen.blit(text, text_rect)
        
        if self.victory_timer > 4 and self.smile_image:
            smile_alpha = min(255, int((self.victory_timer - 4) * 255))
            scaled_image = pygame.transform.scale(self.smile_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
            temp_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            temp_surface.blit(scaled_image, (0, 0))
            temp_surface.set_alpha(smile_alpha)
            screen.blit(temp_surface, (0, 0))

    def check_victory_condition(self):
        """Проверяет условие победы"""
        if self.victory_achieved:
            return
            
        if self.collected_keys < 3 or self.collected_potions < 3:
            return
            
        alice = self.my_player if self.my_player.character_name == "alice" else self.other_player
        rabbit = self.other_player if self.my_player.character_name == "alice" else self.my_player
        
        if len(self.signs) >= 2:
            platform_sign = self.signs[0]
            ground_sign = self.signs[1]
            
            sign_distance = 80
            
            rabbit_near_platform = ((rabbit.x - platform_sign.x) ** 2 + (rabbit.y - platform_sign.y) ** 2) ** 0.5 < sign_distance
            alice_near_ground = ((alice.x - ground_sign.x) ** 2 + (alice.y - ground_sign.y) ** 2) ** 0.5 < sign_distance
            
            if rabbit_near_platform and alice_near_ground:
                self.victory_achieved = True
                self.victory_timer = 0
                print("Победа!")

    def check_platform_activation(self):
        """Проверяет активацию подвижных платформ"""
        triggered_platforms = self.my_player.check_platform_triggers(self.platforms)
        
        for platform in triggered_platforms:
            platform_id = f"{platform.x}_{platform.y}"
            
            if platform.x == 1800:
                if len(self.moving_platforms) > 0 and not self.moving_platforms[0].activated:
                    self.moving_platforms[0].activate()
                    print("Активирована первая подвижная платформа для зайца!")
            elif platform.x == 2000:
                if len(self.moving_platforms) > 1 and not self.moving_platforms[1].activated:
                    self.moving_platforms[1].activate()
                    print("Активирована вторая подвижная платформа для зайца!")

    def make_choice(self, choice_index):
        """Обработка выбора варианта ответа"""
        if not self.dialog_system.my_turn or not self.dialog_system.current_dialog:
            return
        
        if choice_index >= len(self.dialog_system.current_dialog.get("choices", [])):
            return
            
        choice = self.dialog_system.current_dialog["choices"][choice_index]
        next_dialog = choice.get("next")
        
        if next_dialog == "end":
            self.end_dialog()
            try:
                data = pickle.dumps({
                    "type": "dialog_end",
                    "dialog_state": self.dialog_state
                })
                self.socket.sendto(data, self.other_address)
            except Exception as e:
                print(f"Ошибка при отправке завершения диалога: {e}")
                return
            
        if next_dialog and next_dialog in self.dialog_system.dialogs:
            next_dialog_data = self.dialog_system.dialogs[next_dialog]
            next_speaker = next_dialog_data.get("speaker")
            
            self.dialog_state["current_dialog_id"] = next_dialog
            self.dialog_state["current_speaker"] = next_speaker
            self.dialog_state["is_active"] = True
            
            try:
                data = pickle.dumps({
                    "type": "dialog_update",
                    "dialog_state": self.dialog_state
                })
                self.socket.sendto(data, self.other_address)
            except Exception as e:
                print(f"Ошибка при отправке обновления диалога: {e}")
            
            self.dialog_system.reset_state()
            self.dialog_system.start_dialog(next_dialog, self.my_player.character_name)
        else:
            self.end_dialog()

    def receive_data(self):
        """Получение данных от другого игрока"""
        while self.socket_active and not self.is_shutting_down:
            try:
                if not self.socket_active or self.is_shutting_down:
                    break
                    
                data, addr = self.socket.recvfrom(1024)
                if not data:
                    continue
                    
                received_data = pickle.loads(data)
                
                if received_data.get("type") == "dialog_update":
                    dialog_state = received_data.get("dialog_state")
                    if dialog_state:
                        self.dialog_state.update(dialog_state)
                        if dialog_state.get("current_dialog_id"):
                            self.dialog_system.start_dialog(
                                dialog_state["current_dialog_id"],
                                self.my_player.character_name
                            )
                
                elif received_data.get("type") == "dialog_end":
                    self.dialog_system.complete_dialog()
                    self.dialog_state["is_active"] = False
                    self.dialog_state["current_dialog_id"] = None
                    self.dialog_state["current_speaker"] = None
                    self.dialog_state["dialog_completed"] = True
                
                else:
                    # Обработка обычных игровых данных
                    if "player" in received_data:
                        player_data = received_data["player"]
                        self.other_player.x = player_data["x"]
                        self.other_player.y = player_data["y"]
                        self.other_player.facing_right = player_data["facing_right"]
                        self.other_player.moving = player_data["moving"]
                        if "current_state" in player_data:
                            self.other_player.current_state = player_data["current_state"]
                            if self.other_player.current_state != self.other_player.last_state:
                                self.other_player.last_state = self.other_player.current_state
                                self.other_player.sprites[self.other_player.current_state].reset_animation()
                    
                    if "collected_keys" in received_data:
                        for key_index in received_data["collected_keys"]:
                            if key_index < len(self.animated_keys):
                                self.animated_keys[key_index].collected = True
                    
                    if "collected_potions" in received_data:
                        for potion_index in received_data["collected_potions"]:
                            if potion_index < len(self.potions):
                                self.potions[potion_index].collected = True
                    
                    if "counters" in received_data:
                        counters = received_data["counters"]
                        if counters["keys"] > self.collected_keys:
                            self.collected_keys = counters["keys"]
                        if counters["potions"] > self.collected_potions:
                            self.collected_potions = counters["potions"]
                
            except:
                if not self.socket_active or self.is_shutting_down:
                    break
                continue

    def send_data(self):
        """Отправка данных другому игроку"""
        if not self.socket_active:
            return
            
        try:
            # Собираем данные о собранных предметах
            collected_keys_data = []
            for i, key in enumerate(self.animated_keys):
                if key.collected:
                    collected_keys_data.append(i)
            
            collected_potions_data = []
            for i, potion in enumerate(self.potions):
                if potion.collected:
                    collected_potions_data.append(i)
            
            data = pickle.dumps({
                "type": "game_state",
                "player": {
                    "x": self.my_player.x,
                    "y": self.my_player.y,
                    "facing_right": self.my_player.facing_right,
                    "moving": self.my_player.moving,
                    "current_state": self.my_player.current_state
                },
                "collected_keys": collected_keys_data,
                "collected_potions": collected_potions_data,
                "counters": {
                    "keys": self.collected_keys,
                    "potions": self.collected_potions
                }
            })
            if self.socket_active:
                self.socket.sendto(data, self.other_address)
        except socket.error:
            self.socket_active = False
        except Exception as e:
            print(f"Ошибка отправки данных: {e}")
            pass

    def close(self):
        """Корректно закрываем игру и сетевое соединение"""
        self.is_shutting_down = True
        self.socket_active = False
        
        try:
            if hasattr(self, 'socket'):
                try:
                    self.socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                try:
                    self.socket.close()
                except:
                    pass
        except:
            pass
        
        if hasattr(self, 'receive_thread'):
            try:
                self.receive_thread.join(timeout=2.0)
            except:
                pass
        
    def run(self):
        """Основной игровой цикл"""
        running = True
        last_time = time.time()
        try:
            while running:
                current_time = time.time()
                dt = current_time - last_time
                last_time = current_time
                
                if self.is_host and self.initial_dialog_timer is not None:
                    self.initial_dialog_timer -= dt
                    if self.initial_dialog_timer <= 0:
                        self.initial_dialog_timer = None
                        self.start_dialog("start")

                keys = pygame.key.get_pressed()

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                        self.is_shutting_down = True
                        break
                    elif event.type == pygame.KEYDOWN:
                        if (event.key == pygame.K_SPACE or event.key == pygame.K_w) and not self.dialog_system.is_active:
                            self.my_player.jump()
                        else:
                            self.handle_input(event)

                if not running:
                    break

                allow_movement = not self.dialog_system.is_active

                # Обрабатываем нажатия клавиш
                if allow_movement:
                    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                        self.my_player.move(-1)
                    elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                        self.my_player.move(1)
                    else:
                        self.my_player.move(0)
                        self.my_player.moving = False
                        self.my_player.current_state = "idle"
                else:
                    self.my_player.move(0)
                    self.my_player.moving = False
                    self.my_player.current_state = "idle"

                self.my_player._platforms = self.platforms + self.moving_platforms
                self.other_player._platforms = self.platforms + self.moving_platforms
                
                self.my_player.update(self.platforms + self.moving_platforms)
                self.other_player.update(self.platforms + self.moving_platforms)
                
                for key in self.animated_keys:
                    key.update(dt)
                
                for platform in self.moving_platforms:
                    platform.update()
                
                for sign in self.signs:
                    sign.update([self.my_player, self.other_player])
                
                collected = self.my_player.check_collectibles(self.animated_keys)
                if collected:
                    self.collected_keys += len(collected)
                
                collected = self.my_player.check_collectibles(self.potions)
                if collected:
                    self.collected_potions += len(collected)
                
                self.check_platform_activation()
                self.check_victory_condition()
                
                if self.initial_dialog_timer is None:
                    self.check_dialog_trigger()
                
                next_x = self.my_player.x
                next_y = self.my_player.y
                if keys[pygame.K_LEFT]:
                    next_x -= self.my_player.move_speed * 5
                elif keys[pygame.K_RIGHT]:
                    next_x += self.my_player.move_speed * 5
                self.camera.update(next_x, next_y)
                
                self.dialog_system.update(dt)
                
                if self.victory_achieved:
                    self.victory_timer += dt
            
                if self.socket_active:
                    self.send_data()
            
                self.draw_background_with_parallax(self.screen)
                platform_y = SCREEN_HEIGHT - PLATFORM_HEIGHT
                self.screen.blit(self.platform, (0, platform_y))
                
                for platform in self.platforms:
                    platform.draw(self.screen, self.camera)
                for platform in self.moving_platforms:
                    platform.draw(self.screen, self.camera)
                for collectible in self.animated_keys:
                    collectible.draw(self.screen, self.camera)
                for collectible in self.potions:
                    collectible.draw(self.screen, self.camera)
                for lamp in self.lamps:
                    lamp.draw(self.screen, self.camera)
                for decoration in self.decorations:
                    decoration.draw(self.screen, self.camera)
                for sign in self.signs:
                    sign.draw(self.screen, self.camera)
                
                alice = self.my_player if self.my_player.character_name == "alice" else self.other_player
                rabbit = self.other_player if self.my_player.character_name == "alice" else self.my_player
                
                rabbit.draw(self.screen, self.camera)
                alice.draw(self.screen, self.camera)
                
                self.screen.blit(self.shadow, (0, 0))
                self.dialog_system.draw(self.screen, self.my_player.character_name)
                self.draw_ui(self.screen)
                self.draw_victory_screen(self.screen)
            
                pygame.display.flip()
                self.clock.tick(60)
        
        except:
            self.is_shutting_down = True
        finally:
            self.close()
            pygame.quit()

    def handle_input(self, event):
        """Обработка ввода для диалогов"""
        if not self.dialog_system.is_active:
            return

        # Проверяем, что это ход текущего игрока
        current_speaker = self.dialog_system.current_speaker
        if ((self.my_player.character_name == "alice" and current_speaker == "alice") or
            (self.my_player.character_name == "rabbit" and current_speaker == "rabbit")):
            
            choice = self.dialog_system.handle_input(event, self.my_player.character_name)
            if choice is not None:
                print(f"Выбран вариант {choice + 1}")
                self.make_choice(choice)

    def check_dialog_trigger(self):
        """Проверка возможности начать диалог"""
        # Вычисляем расстояние между персонажами
        distance = ((self.my_player.x - self.other_player.x) ** 2 + 
                   (self.my_player.y - self.other_player.y) ** 2) ** 0.5
        
        # Если игроки достаточно близко и диалог не активен и не завершен
        if (distance < DIALOG_TRIGGER_DISTANCE and 
            not self.dialog_system.is_active and 
            not self.dialog_system.dialog_completed):
            
            # Проверяем, кто из персонажей ближе к началу уровня
            if self.my_player.x < self.other_player.x:
                # Если мой персонаж левее, он начинает диалог
                self.start_dialog("start")
            elif self.my_player.x > self.other_player.x and self.is_host:
                # Если мой персонаж правее и я хост, тоже начинаю диалог
                self.start_dialog("start")

    def start_dialog(self, dialog_id):
        """Начало диалога"""
        if not self.dialog_system.dialog_completed:
            # Определяем, кто начинает диалог
            if self.my_player.x < self.other_player.x:
                initial_speaker = self.my_player.character_name
                # Выбираем правильный начальный диалог
                if initial_speaker == "alice":
                    dialog_id = "start_alice"
                else:
                    dialog_id = "start"
            else:
                initial_speaker = self.other_player.character_name
                if initial_speaker == "alice":
                    dialog_id = "start_alice"
                else:
                    dialog_id = "start"
            
            print(f"Начинаем диалог: {dialog_id} (говорит {initial_speaker})")
            self.dialog_system.start_dialog(dialog_id, self.my_player.character_name)
            self.dialog_state["is_active"] = True
            self.dialog_state["current_dialog_id"] = dialog_id
            self.dialog_state["current_speaker"] = initial_speaker
            
            # Отправляем сообщение о начале диалога
            try:
                data = pickle.dumps({
                    "type": "dialog_update",
                    "dialog_state": self.dialog_state
                })
                self.socket.sendto(data, self.other_address)
            except Exception as e:
                print(f"Ошибка при отправке начала диалога: {e}")

    def end_dialog(self):
        """Завершение диалога"""
        print("Завершаем диалог")
        self.dialog_system.complete_dialog()
        self.dialog_state["is_active"] = False
        self.dialog_state["current_dialog_id"] = None
        self.dialog_state["current_speaker"] = None
        self.dialog_state["dialog_completed"] = True
        
        try:
            data = pickle.dumps({
                "type": "dialog_end",
                "dialog_state": self.dialog_state
            })
            self.socket.sendto(data, self.other_address)
        except Exception as e:
            print(f"Ошибка при отправке завершения диалога: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python level2.py [host/client]")
        sys.exit(1)

    is_host = sys.argv[1].lower() == "host"
    game = Game("localhost", is_host)
    game.run() 