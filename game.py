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
ALICE_JUMP_FORCE = -16
RABBIT_JUMP_FORCE = -20
ALICE_MOVE_SPEED = 8
RABBIT_MOVE_SPEED = 10

# Скорости анимации
ALICE_ANIMATION_SPEED = 0.04
RABBIT_IDLE_ANIMATION_SPEED = 0.15
RABBIT_WALK_ANIMATION_SPEED = 0.04

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

class SpriteSheet:
    def __init__(self, frames, animation_speed, width, height):
        self.frames = frames  
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
            old_x = self.x
            new_x = self.x + direction * self.move_speed
            
            # Проверяем горизонтальные коллизии (если есть платформы)
            if hasattr(self, '_platforms'):
                new_x = self.check_horizontal_collisions(self._platforms, new_x)
            
            self.x = new_x
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

    def update(self, platforms=None):
        self.vel_y += GRAVITY
        old_y = self.y
        old_x = self.x
        
        # Сначала обновляем позицию по Y
        self.y += self.vel_y

        # Проверяем коллизии с платформами по вертикали
        player_rect = pygame.Rect(self.x, self.y, self.width - self.offset, self.height - self.offset)
        
        # Сначала проверяем основную платформу
        platform_y = WORLD_HEIGHT - PLATFORM_HEIGHT
        if self.y > platform_y - self.height + self.offset:
            self.y = platform_y - self.height + self.offset
            if self.vel_y > 0:
                self.vel_y = 0
                self.is_jumping = False

        # Проверяем коллизии с дополнительными платформами
        if platforms:
            for platform in platforms:
                platform_rect = platform.rect
                player_rect = pygame.Rect(self.x, self.y, self.width - self.offset, self.height - self.offset)
                
                # Проверяем вертикальные коллизии
                if player_rect.colliderect(platform_rect):
                    # Приземление сверху (игрок падает на платформу)
                    if (old_y + self.height - self.offset <= platform.y + 5 and 
                        self.vel_y > 0 and 
                        self.y + self.height - self.offset > platform.y):
                        self.y = platform.y - self.height + self.offset
                        self.vel_y = 0
                        self.is_jumping = False
                        break
                    # Удар головой снизу (игрок прыгает в платформу снизу)
                    elif (old_y >= platform.y + platform.height - 5 and 
                          self.vel_y < 0 and 
                          self.y < platform.y + platform.height):
                        self.y = platform.y + platform.height
                        self.vel_y = 0
                        break

    def check_horizontal_collisions(self, platforms, new_x):
        """Проверяет горизонтальные коллизии при движении"""
        if not platforms:
            return new_x
            
        player_rect = pygame.Rect(new_x, self.y, self.width - self.offset, self.height - self.offset)
        
        for platform in platforms:
            if player_rect.colliderect(platform.rect):
                # Столкновение слева
                if self.x < platform.x:
                    return platform.x - (self.width - self.offset)
                # Столкновение справа
                else:
                    return platform.x + platform.width
        
        return new_x

    def check_collectibles(self, collectibles):
        """Проверяет сбор предметов"""
        player_rect = pygame.Rect(self.x, self.y, self.width - self.offset, self.height - self.offset)
        collected_items = []
        
        for collectible in collectibles:
            if not collectible.collected and player_rect.colliderect(collectible.rect):
                if collectible.collect(self.character_name):
                    collected_items.append(collectible)
        
        return collected_items

    def check_platform_triggers(self, platforms):
        """Проверяет активацию платформ-триггеров"""
        player_rect = pygame.Rect(self.x, self.y, self.width - self.offset, self.height - self.offset)
        triggered_platforms = []
        
        for platform in platforms:
            if (platform.platform_type == "alice_trigger" and 
                self.character_name == "alice" and
                player_rect.colliderect(platform.rect)):
                triggered_platforms.append(platform)
        
        return triggered_platforms

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
        
        # Загружаем портреты персонажей
        try:
            self.alice_portrait = pygame.image.load(os.path.join("assets", "characters", "alice", "alice_dialog.png")).convert_alpha()
            self.alice_portrait = pygame.transform.scale(self.alice_portrait, (80, 80))
        except:
            self.alice_portrait = None
            
        try:
            self.rabbit_portrait = pygame.image.load(os.path.join("assets", "characters", "rabbit", "rabbit_dialog.png")).convert_alpha()
            self.rabbit_portrait = pygame.transform.scale(self.rabbit_portrait, (80, 80))
        except:
            self.rabbit_portrait = None
        
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

        # Отрисовываем портрет говорящего персонажа
        portrait = None
        if self.current_speaker == "alice" and self.alice_portrait:
            portrait = self.alice_portrait
        elif self.current_speaker == "rabbit" and self.rabbit_portrait:
            portrait = self.rabbit_portrait
        
        if portrait:
            portrait_x = dialog_x + DIALOG_PADDING
            portrait_y = dialog_y + DIALOG_PADDING
            screen.blit(portrait, (portrait_x, portrait_y))
            text_start_x = portrait_x + 90  # Смещаем текст вправо от портрета
        else:
            # Fallback - отображаем имя как раньше
            speaker_text = "Алиса" if self.current_speaker == "alice" else "Кролик"
            speaker_surface = self.font.render(speaker_text, True, (255, 255, 100))
            screen.blit(speaker_surface, (dialog_x + DIALOG_PADDING, dialog_y + DIALOG_PADDING))
            text_start_x = dialog_x + DIALOG_PADDING

        # Вычисляем доступную область для текста
        text_area_width = DIALOG_WIDTH - (text_start_x - dialog_x) - DIALOG_PADDING
        text_start_y = dialog_y + DIALOG_PADDING + 10
        
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
            screen.blit(text_surface, (text_start_x, text_y))
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
                    screen.blit(choice_surface, (text_start_x + indent, choice_y))

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

