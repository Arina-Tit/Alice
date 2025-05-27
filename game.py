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
ALICE_OFFSET = 70  # Смещение для Алисы, чтобы компенсировать размер спрайта
RABBIT_OFFSET = 10  # Небольшое смещение для кролика

# Физика
GRAVITY = 0.5
ALICE_JUMP_FORCE = -8
RABBIT_JUMP_FORCE = -15
ALICE_MOVE_SPEED = 5
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
DIALOG_PADDING = 20
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

class SpriteSheet:
    def __init__(self, frames, animation_speed, width, height):
        self.frames = frames  # Список уже загруженных и масштабированных кадров
        self.frames_count = len(frames)
        self.target_width = width
        self.target_height = height
        self.current_frame = 0
        self.frame_progress = 0.0
        self.last_update = time.time()
        self.animation_speed = animation_speed

    def get_current_frame(self):
        current_time = time.time()
        delta_time = current_time - self.last_update
        self.last_update = current_time

        # Обновляем прогресс анимации
        self.frame_progress += delta_time / self.animation_speed
        
        # Если достигли следующего кадра
        if self.frame_progress >= 1.0:
            self.current_frame = (self.current_frame + 1) % self.frames_count
            self.frame_progress = 0.0
            
        return self.frames[self.current_frame]

    def reset_animation(self):
        self.current_frame = 0
        self.frame_progress = 0.0
        self.last_update = time.time()

def load_sprite(character_name, state="idle"):
    # Настройки количества кадров для каждого спрайта
    sprite_config = {
        "alice": {
            "idle": {"frames": 18, "speed": ALICE_ANIMATION_SPEED, "size": (ALICE_WIDTH, ALICE_HEIGHT)},
            "walk": {"frames": 24, "speed": ALICE_ANIMATION_SPEED, "size": (ALICE_WIDTH, ALICE_HEIGHT)}
        },
        "rabbit": {
            "idle": {"frames": 2, "speed": RABBIT_IDLE_ANIMATION_SPEED, "size": (RABBIT_WIDTH, RABBIT_HEIGHT)},
            "walk": {"frames": 4, "speed": RABBIT_WALK_ANIMATION_SPEED, "size": (RABBIT_WIDTH, RABBIT_HEIGHT)}  # Обновлено до 4 кадров
        }
    }

    base_path = os.path.join("assets", "characters", character_name)
    try:
        config = sprite_config[character_name][state]
        frames = []
        
        # Загружаем каждый кадр отдельно
        for i in range(1, config["frames"] + 1):
            # Пробуем разные форматы файлов
            possible_filenames = [
                f"{character_name}_{state} ({i}).png",
                f"{character_name}_{state} ({i}).jpg"
            ]
            
            frame_path = None
            for filename in possible_filenames:
                temp_path = os.path.join(base_path, filename)
                if os.path.exists(temp_path):
                    frame_path = temp_path
                    break
            
            if not frame_path:
                print(f"Файл не найден для кадра {i} в {character_name}/{state}")
                continue
                
            # Загружаем и масштабируем кадр
            try:
                frame = pygame.image.load(frame_path).convert_alpha()
            except pygame.error as e:
                print(f"Ошибка загрузки {frame_path}: {e}")
                continue
            
            # Определяем размеры для масштабирования с сохранением пропорций
            source_width = frame.get_width()
            source_height = frame.get_height()
            source_ratio = source_width / source_height
            target_ratio = config["size"][0] / config["size"][1]
            
            if source_ratio > target_ratio:
                new_width = config["size"][0]
                new_height = int(new_width / source_ratio)
            else:
                new_height = config["size"][1]
                new_width = int(new_height * source_ratio)
            
            # Масштабируем спрайт
            scaled = pygame.transform.smoothscale(frame, (new_width, new_height))
            
            # Создаем финальную поверхность
            final = pygame.Surface(config["size"], pygame.SRCALPHA)
            
            # Центрируем спрайт
            x = (config["size"][0] - new_width) // 2
            y = (config["size"][1] - new_height) // 2
            
            final.blit(scaled, (x, y))
            frames.append(final)
        
        if not frames:
            raise FileNotFoundError(f"Не найдено кадров для {character_name}/{state}")
            
        return SpriteSheet(frames, config["speed"], config["size"][0], config["size"][1])
    except Exception as e:
        print(f"Ошибка при загрузке спрайтов {character_name}/{state}: {str(e)}")
        # Создаем заглушку при ошибке
        surface = pygame.Surface(sprite_config[character_name][state]["size"], pygame.SRCALPHA)
        color = (255, 0, 0) if character_name == "alice" else (0, 0, 255)
        pygame.draw.rect(surface, color, surface.get_rect())
        return SpriteSheet([surface], 0.1, surface.get_width(), surface.get_height())

