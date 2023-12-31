import pygame
import functools
import math
import random
import collections

DEBUG = {
        "MOVES": True,
        }

event_speed = 5

frame = 0
terminal_lines = []
last_print = 0
messages = set()
def debug(*args):
  global last_print
  text = " ".join(str(a) for a in args)
  print(text)
  terminal_lines.append(text)
  if len(terminal_lines) > 20:
    terminal_lines.pop(0)
  last_print = frame
def udebug(mid, *args):
  text = " ".join(str(a) for a in args)
  key = (mid, text)
  if key in messages:
    return
  messages.add(key)
  debug(text)

def circlegen(center, radius, border=True):
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

@functools.cache
def circle(center, radius, border=True):
  return list(circlegen(center, radius, border))

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
    return self.id == other.id

  def __lt__(self, other):
    return self.id < other.id

class Unit(Idd):
  def __init__(self, player):
    Idd.__init__(self)
    self.player = player
    self.personality = random.randint(1, 255)
    self.skin = (random.randint(1, 255),
        random.randint(1, 255),
        random.randint(1, 255))
    self.active_dst = None
    self.active_waypoint = None
    self.active_command = None
    self.last_command_seq = -1
    self.time = 0

  def __str__(self):
    return "[unit id={} player={}]".format(self.id, self.player.index)

  def __repr__(self):
    return str(self)

  def _formation(self, command, pos):
    # sort by x, break ties by y
    sunits= sorted(list(command.units.keys()),
                   key=lambda unit: (command.units[unit][0], command.units[unit][1]))
    num_cols = int(math.ceil(1.25 * math.sqrt(len(command.units))))
    num_rows = len(command.units) // num_cols + 1
    udebug(command.id, "formation", num_cols, "x", num_rows)
    formation = {}
    i = 0
    for col in range(num_cols):
      for row in range(num_rows):
        if i >= len(sunits):
          break
        formation[sunits[i]] = (col, row)
        i += 1
    spot = formation[self]
    pos = (pos[0] + spot[0], pos[1] + spot[1])
    self.active_dst = pos

  def command(self, command):
    if command.player != self.player or self not in command.units:
      # ignore commands not meant for me
      return
    if command.id <= self.last_command_seq:
      # ignore stale/duplicate commands
      return
    if self.active_command is None or self.active_command != command:
      self.active_command = command
      self.active_waypoint = 0
    pos = command.pos[self.active_waypoint]
    self._formation(command, pos)
    self.last_command_seq = command.id

  # form near the spawn
  def idle_spawn(self, client, pos):
    fan_width = 4
    fan_depth = 4
    dx, dy = 0, 0
    if self.player.spawnpoint[1] >= client.map_h // 2:
      if pos[1] > self.player.spawnpoint[1] - fan_depth:
        dy = -1
    else:
      if pos[1] < self.player.spawnpoint[1] + fan_depth:
        dy = 1
    if pos[0] > client.map_w // 2 - fan_width and pos[0] < client.map_w // 2 + fan_width:
      dx = random.randint(-1, 1)
    return (dx, dy)

  def ai_move(self, client, pos):
    strat = self.id % 3
    dy = 0
    dx = random.randint(-1, 1)
    time = self.time
    if strat == 0: # attacker
      if time < 8 or time > 20:
        # move up towards center, then rush in
        dy = 1
      if pos[1] >= client.map_h - 2:
        # too far, go back
        dy = -1
      if time > 40:
        # close in the flanks
        dx = -1 if pos[0] > client.map_w // 2 else 1
    elif strat == 1: # mid
      # move to center, then sit there
      if y < client.map_h // 2:
        dy = 1
    elif strat == 2: # defender
      # sit close to spawn
      if pos[1] < 5:
        dy = 1
      else:
        dx = 0
    return (dx, dy)

  def get_move(self, client, pos):
    self.time += 1
    if client.ai:
      return self.ai_move(client, pos)
    if not self.active_dst:
      return self.idle_spawn(client, pos)
    dx, dy = 0, 0
    if self.active_dst[0] < pos[0]:
      dx = -1
    elif self.active_dst[0] > pos[0]:
      dx = 1
    if self.active_dst[1] < pos[1]:
      dy = -1
    elif self.active_dst[1] > pos[1]:
      dy = 1
    if dx == 0 and dy == 0:
      if self.active_waypoint is not None:
        self.active_waypoint += 1
        if self.active_waypoint >= len(self.active_command.pos):
          self.active_waypoint = None
          self.active_command = None
        else:
          pos = self.active_command.pos[self.active_waypoint]
          self._formation(self.active_command, pos)
    return (dx, dy)

