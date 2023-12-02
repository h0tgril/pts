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

sid = 0
class Idd:
  def __init__(self):
    global sid
    self.id = sid
    sid += 1

  def __hash__(self):
    return hash(self.id)

  def __eq__(self, other):
    return hash(self.id)

class Unit(Idd):
  def __init__(self, player):
    Idd.__init__(self)
    self.player = player
    self.personality = random.randint(1, 255)
    self.skin = (random.randint(1, 255),
        random.randint(1, 255),
        random.randint(1, 255))

  def __str__(self):
    return "[unit player={}]".format(self.player.index)

class Event(Idd):
  # if old_pos is None, the unit is spawning
  # if new_pos is None, the unit is dying
  def __init__(self, tick, unit, old_pos, new_pos):
    Idd.__init__(self)
    self.tick = tick
    self.unit = unit
    self.old_pos = old_pos
    self.new_pos = new_pos

class Client:
  def __init__(self):
    self.initialized = False

  def setup(self, player_index, map_w, map_h):
    if self.initialized:
      return
    self.player_index = player_index
    self.map_w = map_w
    self.map_h = map_h
    self.dead = set()
    self.spawned = set()
    self.perma_dead = set()
    self.units = {}  # unit => position
    self.seen_events = set()  # IDs
    self.initialized = True

  def handle_event(self, event):
    if event.id in self.seen_events:
      return
    self.seen_events.add(event.id)
    if event.new_pos and not event.old_pos:
      self.spawned.add(event.new_pos)
    if event.old_pos and not event.new_pos:
      self.dead.add(event.old_pos)
      self.perma_dead.add(event.unit)
      del self.units[event.unit]
    if event.new_pos and event.unit not in self.perma_dead:
      self.units[event.unit] = event.new_pos

  def tick(self):
    self.dead.clear()
    self.spawned.clear()

class Server:
  def __init__(self):
    self.initialized = False

  def for_all_squares(self, f):
    for x in range(self.map_w):
      for y in range(self.map_h):
        f(x, y)

  def setup(self, num_players, map_w, map_h, clients):
    if self.initialized:
      return
    self.clients = clients
    self.event_speed = 5
    self.tick_no = 0
    self.map_w = map_w
    self.map_h = map_h
    self.map = {}
    self.event_centers = {}  # event => (center point, radius)
    self.event_map = collections.defaultdict(set)  # point => set of events
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

  def broadcast_event(self, event, pos):
    self.event_centers[event] = (pos, 0)

  def expand_events(self):
    def circle(center, radius):
      # (x-a)^2 + (y-b)^2 = r^2
      # => y = b +-sqrt(r^2 - (x-a)^2)
      a = center[0]
      b = center[1]
      for x in range(a - radius, a + radius + 1):
        s = math.sqrt(radius ** 2 - (x - a) ** 2)
        for y in [b + s, b - s]:
          y = int(round(y))
          yield (x, y)
          # also round inwards
          # TODO this is jank
          x2 = x - 1 if x > 0 else x + 1
          y2 = y - 1 if y > 0 else y + 1
          yield (x2, y)
          yield (x, y2)
          yield (x2, y2)
    to_delete = []
    to_set = []
    for event, el in self.event_centers.items():
      center, radius = el
      for x, y in circle(center, radius):
        if event in self.event_map[(x, y)]:
          self.event_map[(x, y)].remove(event)
      inside = False
      for x, y in circle(center, radius + 1):
        if x >= 0 and x < self.map_w and y >= 0 and y < self.map_h:
          inside = True
          self.event_map[(x, y)].add(event)
      if inside:
        to_set.append((event, center, radius + 1))
      else:
        to_delete.append(event)
    for event, center, radius in to_set:
      self.event_centers[event] = (center, radius)
    for event in to_delete:
      del self.event_centers[event]


  def spawn(self, unit, pos):
    if not self.map[pos]:
