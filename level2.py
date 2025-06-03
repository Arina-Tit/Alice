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

# Импортируем все классы из game.py
from game import SpriteSheet, Camera, Player, DialogSystem, Platform, Collectible, AnimatedKey, Potion, Lamp, Decoration, MovingPlatform, Flag, Sign

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
        
        # Проверяем и создаем файл диалогов, если он отсутствует
        self.ensure_dialog_file_exists("level2_dialog.json")
        
        # Загружаем финальные картинки
        try:
            self.final_image = pygame.image.load(os.path.join("assets", "tiles", "Final level.png")).convert_alpha()
            self.final_image = pygame.transform.scale(self.final_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
            print("Final level.png успешно загружен")
            
            smile_path = os.path.join("assets", "tiles", "Smile.png")
            if not os.path.exists(smile_path):
                print(f"Ошибка: файл {smile_path} не найден")
                self.smile_image = None
            else:
                self.smile_image = pygame.image.load(smile_path).convert_alpha()
                self.smile_image = pygame.transform.scale(self.smile_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
                print("Smile.png успешно загружен")
        except Exception as e:
            print(f"Ошибка при загрузке картинок: {e}")
            self.final_image = None
            self.smile_image = None

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

        # Добавляем систему диалогов
        self.dialog_system = DialogSystem()
        self.is_host = is_host
        
        # Инициализируем состояние диалога
        self.dialog_state = {
            "is_active": False,
            "current_dialog_id": None,
            "current_speaker": None,
            "dialog_completed": False
        }
        
        # Создаем платформы и препятствия
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

    def create_background(self):
        """Создает многослойный фон с параллаксом"""
        backgrounds = {}
        
        try:
            # Загружаем 3 слоя фона
            bg1 = pygame.image.load(os.path.join("assets", "tiles", "BG_1.png")).convert_alpha()
            bg2 = pygame.image.load(os.path.join("assets", "tiles", "BG_2.png")).convert_alpha()
            bg3 = pygame.image.load(os.path.join("assets", "tiles", "BG_3.png")).convert_alpha()
            
            # Масштабируем фоны под размер экрана
            backgrounds['layer1'] = pygame.transform.scale(bg1, (SCREEN_WIDTH, SCREEN_HEIGHT))
            backgrounds['layer2'] = pygame.transform.scale(bg2, (SCREEN_WIDTH, SCREEN_HEIGHT))
            backgrounds['layer3'] = pygame.transform.scale(bg3, (SCREEN_WIDTH, SCREEN_HEIGHT))
            backgrounds['layer4'] = backgrounds['layer3']  # Используем тот же слой для четвертого уровня
            
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
            backgrounds['layer4'] = background.copy()
        
        return backgrounds

    def ensure_dialog_file_exists(self, dialog_filename):
        """Проверяет наличие файла диалогов и создает его, если отсутствует"""
        dialog_path = os.path.join("assets", "dialogs")
        dialog_file = os.path.join(dialog_path, dialog_filename)
        
        if not os.path.exists(dialog_path):
            os.makedirs(dialog_path)
            print(f"Создана директория диалогов: {dialog_path}")
        
        if not os.path.exists(dialog_file):
            default_dialogs = {
                "start": {
                    "text": "Добро пожаловать в Страну Чудес, Алиса! Здесь всё не такое, каким кажется на первый взгляд.",
                    "speaker": "rabbit",
                    "choices": [
                        {
                            "text": "Это действительно удивительное место! Расскажите мне больше.",
                            "next": "dialog2"
                        }
                    ]
                },
                "dialog2": {
                    "text": "О, здесь есть говорящие цветы, улыбающиеся коты, и даже время течёт иначе! А чаепития длятся вечно!",
                    "speaker": "rabbit",
                    "choices": [
                        {
                            "text": "Звучит волшебно! А куда мы направляемся?",
                            "next": "dialog3"
                        }
                    ]
                },
                "dialog3": {
                    "text": "К Безумному Шляпнику на чаепитие! Но сначала нам нужно пройти через этот волшебный сад. Будь осторожна - здесь всё может быть не тем, чем кажется!",
                    "speaker": "rabbit",
                    "choices": [
                        {
                            "text": "Я готова к приключениям! Ведите меня!",
                            "next": "end"
                        }
                    ]
                }
            }
            
            try:
                with open(dialog_file, 'w', encoding='utf-8') as f:
                    json.dump(default_dialogs, f, ensure_ascii=False, indent=4)
                print(f"Создан файл диалогов: {dialog_file}")
            except Exception as e:
                print(f"Ошибка при создании файла диалогов: {e}")

    # Импортируем все остальные методы из game.py
    from game import (create_platform, create_shadow, create_platforms, create_animated_keys,
                     create_potions, create_lamps, create_decorations, create_signs,
                     create_moving_platforms, check_victory_condition, draw_victory_screen,
                     check_platform_activation, make_choice, receive_data, send_data,
                     close, run, handle_input, check_dialog_trigger, start_dialog,
                     end_dialog, draw_ui, draw_background_with_parallax)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python level2.py [host/client]")
        sys.exit(1)

    is_host = sys.argv[1].lower() == "host"
    game = Game("localhost", is_host)
    game.run() 