class Platform:
    def __init__(self, x, y, width, height, platform_type="normal", character_access=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.platform_type = platform_type  # "normal", "alice_only", "rabbit_only", "switch", "door"
        self.character_access = character_access  # None, "alice", "rabbit"
        self.is_active = True  # Для дверей и переключателей
        self.rect = pygame.Rect(x, y, width, height)
        
        # Загружаем текстуры
        self.load_textures()

    def load_textures(self):
        """Загружает текстуры для платформ"""
        try:
            # Загружаем новую текстуру блоков
            self.block_texture = pygame.image.load(os.path.join("assets", "tiles", "mainlev_build.png")).convert_alpha()
            self.terrain_texture = pygame.image.load(os.path.join("assets", "tiles", "terrain.png")).convert_alpha()
            
            # Создаем поверхность для платформы с текстурой
            self.surface = self.create_textured_platform()
        except:
            # Если не удалось загрузить текстуры, используем цветные прямоугольники
            self.block_texture = None
            self.terrain_texture = None
            self.surface = None

    def create_textured_platform(self):
        """Создает текстурированную поверхность платформы"""
        if not self.block_texture:
            return None
            
        surface = pygame.Surface((self.width, self.height + 20), pygame.SRCALPHA)  # Добавляем высоту для основания
        
        # Определяем размер блока (предполагаем 16x16 пикселей на блок в спрайтшите)
        block_size = 16
        tile_size = 32  # Размер тайла в игре
        
        # Заполняем платформу блоками
        for x in range(0, self.width, tile_size):
            for y in range(0, self.height + 20, tile_size):
                # Выбираем подходящий блок из спрайтшита
                if y < self.height:
                    # Верхний слой - используем верхние блоки
                    block_rect = pygame.Rect(0, 0, block_size, block_size)
                else:
                    # Нижний слой - используем нижние блоки
                    block_rect = pygame.Rect(0, block_size, block_size, block_size)
                
                block_sprite = self.block_texture.subsurface(block_rect)
                scaled_block = pygame.transform.scale(block_sprite, (tile_size, tile_size))
                surface.blit(scaled_block, (x, y))
        
        # Добавляем цветовой оверлей для специальных платформ
        if self.platform_type == "alice_only":
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((*ALICE_PLATFORM_COLOR, 80))
            surface.blit(overlay, (0, 0))
        elif self.platform_type == "rabbit_only":
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((*RABBIT_PLATFORM_COLOR, 80))
            surface.blit(overlay, (0, 0))
        elif self.platform_type == "switch":
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((*SWITCH_COLOR, 120))
            surface.blit(overlay, (0, 0))
        
        return surface

    def can_stand_on(self, character_name):
        """Проверяет, может ли персонаж стоять на платформе"""
        if not self.is_active and self.platform_type == "door":
            return False
        if self.character_access is None:
            return True
        return self.character_access == character_name

    def get_color(self):
        """Возвращает цвет платформы в зависимости от типа (для fallback)"""
        if self.platform_type == "alice_only":
            return ALICE_PLATFORM_COLOR
        elif self.platform_type == "rabbit_only":
            return RABBIT_PLATFORM_COLOR
        elif self.platform_type == "switch":
            return SWITCH_COLOR
        elif self.platform_type == "door":
            return DOOR_COLOR if self.is_active else (80, 40, 20)
        elif self.platform_type == "moving":
            return (255, 100, 255)  # Фиолетовый для подвижных платформ
        else:
            return PLATFORM_COLOR

    def draw(self, screen, camera):
        """Отрисовка платформы"""
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -self.width <= screen_x <= SCREEN_WIDTH and -self.height <= screen_y <= SCREEN_HEIGHT:
            
            # Если есть текстурированная поверхность, используем её
            if self.surface:
                # Отрисовываем с основанием (смещение вниз)
                screen.blit(self.surface, (screen_x, screen_y - 20))
            else:
                # Fallback к цветным прямоугольникам
                color = self.get_color()
                pygame.draw.rect(screen, color, (screen_x, screen_y, self.width, self.height))
                
                # Добавляем границу для лучшей видимости
                pygame.draw.rect(screen, (0, 0, 0), (screen_x, screen_y, self.width, self.height), 2)
            
            # Добавляем текст для специальных платформ
            if self.platform_type == "alice_only":
                try:
                    font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), 18)
                except:
                    font = pygame.font.Font(None, 20)
                text = font.render("A", True, (255, 255, 255))
                text_rect = text.get_rect(center=(screen_x + self.width//2, screen_y + self.height//2))
                
                # Добавляем фон для текста
                bg_rect = text_rect.inflate(6, 6)
                pygame.draw.rect(screen, (0, 0, 0, 128), bg_rect)
                screen.blit(text, text_rect)
            elif self.platform_type == "rabbit_only":
                try:
                    font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), 18)
                except:
                    font = pygame.font.Font(None, 20)
                text = font.render("R", True, (255, 255, 255))
                text_rect = text.get_rect(center=(screen_x + self.width//2, screen_y + self.height//2))
                
                # Добавляем фон для текста
                bg_rect = text_rect.inflate(6, 6)
                pygame.draw.rect(screen, (0, 0, 0, 128), bg_rect)
                screen.blit(text, text_rect)
            elif self.platform_type == "switch":
                try:
                    font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), 14)
                except:
                    font = pygame.font.Font(None, 16)
                text = font.render("SW", True, (0, 0, 0))
                text_rect = text.get_rect(center=(screen_x + self.width//2, screen_y + self.height//2))
                screen.blit(text, text_rect)
            elif self.platform_type == "moving":
                # Убираем подсказки с подвижных платформ
                pass

class Collectible:
    def __init__(self, x, y, collectible_type="key"):
        self.x = x
        self.y = y
        self.collectible_type = collectible_type
        self.collected = False
        self.rect = pygame.Rect(x, y, 20, 20)

    def collect(self, character_name):
        """Собирает предмет"""
        if not self.collected:
            self.collected = True
            return True
        return False

    def draw(self, screen, camera):
        """Отрисовка предмета"""
        if self.collected:
            return
            
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -20 <= screen_x <= SCREEN_WIDTH and -20 <= screen_y <= SCREEN_HEIGHT:
            pygame.draw.circle(screen, COLLECTIBLE_COLOR, (screen_x + 10, screen_y + 10), 10)
            pygame.draw.circle(screen, (255, 255, 255), (screen_x + 10, screen_y + 10), 10, 2)
            
            # Добавляем символ ключа
            try:
                font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), 14)
            except:
                font = pygame.font.Font(None, 16)
            text = font.render("K", True, (255, 255, 255))
            screen.blit(text, (screen_x + 6, screen_y + 4))

