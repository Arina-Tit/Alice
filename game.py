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
ALICE_JUMP_FORCE = -12  # Увеличиваем силу прыжка Алисы
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
        self.lerp_speed = 0.08  
        self.deadzone_x = 100   
        self.deadzone_y = 80    

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
            
            
            if hasattr(self, '_platforms'):
                new_x = self.check_horizontal_collisions(self._platforms, new_x)
            
            self.x = new_x
            self.last_update_time = current_time
            
        
        if direction != 0:
            self.facing_right = direction > 0
            self.moving = True
            self.current_state = "walk"
        else:
            self.moving = False
            self.current_state = "idle"
            
       
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
        
        
        self.y += self.vel_y

      
        player_rect = pygame.Rect(self.x, self.y, self.width - self.offset, self.height - self.offset)
        
        
        platform_y = WORLD_HEIGHT - PLATFORM_HEIGHT
        if self.y > platform_y - self.height + self.offset:
            self.y = platform_y - self.height + self.offset
            if self.vel_y > 0:
                self.vel_y = 0
                self.is_jumping = False

        
        if platforms:
            for platform in platforms:
                platform_rect = platform.rect
                player_rect = pygame.Rect(self.x, self.y, self.width - self.offset, self.height - self.offset)
                
                
                if player_rect.colliderect(platform_rect):
                   
                    if (old_y + self.height - self.offset <= platform.y + 5 and 
                        self.vel_y > 0 and 
                        self.y + self.height - self.offset > platform.y):
                        self.y = platform.y - self.height + self.offset
                        self.vel_y = 0
                        self.is_jumping = False
                        break
                    
                    elif (old_y >= platform.y + platform.height - 5 and 
                          self.vel_y < 0 and 
                          self.y < platform.y + platform.height):
                        self.y = platform.y + platform.height
                        self.vel_y = 0
                        break

    def check_horizontal_collisions(self, platforms, new_x):
        
        if not platforms:
            return new_x
            
        player_rect = pygame.Rect(new_x, self.y, self.width - self.offset, self.height - self.offset)
        
        for platform in platforms:
            if player_rect.colliderect(platform.rect):
                
                if self.x < platform.x:
                    return platform.x - (self.width - self.offset)
               
                else:
                    return platform.x + platform.width
        
        return new_x

    def check_collectibles(self, collectibles):
        
        player_rect = pygame.Rect(self.x, self.y, self.width - self.offset, self.height - self.offset)
        collected_items = []
        
        for collectible in collectibles:
            if not collectible.collected and player_rect.colliderect(collectible.rect):
                if collectible.collect(self.character_name):
                    collected_items.append(collectible)
        
        return collected_items

    def check_platform_triggers(self, platforms):
        
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
        
        
        self.dialog_bg = pygame.image.load(os.path.join("assets", "gui", "dialog_box.png"))
        self.dialog_bg = pygame.transform.scale(self.dialog_bg, (DIALOG_WIDTH, DIALOG_HEIGHT))
        
        
        try:
            self.alice_portrait = pygame.image.load(os.path.join("assets", "characters", "alice", "alice_dialog.png")).convert_alpha()
            self.alice_portrait = pygame.transform.scale(self.alice_portrait, (128, 128))
        except:
            self.alice_portrait = None
            
        try:
            self.rabbit_portrait = pygame.image.load(os.path.join("assets", "characters", "rabbit", "rabbit_dialog.png")).convert_alpha()
            self.rabbit_portrait = pygame.transform.scale(self.rabbit_portrait, (128, 128))
        except:
            self.rabbit_portrait = None
        
        
        with open(os.path.join("assets", "dialogs", "rabbit_dialog.json"), 'r', encoding='utf-8') as f:
            self.dialogs = json.load(f)
        
        self.reset_state()

    def reset_state(self):
        
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
        self.dialog_completed = False  
        self.exit_hint_timer = 0  
        self.show_exit_hint = False  

    def start_dialog(self, dialog_id, character_name):
        
        if self.dialog_completed:
            return  
            
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
        
        self.dialog_completed = True
        self.dialog_ended = True
        self.is_active = False
        self.show_exit_hint = True
        self.exit_hint_timer = EXIT_HINT_DURATION
        

    def update(self, dt):
        if self.is_active:
            
            if len(self.current_text) < len(self.target_text):
                self.text_timer += dt
                if self.text_timer >= 0.02:
                    self.text_timer = 0
                    self.current_text = self.target_text[:len(self.current_text) + 1]
            

            if self.text_alpha < 255:
                self.text_alpha = min(255, self.text_alpha + 510 * dt)
        
        
        if self.show_exit_hint:
            self.exit_hint_timer -= dt
            if self.exit_hint_timer <= 0:
                self.show_exit_hint = False

    def wrap_text(self, text, max_width):
        
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
                    
                    lines.append(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines

    def draw(self, screen, character_name):
        
        
        if self.show_exit_hint:
            hint_text = "Теперь нужно найти выход из сада!"
            hint_surface = self.font.render(hint_text, True, DIALOG_PROMPT_COLOR)
            hint_x = (SCREEN_WIDTH - hint_surface.get_width()) // 2
            hint_y = SCREEN_HEIGHT // 2
            
            
            bg_rect = pygame.Rect(hint_x - 10, hint_y - 5, hint_surface.get_width() + 20, hint_surface.get_height() + 10)
            bg_surface = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            bg_surface.fill((0, 0, 0, 128))
            screen.blit(bg_surface, bg_rect)
            screen.blit(hint_surface, (hint_x, hint_y))
            return

        if not self.is_active or not self.current_dialog or self.dialog_completed:
            return

        
        dialog_x = (SCREEN_WIDTH - DIALOG_WIDTH) // 2
        dialog_y = 20

        
        screen.blit(self.dialog_bg, (dialog_x, dialog_y))

        
        portrait = None
        if self.current_speaker == "alice" and self.alice_portrait:
            portrait = self.alice_portrait
        elif self.current_speaker == "rabbit" and self.rabbit_portrait:
            portrait = self.rabbit_portrait
        
        if portrait:
            portrait_x = dialog_x + DIALOG_PADDING
            portrait_y = dialog_y + DIALOG_PADDING
            screen.blit(portrait, (portrait_x, portrait_y))
            text_start_x = portrait_x + 140  
        else:
            
            speaker_text = "Алиса" if self.current_speaker == "alice" else "Кролик"
            speaker_surface = self.font.render(speaker_text, True, (255, 255, 100))
            screen.blit(speaker_surface, (dialog_x + DIALOG_PADDING, dialog_y + DIALOG_PADDING))
            text_start_x = dialog_x + DIALOG_PADDING

        
        text_area_width = DIALOG_WIDTH - (text_start_x - dialog_x) - DIALOG_PADDING
        text_start_y = dialog_y + DIALOG_PADDING + 10
        
        
        lines = self.wrap_text(self.current_text, text_area_width)
        
        
        text_y = text_start_y
        max_text_height = DIALOG_HEIGHT - (text_start_y - dialog_y) - DIALOG_PADDING
        
        for line in lines:
            if text_y + FONT_SIZE > dialog_y + DIALOG_HEIGHT - DIALOG_PADDING:
                break  
                
            text_surface = self.font.render(line, True, TEXT_COLOR)
            text_surface.set_alpha(self.text_alpha)
            screen.blit(text_surface, (text_start_x, text_y))
            text_y += FONT_SIZE + 3

        
        if (self.current_text == self.target_text and 
            self.current_speaker == character_name and 
            self.current_choices):
            
            choices_start_y = text_y + 10
            
            for i, choice in enumerate(self.current_choices):
                choice_y = choices_start_y + i * (FONT_SIZE + CHOICE_PADDING)
                
                
                if choice_y + FONT_SIZE > dialog_y + DIALOG_HEIGHT - DIALOG_PADDING:
                    break
                
                color = CHOICE_HOVER_COLOR if i == self.selected_choice else CHOICE_COLOR
                indent = CHOICE_INDENT * 2 if i == self.selected_choice else CHOICE_INDENT
                
                
                choice_text = choice['text']
                max_choice_width = text_area_width - indent
                choice_lines = self.wrap_text(choice_text, max_choice_width)
                
                if choice_lines:
                    choice_surface = self.font.render(choice_lines[0], True, color)
                    screen.blit(choice_surface, (text_start_x + indent, choice_y))

    def handle_input(self, event, character_name):
        
        if not self.is_active or not self.my_turn or not self.current_choices or self.dialog_completed:
            return None

        if event.type == pygame.KEYDOWN:
            
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
        self.platform_type = platform_type  
        self.character_access = character_access  
        self.is_active = True  
        self.rect = pygame.Rect(x, y, width, height)
        
        
        self.load_textures()

    def load_textures(self):
        
        try:
            
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
        
        if not self.block_texture:
            return None
            
        surface = pygame.Surface((self.width, self.height + 20), pygame.SRCALPHA)  
        
        
        block_size = 16
        tile_size = 32  
        
        
        for x in range(0, self.width, tile_size):
            for y in range(0, self.height + 20, tile_size):
                
                if y < self.height:
                    
                    block_rect = pygame.Rect(0, 0, block_size, block_size)
                else:
                    
                    block_rect = pygame.Rect(0, block_size, block_size, block_size)
                
                block_sprite = self.block_texture.subsurface(block_rect)
                scaled_block = pygame.transform.scale(block_sprite, (tile_size, tile_size))
                surface.blit(scaled_block, (x, y))
        
        
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
        
        if not self.is_active and self.platform_type == "door":
            return False
        
        return True

    def get_color(self):
        
        if self.platform_type == "alice_only":
            return ALICE_PLATFORM_COLOR
        elif self.platform_type == "rabbit_only":
            return RABBIT_PLATFORM_COLOR
        elif self.platform_type == "switch":
            return SWITCH_COLOR
        elif self.platform_type == "door":
            return DOOR_COLOR if self.is_active else (80, 40, 20)
        elif self.platform_type == "moving":
            return (255, 100, 255)  
        else:
            return PLATFORM_COLOR

    def draw(self, screen, camera):
        
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -self.width <= screen_x <= SCREEN_WIDTH and -self.height <= screen_y <= SCREEN_HEIGHT:
            
            
            if self.surface:
                
                screen.blit(self.surface, (screen_x, screen_y - 20))
            else:
                
                color = self.get_color()
                pygame.draw.rect(screen, color, (screen_x, screen_y, self.width, self.height))
                
                
                pygame.draw.rect(screen, (0, 0, 0), (screen_x, screen_y, self.width, self.height), 2)
            
            
            if self.platform_type == "alice_only":
                try:
                    font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), 18)
                except:
                    font = pygame.font.Font(None, 20)
                text = font.render("A", True, (255, 255, 255))
                text_rect = text.get_rect(center=(screen_x + self.width//2, screen_y + self.height//2))
                
                
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
                
                pass

class Collectible:
    def __init__(self, x, y, collectible_type="key"):
        self.x = x
        self.y = y
        self.collectible_type = collectible_type
        self.collected = False
        self.rect = pygame.Rect(x, y, 20, 20)

    def collect(self, character_name):
        
        if not self.collected:
            self.collected = True
            return True
        return False

    def draw(self, screen, camera):
        
        if self.collected:
            return
            
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -20 <= screen_x <= SCREEN_WIDTH and -20 <= screen_y <= SCREEN_HEIGHT:
            pygame.draw.circle(screen, COLLECTIBLE_COLOR, (screen_x + 10, screen_y + 10), 10)
            pygame.draw.circle(screen, (255, 255, 255), (screen_x + 10, screen_y + 10), 10, 2)
            
            
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

        try:
            if self.key_type == "key2":
                
                for i in range(12):  
                    frame_path = os.path.join("assets", "items", f"Key 2 - GOLD - {i:04d}.png")
                    frame = pygame.image.load(frame_path).convert_alpha()
                    
                    original_size = frame.get_size()
                    aspect_ratio = original_size[0] / original_size[1]
                    new_height = 32
                    new_width = int(new_height * aspect_ratio)
                    frame = pygame.transform.scale(frame, (new_width, new_height))
                    self.animation_frames.append(frame)
            elif self.key_type == "key5":
                
                for i in range(18):  
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
                
                for i in range(48):  
                    frame_path = os.path.join("assets", "items", f"Key 15 - GOLD - frame{i:04d}.png")
                    frame = pygame.image.load(frame_path).convert_alpha()
                    
                    original_size = frame.get_size()
                    aspect_ratio = original_size[0] / original_size[1]
                    new_height = 32
                    new_width = int(new_height * aspect_ratio)
                    frame = pygame.transform.scale(frame, (new_width, new_height))
                    self.animation_frames.append(frame)
        except:
            
            fallback = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(fallback, (255, 215, 0), (16, 16), 12)
            pygame.draw.circle(fallback, (255, 255, 255), (16, 16), 8)
            self.animation_frames = [fallback]

    def update(self, dt):
        
        if not self.collected and self.animation_frames:
            self.animation_timer += dt
            if self.animation_timer >= self.animation_speed:
                self.animation_timer = 0
                self.current_frame = (self.current_frame + 1) % len(self.animation_frames)

    def collect(self, character_name):
        
        if not self.collected:
            self.collected = True
            return True
        return False

    def draw(self, screen, camera):
        
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
        
        try:
            if self.potion_type == "red":
                self.texture = pygame.image.load(os.path.join("assets", "items", "Red Potion.png")).convert_alpha()
            elif self.potion_type == "green":
                self.texture = pygame.image.load(os.path.join("assets", "items", "Green Potion.png")).convert_alpha()
            elif self.potion_type == "blue":
                self.texture = pygame.image.load(os.path.join("assets", "items", "Blue Potion.png")).convert_alpha()
            

            original_size = self.texture.get_size()
            aspect_ratio = original_size[0] / original_size[1]
            new_height = 32
            new_width = int(new_height * aspect_ratio)
            self.texture = pygame.transform.scale(self.texture, (new_width, new_height))
            
            
            self.rect = pygame.Rect(self.x, self.y, new_width, new_height)
        except:
            self.texture = None

    def collect(self, character_name):
        
        if not self.collected:
            self.collected = True
            return True
        return False

    def draw(self, screen, camera):
        
        if self.collected:
            return
            
        screen_x, screen_y = camera.apply(self.x, self.y)
        if self.texture:
            texture_width = self.texture.get_width()
            texture_height = self.texture.get_height()
            if -texture_width <= screen_x <= SCREEN_WIDTH and -texture_height <= screen_y <= SCREEN_HEIGHT:
                screen.blit(self.texture, (screen_x, screen_y))
        else:
            
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
        
        try:
            self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "lamp.png")).convert_alpha()
            self.texture = pygame.transform.scale(self.texture, (self.width, self.height))
        except:
            self.texture = None

    def draw(self, screen, camera):
        
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -self.width <= screen_x <= SCREEN_WIDTH and -self.height <= screen_y <= SCREEN_HEIGHT:
            if self.texture:
                screen.blit(self.texture, (screen_x, screen_y))
            else:
                
                pygame.draw.rect(screen, (139, 69, 19), (screen_x, screen_y + 40, 8, 24))  # Столб
                pygame.draw.circle(screen, (255, 255, 0), (screen_x + 4, screen_y + 20), 12)  # Свет
                pygame.draw.circle(screen, (255, 255, 255), (screen_x + 4, screen_y + 20), 8)  # Лампа

