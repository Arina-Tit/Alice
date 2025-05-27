import pygame
import socket
import pickle
import threading
import sys
import os
import time
import random
import json
from game import Player, Camera, DialogSystem, Platform, AnimatedKey, Potion

# Константы
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
WORLD_WIDTH = 3000
WORLD_HEIGHT = 1000

# Физика
GRAVITY = 0.5
ALICE_JUMP_FORCE = -12
RABBIT_JUMP_FORCE = -20
ALICE_MOVE_SPEED = 6
RABBIT_MOVE_SPEED = 8

# Размеры объектов
ALICE_WIDTH = 192
ALICE_HEIGHT = 192
RABBIT_WIDTH = 80
RABBIT_HEIGHT = 80
ALICE_OFFSET = 70
RABBIT_OFFSET = 10

# Константы для диалогов
DIALOG_PADDING = 40
DIALOG_WIDTH = 700
DIALOG_HEIGHT = 200
DIALOG_TRIGGER_DISTANCE = 150

class CheshireCat:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 128
        self.height = 128
        self.visible = False
        self.fade_progress = 0
        self.rect = pygame.Rect(x, y, self.width, self.height)
        
        # Состояния анимации
        self.current_state = "idle"  # или "smile"
        self.animation_timer = 0
        self.animation_speed = 0.1
        self.state_duration = 3.0  # Длительность каждого состояния
        self.state_timer = 0
        
        self.load_textures()

    def load_textures(self):
        try:
            # Загружаем два состояния кота
            self.textures = {
                "idle": pygame.image.load(os.path.join("assets", "characters", "cat_idle.png")).convert_alpha(),
                "smile": pygame.image.load(os.path.join("assets", "characters", "cat_smile.png")).convert_alpha()
            }
            
            # Масштабируем текстуры
            for state in self.textures:
                self.textures[state] = pygame.transform.scale(self.textures[state], 
                                                            (self.width, self.height))
        except Exception as e:
            print(f"Ошибка загрузки текстур кота: {e}")
            fallback = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.ellipse(fallback, (128, 0, 128), (0, 0, self.width, self.height))
            self.textures = {
                "idle": fallback,
                "smile": fallback
            }

    def update(self, dt):
        # Обновляем таймер состояния
        self.state_timer += dt
        if self.state_timer >= self.state_duration:
            self.state_timer = 0
            # Меняем состояние
            self.current_state = "smile" if self.current_state == "idle" else "idle"
        
        # Обновляем прозрачность появления/исчезновения
        if self.visible:
            self.fade_progress = min(1.0, self.fade_progress + dt)
        else:
            self.fade_progress = max(0.0, self.fade_progress - dt)

    def draw(self, screen, camera):
        if self.fade_progress > 0:
            screen_x, screen_y = camera.apply(self.x, self.y)
            
            # Получаем текущую текстуру
            current_texture = self.textures[self.current_state]
            
            # Создаем копию для изменения прозрачности
            temp_surface = current_texture.copy()
            temp_surface.set_alpha(int(255 * self.fade_progress))
            
            screen.blit(temp_surface, (screen_x, screen_y))

class Box:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 64
        self.height = 64
        self.vel_y = 0
        self.is_falling = False
        self.on_ground = False
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.load_texture()

    def load_texture(self):
        try:
            # Загружаем текстуру ящика
            self.texture = pygame.image.load(os.path.join("assets", "items", "crate.png")).convert_alpha()
            self.texture = pygame.transform.scale(self.texture, (self.width, self.height))
        except Exception as e:
            print(f"Ошибка загрузки текстуры ящика: {e}")
            self.texture = pygame.Surface((self.width, self.height))
            self.texture.fill((139, 69, 19))
            pygame.draw.rect(self.texture, (101, 67, 33), (0, 0, self.width, self.height), 4)

    def start_fall(self):
        """Начать падение ящика"""
        if not self.is_falling and not self.on_ground:
            self.is_falling = True
            self.vel_y = 0

    def update(self, platforms):
        if self.is_falling:
            self.vel_y += GRAVITY
            self.y += self.vel_y
            self.rect.y = self.y

            # Проверка столкновений с платформами
            for platform in platforms:
                if self.rect.colliderect(platform.rect):
                    if self.vel_y > 0:  # Падаем вниз
                        self.y = platform.rect.top - self.height
                        self.vel_y = 0
                        self.is_falling = False
                        self.on_ground = True
                        break

    def draw(self, screen, camera):
        screen_x, screen_y = camera.apply(self.x, self.y)
        if -self.width <= screen_x <= SCREEN_WIDTH and -self.height <= screen_y <= SCREEN_HEIGHT:
            screen.blit(self.texture, (screen_x, screen_y))
            
            # Добавляем эффект тени при падении
            if self.is_falling:
                shadow_y = WORLD_HEIGHT - 50 - 10
                shadow_x = screen_x + self.width // 4
                shadow_width = self.width // 2
                shadow_height = 10
                shadow = pygame.Surface((shadow_width, shadow_height), pygame.SRCALPHA)
                pygame.draw.ellipse(shadow, (0, 0, 0, 128), (0, 0, shadow_width, shadow_height))
                screen.blit(shadow, (shadow_x, shadow_y)) 

