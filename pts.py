import pygame
import functools
import math
import random
import collections

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

unit_id = 0
class Unit:
    def __init__(self, player):
        global unit_id
        self.id = unit_id
        unit_id += 1
        self.player = player
        self.personality = random.randint(1, 255)
        self.skin = (random.randint(1, 255),
                random.randint(1, 255),
                random.randint(1, 255))

    def __str__(self):
        return "[unit player={}]".format(self.player.index)

class Event:
    # if old_pos is false, spawn
    # if new_pos is false, die
    def __init__(self, tick, unit, old_pos, new_pos):
        self.tick = tick
        self.unit = unit
        self.old_pos = old_pos
        self.new_pos = new_pos

class CommCenter:
    def __init__(self):
        self.initialized = False

    def setup(self, model):
        if self.initialized:
            return
        self.model = model
        self.map = {}
        self.dead = set()
        self.dead_units = set()
        for x in range(model.map_w):
            for y in range(model.map_h):
                self.map[(x, y)] = None
        self.initialized = True

    def handle_event(self, event):
        if event.old_pos and not event.new_pos:
            self.dead.add(event.old_pos)
            self.dead_units.add(event.unit.id)
        if event.old_pos:
            self.map[event.old_pos] = None
        if event.new_pos and event.unit.id not in self.dead_units:
            self.map[event.new_pos] = event.unit

    def tick(self):
        self.dead.clear()
        for event in model.events[model.tick_no]:
            self.handle_event(event)

class Model:
    def __init__(self):
        self.initialized = False

    def for_all_squares(self, f):
        for x in range(self.map_w):
            for y in range(self.map_h):
                f(x, y)

    def setup(self, num_players, map_w, map_h):
        if self.initialized:
            return
        self.comm_speed = 1 / 5
        self.tick_no = 0
        self.events = collections.defaultdict(list)  # tick => event
        self.map_w = map_w
        self.map_h = map_h
        self.map = {}
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
            focal = self.players[0].spawnpoint
            x = pos[0]
            y = pos[1]
            distance = math.sqrt((x - focal[0]) ** 2 + (y - focal[1]) ** 2)
            future = self.tick_no + max(int(distance / self.comm_speed), 1)
            self.events[future].append(
                    Event(self.tick_no, unit, old_pos=None, new_pos=pos))

    def enqueue_move(self, x, y, dx, dy, detour=False):
        unit = self.map[(x, y)]
        if not unit:
            return
        focal = self.players[0].spawnpoint
        distance = math.sqrt((x - focal[0]) ** 2 + (y - focal[1]) ** 2)
        future = self.tick_no + max(int(distance / self.comm_speed), 1)
        new_x = max(0, min(x + dx, self.map_w - 1))
        new_y = max(0, min(y + dy, self.map_h - 1))
        occupied = self.new_map[(new_x, new_y)]
        if occupied:
            if occupied.player.index != unit.player.index:
                # collide, killing both units
                self.new_map[(x, y)] = None
                self.new_map[(new_x, new_y)] = None
                self.events[future].append(Event(self.tick_no, unit,
                    old_pos=(x, y), new_pos=(new_x, new_y)))
                self.events[future].append(Event(self.tick_no, unit,
                    old_pos=(new_x, new_y), new_pos=None))
                self.events[future].append(Event(self.tick_no, occupied,
                    old_pos=(new_x, new_y), new_pos=None))
                return
            if detour:
                # it's one of our own, just try once to move around it
                dx = ((dx + 1) % 2) - 1
                dy = ((dy + 1) % 2) - 1
                self.enqueue_move(x, y, dx, dy, detour=False)
            return
        self.events[future].append(Event(self.tick_no, unit,
            old_pos=(x, y), new_pos=(new_x, new_y)))
        self.new_map[(new_x, new_y)] = self.new_map[(x, y)]
        self.new_map[(x, y)] = None

    def execute_moves(self):
        self.map = dict(self.new_map)

    def spawn_phase(self):
        for player in self.players:
            self.spawn(Unit(player), player.spawnpoint)

    def tick(self):
        move_speed = 10
        spawn_rate = 100
        if self.tick_no % spawn_rate == 0:
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
        if self.tick_no % move_speed == 0:
            self.for_all_squares(move)
        self.execute_moves()
        self.tick_no += 1


