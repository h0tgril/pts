import pygame
import functools
import math
import random

# constants
fps = 60

# globals
frame = 0
sim_speed = 5

terminal_lines = []
def debug(*args):
    text = " ".join(str(a) for a in args)
    print(text)
    terminal_lines.append(text)
    if len(terminal_lines) > 20:
        terminal_lines.pop(0)

class Player:
    def __init__(self, index, spawnpoint):
        self.index = index
        self.spawnpoint = spawnpoint

class Unit:
    def __init__(self, player):
        self.player = player
        self.personality = random.randint(1, 255)
        self.skin = (random.randint(1, 255),
                random.randint(1, 255),
                random.randint(1, 255))

    def __str__(self):
        return "[unit player={}]".format(self.player.index)

class Model:
    def __init__(self):
        self.initialized = False
        pass

    def for_all_squares(self, f):
        for x in range(self.map_w):
            for y in range(self.map_h):
                f(x, y)

    def setup(self, num_players, map_w, map_h):
        if self.initialized:
            return
        self.map_w = map_w
        self.map_h = map_h
        self.map = {}
        self.units = []
        for x in range(map_w):
            for y in range(map_h):
                self.map[(x, y)] = None
        self.new_map = dict(self.map)
        self.players = []
        center = (map_w / 2, map_h / 2)
        radius = min(map_w, map_h) / 2 * (7 / 8)
        for player in range(num_players):
            angle = math.radians(90 + player * 360 / num_players)
            spawnpoint = (int(center[0] + radius * math.cos(angle)),
                    int(center[1] + radius * math.sin(angle)))
            self.players.append(Player(player, spawnpoint))
        self.initialized = True

    def spawn(self, unit, pos):
        if not self.map[pos]:
#            debug("spawning", unit, "at", pos)
            self.map[pos] = unit
            self.new_map[pos] = unit

    def enqueue_move(self, x, y, dx, dy, detour=False):
        new_x = max(0, min(x + dx, self.map_w - 1))
        new_y = max(0, min(y + dy, self.map_h - 1))
        if self.new_map[(new_x, new_y)]:
            # occupied, cannot move there
            if not detour:
                return
            dx = ((dx + 1) % 2) - 1
            dy = ((dy + 1) % 2) - 1
            self.enqueue_move(x, y, dx, dy, detour=False)
            return
        self.new_map[(new_x, new_y)] = self.new_map[(x, y)]
        self.new_map[(x, y)] = None

    def execute_moves(self):
        self.map = dict(self.new_map)
        self.new_map

    def spawn_phase(self):
        for player in self.players:
            self.spawn(Unit(player), player.spawnpoint)

    def tick(self):
        self.spawn_phase()
        def move(x, y):
            unit = self.map[(x, y)]
            if not unit:
                return
            target_x = int(unit.personality / 255 * self.map_w)
            dx = 0
            if x < target_x:
                dx = 1
            elif x > target_x:
                dx = -1
            dy = -1
            if unit.player.index == 1:
                dy = 1
            self.enqueue_move(x, y, dx, dy, detour=True)
        self.for_all_squares(move)
        self.execute_moves()


# pygame setup
pygame.init()
font = pygame.font.SysFont("Courier New", 20)
screen = pygame.display.set_mode((1280, 720))
clock = pygame.time.Clock()
running = True
dt = 0

model = Model()
square_edge = 30
scale = int(720 / square_edge)
margin = int(scale * 0.1)
while running:
    # poll for events
    # pygame.QUIT event means the user clicked X to close your window
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # fill the screen with a color to wipe away anything from last frame
    screen.fill("black")

    model.setup(2, square_edge, square_edge)
    if frame % (fps // sim_speed) == 0:
        model.tick()

    spawns = set()
    for player in model.players:
        spawns.add(player.spawnpoint)
        x = player.spawnpoint[0]
        y = player.spawnpoint[1]
        hue = 360 * player.index / len(model.players)
        color = pygame.Color(0)
        color.hsva = (int(hue), 35, 100, 100)
        pygame.draw.rect(screen, color, (x * scale, y * scale, scale, scale))
    for x in range(model.map_w):
        for y in range(model.map_h):
            if (x, y) not in spawns:
                # draw the space
                color = (60, 60, 60)
                if x % 2 == y % 2:
                    color = (20, 20, 20)
                pygame.draw.rect(screen, color, (x * scale, y * scale, scale, scale))

            # draw object if needed
            obj = model.map[(x, y)]
            if obj:
                # something is there
                hue = 360 * obj.player.index / len(model.players) + (obj.skin[0] / 12)
                hue = int(hue) % 360
                color = pygame.Color(0)
                color.hsva = (int(hue), 95,
                        100 - (obj.skin[1] // 8),
                        100 - (obj.skin[2] // 8))
                pygame.draw.rect(screen, color, (x * scale + margin, y * scale + margin,
                    scale - margin * 2, scale - margin * 2))

    # print debug
    for i, line in enumerate(terminal_lines):
        text_surface = font.render(line, True, (255, 255, 255))
        screen.blit(text_surface, (10, 10 + i * font.get_height()))

    # flip() the display to put your work on screen
    pygame.display.flip()

    dt = clock.tick(fps) / 1000
    frame += 1

pygame.quit()