class Decoration:
    def __init__(self, x, y, decoration_type="grass"):
        self.x = x
        self.y = y
        self.decoration_type = decoration_type
        self.width = 32
        self.height = 32
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.load_texture()

    def load_texture(self):
        
        try:
            if self.decoration_type == "grass1":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "grass_1.png")).convert_alpha()
            elif self.decoration_type == "grass2":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "grass_2.png")).convert_alpha()
            elif self.decoration_type == "grass3":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "grass_3.png")).convert_alpha()
            elif self.decoration_type == "rock1":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "rock_1.png")).convert_alpha()
            elif self.decoration_type == "rock2":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "rock_2.png")).convert_alpha()
            elif self.decoration_type == "rock3":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "rock_3.png")).convert_alpha()
            elif self.decoration_type == "fence":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "fence_1.png")).convert_alpha()
            elif self.decoration_type == "fence2":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "fence_2.png")).convert_alpha()
            
            
            self.texture = pygame.transform.scale(self.texture, (self.width, self.height))
        except:
            self.texture = None

    def draw(self, screen, camera):
        
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -self.width <= screen_x <= SCREEN_WIDTH and -self.height <= screen_y <= SCREEN_HEIGHT:
            if self.texture:
                screen.blit(self.texture, (screen_x, screen_y))
            else:

                color = (34, 139, 34) if "grass" in self.decoration_type else (139, 69, 19)
                pygame.draw.rect(screen, color, (screen_x, screen_y, self.width, self.height))

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
        self.movement_type = movement_type  
        self.direction = 1  
        self.move_distance = 100  

    def activate(self):
        
        if not self.activated:
            self.activated = True
            self.is_moving = True

    def update(self):
        """Обновляет позицию платформы"""
        if not self.activated:
            return
            
        if self.movement_type == "linear":
            
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
            
            self.x += self.direction * self.move_speed
            
            
            if self.x >= self.start_x + self.move_distance:
                self.x = self.start_x + self.move_distance
                self.direction = -1
            elif self.x <= self.start_x - self.move_distance:
                self.x = self.start_x - self.move_distance
                self.direction = 1
                
            self.rect.x = self.x
            
        elif self.movement_type == "vertical":
            
            self.y += self.direction * self.move_speed
            
            
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
        
        # Флаг для контроля состояния сокета
        self.socket_active = True
        
        # Создаем фон и платформу
        self.background = self.create_background()
        self.platform = self.create_platform()
        self.shadow = self.create_shadow()
        
        # Проверяем и создаем файл диалогов, если он отсутствует
        self.ensure_dialog_file_exists()
        
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
            print(f"Проверьте наличие файлов в папке assets/tiles/")
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
        self.receive_thread = threading.Thread(target=self.receive_data, daemon=False)  # Делаем поток не демоном
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
        self.victory_duration = 5.0  # 5 секунд показа финального экрана
        
        # Если мы хост, инициируем первый диалог после небольшой задержки
        if is_host:
            self.initial_dialog_timer = 2.0  # 2 секунды задержки
        else:
            self.initial_dialog_timer = None

    def ensure_dialog_file_exists(self):
        """Проверяет наличие файла диалогов и создает его, если отсутствует"""
        dialog_path = os.path.join("assets", "dialogs")
        dialog_file = os.path.join(dialog_path, "rabbit_dialog.json")
        
        if not os.path.exists(dialog_path):
            os.makedirs(dialog_path)
            print(f"Создана директория диалогов: {dialog_path}")
        
        if not os.path.exists(dialog_file):
            default_dialogs = {
                "start": {
                    "text": "Ой-ой! Я опаздываю! Я опаздываю!",
                    "speaker": "rabbit",
                    "choices": [
                        {
                            "text": "Постойте! Куда вы так спешите?",
                            "next": "dialog2"
                        }
                    ]
                },
                "dialog2": {
                    "text": "На важное-преважное чаепитие! Нет времени объяснять!",
                    "speaker": "rabbit",
                    "choices": [
                        {
                            "text": "Можно мне с вами?",
                            "next": "dialog3"
                        }
                    ]
                },
                "dialog3": {
                    "text": "Следуйте за мной, если осмелитесь! Только поторопитесь!",
                    "speaker": "rabbit",
                    "choices": [
                        {
                            "text": "Я иду за вами!",
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
        
        # Обычные платформы для прыжков (разные высоты для разнообразия)
     
        platforms.append(Platform(1000, 650, 100, 20))  # Средняя высота
        platforms.append(Platform(1300, 600, 100, 20))  # Выше
        
        # Высокие платформы для зайца (немного изменены)
        platforms.append(Platform(1600, 500, 120, 20))  # Немного ниже
        platforms.append(Platform(1900, 450, 100, 20))  # Выше
        platforms.append(Platform(2200, 400, 100, 20))  # Самая высокая
        
        # Низкие платформы для Алисы (триггеры для подвижных платформ)
        platforms.append(Platform(1800, 820, 100, 20, "alice_trigger"))  # Ниже
        platforms.append(Platform(2000, 800, 100, 20, "alice_trigger"))  # Ниже
        
        # Специальные низкие платформы для Алисы (поднимаем выше, чтобы не мешали проходу)
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT
       
        platforms.append(Platform(1100, ground_level - 80, 100, 20))  # Поднимаем выше
        platforms.append(Platform(1400, ground_level - 100, 120, 20))  # Поднимаем выше
        
      
        
        # Дополнительные платформы для разнообразия
       
        platforms.append(Platform(1750, ground_level - 100, 90, 20)) # Средняя высота
        platforms.append(Platform(2450, ground_level - 120, 100, 20)) # Высокая
        
        # Финальные платформы для совместного прохождения
        platforms.append(Platform(2800, 600, 150, 20))
        platforms.append(Platform(3000, 550, 150, 20))
        
        # Выход - убираем низкую платформу под высокой
        platforms.append(Platform(3200, 500, 200, 20))
        
        # Дополнительная платформа для доступа к предметам
        platforms.append(Platform(850, ground_level - 120, 80, 20))  # Для доступа к ключу
        
        return platforms

    def create_animated_keys(self):
        """Создает анимированные ключи"""
        keys = []
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT  # Добавляем определение ground_level
        
        # Ключи на разных уровнях для интересного геймплея
        keys.append(AnimatedKey(1120, ground_level - 112, "key2"))   # На платформе 1100 (первый ключ)
        keys.append(AnimatedKey(1650, 470, "key5"))  # На высокой платформе зайца
        keys.append(AnimatedKey(770, WORLD_HEIGHT - PLATFORM_HEIGHT - 32, "key15")) # На земле для Алисы
        
        return keys

    def create_potions(self):
        """Создает зелья"""
        potions = []
        
        # Зелья на разных уровнях для всех персонажей
        potions.append(Potion(620, WORLD_HEIGHT - PLATFORM_HEIGHT - 92, "red"))    # На платформе 600 (доступно)
        potions.append(Potion(1750, 420, "green")) # На высокой платформе зайца (выше)
        potions.append(Potion(1770, WORLD_HEIGHT - PLATFORM_HEIGHT - 132, "blue"))  # На средней платформе
        
        return potions

    def create_lamps(self):
        """Создает фонари"""
        lamps = []
        
        # Фонари на разных уровнях для лучшего освещения
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT - 64  # На уровне земли
        lamps.append(Lamp(750, ground_level))   # У старта
        lamps.append(Lamp(1250, ground_level))  # На пути
        lamps.append(Lamp(1750, ground_level))  # У платформ Алисы
        lamps.append(Lamp(2150, ground_level))  # У высоких платформ зайца
        lamps.append(Lamp(2750, ground_level))  # У финала
        
        # Дополнительные фонари на платформах
        
        lamps.append(Lamp(1620, 470))  # На высокой платформе
        lamps.append(Lamp(2820, 570))  # На финальной платформе
        
        return lamps

    def create_decorations(self):
        """Создает декорации"""
        decorations = []
        
        # Уменьшенное количество декораций на земле
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT - 32
        decorations.append(Decoration(700, ground_level, "rock1"))
        decorations.append(Decoration(1500, ground_level, "grass2"))
        decorations.append(Decoration(2100, ground_level, "fence"))
        decorations.append(Decoration(2700, ground_level, "rock2"))
        
        # Декорации на платформах (обновленные позиции)
        decorations.append(Decoration(1020, 620, "grass2"))     # На второй платформе
        decorations.append(Decoration(1320, 570, "fence"))      # На третьей платформе
        decorations.append(Decoration(1620, 470, "rock1"))      # На высокой платформе
        decorations.append(Decoration(1920, 420, "grass3"))     # На платформе зайца
        decorations.append(Decoration(2220, 370, "rock2"))      # На самой высокой платформе
        
        # Декорации на новых платформах
        decorations.append(Decoration(1770, ground_level - 100, "rock3"))  # На средней
        decorations.append(Decoration(2470, ground_level - 120, "fence"))  # На высокой
        
        return decorations

    def create_signs(self):
        """Создает знаки"""
        signs = []
        
        # Только два знака в самом конце карты
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT - 48
        
        # Знак на высокой платформе (для зайца)
        signs.append(Sign(2850, 550))  # На платформе 2800, 600
        
        # Знак на земле (для Алисы)
        signs.append(Sign(2850, ground_level))  # На земле
        
        return signs

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

    def check_victory_condition(self):
        """Проверяет условие победы - оба персонажа рядом с знаками и все предметы собраны"""
        if self.victory_achieved:
            return
            
        # Проверяем, собраны ли все предметы
        if self.collected_keys < 3 or self.collected_potions < 3:
            return  # Если не все предметы собраны, победа невозможна
            
        # Находим позиции обоих игроков
        alice = self.my_player if self.my_player.character_name == "alice" else self.other_player
        rabbit = self.other_player if self.my_player.character_name == "alice" else self.my_player
        
        # Проверяем расстояние до знаков (первый на платформе, второй на земле)
        if len(self.signs) >= 2:
            platform_sign = self.signs[0]  # Знак на платформе (для зайца)
            ground_sign = self.signs[1]    # Знак на земле (для Алисы)
            
            # Расстояние для активации знака
            sign_distance = 80
            
            # Проверяем, находится ли зайец рядом со знаком на платформе, а Алиса рядом со знаком на земле
            rabbit_near_platform = ((rabbit.x - platform_sign.x) ** 2 + (rabbit.y - platform_sign.y) ** 2) ** 0.5 < sign_distance
            alice_near_ground = ((alice.x - ground_sign.x) ** 2 + (alice.y - ground_sign.y) ** 2) ** 0.5 < sign_distance
            
            # Условие победы: все предметы собраны И зайец у знака на платформе И Алиса у знака на земле
            if rabbit_near_platform and alice_near_ground:
                self.victory_achieved = True
                self.victory_timer = 0
                print("Победа! Добро пожаловать в страну чудес!")

    def draw_victory_screen(self, screen):
        """Отрисовывает экран победы"""
        if not self.victory_achieved:
            return
            
        # Белый фон с плавным появлением
        white_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        white_surface.fill((255, 255, 255))
        white_alpha = min(255, int(self.victory_timer * 255))  # Плавное появление белого
        white_surface.set_alpha(white_alpha)
        screen.blit(white_surface, (0, 0))
        
        # Текст победы (черный, с анимацией печатания)
        if self.victory_timer > 1:  # Текст появляется через секунду
            try:
                font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), 48)
            except:
                font = pygame.font.Font(None, 48)
            
            full_text = "Добро пожаловать в страну чудес!"
            # Анимация печатания текста
            text_progress = min(1.0, (self.victory_timer - 1) * 0.5)  # Полное появление за 2 секунды
            visible_chars = int(len(full_text) * text_progress)
            current_text = full_text[:visible_chars]
            
            if current_text:  # Проверяем, что текст не пустой
                text = font.render(current_text, True, (0, 0, 0))  # Черный текст
                text_rect = text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
                screen.blit(text, text_rect)
        
        # Улыбка появляется после завершения анимации текста
        if self.victory_timer > 4 and self.smile_image:  # Улыбка появляется через 4 секунды
            smile_alpha = min(255, int((self.victory_timer - 4) * 255))  # Плавное появление
            
            # Картинка на весь экран
            scaled_image = pygame.transform.scale(self.smile_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
            
            # Создаем временную поверхность для правильного наложения прозрачности
            temp_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            temp_surface.blit(scaled_image, (0, 0))
            temp_surface.set_alpha(smile_alpha)
            screen.blit(temp_surface, (0, 0))

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
            # Отправляем сообщение о завершении диалога
            try:
                data = pickle.dumps({
                    "type": "dialog_end",
                    "dialog_state": self.dialog_state
                })
                self.socket.sendto(data, self.other_address)
            except Exception as e:
                print(f"Ошибка при отправке завершения диалога: {e}")
            return

        # Переход к следующему диалогу
        if next_dialog and next_dialog in self.dialog_system.dialogs:
            next_dialog_data = self.dialog_system.dialogs[next_dialog]
            next_speaker = next_dialog_data.get("speaker")
            
            self.dialog_state["current_dialog_id"] = next_dialog
            self.dialog_state["current_speaker"] = next_speaker
            self.dialog_state["is_active"] = True
            
            # Отправляем обновление состояния диалога
            try:
                data = pickle.dumps({
                    "type": "dialog_update",
                    "dialog_state": self.dialog_state
                })
                self.socket.sendto(data, self.other_address)
            except Exception as e:
                print(f"Ошибка при отправке обновления диалога: {e}")
            
            # Запускаем новый диалог
            self.dialog_system.reset_state()
            self.dialog_system.start_dialog(next_dialog, self.my_player.character_name)
        else:
            # Если следующего диалога нет, завершаем
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
                
                # Обработка сообщений о подключении
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
        if not self.socket_active:  # Проверяем флаг перед отправкой
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
                    "moving": self.my_player.moving
                },
                "collected_keys": collected_keys_data,
                "collected_potions": collected_potions_data,
                "counters": {
                    "keys": self.collected_keys,
                    "potions": self.collected_potions
                }
            })
            if self.socket_active:  # Дополнительная проверка перед отправкой
                self.socket.sendto(data, self.other_address)
        except socket.error:
            self.socket_active = False
        except Exception:
            pass

    def close(self):
        """Корректно закрываем игру и сетевое соединение"""
        # Устанавливаем флаг завершения работы
        self.is_shutting_down = True
        self.socket_active = False
        
        # Закрываем сокет
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
        
        # Ждем завершения потока receive_thread
        if hasattr(self, 'receive_thread'):
            try:
                self.receive_thread.join(timeout=2.0)  # Увеличиваем таймаут до 2 секунд
            except:
                pass

    def run(self):
        running = True
        last_time = time.time()
        try:
            while running:
                current_time = time.time()
                dt = current_time - last_time
                last_time = current_time
                
                # Обработка начального диалога для хоста
                if self.is_host and self.initial_dialog_timer is not None:
                    self.initial_dialog_timer -= dt
                    if self.initial_dialog_timer <= 0:
                        self.initial_dialog_timer = None
                        self.start_dialog("start")

                # Получаем состояние клавиш
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

                # Проверяем, есть ли активный диалог, блокирующий движение
                allow_movement = not self.dialog_system.is_active

                # Обрабатываем нажатия клавиш
                if allow_movement:
                    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                        self.my_player.move(-1)
                    elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                        self.my_player.move(1)
                    else:
                        self.my_player.move(0)
                else:
                    self.my_player.move(0)

                # Обновления игры...
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
                    if self.victory_timer >= self.victory_duration:
                        running = False
                        break
            
                if self.socket_active:
                    self.send_data()
            
                # Отрисовка
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
        
        except Exception as e:
            print(f"Ошибка в игровом цикле: {e}")
            self.is_shutting_down = True
        finally:
            self.close()
            return self.victory_achieved  # Возвращаем флаг победы

    def handle_input(self, event):
        """Обработка ввода для диалогов"""
        if not self.dialog_system.is_active:
            return

        choice = self.dialog_system.handle_input(event, self.my_player.character_name)
        if choice is not None and self.dialog_system.my_turn:
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
            not self.dialog_system.dialog_completed and
            self.my_player.character_name == "alice"):
            
                    self.start_dialog("start")

    def start_dialog(self, dialog_id):
        """Начало диалога"""
        if not self.dialog_system.dialog_completed:
            print(f"Начинаем диалог: {dialog_id}")
            self.dialog_system.start_dialog(dialog_id, self.my_player.character_name)
            self.dialog_state["is_active"] = True
            self.dialog_state["current_dialog_id"] = dialog_id
            self.dialog_state["current_speaker"] = "alice"
            
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
        
        # Отправляем сообщение о завершении диалога
        try:
            data = pickle.dumps({
                "type": "dialog_end",
                "dialog_state": self.dialog_state
            })
            self.socket.sendto(data, self.other_address)
        except Exception as e:
            print(f"Ошибка при отправке завершения диалога: {e}")

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
        
        # Показываем прогресс и подсказки
        if self.collected_keys == 3 and self.collected_potions == 3:
            victory_text = pixel_font.render("Все предметы собраны! Найдите выход из сада!", True, (0, 255, 0))
            screen.blit(victory_text, (10, SCREEN_HEIGHT - 30))
        else:
            hint_text = pixel_font.render("Соберите все предметы, чтобы активировать выход!", True, (255, 200, 0))
            screen.blit(hint_text, (10, SCREEN_HEIGHT - 30))

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
        
        # Заполняем экран черным цветом как базовый фон
        screen.fill((0, 0, 0))
        
        # Отрисовываем слои с параллаксом, если они доступны
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