class AnimatedKey:
    def __init__(self, x, y, key_type="key2"):
        self.x = x
        self.y = y
        self.key_type = key_type
        self.collected = False
        self.rect = pygame.Rect(x, y, 32, 32)
        self.animation_frames = []
        self.current_frame = 0
        self.animation_timer = 0
        self.animation_speed = 0.1
        self.load_animation()

    def load_animation(self):
        """Загружает анимацию ключа"""
        try:
            if self.key_type == "key2":
                # Загружаем Key 2 - GOLD
                for i in range(12):  # 12 кадров
                    frame_path = os.path.join("assets", "items", f"Key 2 - GOLD - {i:04d}.png")
                    frame = pygame.image.load(frame_path).convert_alpha()
                    # Сохраняем пропорции при масштабировании
                    original_size = frame.get_size()
                    aspect_ratio = original_size[0] / original_size[1]
                    new_height = 32
                    new_width = int(new_height * aspect_ratio)
                    frame = pygame.transform.scale(frame, (new_width, new_height))
                    self.animation_frames.append(frame)
            elif self.key_type == "key5":
                # Загружаем Key 5 - GOLD
                for i in range(18):  # 18 кадров
                    frame_path = os.path.join("assets", "items", f"Key 5 - GOLD - frame{i:04d}.png")
                    frame = pygame.image.load(frame_path).convert_alpha()
                    # Сохраняем пропорции при масштабировании
                    original_size = frame.get_size()
                    aspect_ratio = original_size[0] / original_size[1]
                    new_height = 32
                    new_width = int(new_height * aspect_ratio)
                    frame = pygame.transform.scale(frame, (new_width, new_height))
                    self.animation_frames.append(frame)
            elif self.key_type == "key15":
                # Загружаем Key 15 - GOLD
                for i in range(48):  # 48 кадров
                    frame_path = os.path.join("assets", "items", f"Key 15 - GOLD - frame{i:04d}.png")
                    frame = pygame.image.load(frame_path).convert_alpha()
                    # Сохраняем пропорции при масштабировании
                    original_size = frame.get_size()
                    aspect_ratio = original_size[0] / original_size[1]
                    new_height = 32
                    new_width = int(new_height * aspect_ratio)
                    frame = pygame.transform.scale(frame, (new_width, new_height))
                    self.animation_frames.append(frame)
        except:
            # Fallback - создаем простой ключ
            fallback = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(fallback, (255, 215, 0), (16, 16), 12)
            pygame.draw.circle(fallback, (255, 255, 255), (16, 16), 8)
            self.animation_frames = [fallback]

    def update(self, dt):
        """Обновляет анимацию"""
        if not self.collected and self.animation_frames:
            self.animation_timer += dt
            if self.animation_timer >= self.animation_speed:
                self.animation_timer = 0
                self.current_frame = (self.current_frame + 1) % len(self.animation_frames)

    def collect(self, character_name):
        """Собирает ключ"""
        if not self.collected:
            self.collected = True
            return True
        return False

    def draw(self, screen, camera):
        """Отрисовка анимированного ключа"""
        if self.collected or not self.animation_frames:
            return
            
        screen_x, screen_y = camera.apply(self.x, self.y)
        current_sprite = self.animation_frames[self.current_frame]
        sprite_width = current_sprite.get_width()
        sprite_height = current_sprite.get_height()
        
        if -sprite_width <= screen_x <= SCREEN_WIDTH and -sprite_height <= screen_y <= SCREEN_HEIGHT:
            screen.blit(current_sprite, (screen_x, screen_y))

