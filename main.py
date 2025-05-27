import pygame
import sys
import time
import pickle
from story_screen import StoryScreen
from game import Game
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
        game.run()

if __name__ == "__main__":
    main() 