class Camera:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.scroll_x = 0
        self.scroll_y = 0
        self.target_scroll_x = 0
        self.target_scroll_y = 0
        self.lerp_speed = 0.08  # Скорость интерполяции
        self.deadzone_x = 100   # Мертвая зона по горизонтали
        self.deadzone_y = 80    # Мертвая зона по вертикали

    def update(self, target_x, target_y):
        # Вычисляем центр экрана
        screen_center_x = self.width // 2
        screen_center_y = self.height // 2

        # Определяем целевую позицию с учетом мертвой зоны
        current_view_x = target_x - self.scroll_x
        current_view_y = target_y - self.scroll_y

        # Проверяем, вышел ли персонаж за пределы мертвой зоны
        if abs(current_view_x - screen_center_x) > self.deadzone_x:
            if current_view_x > screen_center_x:
                self.target_scroll_x = target_x - (screen_center_x + self.deadzone_x)
            else:
                self.target_scroll_x = target_x - (screen_center_x - self.deadzone_x)
        
        if abs(current_view_y - screen_center_y) > self.deadzone_y:
            if current_view_y > screen_center_y:
                self.target_scroll_y = target_y - (screen_center_y + self.deadzone_y)
            else:
                self.target_scroll_y = target_y - (screen_center_y - self.deadzone_y)

        # Плавная интерполяция к целевой позиции
        self.scroll_x += (self.target_scroll_x - self.scroll_x) * self.lerp_speed
        self.scroll_y += (self.target_scroll_y - self.scroll_y) * self.lerp_speed
        
        # Ограничение камеры границами мира
        self.scroll_x = max(0, min(self.scroll_x, WORLD_WIDTH - self.width))
        self.scroll_y = max(0, min(self.scroll_y, WORLD_HEIGHT - self.height))

    def apply(self, x, y):
        # Округляем значения для избежания дрожания спрайтов
        return round(x - self.scroll_x), round(y - self.scroll_y)