# pygame setup
pygame.init()
font = pygame.font.SysFont("Courier New", 20)
pygame.mixer.init()
sound = pygame.mixer.Sound("die.wav")
screen = pygame.display.set_mode((1280, 720))
clock = pygame.time.Clock()
running = True
dt = 0

# constants
fps = 60
square_edge = 30
scale = int(720 / square_edge)
margin = int(scale * 0.1)

# gui state
model = Model()
comm = CommCenter()
frame = 0
explosions = {}  # coords => frame
last_tick = 0
sim_speed = 30

while running:
    # poll for events
    # pygame.QUIT event means the user clicked X to close your window
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # fill the screen with a color to wipe away anything from last frame
    screen.fill("black")

    model.setup(2, square_edge, square_edge)
    comm.setup(model)
    if frame % (fps // sim_speed) == 0:
        model.tick()
        comm.tick()
        last_tick = frame
        for dead in comm.dead:
            explosions[dead] = frame
            #sound.play()

    to_clear = set()
    for k, v in explosions.items():
        if frame > v + 2 * fps:
            to_clear.add(k)
    for k in to_clear:
        del explosions[k]

    spawns = set()
    for player in model.players:
        spawns.add(player.spawnpoint)
        x = player.spawnpoint[0]
        y = player.spawnpoint[1]
        hue = 360 * player.index / len(model.players)
        color = pygame.Color(0)
        color.hsva = (int(hue), 35, 100, 100)
        pygame.draw.rect(screen, color, (x * scale, y * scale, scale, scale))
    focal = model.players[0].spawnpoint
    for x in range(model.map_w):
        for y in range(model.map_h):
            if (x, y) not in spawns:
                distance = math.sqrt((x - focal[0]) ** 2 + (y - focal[1]) ** 2)
                # draw the space
                purple = max(int(60 - distance * 2), 0)
                color = (purple, int(purple * 2 / 3), purple)
                if x % 2 == y % 2:
                    color = (10, 10, 10)
                pygame.draw.rect(screen, color, (x * scale, y * scale, scale, scale))
            if (x, y) in explosions:
                color = "white"
                if int(frame - explosions[(x, y)]) % 2 == 0:
                    color = "black"
                pygame.draw.rect(screen, color, (x * scale, y * scale, scale, scale))

    for x in range(model.map_w):
        for y in range(model.map_h):
            distance = math.sqrt((x - focal[0]) ** 2 + (y - focal[1]) ** 2)
            # draw object if needed
            obj = comm.map[(x, y)]
            if obj:
                # something is there
                move_x = 0
                move_y = 0
#                if (x, y) in model.moves:
#                    # animate
#                    old_pos = model.moves[(x, y)]
#                    dx = x - old_pos[0]
#                    dy = y - old_pos[1]
#                    mag = (frame - last_tick) / (fps // sim_speed) - 1.0
#                    move_x = dx * mag * scale
#                    move_y = dy * mag * scale
#                    if False and model.map[(x, y)].id % 20 == 0:
#                        debug("animate",
#                                {"frame": frame, "last_tick": last_tick,
#                                    "pos": (x, y), "diff": (dx, dy), "mag": mag,
#                                    "move": (move_x, move_y)})
                hue = 360 * obj.player.index / len(model.players) + (obj.skin[0] / 12)
                hue = int(hue) % 360
                color = pygame.Color(0)
                color.hsva = (int(hue), 95,
                        int(max(0, 100 - (obj.skin[1] // 8) - distance * 2)),
                        max(0, 100 - (obj.skin[2] // 8)))
                pygame.draw.rect(screen, color, (
                    int(x * scale + margin + move_x),
                    int(y * scale + margin + move_y),
                    scale - margin * 2,
                    scale - margin * 2), 0, int(scale / 6))

    # print debug
    for i, line in enumerate(terminal_lines):
        text_surface = font.render(line, True, (255, 255, 255))
        screen.blit(text_surface, (10, 10 + i * font.get_height()))

    # flip() the display to put your work on screen
    pygame.display.flip()

    dt = clock.tick(fps) / 1000
    frame += 1

pygame.quit()