class Command(Idd):
  # units is dict of unit -> selected positions
  def __init__(self, player, units, pos):
    Idd.__init__(self)
    self.player = player
    self.units = units
    self.pos = pos

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

  def setup(self, player, map_w, map_h, ai=False):
    if self.initialized:
      return
    self.ai = ai
    self.player = player
    self.player_index = player.index
    self.map_w = map_w
    self.map_h = map_h
    self.dead = set()
    self.spawned = set()
    self.perma_dead = set()
    self.units = {}  # unit => position
    self.map = collections.defaultdict(lambda: set())  # position => units
    self.seen_events = set()  # IDs
    self.initialized = True

  def handle_event(self, event):
    if event.id in self.seen_events:
      return
    self.seen_events.add(event.id)
    if event.unit in self.units:
      pos = self.units[event.unit]
      self.map[pos].discard(event.unit)
      del self.units[event.unit]
    if event.new_pos and event.unit not in self.perma_dead:
      if not event.old_pos:
        # something spawned
        self.spawned.add(event.new_pos)
      self.units[event.unit] = event.new_pos
      self.map[event.new_pos].add(event.unit)
    if event.old_pos and not event.new_pos:
      # something died
      self.dead.add(event.old_pos)
      self.perma_dead.add(event.unit)

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
    self.event_speed = event_speed
    self.tick_no = 0
    self.map_w = map_w
    self.map_h = map_h
    self.map = {}
    self.event_centers = {}  # event => (center point, radius)
    self.event_map = collections.defaultdict(set)  # point => set of events
    self.command_centers = {}  # command => (center point, radius)
    self.command_map = collections.defaultdict(set)  # point => set of commands
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
    self.event_centers[event] = [pos, 0]

  def broadcast_command(self, command, pos):
    self.command_centers[command] = (pos, 0)

  def expand_events(self):
    to_delete = []
    to_expand = []
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
        to_expand.append(event)
      else:
        to_delete.append(event)
    for event in to_expand:
      cr = self.event_centers[event]
      cr[1] += 1
    for event in to_delete:
      del self.event_centers[event]

  def expand_commands(self):
    to_delete = []
    to_set = []
    for command, el in self.command_centers.items():
      center, radius = el
      for x, y in circle(center, radius):
        if command in self.command_map[(x, y)]:
          self.command_map[(x, y)].remove(command)
      inside = False
      for x, y in circle(center, radius + 1):
        if x >= 0 and x < self.map_w and y >= 0 and y < self.map_h:
          inside = True
          self.command_map[(x, y)].add(command)
          unit = self.map[(x, y)]
          if unit:
            unit.command(command)
      if inside:
        to_set.append((command, center, radius + 1))
      else:
        to_delete.append(command)
    for command, center, radius in to_set:
      self.command_centers[command] = (center, radius)
    for command in to_delete:
      del self.command_centers[command]


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
      if DEBUG["MOVES"] and player.index > 0:
        continue
      self.spawn(Unit(player), player.spawnpoint)

  def tick(self):
    move_speed = 10
    spawn_rate = 50 if DEBUG["MOVES"] else 500
    if self.tick_no % spawn_rate == 0:
      self.spawn_phase()
    def move(x, y):
      unit = self.map[(x, y)]
      if not unit:
        return
      (dx, dy) = unit.get_move(self.clients[unit.player.index], (x, y))
      self.enqueue_move(x, y, dx, dy, detour=True)
    if self.tick_no % move_speed == 0:
      self.for_all_squares(move)
    self.execute_moves()
    if self.tick_no % self.event_speed == 0:
      self.expand_events()
      self.expand_commands()
    for client in self.clients:
      for event in self.event_map[self.players[client.player_index].spawnpoint]:
        client.handle_event(event)
    self.tick_no += 1