class Player:
    def __init__(self, x, y, character_name):
        self.x = x
        self.y = y
        self.character_name = character_name
        self.vel_y = 0
        self.is_jumping = False
        self.facing_right = True
        self.moving = False
        self.width = ALICE_WIDTH if character_name == "alice" else RABBIT_WIDTH
        self.height = ALICE_HEIGHT if character_name == "alice" else RABBIT_HEIGHT
        self.offset = ALICE_OFFSET if character_name == "alice" else RABBIT_OFFSET
        self.sprites = {
            "idle": load_sprite(character_name, "idle"),
            "walk": load_sprite(character_name, "walk")
        }
        self.current_state = "idle"
        self.last_state = "idle"
        self.last_update_time = time.time()
        self.state_changed = False
        
        # Настройки в зависимости от персонажа
        if character_name == "alice":
            self.move_speed = ALICE_MOVE_SPEED
            self.jump_force = ALICE_JUMP_FORCE
        else:
            self.move_speed = RABBIT_MOVE_SPEED
            self.jump_force = RABBIT_JUMP_FORCE

    def move(self, direction):
        current_time = time.time()
        if current_time - self.last_update_time > 1/60:
            self.x += direction * self.move_speed
            self.last_update_time = current_time
            
        # Обновляем направление и состояние движения
        if direction != 0:
            self.facing_right = direction > 0
            self.moving = True
            self.current_state = "walk"
        else:
            self.moving = False
            self.current_state = "idle"
            
        # Сбрасываем анимацию при смене состояния
        if self.current_state != self.last_state:
            self.last_state = self.current_state
            self.sprites[self.current_state].reset_animation()

    def jump(self):
        if not self.is_jumping:
            self.vel_y = self.jump_force
            self.is_jumping = True

    def update(self):
        self.vel_y += GRAVITY
        self.y += self.vel_y

        # Обработка приземления на платформу
        platform_y = WORLD_HEIGHT - PLATFORM_HEIGHT
        if self.y > platform_y - self.height + self.offset:
            self.y = platform_y - self.height + self.offset
            if self.vel_y > 0:  # Если падали вниз
                self.vel_y = 0
                self.is_jumping = False

    def draw(self, screen, camera):
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -self.width <= screen_x <= SCREEN_WIDTH and -self.height <= screen_y <= SCREEN_HEIGHT:
            sprite = self.sprites[self.current_state].get_current_frame()
            if not self.facing_right:
                sprite = pygame.transform.flip(sprite, True, False)
            screen.blit(sprite, (screen_x, screen_y))