#      debug("spawning", unit, "at", pos)
      self.map[pos] = unit
      self.new_map[pos] = unit
      self.broadcast_event(Event(self.tick_no, unit, old_pos=None, new_pos=pos), pos)

  def enqueue_move(self, x, y, dx, dy, detour=False):
    unit = self.map[(x, y)]
    if not unit:
      return
    new_x = max(0, min(x + dx, self.map_w - 1))
    new_y = max(0, min(y + dy, self.map_h - 1))
    occupied = self.new_map[(new_x, new_y)]
    if occupied:
      if occupied.player.index != unit.player.index:
        # collide, killing both units
        #debug("collision at", new_x, new_y)
        self.new_map[(x, y)] = None
        self.new_map[(new_x, new_y)] = None
        self.broadcast_event(Event(self.tick_no, unit,
          old_pos=(x, y), new_pos=(new_x, new_y)), (new_x, new_y))
        self.broadcast_event(Event(self.tick_no, unit,
          old_pos=(new_x, new_y), new_pos=None), (new_x, new_y))
        self.broadcast_event(Event(self.tick_no, occupied,
          old_pos=(new_x, new_y), new_pos=None), (new_x, new_y))
        return
      if detour:
        # it's one of our own, just try once to move around it
        dx = ((dx + 1) % 2) - 1
        dy = ((dy + 1) % 2) - 1
        self.enqueue_move(x, y, dx, dy, detour=False)
      return
    self.broadcast_event(Event(self.tick_no, unit,
      old_pos=(x, y), new_pos=(new_x, new_y)), (x, y))
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
    if self.tick_no % self.event_speed == 0:
      self.expand_events()
    for client in self.clients:
      for event in self.event_map[self.players[client.player_index].spawnpoint]:
        client.handle_event(event)
    self.tick_no += 1


# pygame setup
pygame.init()
font = pygame.font.SysFont("Courier New", 20)
pygame.mixer.init()
die_sounds = [pygame.mixer.Sound(d + ".wav") for d in ["die", "die2"]]
spawn_sounds = [pygame.mixer.Sound(d + ".wav") for d in ["spawn"]]
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
server = Server()
client = Client()
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
  
  client.setup(0, square_edge, square_edge)
  server.setup(2, square_edge, square_edge, [client])
  if frame % (fps // sim_speed) == 0:
    server.tick()
    last_tick = frame
    for spawned in client.spawned:
      spawn_sounds[random.randint(0, len(spawn_sounds) - 1)].play()
    for dead in client.dead:
    #  debug("explosion at", dead, ", frame", frame)
      explosions[dead] = frame
      die_sounds[random.randint(0, len(die_sounds) - 1)].play()
    client.tick()

  to_clear = set()
  for k, v in explosions.items():
    if frame > v + 2 * fps:
      to_clear.add(k)
  for k in to_clear:
    del explosions[k]

  spawns = set()
  for player in server.players:
    spawns.add(player.spawnpoint)
    x = player.spawnpoint[0]
    y = player.spawnpoint[1]
    hue = 360 * player.index / len(server.players)
    color = pygame.Color(0)
    color.hsva = (int(hue), 35, 100, 100)
    pygame.draw.rect(screen, color, (x * scale, y * scale, scale, scale))
  focal = server.players[0].spawnpoint
  for x in range(server.map_w):
    for y in range(server.map_h):
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

      if False:  # edit to show events
        for event in server.event_map[(x, y)]:
          if event.new_pos: continue   # explosions only
          color = (0, 150 - 3 * (event.id % 20), 0)
          pygame.draw.rect(screen, color, (x * scale, y * scale, scale, scale))

  for unit, pos in client.units.items():
    x, y = pos
    distance = math.sqrt((x - focal[0]) ** 2 + (y - focal[1]) ** 2)
    move_x = 0
    move_y = 0
#    if (x, y) in server.moves:
#      # animate
#      old_pos = server.moves[(x, y)]
#      dx = x - old_pos[0]
#      dy = y - old_pos[1]
#      mag = (frame - last_tick) / (fps // sim_speed) - 1.0
#      move_x = dx * mag * scale
#      move_y = dy * mag * scale
#      if False and server.map[(x, y)].id % 20 == 0:
#        debug("animate",
#            {"frame": frame, "last_tick": last_tick,
#              "pos": (x, y), "diff": (dx, dy), "mag": mag,
#              "move": (move_x, move_y)})
    hue = 360 * unit.player.index / len(server.players) + (unit.skin[0] / 12)
    hue = int(hue) % 360
    color = pygame.Color(0)
    color.hsva = (int(hue), 95,
        int(max(50, 100 - (unit.skin[1] // 8) - distance * 2)),
        max(50, 100 - (unit.skin[2] // 8)))
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