# pygame setup
pygame.init()
font = pygame.font.SysFont("Courier New", 20)
pygame.mixer.init()
sounds = lambda names: [pygame.mixer.Sound(d + ".wav") for d in names]
play_sound = lambda sounds: sounds[random.randint(0, len(sounds) - 1)].play()
die_sounds = sounds(["die", "die2"])
attack_sounds = sounds(["attack", "attack2"])
alert_sounds = sounds(["alert", "alert2"])
recall_sounds = sounds(["recall", "recall2"])
hi_sounds = sounds(["hi", "hi2"])
spawn_sounds = sounds(["spawn"])
spot_sounds = sounds(["spot"])
RES_X = 720
RES_Y = 720
screen = pygame.display.set_mode((RES_X, RES_Y))
clock = pygame.time.Clock()
running = True
dt = 0

# constants
fps = 30
square_edge = 100
base_scale = int(720 / square_edge)
scale = base_scale
zoom = 1
margin = int(scale * 0.1)

# gui state
server = Server()
client = Client()
ai = Client()
explosions = {}  # coords => frame
last_tick = 0
sim_speed = 30
select_start = None
select_end = None
selected_units = {}
selected_pos = None
waypoints = []
camera = (0, 0)
def pos_to_square(pos):
  return ((pos[0] - camera[0]) // scale, (pos[1] - camera[1]) // scale)
def square_to_pos(square):
  return (square[0] * scale + scale // 2 + camera[0], square[1] * scale + scale // 2 + camera[1])

while running:
  # poll for events
  # pygame.QUIT event means the user clicked X to close your window
  for event in pygame.event.get():
    if event.type == pygame.QUIT:
      running = False
    elif event.type == pygame.MOUSEWHEEL:
      y = event.y * -1
      if y > 0:
        y = min(y, 3)
      if y < 0:
        y = max(y, -3)
      mouse_x, mouse_y = pygame.mouse.get_pos()
      zoom = max(0.75, min(10, zoom - y * 0.1))
      scale = int(base_scale * zoom)
      camera = (int(RES_X / 2 - mouse_x * zoom),
                int(RES_Y / 2 - mouse_y * zoom))
    elif event.type == pygame.MOUSEBUTTONDOWN:
      if event.button == 1:  # left click
        select_start = event.pos
      elif event.button == 3:  # right click
        if selected_units: # order move
          dst = pos_to_square(event.pos)
          waypoints.append(dst)
          debug("waypoint", dst)
          if not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
            command = Command(server.players[0], dict(selected_units), waypoints)
            server.broadcast_command(command, server.players[0].spawnpoint)
            waypoints = []
            if dst[1] <= selected_pos[1]:
              play_sound(attack_sounds)
            else:
              play_sound(recall_sounds)
    elif event.type == pygame.MOUSEBUTTONUP:
      if event.button == 1:      
        if select_start and select_end:
          square_start = pos_to_square(select_start)
          square_end = pos_to_square(select_end)
          selected_units = {}
          for x in range(min(square_start[0], square_end[0]),
                         max(square_start[0], square_end[0])):
            for y in range(min(square_start[1], square_end[1]),
                           max(square_start[1], square_end[1])):
              units = client.map[(x, y)]
              for unit in units:
                if unit.player.index == 0:
                  selected_pos = (x, y)
                  selected_units[unit] = (x, y)
          select_start = None
          select_end = None
          if selected_units:
              #            debug("selected", len(selected_units), "units")
            play_sound(hi_sounds)
    elif event.type == pygame.MOUSEMOTION:
      if select_start:
        select_end = event.pos
  keys = pygame.key.get_pressed()
  move_x, move_y = 0, 0
  if keys[pygame.K_w]:
    move_y += 1
  if keys[pygame.K_s]:
    move_y -= 1
  if keys[pygame.K_a]:
    move_x += 1
  if keys[pygame.K_d]:
    move_x -= 1
  if move_x != 0 or move_y != 0:
    camera_speed = scale  * fps / 30
    camera = (int(camera[0] + move_x * camera_speed), int(camera[1] + move_y * camera_speed))

  # fill the screen with a color to wipe away anything from last frame
  screen.fill("black")
  
  server.setup(2, square_edge, square_edge, [client, ai])
  client.setup(server.players[0], square_edge, square_edge)
  ai.setup(server.players[1], square_edge, square_edge, ai=True)
  if frame % (fps // sim_speed) == 0:
    server.tick()
    last_tick = frame
    for spawned in client.spawned:
      play_sound(spawn_sounds)
    for dead in client.dead:
    #  debug("explosion at", dead, ", frame", frame)
      explosions[dead] = frame
      play_sound(die_sounds)
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
    pygame.draw.rect(screen, color, (x * scale + camera[0], y * scale + camera[1], scale, scale))
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
        pygame.draw.rect(screen, color, (x * scale + camera[0], y * scale + camera[1], scale, scale))
      if (x, y) in explosions:
        color = "white"
        if int(frame - explosions[(x, y)]) % 2 == 0:
          color = "black"
        pygame.draw.rect(screen, color, (x * scale + camera[0], y * scale + camera[1], scale, scale))

      if False:  # edit to show events
        for event in server.event_map[(x, y)]:
          if event.new_pos: continue   # explosions only
          color = (0, 150 - 3 * (event.id % 20), 0)
          pygame.draw.rect(screen, color, (x * scale + camera[0], y * scale + camera[1], scale, scale))

  for i, pos in enumerate(waypoints):
    x, y = pos
    color = (0, max(100 - i * 20, 20), 0)
    pygame.draw.rect(screen, color, (x * scale + camera[0], y * scale + camera[1], scale, scale))

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
    if unit in selected_units.keys():
      color = "white"
    pygame.draw.rect(screen, color, (
      int(x * scale + margin + move_x) + camera[0],
      int(y * scale + margin + move_y) + camera[1],
      scale - margin * 2,
      scale - margin * 2), 0, int(scale / 6))

  if select_end:
    select_rect = pygame.Rect(
            min(select_start[0], select_end[0]),
            min(select_start[1], select_end[1]),
            abs(select_start[0] - select_end[0]),
            abs(select_start[1] - select_end[1]))
    pygame.draw.rect(screen, "white", select_rect, 2)

  # animate commands (not to scale)
  for command, val in server.command_centers.items():
    center, radius = val
    if command.player == server.players[0] and radius < 4:
      pos = square_to_pos(center)
      pygame.draw.circle(screen, (0, 100, 0),
                         (pos[0], pos[1]),
                         radius * scale * 2, 1)

  # print debug
  if len(terminal_lines) > 0 and frame - last_print > fps * 2:
    terminal_lines.pop(0)
  for i, line in enumerate(terminal_lines):
    text_surface = font.render(line, True, (255, 255, 255))
    screen.blit(text_surface, (10, 10 + i * font.get_height()))

  # flip() the display to put your work on screen
  pygame.display.flip()

  dt = clock.tick(fps) / 1000
  frame += 1

pygame.quit()
