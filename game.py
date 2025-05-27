import pygame
import socket
import pickle
import threading
import sys
import os
import time

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

# Цвета
WHITE = (255, 255, 255)
GRAY = (100, 100, 100)

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
        self.base_y = y  # Сохраняем базовую высоту
        self.character_name = character_name
        self.vel_y = 0
        self.is_jumping = False
        self.facing_right = True
        self.moving = False
        self.width = ALICE_WIDTH if character_name == "alice" else RABBIT_WIDTH
        self.height = ALICE_HEIGHT if character_name == "alice" else RABBIT_HEIGHT
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
            
        self.facing_right = direction >= 0 if direction != 0 else self.facing_right
        self.moving = direction != 0
        
        # Обновляем состояние анимации
        new_state = "walk" if self.moving else "idle"
        if new_state != self.current_state:
            self.last_state = self.current_state
            self.current_state = new_state
            self.state_changed = True
            # Сбрасываем анимацию при смене состояния
            self.sprites[self.current_state].reset_animation()

    def jump(self):
        if not self.is_jumping:
            self.vel_y = self.jump_force
            self.is_jumping = True

    def update(self):
        self.vel_y += GRAVITY
        self.y += self.vel_y

        # Обработка приземления с учетом базовой высоты
        if self.y > self.base_y:
            self.y = self.base_y
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

class Game:
    def __init__(self, host, is_host):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("P2P Game")
        self.clock = pygame.time.Clock()
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)
        
        self.background = self.create_background()

        # Создание игроков с соответствующими спрайтами
        if is_host:
            self.my_player = Player(100, WORLD_HEIGHT - ALICE_HEIGHT, "alice")
            self.other_player = Player(250, WORLD_HEIGHT - RABBIT_HEIGHT - 50, "rabbit")
        else:
            self.my_player = Player(250, WORLD_HEIGHT - RABBIT_HEIGHT - 50, "rabbit")
            self.other_player = Player(100, WORLD_HEIGHT - ALICE_HEIGHT, "alice")

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

    def create_background(self):
        background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        background.fill(WHITE)
        return background

    def draw_background(self):
        # Просто заливаем экран белым цветом
        self.screen.blit(self.background, (0, 0))

    def receive_data(self):
        while True:
            try:
                data, addr = self.socket.recvfrom(1024)
                other_data = pickle.loads(data)
                self.other_player.x = other_data[0]
                self.other_player.y = other_data[1]
                self.other_player.facing_right = other_data[2]
                self.other_player.moving = other_data[3]
            except:
                pass

    def send_data(self):
        data = pickle.dumps((
            self.my_player.x,
            self.my_player.y,
            self.my_player.facing_right,
            self.my_player.moving
        ))
        self.socket.sendto(data, self.other_address)

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.my_player.jump()

            # Обработка нажатий клавиш
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]:
                self.my_player.move(-1)
            elif keys[pygame.K_RIGHT]:
                self.my_player.move(1)
            else:
                self.my_player.move(0)

            # Обновление физики
            self.my_player.update()
            self.other_player.update()

            # Обновление камеры с предсказанием движения
            next_x = self.my_player.x
            next_y = self.my_player.y
            if keys[pygame.K_LEFT]:
                next_x -= self.my_player.move_speed * 5
            elif keys[pygame.K_RIGHT]:
                next_x += self.my_player.move_speed * 5
            self.camera.update(next_x, next_y)

            # Отправка данных
            self.send_data()

            # Отрисовка
            self.draw_background()
            self.my_player.draw(self.screen, self.camera)
            self.other_player.draw(self.screen, self.camera)
            
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