class Flag:
    def __init__(self, x, y, flag_type="top"):
        self.x = x
        self.y = y
        self.flag_type = flag_type  # "top" или "bottom"
        self.width = 32
        self.height = 64
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.load_texture()

    def load_texture(self):
        """Загружает текстуру флага"""
        try:
            # Используем текстуру лампы как основу для флага
            self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "lamp.png")).convert_alpha()
            self.texture = pygame.transform.scale(self.texture, (self.width, self.height))
            
            # Создаем флаг поверх лампы
            flag_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            flag_surface.blit(self.texture, (0, 0))
            
            # Добавляем флаг
            flag_color = (255, 0, 0) if self.flag_type == "top" else (0, 0, 255)
            pygame.draw.rect(flag_surface, flag_color, (self.width//2, 5, 20, 15))
            pygame.draw.polygon(flag_surface, flag_color, [(self.width//2 + 20, 5), (self.width//2 + 20, 12), (self.width//2 + 25, 10)])
            
            self.texture = flag_surface
        except:
            # Fallback - простой флаг
            self.texture = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.rect(self.texture, (139, 69, 19), (self.width//2 - 2, 20, 4, 40))  # Столб
            flag_color = (255, 0, 0) if self.flag_type == "top" else (0, 0, 255)
            pygame.draw.rect(self.texture, flag_color, (self.width//2, 5, 20, 15))

    def draw(self, screen, camera):
        """Отрисовка флага"""
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -self.width <= screen_x <= SCREEN_WIDTH and -self.height <= screen_y <= SCREEN_HEIGHT:
            screen.blit(self.texture, (screen_x, screen_y))

class Decoration:
    def __init__(self, x, y, decoration_type="grass"):
        self.x = x
        self.y = y
        self.decoration_type = decoration_type
        self.width = 32
        self.height = 32
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.load_texture()

    def load_texture(self):
        """Загружает текстуру декорации"""
        try:
            if self.decoration_type == "grass1":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "grass_1.png")).convert_alpha()
            elif self.decoration_type == "grass2":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "grass_2.png")).convert_alpha()
            elif self.decoration_type == "grass3":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "grass_3.png")).convert_alpha()
            elif self.decoration_type == "rock1":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "rock_1.png")).convert_alpha()
            elif self.decoration_type == "rock2":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "rock_2.png")).convert_alpha()
            elif self.decoration_type == "rock3":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "rock_3.png")).convert_alpha()
            elif self.decoration_type == "fence":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "fence_1.png")).convert_alpha()
            elif self.decoration_type == "fence2":
                self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "fence_2.png")).convert_alpha()
            
            # Масштабируем декорацию
            self.texture = pygame.transform.scale(self.texture, (self.width, self.height))
        except:
            self.texture = None

    def draw(self, screen, camera):
        """Отрисовка декорации"""
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -self.width <= screen_x <= SCREEN_WIDTH and -self.height <= screen_y <= SCREEN_HEIGHT:
            if self.texture:
                screen.blit(self.texture, (screen_x, screen_y))
            else:
                # Fallback - простая декорация
                color = (34, 139, 34) if "grass" in self.decoration_type else (139, 69, 19)
                pygame.draw.rect(screen, color, (screen_x, screen_y, self.width, self.height))

    def create_flags(self):
        """Создает флаги для финала"""
        flags = []
        
        # Верхний флаг на высокой платформе зайца (2200, 450)
        flags.append(Flag(2220, 386, "top"))  # На платформе 2200, 450 - высота флага 64
        
        # Нижний флаг под платформой
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT - 64
        flags.append(Flag(2220, ground_level, "bottom"))
        
        return flags

    def create_signs(self):
        """Создает знаки"""
        signs = []
        
        # Только два знака в самом конце карты
        ground_level = WORLD_HEIGHT - PLATFORM_HEIGHT - 48
        
        # Знак на высокой платформе (для зайца)
        signs.append(Sign(2850, 550))  # На платформе 2800, 600
        
        # Знак на земле (для Алисы)
        signs.append(Sign(2850, ground_level))  # На земле
        
        return signs