class Potion:
    def __init__(self, x, y, potion_type="red"):
        self.x = x
        self.y = y
        self.potion_type = potion_type
        self.collected = False
        self.rect = pygame.Rect(x, y, 24, 32)
        self.load_texture()

    def load_texture(self):
        """Загружает текстуру зелья"""
        try:
            if self.potion_type == "red":
                self.texture = pygame.image.load(os.path.join("assets", "items", "Red Potion.png")).convert_alpha()
            elif self.potion_type == "green":
                self.texture = pygame.image.load(os.path.join("assets", "items", "Green Potion.png")).convert_alpha()
            elif self.potion_type == "blue":
                self.texture = pygame.image.load(os.path.join("assets", "items", "Blue Potion.png")).convert_alpha()
            
            # Сохраняем пропорции при масштабировании
            original_size = self.texture.get_size()
            aspect_ratio = original_size[0] / original_size[1]
            new_height = 32
            new_width = int(new_height * aspect_ratio)
            self.texture = pygame.transform.scale(self.texture, (new_width, new_height))
            
            # Обновляем rect с новыми размерами
            self.rect = pygame.Rect(self.x, self.y, new_width, new_height)
        except:
            self.texture = None

    def collect(self, character_name):
        """Собирает зелье"""
        if not self.collected:
            self.collected = True
            return True
        return False

    def draw(self, screen, camera):
        """Отрисовка зелья"""
        if self.collected:
            return
            
        screen_x, screen_y = camera.apply(self.x, self.y)
        if self.texture:
            texture_width = self.texture.get_width()
            texture_height = self.texture.get_height()
            if -texture_width <= screen_x <= SCREEN_WIDTH and -texture_height <= screen_y <= SCREEN_HEIGHT:
                screen.blit(self.texture, (screen_x, screen_y))
        else:
            # Fallback
            color = (255, 0, 0) if self.potion_type == "red" else (0, 255, 0) if self.potion_type == "green" else (0, 0, 255)
            pygame.draw.rect(screen, color, (screen_x, screen_y, 24, 32))