class Level2:
    def __init__(self, host, is_host):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Alice in Wonderland - Level 2")
        self.clock = pygame.time.Clock()
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)
        
        # Сетевые компоненты
        self.socket_active = True
        self.is_host = is_host
        self.setup_network(host)
        
        # Создаем игроков
        self.create_players()
        
        # Загружаем фон
        self.load_background()
        
        # Создаем объекты уровня
        self.platforms = self.create_platforms()
        self.boxes = self.create_boxes()
        self.keys = self.create_keys()
        self.potions = self.create_potions()
        self.cheshire_cat = CheshireCat(1500, 300)
        
        # Создаем диалоговую систему
        self.dialog_system = DialogSystem()
        self.load_cat_dialogs()
        
        # Состояние игры
        self.collected_keys = 0
        self.collected_potions = 0
        self.puzzle_solved = False
        self.is_shutting_down = False

    def setup_network(self, host):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.is_host:
            self.socket.bind((host, 5002))
            self.other_address = (host, 5003)
        else:
            self.socket.bind((host, 5003))
            self.other_address = (host, 5002)
        
        self.socket.settimeout(0.1)
        self.receive_thread = threading.Thread(target=self.receive_data, daemon=True)
        self.receive_thread.start()

    def create_players(self):
        platform_y = WORLD_HEIGHT - 100
        if self.is_host:
            self.my_player = Player(100, platform_y, "alice")
            self.other_player = Player(250, platform_y, "rabbit")
        else:
            self.my_player = Player(250, platform_y, "rabbit")
            self.other_player = Player(100, platform_y, "alice")

    def load_background(self):
        """Загружает многослойный фон"""
        self.backgrounds = {}
        try:
            # Загружаем все три слоя фона
            bg1 = pygame.image.load(os.path.join("assets", "tiles", "BG_1.png")).convert_alpha()
            bg2 = pygame.image.load(os.path.join("assets", "tiles", "BG_2.png")).convert_alpha()
            bg3 = pygame.image.load(os.path.join("assets", "tiles", "BG_3.png")).convert_alpha()
            
            # Масштабируем каждый слой под размер экрана
            self.backgrounds['layer1'] = pygame.transform.scale(bg1, (SCREEN_WIDTH, SCREEN_HEIGHT))
            self.backgrounds['layer2'] = pygame.transform.scale(bg2, (SCREEN_WIDTH, SCREEN_HEIGHT))
            self.backgrounds['layer3'] = pygame.transform.scale(bg3, (SCREEN_WIDTH, SCREEN_HEIGHT))
            
        except Exception as e:
            print(f"Ошибка загрузки фона: {e}")
            fallback = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            for y in range(SCREEN_HEIGHT):
                color_value = max(20, 80 - (y * 60 // SCREEN_HEIGHT))
                color = (color_value, color_value - 10, color_value - 5)
                pygame.draw.line(fallback, color, (0, y), (SCREEN_WIDTH, y))
            
            self.backgrounds['layer1'] = fallback
            self.backgrounds['layer2'] = fallback.copy()
            self.backgrounds['layer3'] = fallback.copy()

    def draw_background_with_parallax(self, screen):
        """Отрисовывает многослойный фон с эффектом параллакса"""
        parallax_factors = {
            'layer1': 0.2,  # Дальний слой движется медленнее
            'layer2': 0.4,  # Средний слой
            'layer3': 0.6   # Ближний слой движется быстрее
        }
        
        screen.fill((0, 0, 0))
        
        for layer, factor in parallax_factors.items():
            if layer in self.backgrounds:
                offset = int(self.camera.scroll_x * factor)
                screen.blit(self.backgrounds[layer], (-offset % SCREEN_WIDTH, 0))
                if offset > 0:
                    screen.blit(self.backgrounds[layer], 
                              (SCREEN_WIDTH - (offset % SCREEN_WIDTH), 0))

    def create_platforms(self):
        platforms = []
        
        # Основная платформа
        platforms.append(Platform(0, WORLD_HEIGHT - 50, WORLD_WIDTH, 50))
        
        # Платформы для кролика (верхний путь)
        platforms.append(Platform(500, 400, 200, 20))
        platforms.append(Platform(800, 350, 200, 20))
        platforms.append(Platform(1200, 300, 200, 20))
        
        # Платформы для Алисы (нижний путь)
        platforms.append(Platform(600, 600, 150, 20))
        platforms.append(Platform(900, 550, 150, 20))
        
        # Платформы для головоломки
        platforms.append(Platform(1500, 400, 100, 20, "switch"))
        platforms.append(Platform(1700, 400, 100, 20, "switch"))
        
        return platforms

    def create_boxes(self):
        boxes = []
        # Коробки, которые кролик может сбросить
        boxes.append(Box(800, 300))
        boxes.append(Box(1200, 250))
        return boxes

    def create_keys(self):
        keys = []
        # Ключи на разных уровнях
        keys.append(AnimatedKey(700, 350, "key2"))
        keys.append(AnimatedKey(1300, 250, "key5"))
        keys.append(AnimatedKey(1800, 350, "key15"))
        return keys

    def create_potions(self):
        potions = []
        # Зелья на разных уровнях
        potions.append(Potion(600, 550, "red"))
        potions.append(Potion(1100, 500, "blue"))
        potions.append(Potion(1600, 350, "green"))
        return potions

    def load_cat_dialogs(self):
        cat_dialogs = {
            "cat_start": {
                "text": "Ах, какие интересные гости! Алиса и Белый Кролик...",
                "speaker": "cat",
                "choices": [
                    {
                        "text": "Кто ты?",
                        "next": "cat_intro"
                    }
                ]
            },
            "cat_intro": {
                "text": "Я - Чеширский Кот. И я могу подсказать вам путь... Или запутать ещё больше!",
                "speaker": "cat",
                "choices": [
                    {
                        "text": "Помоги нам, пожалуйста!",
                        "next": "cat_hint"
                    }
                ]
            },
            "cat_hint": {
                "text": "Кролик должен помочь Алисе снизу... А может и сверху? Хи-хи-хи!",
                "speaker": "cat",
                "choices": [
                    {
                        "text": "Спасибо за подсказку!",
                        "next": "end"
                    }
                ]
            }
        }
        
        # Сохраняем диалоги в файл
        dialog_path = os.path.join("assets", "dialogs")
        if not os.path.exists(dialog_path):
            os.makedirs(dialog_path)
        
        with open(os.path.join(dialog_path, "cat_dialog.json"), 'w', encoding='utf-8') as f:
            json.dump(cat_dialogs, f, ensure_ascii=False, indent=4)
        
        # Загружаем диалоги в систему
        self.dialog_system.dialogs.update(cat_dialogs)

    def check_cat_trigger(self):
        """Проверяет, нужно ли активировать диалог с котом"""
        if not self.cheshire_cat.visible:
            # Проверяем расстояние до кота
            cat_distance = ((self.my_player.x - self.cheshire_cat.x) ** 2 + 
                           (self.my_player.y - self.cheshire_cat.y) ** 2) ** 0.5
            
            if cat_distance < DIALOG_TRIGGER_DISTANCE:
                self.cheshire_cat.visible = True
                if not self.dialog_system.is_active:
                    self.start_dialog("cat_start")

    def start_dialog(self, dialog_id):
        """Начинает диалог"""
        if not self.dialog_system.dialog_completed:
            print(f"Начинаем диалог: {dialog_id}")
            self.dialog_system.start_dialog(dialog_id, self.my_player.character_name)
            
            # Отправляем сообщение о начале диалога
            if self.socket_active:
                try:
                    data = pickle.dumps({
                        "type": "dialog_start",
                        "dialog_id": dialog_id
                    })
                    self.socket.sendto(data, self.other_address)
                except Exception as e:
                    print(f"Ошибка при отправке начала диалога: {e}")

    def handle_dialog_choice(self, choice):
        """Обрабатывает выбор в диалоге"""
        if not self.dialog_system.current_dialog:
            return
        
        if choice >= len(self.dialog_system.current_dialog.get("choices", [])):
            return
        
        selected_choice = self.dialog_system.current_dialog["choices"][choice]
        next_dialog = selected_choice.get("next")
        
        if next_dialog == "end":
            self.dialog_system.complete_dialog()
            self.cheshire_cat.visible = False
        elif next_dialog:
            self.start_dialog(next_dialog)

    def update(self, dt):
        """Обновляет состояние уровня"""
        # Обновляем игроков
        self.my_player.update(self.platforms)
        self.other_player.update(self.platforms)
        
        # Обновляем коробки
        for box in self.boxes:
            box.update(self.platforms)
        
        # Обновляем кота
        self.cheshire_cat.update(dt)
        
        # Проверяем триггер диалога с котом
        self.check_cat_trigger()
        
        # Проверяем сбор предметов
        collected_keys = self.my_player.check_collectibles(self.keys)
        if collected_keys:
            self.collected_keys += len(collected_keys)
        
        collected_potions = self.my_player.check_collectibles(self.potions)
        if collected_potions:
            self.collected_potions += len(collected_potions)
        
        # Обновляем камеру
        self.camera.update(self.my_player.x, self.my_player.y)
        
        # Обновляем диалоговую систему
        self.dialog_system.update(dt)
        
        # Отправляем данные по сети
        if self.socket_active:
            self.send_network_update()

    def draw(self):
        """Отрисовывает уровень"""
        # Отрисовка фона с параллаксом
        self.draw_background_with_parallax(self.screen)
        
        # Отрисовка платформ
        for platform in self.platforms:
            platform.draw(self.screen, self.camera)
        
        # Отрисовка коробок
        for box in self.boxes:
            box.draw(self.screen, self.camera)
        
        # Отрисовка предметов
        for key in self.keys:
            if not key.collected:
                key.draw(self.screen, self.camera)
        
        for potion in self.potions:
            if not potion.collected:
                potion.draw(self.screen, self.camera)
        
        # Отрисовка кота
        self.cheshire_cat.draw(self.screen, self.camera)
        
        # Отрисовка игроков
        self.my_player.draw(self.screen, self.camera)
        self.other_player.draw(self.screen, self.camera)
        
        # Отрисовка диалогов
        self.dialog_system.draw(self.screen, self.my_player.character_name)
        
        # Отрисовка UI
        self.draw_ui()

    def draw_ui(self):
        """Отрисовывает пользовательский интерфейс"""
        # Используем пиксельный шрифт
        try:
            font = pygame.font.Font(os.path.join("assets", "fonts", "visitor2.otf"), 20)
        except:
            font = pygame.font.Font(None, 20)
        
        # Показываем количество собранных предметов
        keys_text = font.render(f"Ключи: {self.collected_keys}/3", True, (255, 255, 255))
        self.screen.blit(keys_text, (10, 10))
        
        potions_text = font.render(f"Зелья: {self.collected_potions}/3", True, (255, 255, 255))
        self.screen.blit(potions_text, (10, 35))
        
        # Подсказка для кролика
        if self.my_player.character_name == "rabbit":
            hint_text = font.render("Нажмите E чтобы сбросить ящик", True, (255, 200, 0))
            self.screen.blit(hint_text, (10, SCREEN_HEIGHT - 30))

    def send_network_update(self):
        """Отправляет обновления по сети"""
        if not self.socket_active:
            return
        
        try:
            # Собираем данные о собранных предметах
            collected_keys_data = [i for i, key in enumerate(self.keys) if key.collected]
            collected_potions_data = [i for i, potion in enumerate(self.potions) if potion.collected]
            
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
            self.socket.sendto(data, self.other_address)
        except Exception as e:
            print(f"Ошибка отправки данных: {e}")
            self.socket_active = False

    def receive_data(self):
        """Получает данные по сети"""
        while self.socket_active and not self.is_shutting_down:
            try:
                data, addr = self.socket.recvfrom(1024)
                if not data:
                    continue
                
                received_data = pickle.loads(data)
                
                if received_data.get("type") == "game_state":
                    # Обновляем позицию другого игрока
                    player_data = received_data.get("player")
                    if player_data:
                        self.other_player.x = player_data["x"]
                        self.other_player.y = player_data["y"]
                        self.other_player.facing_right = player_data["facing_right"]
                        self.other_player.moving = player_data["moving"]
                    
                    # Обновляем собранные предметы
                    for key_index in received_data.get("collected_keys", []):
                        if key_index < len(self.keys):
                            self.keys[key_index].collected = True
                    
                    for potion_index in received_data.get("collected_potions", []):
                        if potion_index < len(self.potions):
                            self.potions[potion_index].collected = True
                    
                    # Обновляем счетчики
                    counters = received_data.get("counters", {})
                    if counters.get("keys", 0) > self.collected_keys:
                        self.collected_keys = counters["keys"]
                    if counters.get("potions", 0) > self.collected_potions:
                        self.collected_potions = counters["potions"]
                
                elif received_data.get("type") == "dialog_start":
                    dialog_id = received_data.get("dialog_id")
                    if dialog_id:
                        self.dialog_system.start_dialog(dialog_id, self.my_player.character_name)
            
            except OSError:
                break
            except Exception as e:
                if not self.socket_active or self.is_shutting_down:
                    break
                continue

    def run(self):
        """Основной игровой цикл"""
        running = True
        last_time = time.time()
        
        try:
            while running:
                current_time = time.time()
                dt = current_time - last_time
                last_time = current_time

                # Обработка событий
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            running = False
                        elif event.key == pygame.K_e and self.my_player.character_name == "rabbit":
                            self.try_drop_box()
                        else:
                            self.handle_input(event)

                # Обработка нажатых клавиш
                keys = pygame.key.get_pressed()
                if not self.dialog_system.is_active:
                    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                        self.my_player.move(-1)
                    elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                        self.my_player.move(1)
                    else:
                        self.my_player.move(0)
                    
                    if (keys[pygame.K_SPACE] or keys[pygame.K_w]) and not self.my_player.is_jumping:
                        self.my_player.jump()

                # Обновление и отрисовка
                self.update(dt)
                self.draw()
                
                pygame.display.flip()
                self.clock.tick(60)

        except Exception as e:
            print(f"Ошибка в игровом цикле: {e}")
        finally:
            self.is_shutting_down = True
            self.close()
            pygame.quit()

    def try_drop_box(self):
        """Пытается сбросить коробку, если кролик находится рядом с ней"""
        if self.my_player.character_name != "rabbit":
            return
        
        # Проверяем все коробки
        for box in self.boxes:
            if not box.is_falling and not box.on_ground:
                # Проверяем расстояние до коробки
                distance = ((self.my_player.x - box.x) ** 2 + 
                           (self.my_player.y - box.y) ** 2) ** 0.5
                
                if distance < 100:  # Расстояние для активации
                    box.start_fall()
                    # Отправляем сообщение о падении коробки
                    if self.socket_active:
                        try:
                            data = pickle.dumps({
                                "type": "box_fall",
                                "box_index": self.boxes.index(box)
                            })
                            self.socket.sendto(data, self.other_address)
                        except Exception as e:
                            print(f"Ошибка отправки данных о коробке: {e}")
                    break

    def handle_input(self, event):
        """Обрабатывает ввод пользователя"""
        if event.type == pygame.KEYDOWN:
            if self.dialog_system.is_active:
                if event.key in [pygame.K_1, pygame.K_2, pygame.K_3]:
                    choice = event.key - pygame.K_1
                    self.handle_dialog_choice(choice)
                elif event.key == pygame.K_RETURN:
                    self.dialog_system.next_dialog()
            else:
                if event.key == pygame.K_e and self.my_player.character_name == "rabbit":
                    self.try_drop_box()

    def close(self):
        """Закрывает соединение и освобождает ресурсы"""
        self.socket_active = False
        try:
            self.socket.close()
        except:
            pass

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python level2.py [host/client]")
        sys.exit(1)

    is_host = sys.argv[1].lower() == "host"
    level = Level2("localhost", is_host)
    level.run()