class DialogSystem:
    def __init__(self):
        pygame.font.init()
        self.font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), FONT_SIZE)
        
        # Загружаем графику диалогов
        self.dialog_bg = pygame.image.load(os.path.join("assets", "gui", "dialog_box.png"))
        self.dialog_bg = pygame.transform.scale(self.dialog_bg, (DIALOG_WIDTH, DIALOG_HEIGHT))
        
        # Загружаем диалоги
        with open(os.path.join("assets", "dialogs", "rabbit_dialog.json"), 'r', encoding='utf-8') as f:
            self.dialogs = json.load(f)
        
        self.reset_state()

    def reset_state(self):
        """Сброс состояния диалоговой системы"""
        self.current_dialog = None
        self.current_choices = []
        self.selected_choice = 0
        self.is_active = False
        self.text_alpha = 0
        self.current_text = ""
        self.target_text = ""
        self.text_timer = 0
        self.my_turn = False
        self.current_speaker = None
        self.dialog_ended = False
        self.dialog_completed = False  # Флаг полного завершения диалога
        self.exit_hint_timer = 0  # Таймер для подсказки о выходе
        self.show_exit_hint = False  # Показывать ли подсказку о выходе

    def start_dialog(self, dialog_id, character_name):
        """Запуск диалога"""
        if self.dialog_completed:
            return  # Диалог уже завершен, не запускаем повторно
            
        if dialog_id in self.dialogs:
            print(f"Запуск диалога {dialog_id} для {character_name}")
            self.current_dialog = self.dialogs[dialog_id]
            self.current_choices = self.current_dialog.get("choices", [])
            self.selected_choice = 0
            self.is_active = True
            self.text_alpha = 0
            self.current_text = ""
            self.target_text = self.current_dialog["text"]
            self.text_timer = 0
            self.current_speaker = self.current_dialog.get("speaker")
            self.my_turn = (self.current_speaker == character_name)
            self.dialog_ended = False
            print(f"Диалог запущен. Говорящий: {self.current_speaker}, Мой ход: {self.my_turn}")
        else:
            print(f"Ошибка: диалог {dialog_id} не найден")

    def complete_dialog(self):
        """Полное завершение диалога с показом подсказки"""
        self.dialog_completed = True
        self.dialog_ended = True
        self.is_active = False
        self.show_exit_hint = True
        self.exit_hint_timer = EXIT_HINT_DURATION
        print("Диалог полностью завершен, показываем подсказку о выходе")

    def update(self, dt):
        if self.is_active:
            # Анимация появления текста
            if len(self.current_text) < len(self.target_text):
                self.text_timer += dt
                if self.text_timer >= 0.02:
                    self.text_timer = 0
                    self.current_text = self.target_text[:len(self.current_text) + 1]
            
            # Анимация прозрачности
            if self.text_alpha < 255:
                self.text_alpha = min(255, self.text_alpha + 510 * dt)
        
        # Обновляем таймер подсказки о выходе
        if self.show_exit_hint:
            self.exit_hint_timer -= dt
            if self.exit_hint_timer <= 0:
                self.show_exit_hint = False

    def wrap_text(self, text, max_width):
        """Разбивает текст на строки с учетом максимальной ширины"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            test_surface = self.font.render(test_line, True, TEXT_COLOR)
            if test_surface.get_width() <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Если одно слово слишком длинное, разбиваем его
                    lines.append(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines

    def draw(self, screen, character_name):
        """Отрисовка диалогового окна"""
        # Показываем подсказку о выходе из норы
        if self.show_exit_hint:
            hint_text = "Теперь нужно найти выход из кроличьей норы!"
            hint_surface = self.font.render(hint_text, True, DIALOG_PROMPT_COLOR)
            hint_x = (SCREEN_WIDTH - hint_surface.get_width()) // 2
            hint_y = SCREEN_HEIGHT // 2
            
            # Добавляем полупрозрачный фон для лучшей читаемости
            bg_rect = pygame.Rect(hint_x - 10, hint_y - 5, hint_surface.get_width() + 20, hint_surface.get_height() + 10)
            bg_surface = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            bg_surface.fill((0, 0, 0, 128))
            screen.blit(bg_surface, bg_rect)
            screen.blit(hint_surface, (hint_x, hint_y))
            return

        if not self.is_active or not self.current_dialog or self.dialog_completed:
            return

        # Позиционируем диалоговое окно вверху экрана
        dialog_x = (SCREEN_WIDTH - DIALOG_WIDTH) // 2
        dialog_y = 20

        # Отрисовываем фон диалога
        screen.blit(self.dialog_bg, (dialog_x, dialog_y))

        # Отрисовываем имя говорящего
        speaker_text = "Алиса" if self.current_speaker == "alice" else "Кролик"
        speaker_surface = self.font.render(speaker_text, True, (255, 255, 100))
        screen.blit(speaker_surface, (dialog_x + DIALOG_PADDING, dialog_y + DIALOG_PADDING))

        # Вычисляем доступную область для текста
        text_area_width = DIALOG_WIDTH - 2 * DIALOG_PADDING
        text_start_y = dialog_y + DIALOG_PADDING + FONT_SIZE + 10
        
        # Разбиваем текст на строки
        lines = self.wrap_text(self.current_text, text_area_width)
        
        # Отрисовываем текст диалога
        text_y = text_start_y
        max_text_height = DIALOG_HEIGHT - (text_start_y - dialog_y) - DIALOG_PADDING
        
        for line in lines:
            if text_y + FONT_SIZE > dialog_y + DIALOG_HEIGHT - DIALOG_PADDING:
                break  # Не выходим за границы диалогового окна
                
            text_surface = self.font.render(line, True, TEXT_COLOR)
            text_surface.set_alpha(self.text_alpha)
            screen.blit(text_surface, (dialog_x + DIALOG_PADDING, text_y))
            text_y += FONT_SIZE + 3

        # Отрисовываем варианты ответов только если текст полностью появился
        if (self.current_text == self.target_text and 
            self.current_speaker == character_name and 
            self.current_choices):
            
            choices_start_y = text_y + 10
            
            for i, choice in enumerate(self.current_choices):
                choice_y = choices_start_y + i * (FONT_SIZE + CHOICE_PADDING)
                
                # Проверяем, помещается ли выбор в диалоговое окно
                if choice_y + FONT_SIZE > dialog_y + DIALOG_HEIGHT - DIALOG_PADDING:
                    break
                
                color = CHOICE_HOVER_COLOR if i == self.selected_choice else CHOICE_COLOR
                indent = CHOICE_INDENT * 2 if i == self.selected_choice else CHOICE_INDENT
                
                # Обрезаем текст выбора если он слишком длинный
                choice_text = choice['text']
                max_choice_width = text_area_width - indent
                choice_lines = self.wrap_text(choice_text, max_choice_width)
                
                if choice_lines:
                    choice_surface = self.font.render(choice_lines[0], True, color)
                    screen.blit(choice_surface, (dialog_x + DIALOG_PADDING + indent, choice_y))

    def handle_input(self, event, character_name):
        """Обработка ввода для диалоговой системы"""
        if not self.is_active or not self.my_turn or not self.current_choices or self.dialog_completed:
            return None

        if event.type == pygame.KEYDOWN:
            # Если текст ещё не полностью появился, показываем его сразу
            if self.current_text != self.target_text:
                self.current_text = self.target_text
                return None

            if event.key == pygame.K_UP:
                self.selected_choice = (self.selected_choice - 1) % len(self.current_choices)
                return None
            elif event.key == pygame.K_DOWN:
                self.selected_choice = (self.selected_choice + 1) % len(self.current_choices)
                return None
            elif event.key == pygame.K_RETURN:
                if self.selected_choice < len(self.current_choices):
                    return self.selected_choice
        return None

class Game:
    def __init__(self, host, is_host):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("P2P Game")
        self.clock = pygame.time.Clock()
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)
        
        # Создаем фон и платформу
        self.background = self.create_background()
        self.platform = self.create_platform()
        self.shadow = self.create_shadow()

        # Создание игроков с соответствующими спрайтами
        platform_y = WORLD_HEIGHT - PLATFORM_HEIGHT
        if is_host:
            self.my_player = Player(100, platform_y - ALICE_HEIGHT + ALICE_OFFSET, "alice")
            self.other_player = Player(250, platform_y - RABBIT_HEIGHT + RABBIT_OFFSET, "rabbit")
        else:
            self.my_player = Player(250, platform_y - RABBIT_HEIGHT + RABBIT_OFFSET, "rabbit")
            self.other_player = Player(100, platform_y - ALICE_HEIGHT + ALICE_OFFSET, "alice")

        # Настройка сети
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if is_host:
            self.socket.bind((host, 5000))
            self.other_address = (host, 5001)
        else:
            self.socket.bind((host, 5001))
            self.other_address = (host, 5000)

        # Запуск потока для приема данных
        self.receive_thread = threading.Thread(target=self.receive_data)
        self.receive_thread.daemon = True
        self.receive_thread.start()

        # Добавляем систему диалогов
        self.dialog_system = DialogSystem()
        self.is_host = is_host
        
        # Упрощенное состояние диалога для синхронизации
        self.dialog_state = {
            "is_active": False,
            "current_dialog_id": None,
            "current_speaker": None,
            "dialog_completed": False
        }

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
        for _ in range(500):  # Меньше вариаций для платформы
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, PLATFORM_HEIGHT)
            size = random.randint(2, 4)
            color = random.choice([DIRT_DARK, DIRT_LIGHT])
            pygame.draw.ellipse(platform, color, (x, y, size, size * 0.7))
        
        # Добавляем верхнюю границу платформы
        pygame.draw.line(platform, DIRT_LIGHT, (0, 0), (SCREEN_WIDTH, 0), 2)
        
        return platform

    def create_background(self):
        """Создает текстурированный фон почвы"""
        background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        background.fill(DIRT_DARK)  # Делаем фон немного темнее
        
        # Добавляем вариации цвета для создания текстуры
        for _ in range(2000):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, SCREEN_HEIGHT)
            size = random.randint(2, 6)
            color = random.choice([DIRT_DARK, DIRT_BROWN])
            pygame.draw.ellipse(background, color, (x, y, size, size * 0.7))
        
        return background

    def send_data(self):
        """Отправка данных другому игроку"""
        data = pickle.dumps({
            "player": {
                "x": self.my_player.x,
                "y": self.my_player.y,
                "facing_right": self.my_player.facing_right,
                "moving": self.my_player.moving
            },
            "dialog": self.dialog_state
        })
        self.socket.sendto(data, self.other_address)

    def receive_data(self):
        """Получение данных от другого игрока"""
        while True:
            try:
                data, addr = self.socket.recvfrom(1024)
                received_data = pickle.loads(data)
                
                # Обновляем позицию другого игрока
                player_data = received_data["player"]
                self.other_player.x = player_data["x"]
                self.other_player.y = player_data["y"]
                self.other_player.facing_right = player_data["facing_right"]
                self.other_player.moving = player_data["moving"]
                
                # Синхронизируем состояние диалога
                other_dialog_state = received_data["dialog"]
                
                # Проверяем, нужно ли обновить диалог
                if (other_dialog_state["is_active"] != self.dialog_state["is_active"] or
                    other_dialog_state["current_dialog_id"] != self.dialog_state["current_dialog_id"] or
                    other_dialog_state["current_speaker"] != self.dialog_state["current_speaker"]):
                    
                    print("Получено обновление состояния диалога:")
                    print(f"Активен: {other_dialog_state['is_active']}")
                    print(f"Текущий диалог: {other_dialog_state['current_dialog_id']}")
                    print(f"Говорящий: {other_dialog_state['current_speaker']}")
                    
                    self.handle_other_player_choice(other_dialog_state)
            except:
                pass

    def handle_other_player_choice(self, other_dialog_state):
        """Обработка выбора другого игрока"""
        # Проверяем завершение диалога
        if other_dialog_state.get("dialog_completed") or not other_dialog_state["is_active"]:
            print("Получено завершение диалога от другого игрока")
            self.dialog_system.complete_dialog()
            self.dialog_state.update(other_dialog_state)
            return

        # Обновляем состояние диалога
        if other_dialog_state["current_dialog_id"] != self.dialog_state["current_dialog_id"]:
            print(f"Переход к диалогу: {other_dialog_state['current_dialog_id']}")
            self.dialog_state.update(other_dialog_state)
            
            if other_dialog_state["current_dialog_id"]:
                self.dialog_system.reset_state()
                self.dialog_system.start_dialog(
                    other_dialog_state["current_dialog_id"], 
                    self.my_player.character_name
                )

    def start_dialog(self, dialog_id):
        """Начало диалога"""
        if not self.dialog_system.dialog_completed:
            self.dialog_system.start_dialog(dialog_id, self.my_player.character_name)
            self.dialog_state["is_active"] = True
            self.dialog_state["current_dialog_id"] = dialog_id
            self.dialog_state["current_speaker"] = "alice"
            self.send_data()

    def end_dialog(self):
        """Завершение диалога"""
        self.dialog_system.complete_dialog()
        self.dialog_state["is_active"] = False
        self.dialog_state["current_dialog_id"] = None
        self.dialog_state["current_speaker"] = None
        self.dialog_state["dialog_completed"] = True
        self.send_data()

    def make_choice(self, choice_index):
        """Обработка выбора варианта ответа"""
        if not self.dialog_system.my_turn or not self.dialog_system.current_dialog:
            return
            
        if choice_index >= len(self.dialog_system.current_dialog.get("choices", [])):
            return
            
        choice = self.dialog_system.current_dialog["choices"][choice_index]
        next_dialog = choice.get("next")
        
        # Если это конец диалога
        if next_dialog == "end":
            self.end_dialog()
            return

        # Переход к следующему диалогу
        if next_dialog and next_dialog in self.dialog_system.dialogs:
            next_dialog_data = self.dialog_system.dialogs[next_dialog]
            next_speaker = next_dialog_data.get("speaker")
            
            self.dialog_state["current_dialog_id"] = next_dialog
            self.dialog_state["current_speaker"] = next_speaker
            self.dialog_state["is_active"] = True
            self.send_data()
            
            # Запускаем новый диалог
            self.dialog_system.reset_state()
            self.dialog_system.start_dialog(next_dialog, self.my_player.character_name)
        else:
            # Если следующего диалога нет, завершаем
            self.end_dialog()

    def check_dialog_trigger(self):
        """Проверка возможности начать диалог"""
        # Вычисляем расстояние между персонажами
        distance = ((self.my_player.x - self.other_player.x) ** 2 + 
                   (self.my_player.y - self.other_player.y) ** 2) ** 0.5
        
        # Если игроки достаточно близко и диалог не активен и не завершен
        if (distance < DIALOG_TRIGGER_DISTANCE and 
            not self.dialog_system.is_active and 
            not self.dialog_system.dialog_completed and
            self.my_player.character_name == "alice"):
            
            self.start_dialog("start")

    def handle_input(self, event):
        """Обработка ввода для диалогов"""
        if not self.dialog_system.is_active:
            return

        choice = self.dialog_system.handle_input(event, self.my_player.character_name)
        if choice is not None:
            print(f"Выбран вариант {choice + 1}")
            self.make_choice(choice)

    def run(self):
        running = True
        last_time = time.time()
        while running:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            # Получаем состояние клавиш
            keys = pygame.key.get_pressed()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE and not self.dialog_system.is_active:
                        self.my_player.jump()
                    else:
                        self.handle_input(event)

            # Проверяем, есть ли активный диалог, блокирующий движение
            allow_movement = True
            if self.dialog_system.is_active:
                allow_movement = False

            # Обрабатываем нажатия клавиш
            if allow_movement and not self.dialog_system.dialog_completed:
                if keys[pygame.K_LEFT]:
                    self.my_player.move(-1)
                elif keys[pygame.K_RIGHT]:
                    self.my_player.move(1)
                else:
                    self.my_player.move(0)
            else:
                self.my_player.move(0)

            # Обновление физики и проверка диалога
            self.my_player.update()
            self.other_player.update()
            self.check_dialog_trigger()

            # Обновление камеры
            next_x = self.my_player.x
            next_y = self.my_player.y
            if keys[pygame.K_LEFT]:
                next_x -= self.my_player.move_speed * 5
            elif keys[pygame.K_RIGHT]:
                next_x += self.my_player.move_speed * 5
            self.camera.update(next_x, next_y)

            # Обновляем анимацию диалогов
            self.dialog_system.update(dt)

            # Отправка данных
            self.send_data()

            # Отрисовка
            self.screen.blit(self.background, (0, 0))
            platform_y = SCREEN_HEIGHT - PLATFORM_HEIGHT
            self.screen.blit(self.platform, (0, platform_y))
            
            # Находим Алису и Кролика
            alice = self.my_player if self.my_player.character_name == "alice" else self.other_player
            rabbit = self.other_player if self.my_player.character_name == "alice" else self.my_player
            
            # Сначала отрисовываем Кролика, потом Алису
            rabbit.draw(self.screen, self.camera)
            alice.draw(self.screen, self.camera)
            
            self.screen.blit(self.shadow, (0, 0))
            self.dialog_system.draw(self.screen, self.my_player.character_name)
            
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        self.socket.close()
        sys.exit()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python game.py [host/client]")
        sys.exit(1)

    is_host = sys.argv[1].lower() == "host"
    game = Game("localhost", is_host)
    game.run() 