class Lamp:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 32
        self.height = 64
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.load_texture()

    def load_texture(self):
        """Загружает текстуру фонаря"""
        try:
            self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "lamp.png")).convert_alpha()
            self.texture = pygame.transform.scale(self.texture, (self.width, self.height))
        except:
            self.texture = None

    def draw(self, screen, camera):
        """Отрисовка фонаря"""
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -self.width <= screen_x <= SCREEN_WIDTH and -self.height <= screen_y <= SCREEN_HEIGHT:
            if self.texture:
                screen.blit(self.texture, (screen_x, screen_y))
            else:
                # Fallback - простой фонарь
                pygame.draw.rect(screen, (139, 69, 19), (screen_x, screen_y + 40, 8, 24))  # Столб
                pygame.draw.circle(screen, (255, 255, 0), (screen_x + 4, screen_y + 20), 12)  # Свет
                pygame.draw.circle(screen, (255, 255, 255), (screen_x + 4, screen_y + 20), 8)  # Лампа

class MovingPlatform(Platform):
    def __init__(self, x, y, width, height, target_x, target_y, platform_type="moving", movement_type="linear"):
        super().__init__(x, y, width, height, platform_type)
        self.start_x = x
        self.start_y = y
        self.target_x = target_x
        self.target_y = target_y
        self.is_moving = False
        self.move_speed = 2
        self.activated = False
        self.movement_type = movement_type  # "linear", "horizontal", "vertical"
        self.direction = 1  # Направление движения для циклических платформ
        self.move_distance = 100  # Расстояние движения для циклических платформ

    def activate(self):
        """Активирует движение платформы"""
        if not self.activated:
            self.activated = True
            self.is_moving = True

    def update(self):
        """Обновляет позицию платформы"""
        if not self.activated:
            return
            
        if self.movement_type == "linear":
            # Линейное движение к цели
            if self.is_moving:
                dx = self.target_x - self.x
                dy = self.target_y - self.y
                distance = (dx * dx + dy * dy) ** 0.5
                
                if distance > self.move_speed:
                    self.x += (dx / distance) * self.move_speed
                    self.y += (dy / distance) * self.move_speed
                    self.rect.x = self.x
                    self.rect.y = self.y
                else:
                    self.x = self.target_x
                    self.y = self.target_y
                    self.rect.x = self.x
                    self.rect.y = self.y
                    self.is_moving = False
                    
        elif self.movement_type == "horizontal":
            # Горизонтальное движение туда-сюда
            self.x += self.direction * self.move_speed
            
            # Проверяем границы движения
            if self.x >= self.start_x + self.move_distance:
                self.x = self.start_x + self.move_distance
                self.direction = -1
            elif self.x <= self.start_x - self.move_distance:
                self.x = self.start_x - self.move_distance
                self.direction = 1
                
            self.rect.x = self.x
            
        elif self.movement_type == "vertical":
            # Вертикальное движение туда-сюда
            self.y += self.direction * self.move_speed
            
            # Проверяем границы движения
            if self.y >= self.start_y + self.move_distance:
                self.y = self.start_y + self.move_distance
                self.direction = -1
            elif self.y <= self.start_y - self.move_distance:
                self.y = self.start_y - self.move_distance
                self.direction = 1
                
            self.rect.y = self.y

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
        
        # Создаем платформы и препятствия
        self.platforms = self.create_platforms()
        self.animated_keys = self.create_animated_keys()
        self.potions = self.create_potions()
        self.lamps = self.create_lamps()
        self.collected_keys = 0
        self.collected_potions = 0
        self.moving_platforms = self.create_moving_platforms()

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
        """Создает многослойный фон пещеры с параллаксом"""
        backgrounds = {}
        
        try:
            # Загружаем 4 слоя фона пещеры с правильными именами
            bg1 = pygame.image.load(os.path.join("assets", "tiles", "background_caves  1.png")).convert_alpha()
            bg2 = pygame.image.load(os.path.join("assets", "tiles", "background_caves  2.png")).convert_alpha()
            bg3 = pygame.image.load(os.path.join("assets", "tiles", "background_caves  3.png")).convert_alpha()
            bg4 = pygame.image.load(os.path.join("assets", "tiles", "background_caves  4.png")).convert_alpha()
            
            # Масштабируем фоны под размер экрана
            backgrounds['layer1'] = pygame.transform.scale(bg1, (SCREEN_WIDTH, SCREEN_HEIGHT))
            backgrounds['layer2'] = pygame.transform.scale(bg2, (SCREEN_WIDTH, SCREEN_HEIGHT))
            backgrounds['layer3'] = pygame.transform.scale(bg3, (SCREEN_WIDTH, SCREEN_HEIGHT))
            backgrounds['layer4'] = pygame.transform.scale(bg4, (SCREEN_WIDTH, SCREEN_HEIGHT))
            
        except Exception as e:
            print(f"Ошибка загрузки фона: {e}")
            # Fallback - создаем простой градиентный фон пещеры
            background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            for y in range(SCREEN_HEIGHT):
                # Градиент от темно-серого к черному
                color_value = max(20, 80 - (y * 60 // SCREEN_HEIGHT))
                color = (color_value, color_value - 10, color_value - 5)
                pygame.draw.line(background, color, (0, y), (SCREEN_WIDTH, y))
            
            backgrounds['layer1'] = background
            backgrounds['layer2'] = background.copy()
            backgrounds['layer3'] = background.copy()
            backgrounds['layer4'] = background.copy()
        
        return backgrounds

    def create_platforms(self):
        """Создает платформы и препятствия для кооперативного прохождения"""
        platforms = []
        
        # Обычные платформы для прыжков (подняты выше)
        platforms.append(Platform(800, 750, 100, 20))
        platforms.append(Platform(1000, 700, 100, 20))
        platforms.append(Platform(1300, 650, 100, 20))
        
        # Высокие платформы для зайца (подняты выше)
        platforms.append(Platform(1600, 550, 120, 20))
        platforms.append(Platform(1900, 500, 100, 20))
        platforms.append(Platform(2200, 450, 100, 20))
        
        # Низкие платформы для Алисы (триггеры для подвижных платформ)
        platforms.append(Platform(1800, 800, 100, 20, "alice_trigger"))
        platforms.append(Platform(2000, 770, 100, 20, "alice_trigger"))
        platforms.append(Platform(2300, 750, 100, 20))
        
        # Финальные платформы для совместного прохождения
        platforms.append(Platform(2800, 600, 150, 20))
        platforms.append(Platform(3000, 550, 150, 20))
        
        # Выход
        platforms.append(Platform(3200, 500, 200, 20))
        
        return platforms

    def create_animated_keys(self):
        """Создает анимированные ключи"""
        keys = []
        
        # Ключи на разных платформах (обновленные позиции)
        keys.append(AnimatedKey(850, 720, "key2"))   # На первой платформе
        keys.append(AnimatedKey(1650, 520, "key5"))  # На высокой платформе зайца
        keys.append(AnimatedKey(1850, 770, "key15")) # На платформе Алисы
        
        return keys

    def create_potions(self):
        """Создает зелья"""
        potions = []
        
        # Зелья на других позициях (обновленные)
        potions.append(Potion(950, 720, "red"))    # На первой платформе (сдвинуто)
        potions.append(Potion(1750, 520, "green")) # На высокой платформе зайца (сдвинуто)
        potions.append(Potion(1950, 770, "blue"))  # На платформе Алисы (сдвинуто)
        
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
        
        return lamps

    def create_moving_platforms(self):
        """Создает подвижные платформы для зайца и Алисы"""
        moving_platforms = []
        
        # Платформы для кролика - горизонтальное движение
        moving_platforms.append(MovingPlatform(1500, 600, 100, 20, 0, 0, "moving", "horizontal"))
        moving_platforms.append(MovingPlatform(2100, 550, 100, 20, 0, 0, "moving", "horizontal"))
        
        # Платформы для Алисы - вертикальное движение
        moving_platforms.append(MovingPlatform(1700, 700, 100, 20, 0, 0, "moving", "vertical"))
        moving_platforms.append(MovingPlatform(2300, 650, 100, 20, 0, 0, "moving", "vertical"))
        
        # Активируем их сразу для демонстрации
        for platform in moving_platforms:
            platform.activate()
        
        return moving_platforms

    def check_platform_activation(self):
        """Проверяет активацию подвижных платформ"""
        triggered_platforms = self.my_player.check_platform_triggers(self.platforms)
        
        for platform in triggered_platforms:
            # Когда Алиса становится на платформу, активируем соответствующую подвижную платформу
            platform_id = f"{platform.x}_{platform.y}"
            
            # Активируем подвижные платформы в зависимости от триггера
            if platform.x == 1800:  # Первая платформа Алисы
                if len(self.moving_platforms) > 0 and not self.moving_platforms[0].activated:
                    self.moving_platforms[0].activate()
                    print("Активирована первая подвижная платформа для зайца!")
            elif platform.x == 2000:  # Вторая платформа Алисы
                if len(self.moving_platforms) > 1 and not self.moving_platforms[1].activated:
                    self.moving_platforms[1].activate()
                    print("Активирована вторая подвижная платформа для зайца!")

    def send_data(self):
        """Отправка данных другому игроку"""
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
            "player": {
                "x": self.my_player.x,
                "y": self.my_player.y,
                "facing_right": self.my_player.facing_right,
                "moving": self.my_player.moving
            },
            "dialog": self.dialog_state,
            "collected_keys": collected_keys_data,
            "collected_potions": collected_potions_data
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
                
                # Синхронизируем собранные предметы
                if "collected_keys" in received_data:
                    for key_index in received_data["collected_keys"]:
                        if key_index < len(self.animated_keys):
                            self.animated_keys[key_index].collected = True
                
                if "collected_potions" in received_data:
                    for potion_index in received_data["collected_potions"]:
                        if potion_index < len(self.potions):
                            self.potions[potion_index].collected = True
                
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

    def draw_ui(self, screen):
        """Отрисовка пользовательского интерфейса"""
        # Показываем UI только после завершения диалога
        if not self.dialog_system.dialog_completed:
            return
            
        # Используем пиксельный шрифт
        try:
            pixel_font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), 20)
        except:
            # Fallback на системный шрифт
            pixel_font = pygame.font.Font(None, 20)
        
        # Показываем количество собранных ключей
        keys_text = pixel_font.render(f"Ключи: {self.collected_keys}/3", True, (255, 255, 255))
        screen.blit(keys_text, (10, 10))
        
        # Показываем количество собранных зелий
        potions_text = pixel_font.render(f"Зелья: {self.collected_potions}/3", True, (255, 255, 255))
        screen.blit(potions_text, (10, 35))
        
        # Показываем прогресс
        if self.collected_keys == 3 and self.collected_potions == 3:
            victory_text = pixel_font.render("Все предметы собраны! Найдите выход из норы!", True, (0, 255, 0))
            screen.blit(victory_text, (10, SCREEN_HEIGHT - 30))

    def draw_background_with_parallax(self, screen):
        """Отрисовывает многослойный фон с эффектом параллакса"""
        # Вычисляем смещение для параллакса
        parallax_factor_1 = 0.1  # Самый дальний слой
        parallax_factor_2 = 0.3
        parallax_factor_3 = 0.5
        parallax_factor_4 = 0.7  # Ближайший слой
        
        # Вычисляем смещения
        offset_1 = int(self.camera.scroll_x * parallax_factor_1)
        offset_2 = int(self.camera.scroll_x * parallax_factor_2)
        offset_3 = int(self.camera.scroll_x * parallax_factor_3)
        offset_4 = int(self.camera.scroll_x * parallax_factor_4)
        
        # Отрисовываем слои с параллаксом
        # Слой 1 - самый дальний
        screen.blit(self.background['layer1'], (-offset_1, 0))
        if offset_1 > 0:
            screen.blit(self.background['layer1'], (SCREEN_WIDTH - offset_1, 0))
        
        # Слой 2
        screen.blit(self.background['layer2'], (-offset_2, 0))
        if offset_2 > 0:
            screen.blit(self.background['layer2'], (SCREEN_WIDTH - offset_2, 0))
        
        # Слой 3
        screen.blit(self.background['layer3'], (-offset_3, 0))
        if offset_3 > 0:
            screen.blit(self.background['layer3'], (SCREEN_WIDTH - offset_3, 0))
        
        # Слой 4 - ближайший
        screen.blit(self.background['layer4'], (-offset_4, 0))
        if offset_4 > 0:
            screen.blit(self.background['layer4'], (SCREEN_WIDTH - offset_4, 0))

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
                    if (event.key == pygame.K_SPACE or event.key == pygame.K_w) and not self.dialog_system.is_active:
                        self.my_player.jump()
                    else:
                        self.handle_input(event)

            # Проверяем, есть ли активный диалог, блокирующий движение
            allow_movement = True
            if self.dialog_system.is_active:
                allow_movement = False

            # Обрабатываем нажатия клавиш - добавляем поддержку WASD
            if allow_movement:
                if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                    self.my_player.move(-1)
                elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                    self.my_player.move(1)
                else:
                    self.my_player.move(0)
            else:
                self.my_player.move(0)

            # Обновление физики и проверка диалога
            # Передаем платформы игрокам для проверки коллизий
            self.my_player._platforms = self.platforms + self.moving_platforms
            self.other_player._platforms = self.platforms + self.moving_platforms
            
            self.my_player.update(self.platforms + self.moving_platforms)
            self.other_player.update(self.platforms + self.moving_platforms)
            
            # Обновляем анимации ключей
            for key in self.animated_keys:
                key.update(dt)
            
            # Обновляем подвижные платформы
            for platform in self.moving_platforms:
                platform.update()
            
            # Проверяем сбор ключей
            collected = self.my_player.check_collectibles(self.animated_keys)
            if collected:
                self.collected_keys += len(collected)
                print(f"Собрано ключей: {self.collected_keys}")
            
            # Проверяем сбор зелий
            collected = self.my_player.check_collectibles(self.potions)
            if collected:
                self.collected_potions += len(collected)
                print(f"Собрано зелий: {self.collected_potions}")
            
            # Проверяем активацию подвижных платформ
            self.check_platform_activation()
            
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
            # Отрисовываем фон пещеры с параллаксом
            self.draw_background_with_parallax(self.screen)
            
            platform_y = SCREEN_HEIGHT - PLATFORM_HEIGHT
            self.screen.blit(self.platform, (0, platform_y))
            
            # Отрисовываем дополнительные платформы
            for platform in self.platforms:
                platform.draw(self.screen, self.camera)
            
            # Отрисовываем подвижные платформы
            for platform in self.moving_platforms:
                platform.draw(self.screen, self.camera)
            
            # Отрисовываем предметы
            for collectible in self.animated_keys:
                collectible.draw(self.screen, self.camera)
            for collectible in self.potions:
                collectible.draw(self.screen, self.camera)
            
            # Отрисовываем фонари
            for lamp in self.lamps:
                lamp.draw(self.screen, self.camera)
            
            # Находим Алису и Кролика
            alice = self.my_player if self.my_player.character_name == "alice" else self.other_player
            rabbit = self.other_player if self.my_player.character_name == "alice" else self.my_player
            
            # Сначала отрисовываем Кролика, потом Алису
            rabbit.draw(self.screen, self.camera)
            alice.draw(self.screen, self.camera)
            
            self.screen.blit(self.shadow, (0, 0))
            self.dialog_system.draw(self.screen, self.my_player.character_name)
            
            self.draw_ui(self.screen)
            
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