class Sign:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 32
        self.height = 48
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.detection_radius = 80  # Радиус обнаружения персонажей
        self.is_player_near = False
        self.load_texture()

    def load_texture(self):
        """Загружает текстуру знака"""
        try:
            self.texture = pygame.image.load(os.path.join("assets", "tiles", "oak_woods_v1.0", "decorations", "sign.png")).convert_alpha()
            self.texture = pygame.transform.scale(self.texture, (self.width, self.height))
        except:
            # Fallback - простой знак
            self.texture = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            # Столб
            pygame.draw.rect(self.texture, (139, 69, 19), (self.width//2 - 2, 30, 4, 18))
            # Табличка
            pygame.draw.rect(self.texture, (160, 82, 45), (4, 8, 24, 16))
            pygame.draw.rect(self.texture, (0, 0, 0), (4, 8, 24, 16), 2)

    def update(self, players):
        """Обновляет состояние знака в зависимости от близости игроков"""
        self.is_player_near = False
        
        for player in players:
            distance = ((player.x - self.x) ** 2 + (player.y - self.y) ** 2) ** 0.5
            if distance <= self.detection_radius:
                self.is_player_near = True
                break

    def draw(self, screen, camera):
        """Отрисовка знака с размытой подсветкой"""
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -self.width <= screen_x <= SCREEN_WIDTH and -self.height <= screen_y <= SCREEN_HEIGHT:
            # Создаем размытое свечение
            glow_color = (0, 255, 0) if self.is_player_near else (255, 0, 0)
            
            # Создаем несколько слоев свечения для эффекта размытия
            glow_sizes = [40, 30, 20, 10]
            glow_alphas = [30, 50, 80, 120]
            
            for size, alpha in zip(glow_sizes, glow_alphas):
                glow_surface = pygame.Surface((self.width + size, self.height + size), pygame.SRCALPHA)
                glow_rect = pygame.Rect(0, 0, self.width + size, self.height + size)
                
                # Создаем градиентное свечение
                for i in range(size // 2):
                    current_alpha = max(0, alpha - (i * alpha // (size // 2)))
                    current_color = (*glow_color, current_alpha)
                    
                    inner_rect = pygame.Rect(i, i, self.width + size - 2*i, self.height + size - 2*i)
                    if inner_rect.width > 0 and inner_rect.height > 0:
                        pygame.draw.ellipse(glow_surface, current_color, inner_rect)
                
                screen.blit(glow_surface, (screen_x - size//2, screen_y - size//2))
            
            # Отрисовываем сам знак
            if self.texture:
                screen.blit(self.texture, (screen_x, screen_y))
            else:
                # Fallback
                pygame.draw.rect(screen, (139, 69, 19), (screen_x + self.width//2 - 2, screen_y + 30, 4, 18))
                pygame.draw.rect(screen, (160, 82, 45), (screen_x + 4, screen_y + 8, 24, 16))
                pygame.draw.rect(screen, (0, 0, 0), (screen_x + 4, screen_y + 8, 24, 16), 2)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python game.py [host/client]")
        sys.exit(1)

    is_host = sys.argv[1].lower() == "host"
    game = Game("localhost", is_host)
    game.run() 