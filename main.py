import pygame
import sys
import time
import pickle
from story_screen import StoryScreen
from game import Game
from level2 import Game as Level2
from network_manager import NetworkManager

def main():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Алиса в Стране Чудес")
    
    if len(sys.argv) != 2:
        print("Использование: python main.py [host/client]")
        sys.exit(1)

    is_host = sys.argv[1].lower() == "host"
    
    # Сначала показываем историю
    story = StoryScreen()
    story.set_initial_stage(is_host)  # Устанавливаем начальное состояние
    network = NetworkManager("localhost", is_host, story)
    
    clock = pygame.time.Clock()
    running = True
    current_level = 1
    fade_alpha = 0
    fade_surface = pygame.Surface((800, 600))
    fade_surface.fill((0, 0, 0))
    fading_out = False
    fading_in = False
    
    # Основной цикл для story_screen
    while running:
        dt = clock.tick(60) / 1000.0
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                network.close()
                pygame.quit()
                sys.exit()
        
        story.update(dt)
        story.draw(screen)
        pygame.display.flip()
        
        # Если история закончилась, переходим к игре
        if story.current_stage == "game":
            network.close()
            break
    
    # Запускаем основную игру
    if running:  # Если не было выхода во время истории
        game = Game("localhost", is_host)
        level2 = None
        
        while running and current_level <= 2:
            if current_level == 1:
                if not fading_out:
                    # Запускаем первый уровень
                    victory = game.run()
                    if victory:
                        fading_out = True
                        fade_alpha = 0
                
                if fading_out:
                    # Отрисовываем затемнение
                    screen.fill((0, 0, 0))
                    fade_alpha = min(255, fade_alpha + 5)
                    fade_surface.set_alpha(fade_alpha)
                    screen.blit(fade_surface, (0, 0))
                    pygame.display.flip()
                    
                    if fade_alpha >= 255:
                        current_level = 2
                        level2 = Level2("localhost", is_host)
                        fading_out = False
                        fading_in = True
                        fade_alpha = 255
                        pygame.time.wait(500)  # Небольшая пауза перед началом нового уровня
                    
            elif current_level == 2:
                if fading_in:
                    # Отрисовываем появление
                    screen.fill((0, 0, 0))
                    fade_alpha = max(0, fade_alpha - 5)
                    fade_surface.set_alpha(fade_alpha)
                    screen.blit(fade_surface, (0, 0))
                    pygame.display.flip()
                    
                    if fade_alpha <= 0:
                        fading_in = False
                else:
                    # Запускаем второй уровень
                    victory = level2.run()
                    if victory:
                        running = False
                        break

            clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main() 