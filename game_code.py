import pygame, cv2, mediapipe as mp, random, math
import numpy as np

pygame.init()
WIDTH, HEIGHT = 900, 500
win = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Human Racing Game – Level Edition")
clock = pygame.time.Clock()

# ─── FONTS ────────────────────────────────────────────────────────────────────
font        = pygame.font.SysFont("arial", 24)
title_font  = pygame.font.SysFont("arial", 64, bold=True)
menu_font   = pygame.font.SysFont("arial", 38)
small_font  = pygame.font.SysFont("arial", 18)
tiny_font   = pygame.font.SysFont("arial", 14)
hud_font    = pygame.font.SysFont("arial", 20, bold=True)
label_font  = pygame.font.SysFont("arial", 13)
level_popup_font = pygame.font.SysFont("arial", 48, bold=True)

# ─── NEON PALETTE ─────────────────────────────────────────────────────────────
NEON_CYAN   = (0,   255, 255)
NEON_BLUE   = (0,   120, 255)
NEON_GREEN  = (57,  255, 20)
NEON_RED    = (255, 50,  80)
NEON_PURPLE = (180, 0,   255)
NEON_GOLD   = (255, 215, 0)
DARK_BG     = (8,   10,  24)
PANEL_BG    = (15,  18,  40)

# ─── GAME STATES ──────────────────────────────────────────────────────────────
MENU = 0; PLAYING = 1; GAME_OVER = 2; SHOP = 3; CUSTOMIZE = 4
LEVEL_COMPLETE = 6   # new state for popup pause
game_state    = MENU
difficulty    = "NORMAL"
total_coins_ever = 0

# ══════════════════════════════════════════════════════════════════════════════
#  ██  LEVEL MANAGER  ██
# ══════════════════════════════════════════════════════════════════════════════
LEVEL_DEFINITIONS = [
    # (score_threshold, name, environment, base_speed_add, spawn_subtract, bird_mult, description)
    (0,    "Level 1", "day",   0,  0,   1.0, "City Streets – Morning Run"),
    (500,  "Level 2", "night", 1,  10,  1.2, "Night City – Watch Your Step"),
    (1000,  "Level 3", "rain",  2,  20,  1.5, "Rainy Roads – Slippery Ground"),
    (1500, "Level 4", "fog",   3,  30,  1.8, "Foggy Dawn – Low Visibility"),
    (2000, "Level 5", "space", 5,  40,  2.0, "Space Colony – Zero Gravity"),
]

current_level      = 1        # 1-indexed level number
level_just_changed = False    # flag so we trigger popup once
level_complete_timer = 0      # frames the popup has been shown
LEVEL_POPUP_DURATION = 180    # 3 seconds at 60fps
level_popup_anim    = 0.0     # 0..1 fade/scale animation
level_popup_phase   = "in"    # "in" | "hold" | "out"
level_complete_particles = []

def get_level_def(lvl_number):
    """Return the definition tuple for a 1-indexed level."""
    idx = min(lvl_number - 1, len(LEVEL_DEFINITIONS) - 1)
    return LEVEL_DEFINITIONS[idx]

def get_environment():
    """Return the environment string for the current level."""
    return get_level_def(current_level)[2]

def apply_level_to_speed(base_speed, base_spawn, base_bird):
    """Apply level bonuses on top of difficulty settings."""
    _, _, _, spd_add, spawn_sub, bird_mult, _ = get_level_def(current_level)
    return base_speed + spd_add, max(25, base_spawn - spawn_sub), base_bird * bird_mult

# ─── ENVIRONMENT CONFIGS ──────────────────────────────────────────────────────
ENV_CONFIG = {
    "day":   {"sky":(135,206,250), "ground":(80,170,80),  "horizon":(180,220,255),
              "overlay":None, "ground_detail":(60,140,60)},
    "night": {"sky":(10,12,40),   "ground":(30,50,30),   "horizon":(20,30,60),
              "overlay":(0,0,20,60), "ground_detail":(20,40,20)},
    "rain":  {"sky":(60,80,110),  "ground":(50,80,50),   "horizon":(80,100,130),
              "overlay":(20,40,80,70), "ground_detail":(30,60,30)},
    "fog":   {"sky":(160,170,180),"ground":(100,120,100),"horizon":(200,205,210),
              "overlay":(180,185,190,90), "ground_detail":(80,100,80)},
    "space": {"sky":(5,5,20),     "ground":(60,40,80),   "horizon":(20,10,40),
              "overlay":(0,0,0,40), "ground_detail":(40,20,60)},
}

# ─── RAIN SYSTEM ──────────────────────────────────────────────────────────────
rain_drops  = []
rain_splashes = []
MAX_RAIN    = 200

class RainDrop:
    def __init__(self):
        self.reset()
    def reset(self):
        self.x = random.randint(-50, WIDTH+50)
        self.y = random.randint(-HEIGHT, 0)
        self.speed = random.uniform(12, 20)
        self.length = random.randint(10, 22)
        self.alpha  = random.randint(100, 200)
    def update(self):
        self.x -= 2          # slight wind
        self.y += self.speed
        if self.y > HEIGHT - 130:
            rain_splashes.append(RainSplash(self.x, HEIGHT - 130))
            self.reset()
    def draw(self, surface):
        s = pygame.Surface((4, self.length + 4), pygame.SRCALPHA)
        pygame.draw.line(s, (150,190,255,self.alpha), (1,0), (3,self.length), 1)
        surface.blit(s, (int(self.x), int(self.y)))

class RainSplash:
    def __init__(self, x, y):
        self.x = x; self.y = y
        self.life = 20
        self.r    = 1
    def update(self):
        self.life -= 2; self.r += 0.5
    def draw(self, surface):
        if self.life > 0:
            s = pygame.Surface((int(self.r*2+4), 6), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (150,200,255, max(0,self.life*8)),
                                s.get_rect(), 1)
            surface.blit(s, (int(self.x - self.r), self.y - 2))

def init_rain():
    global rain_drops
    rain_drops = [RainDrop() for _ in range(MAX_RAIN)]
    for rd in rain_drops:          # scatter vertically on start
        rd.y = random.randint(-HEIGHT, HEIGHT)

def draw_rain(surface):
    for rd in rain_drops:
        rd.update(); rd.draw(surface)
    for sp in rain_splashes[:]:
        sp.update(); sp.draw(surface)
        if sp.life <= 0: rain_splashes.remove(sp)

# ─── FOG SYSTEM ───────────────────────────────────────────────────────────────
fog_offset = 0
def draw_fog(surface):
    global fog_offset
    fog_offset = (fog_offset + 0.3) % WIDTH
    for layer_y, alpha, height, speed_mult in [
        (HEIGHT-200, 60, 120, 1.0),
        (HEIGHT-280, 40, 100, 0.6),
        (HEIGHT-330, 25, 80,  0.3),
    ]:
        fog_surf = pygame.Surface((WIDTH*2, height), pygame.SRCALPHA)
        for x in range(0, WIDTH*2, 60):
            w  = random.randint(80, 160)
            h2 = random.randint(40, height)
            pygame.draw.ellipse(fog_surf, (190,195,200,alpha),
                                (x, height//2-h2//2, w, h2))
        ox = int(fog_offset * speed_mult) % WIDTH
        surface.blit(fog_surf, (-ox, layer_y))
        surface.blit(fog_surf, (WIDTH - ox, layer_y))

# ─── SPACE STARS (in-game) ────────────────────────────────────────────────────
space_stars = [(random.randint(0,WIDTH), random.randint(0,HEIGHT-120),
                random.choice([1,1,2]), random.uniform(0,6.28)) for _ in range(180)]
space_nebula_offset = 0

def draw_space_bg(surface, tick):
    global space_nebula_offset
    space_nebula_offset = (space_nebula_offset + 0.2) % WIDTH
    # slow parallax star layers
    for sx, sy, ss, phase in space_stars:
        bright = int(100 + math.sin(tick*0.02+phase)*100)
        bright = max(60, min(255, bright))
        pygame.draw.circle(surface, (bright,bright,bright+30), (sx,sy), ss)
    # drifting nebula smear
    for bx, by, brad, bcol in [(200,100,90,(40,0,60)), (650,150,110,(0,40,70))]:
        nb = pygame.Surface((brad*2, brad*2), pygame.SRCALPHA)
        pygame.draw.circle(nb, (*bcol,25), (brad,brad), brad)
        ox = int(space_nebula_offset*0.1) % WIDTH
        surface.blit(nb, (bx-brad-ox, by-brad))

# ─── FLOATING ASTEROIDS (space level obstacles / deco) ────────────────────────
space_rocks = []
def spawn_space_rock():
    space_rocks.append({
        "x": WIDTH + 30,
        "y": random.randint(60, HEIGHT - 180),
        "r": random.randint(10, 22),
        "rot": random.uniform(0, 360),
        "rot_speed": random.uniform(-2, 2),
        "speed": stone_speed * 0.6
    })

def draw_space_rocks(surface):
    for rock in space_rocks:
        rock["x"]  -= rock["speed"]
        rock["rot"] = (rock["rot"] + rock["rot_speed"]) % 360
        cx, cy, r   = int(rock["x"]), int(rock["y"]), rock["r"]
        pts = []
        for i in range(8):
            ang = math.radians(rock["rot"] + i*45)
            ri  = r + random.randint(-3,3)
            pts.append((cx + ri*math.cos(ang), cy + ri*math.sin(ang)))
        pygame.draw.polygon(surface, (90,75,110), pts)
        pygame.draw.polygon(surface, (130,110,150), pts, 2)
    space_rocks[:] = [r for r in space_rocks if r["x"] > -60]

# ─── MENU LEVEL CARDS & BUTTONS DATA (unchanged names) ────────────────────────
MENU_LEVELS = [
    {"name":"City",   "icon":"🏙", "mult":"×1.0","unlock":"Starter",    "color":(0,180,255),  "locked":False},
    {"name":"Forest", "icon":"🌲", "mult":"×1.5","unlock":"Score 300",  "color":(57,255,20),  "locked":True},
    {"name":"Rain",   "icon":"🌧",  "mult":"×2.0","unlock":"Score 700",  "color":(100,160,255),"locked":True},
    {"name":"Fog",    "icon":"🌫",  "mult":"×2.5","unlock":"Score 1200", "color":(180,190,200),"locked":True},
    {"name":"Space",  "icon":"🚀", "mult":"×3.0","unlock":"Score 1800", "color":(180,0,255),  "locked":True},
]
selected_level_card = 0

# ─── CHARACTER SKINS ──────────────────────────────────────────────────────────
character_skins = {
    "Classic":   {"cost": 0,  "unlocked": True,  "color": (255,200,150), "style":"normal",  "hair":(50,30,20)},
    "Athlete":   {"cost": 10, "unlocked": False, "color": (255,180,140), "style":"athletic","hair":(30,20,10)},
    "Shadow":    {"cost": 10, "unlocked": False, "color": (50,50,50),    "style":"ninja",   "hair":(20,20,20)},
    "Superhero": {"cost": 10, "unlocked": False, "color": (220,50,50),   "style":"hero",    "hair":(100,50,0)},
    "Gold":      {"cost": 10, "unlocked": False, "color": (255,215,0),   "style":"normal",  "hair":(200,160,0)},
    "Scientist": {"cost": 10, "unlocked": False, "color": (255,255,255), "style":"smart",   "hair":(150,150,150)},
    "Robot":     {"cost": 10, "unlocked": False, "color": (200,200,255), "style":"robot",   "hair":(150,150,200)},
    "Ninja":     {"cost": 10, "unlocked": False, "color": (100,0,150),   "style":"ninja",   "hair":(50,0,75)},
    "Viking":    {"cost": 10, "unlocked": False, "color": (255,190,150), "style":"warrior", "hair":(200,100,0)},
    "Astronaut": {"cost": 10, "unlocked": False, "color": (240,240,240), "style":"space",   "hair":(100,100,100)},
    "Rainbow":   {"cost": 10, "unlocked": False, "color": (255,100,200), "style":"rainbow", "hair":(255,150,200)},
}
hats = {
    "None":{"cost":0,"unlocked":True}, "Cap":{"cost":10,"unlocked":False},
    "Beanie":{"cost":10,"unlocked":False}, "Crown":{"cost":10,"unlocked":False},
    "Wizard Hat":{"cost":10,"unlocked":False}, "Headphones":{"cost":10,"unlocked":False},
    "Santa Hat":{"cost":10,"unlocked":False}, "Halo":{"cost":10,"unlocked":False},
    "Pirate Hat":{"cost":10,"unlocked":False}, "Top Hat":{"cost":10,"unlocked":False},
    "Viking Helmet":{"cost":10,"unlocked":False}, "Party Hat":{"cost":10,"unlocked":False},
}
color_themes = {
    "Classic":{"cost":0,"unlocked":True,"sky":(135,206,250),"ground":(100,200,100)},
    "Sunset":{"cost":10,"unlocked":False,"sky":(255,140,100),"ground":(150,100,50)},
    "Ocean":{"cost":10,"unlocked":False,"sky":(100,180,255),"ground":(255,220,150)},
    "Purple":{"cost":10,"unlocked":False,"sky":(180,100,255),"ground":(200,150,255)},
    "Night":{"cost":10,"unlocked":False,"sky":(20,20,60),"ground":(50,80,50)},
}
glasses = {
    "None":{"cost":0,"unlocked":True}, "Sunglasses":{"cost":10,"unlocked":False},
    "Round Glasses":{"cost":10,"unlocked":False}, "3D Glasses":{"cost":10,"unlocked":False},
    "Monocle":{"cost":10,"unlocked":False}, "Goggles":{"cost":10,"unlocked":False},
}

current_skin    = "Classic"
current_hat     = "None"
current_theme   = "Classic"
current_trail   = "None"
current_glasses = "None"

# ─── ANIMATION STATE ──────────────────────────────────────────────────────────
menu_animation_offset = 0
particle_systems  = []
leg_animation     = 0
shield_pulse      = 0
rainbow_offset    = 0
time_of_day       = 0
torch_flicker     = 0
_menu_tick        = 0
_game_tick        = 0

# ─── PLAYER ───────────────────────────────────────────────────────────────────
px, py   = 150, 330
vel      = 0
gravity  = 0.8
jump_power      = -14
high_jump_power = -20
ground          = 350
on_ground       = True

# ─── POWER-UPS ────────────────────────────────────────────────────────────────
shield_active  = False; shield_timer  = 0; shield_duration  = 300
magnet_active  = False; magnet_timer  = 0; magnet_duration  = 240; magnet_range = 150

# ─── GAME OBJECTS ─────────────────────────────────────────────────────────────
stones=[]; birds=[]; clouds=[]; coins=[]; shields=[]; magnets=[]
timer=0; bird_timer=0; coin_timer=0; powerup_timer=0
score=0; coins_collected=0; high_score=0
jetpack_active=False; jetpack_timer=0; jetpack_fuel=100; jetpack_max_fuel=100
jetpack_thrust=-0.5; jetpack_particles=[]; jetpacks=[]; jetpack_spawn_timer=0
jetpack_landing_invincibility=False; jetpack_invincibility_timer=0
jetpack_invincibility_duration=180; jetpack_was_active=False
max_player_height=50
space_rock_timer = 0

# ─── DIFFICULTY ───────────────────────────────────────────────────────────────
difficulty_settings = {
    "EASY":   {"speed":5,  "spawn":100, "bird_freq":0.5, "color":(57,255,20)},
    "NORMAL": {"speed":7,  "spawn":80,  "bird_freq":0.7, "color":(0,120,255)},
    "HARD":   {"speed":10, "spawn":60,  "bird_freq":1.0, "color":(255,50,80)},
}
stone_speed=7; spawn_rate=80; bird_freq=0.7

# ══════════════════════════════════════════════════════════════════════════════
#  HELPER DRAW UTILITIES
# ══════════════════════════════════════════════════════════════════════════════
def draw_neon_rect(surface, color, rect, radius=12, glow_width=3,
                   glow_alpha=80, fill=True, fill_alpha=30):
    x,y,w,h = rect
    for i in range(4,0,-1):
        s = pygame.Surface((w+i*6, h+i*6), pygame.SRCALPHA)
        pygame.draw.rect(s, (*color, max(0, glow_alpha-i*18)),
                         s.get_rect(), border_radius=radius+i*2)
        surface.blit(s, (x-i*3, y-i*3))
    if fill:
        glass = pygame.Surface((w,h), pygame.SRCALPHA)
        pygame.draw.rect(glass, (*color, fill_alpha), glass.get_rect(), border_radius=radius)
        surface.blit(glass, (x,y))
    pygame.draw.rect(surface, color, rect, glow_width, border_radius=radius)

def draw_glow_text(surface, text, font_obj, color, pos,
                   glow_color=None, glow_radius=3, center=False):
    if glow_color is None: glow_color = color
    ts = font_obj.render(text, True, glow_color)
    tx, ty = pos
    if center: tx -= ts.get_width()//2; ty -= ts.get_height()//2
    for dx in range(-glow_radius, glow_radius+1):
        for dy in range(-glow_radius, glow_radius+1):
            if dx==0 and dy==0: continue
            gs = font_obj.render(text, True, (*glow_color[:3], 40))
            gs.set_alpha(max(0, 80-(abs(dx)+abs(dy))*20))
            surface.blit(gs, (tx+dx, ty+dy))
    surface.blit(ts, (tx, ty))
    return ts.get_rect(topleft=(tx,ty))

def neon_star_bg(surface, stars_data, tick):
    for y in range(HEIGHT):
        t = y/HEIGHT
        pygame.draw.line(surface,(int(8+t*4),int(10+t*5),int(24+t*30)),(0,y),(WIDTH,y))
    for bx,by,brad,bcol in [(150,120,80,(0,40,80)),(600,200,120,(40,0,80)),
                             (800,80,60,(0,60,60)),(300,350,70,(60,0,40))]:
        nb=pygame.Surface((brad*2,brad*2),pygame.SRCALPHA)
        pygame.draw.circle(nb,(*bcol,18),(brad,brad),brad)
        surface.blit(nb,(bx-brad,by-brad))
    for sx,sy,ss,phase in stars_data:
        bright=int(120+math.sin(tick*0.03+phase)*100)
        pygame.draw.circle(surface,(max(80,min(255,bright)),)*3,(sx,sy),ss)

def draw_scanline_overlay(surface):
    for y in range(0,HEIGHT,4):
        s=pygame.Surface((WIDTH,1),pygame.SRCALPHA); s.fill((0,0,0,18))
        surface.blit(s,(0,y))

def lerp_color(a,b,t):
    return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))

_stars = [(random.randint(0,WIDTH),random.randint(0,HEIGHT-80),
           random.choice([1,1,1,2]),random.uniform(0,6.28)) for _ in range(120)]

# ══════════════════════════════════════════════════════════════════════════════
#  NEO BUTTON
# ══════════════════════════════════════════════════════════════════════════════
class NeonButton:
    def __init__(self, x, y, w, h, label, color, sub="", stars=0):
        self.rect=pygame.Rect(x,y,w,h); self.label=label; self.color=color
        self.sub=sub; self.stars=stars; self.hovered=False; self.hover_t=0.0; self._pulse=0.0
    def update(self):
        self.hover_t+=(( 1.0 if self.hovered else 0.0)-self.hover_t)*0.12
        self._pulse=(self._pulse+0.07)%(2*math.pi)
    def draw(self, surface):
        self.update(); t=self.hover_t; inflate=int(t*6); r=self.rect.inflate(inflate,inflate)
        glow_alpha=int(40+t*80)
        for i in range(5,0,-1):
            gs=pygame.Surface((r.width+i*8,r.height+i*8),pygame.SRCALPHA)
            pygame.draw.rect(gs,(*self.color,max(0,glow_alpha-i*12)),gs.get_rect(),border_radius=16+i*2)
            surface.blit(gs,(r.x-i*4,r.y-i*4))
        glass=pygame.Surface((r.width,r.height),pygame.SRCALPHA)
        pygame.draw.rect(glass,(*self.color,int(35+t*40)),glass.get_rect(),border_radius=16)
        shine=pygame.Surface((r.width,r.height//3),pygame.SRCALPHA)
        pygame.draw.rect(shine,(255,255,255,20),shine.get_rect(),border_radius=16)
        glass.blit(shine,(0,0)); surface.blit(glass,r.topleft)
        pygame.draw.rect(surface,lerp_color(self.color,(255,255,255),t*0.4),r,2,border_radius=16)
        lsurf=menu_font.render(self.label,True,(255,255,255))
        lx=r.centerx-lsurf.get_width()//2
        ly=r.centery-lsurf.get_height()//2-(8 if self.sub else 0)-(6 if self.stars else 0)
        surface.blit(lsurf,(lx,ly))
        if self.sub:
            ss=small_font.render(self.sub,True,(*self.color,))
            surface.blit(ss,(r.centerx-ss.get_width()//2,ly+lsurf.get_height()+2))
        if self.stars:
            star_y=ly+lsurf.get_height()+(18 if self.sub else 4)
            sx2=r.centerx-self.stars*11
            for i in range(self.stars): draw_star(surface,sx2+i*22,star_y+6,7,NEON_GOLD)
    def check_hover(self,pos): self.hovered=self.rect.collidepoint(pos)
    def is_clicked(self,pos): return self.rect.collidepoint(pos)

def draw_star(surface,cx,cy,r,color):
    pts=[]
    for i in range(10):
        ang=math.pi/2+i*math.pi/5; rad=r if i%2==0 else r//2
        pts.append((cx+rad*math.cos(ang),cy-rad*math.sin(ang)))
    pygame.draw.polygon(surface,color,pts)

class LevelCard:
    def __init__(self,idx,x,y,data):
        self.idx=idx; self.rect=pygame.Rect(x,y,130,110); self.data=data
        self.hovered=False; self.hover_t=0.0; self._t=0.0
    def update(self):
        self.hover_t+=((1.0 if self.hovered else 0.0)-self.hover_t)*0.10
        self._t=(self._t+0.05)%(2*math.pi)
    def draw(self,surface,selected):
        self.update(); t=self.hover_t; color=self.data["color"]
        r=self.rect.inflate(int(t*8),int(t*8)); locked=self.data["locked"]
        glow_a=int(50+t*100) if selected else int(20+t*60)
        for i in range(4,0,-1):
            gs=pygame.Surface((r.width+i*6,r.height+i*6),pygame.SRCALPHA)
            pygame.draw.rect(gs,(*color,max(0,glow_a-i*12)),gs.get_rect(),border_radius=14+i)
            surface.blit(gs,(r.x-i*3,r.y-i*3))
        glass=pygame.Surface((r.width,r.height),pygame.SRCALPHA)
        fa=55 if selected else 30
        pygame.draw.rect(glass,(*color,fa),glass.get_rect(),border_radius=14)
        if locked: pygame.draw.rect(glass,(0,0,0,80),glass.get_rect(),border_radius=14)
        surface.blit(glass,r.topleft)
        bc=color if not locked else (80,80,100); bw=3 if selected else 2
        pygame.draw.rect(surface,bc,r,bw,border_radius=14)
        icon=tiny_font.render(self.data["icon"],True,(255,255,255))
        iw=34; iy=r.y+10
        pygame.draw.circle(surface,(*color,120),(r.centerx,iy+iw//2),iw//2+4)
        surface.blit(icon,(r.centerx-icon.get_width()//2,iy+iw//2-icon.get_height()//2))
        nm=small_font.render(self.data["name"],True,(255,255,255) if not locked else (120,120,140))
        surface.blit(nm,(r.centerx-nm.get_width()//2,iy+iw+8))
        mult_col=color if not locked else (80,80,100)
        mb=pygame.Rect(r.x+8,iy+iw+28,r.width-16,18)
        pygame.draw.rect(surface,(*mult_col,80),mb,border_radius=6)
        pygame.draw.rect(surface,mult_col,mb,1,border_radius=6)
        mt=tiny_font.render(self.data["mult"],True,mult_col)
        surface.blit(mt,(mb.centerx-mt.get_width()//2,mb.y+2))
        ul=label_font.render(self.data["unlock"],True,(160,160,180) if locked else (100,220,100))
        surface.blit(ul,(r.centerx-ul.get_width()//2,mb.bottom+4))
        if locked:
            lk=font.render("🔒",True,(200,200,220))
            surface.blit(lk,(r.centerx-lk.get_width()//2,r.centery-lk.get_height()//2-10))
    def check_hover(self,pos): self.hovered=self.rect.collidepoint(pos)
    def is_clicked(self,pos): return self.rect.collidepoint(pos)

# Create UI elements
easy_btn   = NeonButton(60, 200,240,68,"EASY",   NEON_GREEN, "Relaxed pace",stars=2)
normal_btn = NeonButton(60, 282,240,68,"NORMAL", NEON_BLUE,  "Balanced challenge",stars=3)
hard_btn   = NeonButton(60, 364,240,68,"HARD",   NEON_RED,   "For the fearless",stars=5)
shop_btn   = NeonButton(60, HEIGHT-70,140,48,"SHOP",    NEON_GOLD,"")
cust_btn   = NeonButton(215,HEIGHT-70,180,48,"CUSTOMIZE",NEON_PURPLE,"")

_card_y=180; _card_gap=142
level_cards=[LevelCard(i,335+i*_card_gap,_card_y,MENU_LEVELS[i]) for i in range(5)]

# ══════════════════════════════════════════════════════════════════════════════
#  PARTICLE CLASSES
# ══════════════════════════════════════════════════════════════════════════════
class Particle:
    def __init__(self,x,y,color,vx_range=(-3,3),vy_range=(-5,-1)):
        self.x=x; self.y=y
        self.vx=random.uniform(*vx_range); self.vy=random.uniform(*vy_range)
        self.color=color; self.life=255; self.size=random.randint(3,7)
    def update(self):
        self.x+=self.vx; self.y+=self.vy; self.vy+=0.2; self.life-=5
    def draw(self,surface):
        if self.life>0:
            s=pygame.Surface((self.size*2,self.size*2),pygame.SRCALPHA)
            pygame.draw.circle(s,(*self.color,max(0,self.life)),(self.size,self.size),self.size)
            surface.blit(s,(self.x-self.size,self.y-self.size))

class LevelCompleteParticle:
    """Big celebratory burst particle for level complete popup."""
    def __init__(self, x, y):
        self.x=x; self.y=y
        angle=random.uniform(0,math.pi*2)
        speed=random.uniform(3,9)
        self.vx=math.cos(angle)*speed; self.vy=math.sin(angle)*speed
        self.color=random.choice([NEON_CYAN,NEON_GOLD,NEON_GREEN,NEON_PURPLE,(255,255,255)])
        self.life=255; self.size=random.randint(4,10)
    def update(self):
        self.x+=self.vx; self.y+=self.vy
        self.vy+=0.15; self.vx*=0.98
        self.life-=4
    def draw(self,surface):
        if self.life>0:
            s=pygame.Surface((self.size*2,self.size*2),pygame.SRCALPHA)
            pygame.draw.circle(s,(*self.color,max(0,self.life)),(self.size,self.size),self.size)
            surface.blit(s,(int(self.x-self.size),int(self.y-self.size)))

class JetpackParticle:
    def __init__(self,x,y):
        self.x=x; self.y=y
        self.vx=random.uniform(-3,3); self.vy=random.uniform(2,6)
        self.color=random.choice([(255,150,0),(255,100,0),(255,200,50)])
        self.life=255; self.size=random.randint(4,8)
    def update(self):
        self.x+=self.vx; self.y+=self.vy; self.vy+=0.3
        self.life-=15; self.size=max(2,self.size-0.3)
    def draw(self,surface):
        if self.life>0:
            s=pygame.Surface((int(self.size*2),int(self.size*2)),pygame.SRCALPHA)
            pygame.draw.circle(s,(*self.color,max(0,int(self.life))),(int(self.size),int(self.size)),int(self.size))
            surface.blit(s,(int(self.x-self.size),int(self.y-self.size)))

class Cloud:
    def __init__(self):
        self.x=random.randint(-100,WIDTH); self.y=random.randint(30,200)
        self.speed=random.uniform(0.3,0.8); self.size=random.randint(40,80)
    def update(self): self.x+=self.speed
    if True: pass  # guard
    def _wrap(self):
        if self.x>WIDTH+100: self.x=-100; self.y=random.randint(30,200)
    def draw(self,surface):
        self._wrap()
        pygame.draw.circle(surface,(255,255,255),(int(self.x),int(self.y)),self.size//2)
        pygame.draw.circle(surface,(255,255,255),(int(self.x+self.size//2),int(self.y)),self.size//2)
        pygame.draw.circle(surface,(255,255,255),(int(self.x+self.size//4),int(self.y-self.size//3)),self.size//3)

class Coin:
    def __init__(self,x,y):
        self.x=x; self.y=y; self.rect=pygame.Rect(x,y,25,25); self.rotation=0; self.pulse=0
    def update(self,speed):
        self.x-=speed; self.rect.x=self.x; self.rotation+=5; self.pulse=(self.pulse+0.1)%(2*math.pi)
    def draw(self,surface):
        size_mult=abs(math.cos(self.rotation*0.05)); coin_width=int(25*size_mult)
        glow_size=int(30+math.sin(self.pulse)*5)
        glow_surf=pygame.Surface((glow_size*2,glow_size*2),pygame.SRCALPHA)
        pygame.draw.circle(glow_surf,(255,215,0,50),(glow_size,glow_size),glow_size)
        surface.blit(glow_surf,(self.x+12-glow_size,self.y+12-glow_size))
        if coin_width>5:
            pygame.draw.ellipse(surface,(255,200,0),(self.x+12-coin_width//2,self.y,coin_width,25))
            pygame.draw.ellipse(surface,(255,215,0),(self.x+12-coin_width//2+2,self.y+2,max(1,coin_width-4),21))
            if coin_width>10: pygame.draw.circle(surface,(255,200,0),(self.x+12,self.y+12),coin_width//4)

class Shield:
    def __init__(self,x,y):
        self.x=x; self.y=y; self.rect=pygame.Rect(x,y,30,30); self.pulse=0
    def update(self,speed):
        self.x-=speed; self.rect.x=self.x; self.pulse=(self.pulse+0.15)%(2*math.pi)
    def draw(self,surface):
        glow_size=int(35+math.sin(self.pulse)*5)
        gs=pygame.Surface((glow_size*2,glow_size*2),pygame.SRCALPHA)
        pygame.draw.circle(gs,(100,200,255,60),(glow_size,glow_size),glow_size)
        surface.blit(gs,(self.x+15-glow_size,self.y+15-glow_size))
        pygame.draw.rect(surface,(100,200,255),(self.x+5,self.y,20,20),border_radius=3)
        pygame.draw.polygon(surface,(150,220,255),[(self.x+15,self.y+5),(self.x+25,self.y+15),(self.x+15,self.y+25),(self.x+5,self.y+15)])
        pygame.draw.rect(surface,(255,255,255),(self.x+5,self.y,20,20),2,border_radius=3)

class Magnet:
    def __init__(self,x,y):
        self.x=x; self.y=y; self.rect=pygame.Rect(x,y,30,30); self.pulse=0
    def update(self,speed):
        self.x-=speed; self.rect.x=self.x; self.pulse=(self.pulse+0.15)%(2*math.pi)
    def draw(self,surface):
        glow_size=int(35+math.sin(self.pulse)*5)
        gs=pygame.Surface((glow_size*2,glow_size*2),pygame.SRCALPHA)
        pygame.draw.circle(gs,(255,100,100,60),(glow_size,glow_size),glow_size)
        surface.blit(gs,(self.x+15-glow_size,self.y+15-glow_size))
        pygame.draw.rect(surface,(255,50,50),(self.x+5,self.y+5,6,20))
        pygame.draw.rect(surface,(255,50,50),(self.x+19,self.y+5,6,20))
        pygame.draw.rect(surface,(100,100,255),(self.x+5,self.y+20,20,6))
        pygame.draw.rect(surface,(255,255,255),(self.x+5,self.y+5,20,21),2)

class Jetpack:
    def __init__(self,x,y):
        self.x=x; self.y=y; self.rect=pygame.Rect(x,y,35,35); self.pulse=0; self.float_offset=0
    def update(self,speed):
        self.x-=speed; self.rect.x=self.x; self.pulse=(self.pulse+0.1)%(2*math.pi)
        self.float_offset=math.sin(self.pulse*2)*3
    def draw(self,surface):
        y_pos=self.y+self.float_offset
        glow_size=int(40+math.sin(self.pulse)*5)
        gs=pygame.Surface((glow_size*2,glow_size*2),pygame.SRCALPHA)
        pygame.draw.circle(gs,(255,150,0,60),(glow_size,glow_size),glow_size)
        surface.blit(gs,(self.x+17-glow_size,y_pos+17-glow_size))
        pygame.draw.rect(surface,(120,120,140),(self.x+8,y_pos+5,20,25),border_radius=5)
        pygame.draw.rect(surface,(150,150,170),(self.x+10,y_pos+7,16,21),border_radius=4)
        pygame.draw.ellipse(surface,(200,50,50),(self.x+5,y_pos+8,8,18))
        pygame.draw.ellipse(surface,(200,50,50),(self.x+23,y_pos+8,8,18))
        pygame.draw.rect(surface,(80,80,100),(self.x+8,y_pos+28,6,5))
        pygame.draw.rect(surface,(80,80,100),(self.x+22,y_pos+28,6,5))
        fh=int(5+abs(math.sin(self.pulse*3))*3)
        pygame.draw.polygon(surface,(255,150,0),[(self.x+11,y_pos+33),(self.x+9,y_pos+33+fh),(self.x+13,y_pos+33)])
        pygame.draw.polygon(surface,(255,150,0),[(self.x+25,y_pos+33),(self.x+23,y_pos+33+fh),(self.x+27,y_pos+33)])
        pygame.draw.ellipse(surface,(255,255,255),(self.x+12,y_pos+10,6,4))

for _ in range(5): clouds.append(Cloud())

# ══════════════════════════════════════════════════════════════════════════════
#  HAND / CV
# ══════════════════════════════════════════════════════════════════════════════
cap = cv2.VideoCapture(0)
mp_hands = mp.solutions.hands
hands    = mp_hands.Hands(max_num_hands=1)
draw_mp  = mp.solutions.drawing_utils

def is_paper_hand(lm):
    fingers=[lm[8].y<lm[6].y,lm[12].y<lm[10].y,lm[16].y<lm[14].y,lm[20].y<lm[18].y]
    return fingers==[1,1,1,1]

def detect_hand_gesture():
    success,img=cap.read()
    if not success: return None,False,None
    imgRGB=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
    result=hands.process(imgRGB)
    jump_type=None; restart=False
    if result.multi_hand_landmarks:
        hand=result.multi_hand_landmarks[0]; lm=hand.landmark
        fingers=[lm[8].y<lm[6].y,lm[12].y<lm[10].y,lm[16].y<lm[14].y,lm[20].y<lm[18].y]
        if fingers==[1,0,0,0]: jump_type="normal"
        elif fingers==[1,1,0,0]: jump_type="high"
        if is_paper_hand(lm): restart=True
        draw_mp.draw_landmarks(img,hand,mp_hands.HAND_CONNECTIONS)
    img=cv2.resize(img,(220,160))
    img=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
    img=pygame.surfarray.make_surface(img)
    img=pygame.transform.rotate(img,-90)
    img=pygame.transform.flip(img,True,False)
    return jump_type,restart,img

# ══════════════════════════════════════════════════════════════════════════════
#  GAME RESET
# ══════════════════════════════════════════════════════════════════════════════
def reset_game():
    global py,vel,stones,birds,score,coins_collected,stone_speed,spawn_rate,bird_freq
    global timer,bird_timer,coin_timer,powerup_timer,game_state,on_ground,time_of_day
    global shield_active,shield_timer,magnet_active,magnet_timer,coins,shields,magnets
    global jetpack_active,jetpack_timer,jetpack_fuel,jetpacks,jetpack_spawn_timer,jetpack_particles
    global jetpack_landing_invincibility,jetpack_invincibility_timer,jetpack_was_active
    global current_level,level_just_changed,level_complete_timer,level_popup_anim,level_popup_phase
    global level_complete_particles,space_rocks,space_rock_timer,_game_tick

    py=330; vel=0; on_ground=True
    stones.clear(); birds.clear(); coins.clear(); shields.clear()
    magnets.clear(); jetpacks.clear(); jetpack_particles.clear()
    space_rocks.clear()
    score=0; coins_collected=0
    timer=0; bird_timer=0; coin_timer=0; powerup_timer=0; space_rock_timer=0
    shield_active=False; shield_timer=0; magnet_active=False; magnet_timer=0
    jetpack_active=False; jetpack_timer=0; jetpack_fuel=100; jetpack_spawn_timer=0
    jetpack_landing_invincibility=False; jetpack_invincibility_timer=0; jetpack_was_active=False
    current_level=1; level_just_changed=False; level_complete_timer=0
    level_popup_anim=0.0; level_popup_phase="in"; level_complete_particles=[]
    time_of_day=0; _game_tick=0

    # Apply difficulty
    s=difficulty_settings[difficulty]
    base_spd=s["speed"]; base_spawn=s["spawn"]; base_bird=s["bird_freq"]
    stone_speed,spawn_rate,bird_freq=apply_level_to_speed(base_spd,base_spawn,base_bird)
    game_state=PLAYING

    # Rain needs initialisation
    if get_environment()=="rain": init_rain()

# ══════════════════════════════════════════════════════════════════════════════
#  LEVEL PROGRESSION UPDATE  (called every PLAYING frame)
# ══════════════════════════════════════════════════════════════════════════════
def update_level_progression():
    """Check if score crossed a threshold and trigger level-up."""
    global current_level,level_just_changed,level_complete_timer
    global level_popup_anim,level_popup_phase,level_complete_particles
    global stone_speed,spawn_rate,bird_freq,game_state

    if game_state==LEVEL_COMPLETE:
        # Animate the popup
        level_complete_timer+=1
        if level_popup_phase=="in":
            level_popup_anim=min(1.0,level_popup_anim+0.05)
            if level_popup_anim>=1.0: level_popup_phase="hold"
        elif level_popup_phase=="hold":
            if level_complete_timer>=LEVEL_POPUP_DURATION:
                level_popup_phase="out"
        elif level_popup_phase=="out":
            level_popup_anim=max(0.0,level_popup_anim-0.05)
            if level_popup_anim<=0.0:
                game_state=PLAYING        # resume game
                level_just_changed=False
        return

    # Find next level threshold
    if current_level < len(LEVEL_DEFINITIONS):
        next_thresh = LEVEL_DEFINITIONS[current_level][0]   # index = current_level (0-indexed next)
        if score>=next_thresh and not level_just_changed:
            current_level+=1
            level_just_changed=True
            level_complete_timer=0
            level_popup_anim=0.0
            level_popup_phase="in"
            game_state=LEVEL_COMPLETE

            # Update speeds for new level
            s=difficulty_settings[difficulty]
            stone_speed,spawn_rate,bird_freq=apply_level_to_speed(
                s["speed"],s["spawn"],s["bird_freq"])

            # Burst particles
            for _ in range(60):
                level_complete_particles.append(
                    LevelCompleteParticle(WIDTH//2, HEIGHT//2))

            # Init environment effects
            env=get_environment()
            if env=="rain": init_rain()

# ══════════════════════════════════════════════════════════════════════════════
#  LEVEL COMPLETE POPUP DRAW
# ══════════════════════════════════════════════════════════════════════════════
def draw_level_complete_popup():
    if game_state!=LEVEL_COMPLETE: return

    t = level_popup_anim
    # easeOutBack for scale
    scale = t * (1.0 + 0.15*math.sin(t*math.pi))

    overlay=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
    overlay.fill((0,0,0,int(160*t)))
    win.blit(overlay,(0,0))

    # Update & draw celebrate particles
    for p in level_complete_particles[:]:
        p.update(); p.draw(win)
        if p.life<=0: level_complete_particles.remove(p)

    # Panel
    pw,ph=480,200
    px2=WIDTH//2-pw//2; py2=HEIGHT//2-ph//2

    panel_surf=pygame.Surface((pw,ph),pygame.SRCALPHA)
    pygame.draw.rect(panel_surf,(10,15,40,220),panel_surf.get_rect(),border_radius=20)
    # scale panel
    scaled_w=int(pw*scale); scaled_h=int(ph*scale)
    if scaled_w>0 and scaled_h>0:
        panel_surf=pygame.transform.scale(panel_surf,(scaled_w,scaled_h))
        sx=WIDTH//2-scaled_w//2; sy=HEIGHT//2-scaled_h//2
        win.blit(panel_surf,(sx,sy))

        # Neon border glow
        glow_rect=(sx,sy,scaled_w,scaled_h)
        draw_neon_rect(win,NEON_GOLD,glow_rect,radius=20,glow_width=3,glow_alpha=100,fill=False)

        # Text — scale via font size approximation (we draw at normal size and scale)
        completed_str=f"✦  Level {current_level-1} Complete!  ✦"
        ct=level_popup_font.render(completed_str,True,NEON_GOLD)
        ctr=ct.get_rect(center=(WIDTH//2,sy+int(scaled_h*0.32)))
        alpha_surf=pygame.Surface(ct.get_size(),pygame.SRCALPHA)
        alpha_surf.blit(ct,(0,0))
        alpha_surf.set_alpha(int(255*t))
        win.blit(alpha_surf,ctr)

        unlock_str=f"Level {current_level} Unlocked — {get_level_def(current_level)[5]}"
        ut=small_font.render(unlock_str,True,NEON_CYAN)
        utr=ut.get_rect(center=(WIDTH//2,sy+int(scaled_h*0.60)))
        ut.set_alpha(int(255*t))
        win.blit(ut,utr)

        # env badge
        env_name=get_level_def(current_level)[2].upper()
        env_colors={"DAY":NEON_CYAN,"NIGHT":(100,120,255),"RAIN":(100,180,255),
                    "FOG":(180,190,200),"SPACE":NEON_PURPLE}
        ec=env_colors.get(env_name,NEON_CYAN)
        badge_rect=pygame.Rect(WIDTH//2-80,sy+int(scaled_h*0.73),160,26)
        draw_neon_rect(win,ec,badge_rect,radius=8,glow_width=2,glow_alpha=60,fill_alpha=25)
        et=tiny_font.render(f"Environment: {env_name}",True,ec)
        et.set_alpha(int(255*t))
        win.blit(et,(badge_rect.centerx-et.get_width()//2,badge_rect.y+5))

# ══════════════════════════════════════════════════════════════════════════════
#  ENVIRONMENT BACKGROUNDS
# ══════════════════════════════════════════════════════════════════════════════
def draw_environment_background():
    """Draw the sky/ground appropriate for the current level environment."""
    env=get_environment(); cfg=ENV_CONFIG[env]
    sky=cfg["sky"]; horizon=cfg["horizon"]

    if env=="space":
        # Draw pure space
        for y in range(HEIGHT):
            t=y/HEIGHT
            pygame.draw.line(win,(max(0,5+int(t*10)),max(0,5+int(t*5)),max(0,20+int(t*10))),(0,y),(WIDTH,y))
        draw_space_bg(win,_game_tick)
    elif env=="fog":
        # Light grey gradient
        for y in range(HEIGHT):
            t=y/HEIGHT
            r=int(sky[0]*(1-t)+cfg["ground"][0]*t)
            g=int(sky[1]*(1-t)+cfg["ground"][1]*t)
            b=int(sky[2]*(1-t)+cfg["ground"][2]*t)
            pygame.draw.line(win,(r,g,b),(0,y),(WIDTH,y))
    else:
        # Standard gradient sky
        for y in range(HEIGHT):
            t=y/HEIGHT
            r=int(sky[0]*(1-t)+horizon[0]*t)
            g=int(sky[1]*(1-t)+horizon[1]*t)
            b=int(sky[2]*(1-t)+horizon[2]*t)
            pygame.draw.line(win,(max(0,min(255,r)),max(0,min(255,g)),max(0,min(255,b))),(0,y),(WIDTH,y))

    if env=="night":
        # Stars
        for sx,sy,ss,phase in _stars:
            bright=int(120+math.sin(_game_tick*0.03+phase)*100)
            pygame.draw.circle(win,(max(80,min(255,bright)),)*3,(sx,sy),ss)

    # Clouds (skip in space/fog)
    if env not in ("space","fog"):
        for cloud in clouds: cloud.draw(win)

def draw_environment_ground():
    env=get_environment(); cfg=ENV_CONFIG[env]
    ground_color=cfg["ground"]; detail_color=cfg["ground_detail"]

    if env=="space":
        # Purple-tinted alien ground
        pygame.draw.rect(win,(40,25,60),(0,ground+20,WIDTH,HEIGHT-ground-20))
        for i in range(0,WIDTH,20):
            off=math.sin(i*0.15+score*0.01)*4
            pygame.draw.line(win,(80,50,100),(i,ground+20),(i+off,ground+14),2)
    else:
        pygame.draw.rect(win,ground_color,(0,ground+20,WIDTH,HEIGHT-ground-20))
        # Grass / ground detail
        for i in range(0,WIDTH,15):
            off=math.sin(i*0.1+score*0.01)*3
            pygame.draw.line(win,detail_color,(i,ground+20),(i+off,ground+13),2)

    pygame.draw.line(win,detail_color,(0,ground+20),(WIDTH,ground+20),4)

def draw_environment_overlay():
    """Post-scene overlays: rain, fog veil, etc."""
    env=get_environment(); cfg=ENV_CONFIG[env]
    if cfg["overlay"]:
        ov=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
        ov.fill(cfg["overlay"])
        win.blit(ov,(0,0))
    if env=="rain":
        draw_rain(win)
    elif env=="fog":
        draw_fog(win)

def draw_night_city_lights():
    """Decorative window-lights in night mode."""
    if get_environment()!="night": return
    # simple building silhouettes on horizon
    for bx,bw,bh in [(50,60,120),(130,40,90),(200,70,140),(310,50,100),
                      (420,80,160),(530,45,110),(640,65,130),(760,55,95),(840,70,150)]:
        pygame.draw.rect(win,(20,25,50),(bx,ground+20-bh,bw,bh))
        # windows
        for wy in range(ground+20-bh+8,ground+20-8,14):
            for wx in range(bx+5,bx+bw-5,10):
                if random.random()<0.6 or (bx+wy)%7!=0:  # mostly lit
                    wcol=random.choice([(255,220,100,120),(200,230,255,120),(255,200,150,120)])
                    ws=pygame.Surface((6,8),pygame.SRCALPHA)
                    ws.fill(wcol); win.blit(ws,(wx,wy))

# ══════════════════════════════════════════════════════════════════════════════
#  HAT / GLASSES / PLAYER DRAWING  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════
def draw_hat(surface,x,y,hat_type):
    if hat_type=="Cap":
        pygame.draw.ellipse(surface,(255,0,0),(x,y-70,24,8))
        pygame.draw.rect(surface,(255,0,0),(x+5,y-75,14,10),border_radius=3)
        pygame.draw.circle(surface,(255,255,255),(x+12,y-71),2)
    elif hat_type=="Beanie":
        pygame.draw.ellipse(surface,(100,50,150),(x+2,y-72,20,12))
        pygame.draw.circle(surface,(150,100,200),(x+12,y-75),3)
    elif hat_type=="Crown":
        pygame.draw.polygon(surface,(255,215,0),[(x+3,y-68),(x+7,y-75),(x+12,y-70),(x+17,y-75),(x+21,y-68),(x+12,y-65)])
        for i in range(3): pygame.draw.circle(surface,(255,0,0),(x+7+i*5,y-75),2)
    elif hat_type=="Wizard Hat":
        pygame.draw.polygon(surface,(50,0,150),[(x+12,y-90),(x+5,y-65),(x+19,y-65)])
        pygame.draw.ellipse(surface,(50,0,150),(x,y-68,24,8))
        for i in range(3): pygame.draw.circle(surface,(255,255,100),(x+8+i*4,y-75-i*5),2)
    elif hat_type=="Halo":
        pygame.draw.ellipse(surface,(255,255,100),(x,y-80,24,8),2)
        for i in range(4):
            angle=i*1.57; gx=x+12+math.cos(angle)*12; gy=y-76+math.sin(angle)*4
            pygame.draw.circle(surface,(255,255,150),(int(gx),int(gy)),2)
    elif hat_type=="Headphones":
        pygame.draw.arc(surface,(50,50,50),(x+2,y-72,20,20),3.14,6.28,3)
        pygame.draw.circle(surface,(50,50,50),(x+4,y-62),4)
        pygame.draw.circle(surface,(50,50,50),(x+20,y-62),4)
        pygame.draw.circle(surface,(200,200,200),(x+4,y-62),2)
        pygame.draw.circle(surface,(200,200,200),(x+20,y-62),2)
    elif hat_type=="Santa Hat":
        pygame.draw.polygon(surface,(200,0,0),[(x+12,y-85),(x+5,y-65),(x+19,y-65)])
        pygame.draw.ellipse(surface,(255,255,255),(x+8,y-88,8,8))
        pygame.draw.ellipse(surface,(255,255,255),(x,y-68,24,8))
    elif hat_type=="Top Hat":
        pygame.draw.rect(surface,(0,0,0),(x+6,y-80,12,15))
        pygame.draw.ellipse(surface,(0,0,0),(x,y-68,24,8))
        pygame.draw.rect(surface,(255,0,0),(x+6,y-75,12,3))
    elif hat_type=="Viking Helmet":
        pygame.draw.ellipse(surface,(150,150,150),(x+2,y-70,20,12))
        pygame.draw.circle(surface,(200,200,0),(x+12,y-75),3)
        pygame.draw.polygon(surface,(255,220,150),[(x+2,y-70),(x,y-78),(x+4,y-68)])
        pygame.draw.polygon(surface,(255,220,150),[(x+22,y-70),(x+24,y-78),(x+20,y-68)])
    elif hat_type=="Pirate Hat":
        pygame.draw.polygon(surface,(0,0,0),[(x+3,y-65),(x+21,y-65),(x+18,y-75),(x+6,y-75)])
        pygame.draw.circle(surface,(255,255,255),(x+12,y-70),3)
        pygame.draw.line(surface,(255,255,255),(x+9,y-72),(x+15,y-68),2)
    elif hat_type=="Party Hat":
        pygame.draw.polygon(surface,(255,100,200),[(x+12,y-85),(x+6,y-65),(x+18,y-65)])
        for i in range(4):
            color=[(255,0,0),(0,255,0),(0,0,255),(255,255,0)][i]
            pygame.draw.circle(surface,color,(x+8+i*3,y-70-i*4),2)

def draw_glasses(surface,x,y,glasses_type):
    if glasses_type=="Sunglasses":
        pygame.draw.ellipse(surface,(0,0,0),(x-6,y-4,8,6))
        pygame.draw.ellipse(surface,(0,0,0),(x+2,y-4,8,6))
        pygame.draw.line(surface,(0,0,0),(x-6,y-1),(x-10,y-2),2)
        pygame.draw.line(surface,(0,0,0),(x+10,y-1),(x+14,y-2),2)
        pygame.draw.line(surface,(0,0,0),(x+2,y-1),(x-2,y-1),2)
    elif glasses_type=="Round Glasses":
        pygame.draw.circle(surface,(100,50,0),(x-3,y-1),4,2)
        pygame.draw.circle(surface,(100,50,0),(x+5,y-1),4,2)
        pygame.draw.line(surface,(100,50,0),(x+1,y-1),(x-1,y-1),2)
    elif glasses_type=="3D Glasses":
        pygame.draw.ellipse(surface,(255,0,0),(x-6,y-4,8,6),2)
        pygame.draw.ellipse(surface,(0,100,255),(x+2,y-4,8,6),2)
        pygame.draw.line(surface,(0,0,0),(x+2,y-1),(x-2,y-1),2)
    elif glasses_type=="Monocle":
        pygame.draw.circle(surface,(200,150,0),(x+5,y-1),4,2)
        pygame.draw.line(surface,(200,150,0),(x+5,y+3),(x+5,y+8),2)
    elif glasses_type=="Goggles":
        pygame.draw.ellipse(surface,(100,100,100),(x-6,y-4,8,7))
        pygame.draw.ellipse(surface,(100,100,100),(x+2,y-4,8,7))
        pygame.draw.ellipse(surface,(150,200,255),(x-5,y-3,6,5))
        pygame.draw.ellipse(surface,(150,200,255),(x+3,y-3,6,5))

def draw_torch(surface,x,y):
    global torch_flicker
    torch_flicker=(torch_flicker+0.3)%(2*math.pi)

def draw_jetpack_on_player(surface,x,y):
    global torch_flicker
    pygame.draw.rect(surface,(120,120,140),(x+8,y-50,16,20),border_radius=4)
    pygame.draw.rect(surface,(150,150,170),(x+10,y-48,12,16),border_radius=3)
    pygame.draw.ellipse(surface,(200,50,50),(x+6,y-46,6,14))
    pygame.draw.ellipse(surface,(200,50,50),(x+20,y-46,6,14))
    pygame.draw.rect(surface,(80,80,100),(x+8,y-30,5,4))
    pygame.draw.rect(surface,(80,80,100),(x+19,y-30,5,4))
    pygame.draw.rect(surface,(139,69,19),(x+30,y-30,5,25))
    flame_offset=math.sin(torch_flicker)*2; flame_size=12+abs(math.sin(torch_flicker*2))*3
    glow_size=int(flame_size*2.5)
    glow_surf=pygame.Surface((glow_size*2,glow_size*2),pygame.SRCALPHA)
    pygame.draw.circle(glow_surf,(255,200,0,30),(glow_size,glow_size),glow_size)
    surface.blit(glow_surf,(x+32-glow_size,y-38-glow_size+flame_offset))
    pygame.draw.ellipse(surface,(255,140,0),(x+28,y-45+flame_offset,10,int(flame_size)))
    pygame.draw.ellipse(surface,(255,220,0),(x+30,y-43+flame_offset,6,int(flame_size*0.7)))
    pygame.draw.ellipse(surface,(255,255,200),(x+31,y-41+flame_offset,4,int(flame_size*0.4)))

def draw_running_player(surface,x,y,leg_frame):
    global rainbow_offset
    skin_data=character_skins[current_skin]; base_color=skin_data["color"]
    style=skin_data["style"]; hair_color=skin_data["hair"]
    is_night=get_environment()=="night"
    if current_skin=="Rainbow":
        rainbow_offset=(rainbow_offset+2)%360
        shirt_color=get_rainbow_color(rainbow_offset)
        hair_color=get_rainbow_color((rainbow_offset+60)%360)
    else: shirt_color=base_color
    head_radius=12; head_x=x+12; head_y=y-60
    torso_start_y=y-45; torso_end_y=y-15
    if style=="robot": skin_tone=(200,200,230); pants_color=(150,150,180); shoe_color=(120,120,150)
    elif style=="space": skin_tone=(240,240,240); pants_color=(200,200,200); shoe_color=(180,180,180)
    else: skin_tone=(255,220,177); pants_color=(40,40,60); shoe_color=(80,40,20)
    if on_ground:
        leg_swing=math.sin(leg_frame*1.2)
        lkx=x+8+leg_swing*45; lky=y-5
        lfx=lkx-abs(leg_swing)*30; lfy=y+8
        rkx=x+16-leg_swing*45; rky=y-5
        rfx=rkx+abs(leg_swing)*30; rfy=y+8
        pygame.draw.line(surface,pants_color,(x+12,torso_end_y),(lkx,lky),8)
        pygame.draw.circle(surface,pants_color,(int(lkx),int(lky)),5)
        pygame.draw.line(surface,pants_color,(lkx,lky),(lfx,lfy),7)
        pygame.draw.ellipse(surface,shoe_color,(lfx-8,lfy-4,16,8))
        pygame.draw.ellipse(surface,(0,0,0),(lfx-8,lfy-4,16,8),2)
        pygame.draw.line(surface,pants_color,(x+12,torso_end_y),(rkx,rky),8)
        pygame.draw.circle(surface,pants_color,(int(rkx),int(rky)),5)
        pygame.draw.line(surface,pants_color,(rkx,rky),(rfx,rfy),7)
        pygame.draw.ellipse(surface,shoe_color,(rfx-8,rfy-4,16,8))
        pygame.draw.ellipse(surface,(0,0,0),(rfx-8,rfy-4,16,8),2)
    else:
        pygame.draw.line(surface,pants_color,(x+12,torso_end_y),(x+5,y+5),8)
        pygame.draw.line(surface,pants_color,(x+5,y+5),(x+3,y+12),7)
        pygame.draw.ellipse(surface,shoe_color,(x-5,y+10,16,8))
        pygame.draw.line(surface,pants_color,(x+12,torso_end_y),(x+19,y+5),8)
        pygame.draw.line(surface,pants_color,(x+19,y+5),(x+21,y+12),7)
        pygame.draw.ellipse(surface,shoe_color,(x+13,y+10,16,8))
    torso_points=[(x+4,torso_start_y),(x+20,torso_start_y),(x+18,torso_end_y),(x+6,torso_end_y)]
    pygame.draw.polygon(surface,shirt_color,torso_points)
    pygame.draw.polygon(surface,(0,0,0),torso_points,2)
    if style=="hero":
        pygame.draw.circle(surface,(255,255,100),(x+12,torso_start_y+15),6)
        pygame.draw.polygon(surface,(255,200,0),[(x+12,torso_start_y+12),(x+9,torso_start_y+18),(x+15,torso_start_y+18)])
    elif style=="smart":
        for i in range(3): pygame.draw.circle(surface,(50,50,50),(x+12,torso_start_y+5+i*8),2)
    else: pygame.draw.line(surface,(255,255,255),(x+8,torso_start_y+2),(x+16,torso_start_y+2),2)
    if jetpack_active: draw_jetpack_on_player(surface,x,y)
    arm_swing=math.sin(leg_frame*1.2)*35
    if is_night:
        lsx=x+6; lsy=torso_start_y+3; lex=lsx-10-arm_swing; ley=lsy+12; lhx=lex-8; lhy=ley+10
        pygame.draw.line(surface,skin_tone,(lsx,lsy),(lex,ley),6)
        pygame.draw.circle(surface,skin_tone,(int(lex),int(ley)),4)
        pygame.draw.line(surface,skin_tone,(lex,ley),(lhx,lhy),5)
        pygame.draw.circle(surface,skin_tone,(int(lhx),int(lhy)),5)
        rsx=x+18; rsy=torso_start_y+3; rex=rsx+15; rey=rsy+8; rhx=rex+10; rhy=rey+5
        pygame.draw.line(surface,skin_tone,(rsx,rsy),(rex,rey),6)
        pygame.draw.circle(surface,skin_tone,(int(rex),int(rey)),4)
        pygame.draw.line(surface,skin_tone,(rex,rey),(rhx,rhy),5)
        pygame.draw.circle(surface,skin_tone,(int(rhx),int(rhy)),5)
        draw_torch(surface,rhx-15,rhy+15)
    else:
        lsx=x+6; lsy=torso_start_y+3; lex=lsx-12-arm_swing; ley=lsy+12; lhx=lex-6-arm_swing/2; lhy=ley+8
        pygame.draw.line(surface,skin_tone,(lsx,lsy),(lex,ley),6)
        pygame.draw.circle(surface,skin_tone,(int(lex),int(ley)),4)
        pygame.draw.line(surface,skin_tone,(lex,ley),(lhx,lhy),5)
        pygame.draw.circle(surface,skin_tone,(int(lhx),int(lhy)),5)
        rsx=x+18; rsy=torso_start_y+3; rex=rsx+12+arm_swing; rey=rsy+12; rhx=rex+6+arm_swing/2; rhy=rey+8
        pygame.draw.line(surface,skin_tone,(rsx,rsy),(rex,rey),6)
        pygame.draw.circle(surface,skin_tone,(int(rex),int(rey)),4)
        pygame.draw.line(surface,skin_tone,(rex,rey),(rhx,rhy),5)
        pygame.draw.circle(surface,skin_tone,(int(rhx),int(rhy)),5)
    pygame.draw.line(surface,skin_tone,(x+12,torso_start_y),(x+12,head_y+head_radius),5)
    pygame.draw.circle(surface,(0,0,0),(head_x,head_y),head_radius+1)
    pygame.draw.circle(surface,skin_tone,(head_x,head_y),head_radius)
    if style=="warrior":
        pygame.draw.arc(surface,hair_color,(head_x-head_radius,head_y-head_radius-5,head_radius*2,head_radius*2),0,3.14,4)
        pygame.draw.ellipse(surface,hair_color,(head_x-6,head_y+3,12,10))
    elif style=="robot":
        pygame.draw.line(surface,(150,150,200),(head_x,head_y-head_radius),(head_x,head_y-head_radius-8),3)
        pygame.draw.circle(surface,(255,0,0),(head_x,head_y-head_radius-8),3)
    elif style=="space":
        pygame.draw.ellipse(surface,(100,150,255),(head_x-10,head_y-6,20,12))
    else:
        pygame.draw.arc(surface,hair_color,(head_x-head_radius,head_y-head_radius-5,head_radius*2,head_radius*2),0,3.14,4)
    if style!="robot":
        for ex,ey_off in [(-4,-2),(4,-2)]:
            pygame.draw.circle(surface,(255,255,255),(head_x+ex,head_y+ey_off),3)
            pygame.draw.circle(surface,(0,100,200),(head_x+ex,head_y+ey_off),2)
            pygame.draw.circle(surface,(0,0,0),(head_x+ex+1,head_y+ey_off),1)
        pygame.draw.line(surface,(40,25,15),(head_x-6,head_y-6),(head_x-2,head_y-5),2)
        pygame.draw.line(surface,(40,25,15),(head_x+2,head_y-5),(head_x+6,head_y-6),2)
    else:
        pygame.draw.circle(surface,(255,0,0),(head_x-4,head_y-2),3)
        pygame.draw.circle(surface,(255,0,0),(head_x+4,head_y-2),3)
    if current_glasses!="None": draw_glasses(surface,head_x,head_y,current_glasses)
    if style!="robot":
        pygame.draw.line(surface,(200,150,100),(head_x,head_y),(head_x,head_y+3),2)
        pygame.draw.circle(surface,(200,150,100),(head_x-1,head_y+3),1)
        pygame.draw.circle(surface,(200,150,100),(head_x+1,head_y+3),1)
    pygame.draw.arc(surface,(150,50,50),(head_x-5,head_y+2,10,6),0,3.14,2)
    if current_hat!="None": draw_hat(surface,head_x-12,head_y,current_hat)

def get_rainbow_color(offset):
    hue=(offset%360)/360
    return (int(abs(math.sin(hue*6.28)*255)),int(abs(math.sin((hue+0.33)*6.28)*255)),int(abs(math.sin((hue+0.66)*6.28)*255)))

def draw_shield_effect(surface,x,y):
    global shield_pulse
    shield_pulse=(shield_pulse+0.15)%(2*math.pi)
    shield_radius=int(50+math.sin(shield_pulse)*5)
    for i in range(3):
        s=pygame.Surface((shield_radius*2+i*10,shield_radius*2+i*10),pygame.SRCALPHA)
        pygame.draw.circle(s,(100,200,255,30-i*10),(shield_radius+i*5,shield_radius+i*5),shield_radius+i*5)
        surface.blit(s,(x+12-shield_radius-i*5,y-35-shield_radius-i*5))
    ss=pygame.Surface((shield_radius*2,shield_radius*2),pygame.SRCALPHA)
    pygame.draw.circle(ss,(150,220,255,100),(shield_radius,shield_radius),shield_radius)
    pygame.draw.circle(ss,(200,240,255,150),(shield_radius,shield_radius),shield_radius,3)
    surface.blit(ss,(x+12-shield_radius,y-35-shield_radius))

def draw_magnet_effect(surface,x,y):
    for i in range(3):
        radius=int(magnet_range-i*40+math.sin(pygame.time.get_ticks()*0.01+i)*10)
        if radius<5: continue
        s=pygame.Surface((radius*2,radius*2),pygame.SRCALPHA)
        pygame.draw.circle(s,(255,100,100,40-i*13),(radius,radius),radius,2)
        surface.blit(s,(x+12-radius,y-35-radius))

# ══════════════════════════════════════════════════════════════════════════════
#  HUD
# ══════════════════════════════════════════════════════════════════════════════
def draw_hud():
    """Extended HUD including level info and progress bar."""
    # ── main stats panel (top-left)
    hud=pygame.Rect(8,8,258,104)
    draw_neon_rect(win,NEON_BLUE,hud,radius=12,glow_width=2,glow_alpha=50,fill_alpha=25)
    win.blit(hud_font.render(f"⬡  SCORE  {score}",True,NEON_CYAN),(22,18))
    win.blit(hud_font.render(f"◈  COINS  {coins_collected}",True,NEON_GOLD),(22,44))
    dcol=difficulty_settings[difficulty]["color"]
    db=pygame.Rect(18,70,100,24)
    draw_neon_rect(win,dcol,db,radius=6,glow_width=1,glow_alpha=50,fill_alpha=20)
    win.blit(tiny_font.render(difficulty,True,dcol),(db.x+8,db.y+5))
    win.blit(tiny_font.render(f"SPD {stone_speed:.0f}",True,(180,200,255)),(135,77))

    # ── LEVEL BADGE (top-centre)
    env=get_environment()
    env_colors={"day":NEON_CYAN,"night":(100,130,255),"rain":(80,170,255),
                "fog":(180,190,200),"space":NEON_PURPLE}
    lv_col=env_colors.get(env,NEON_CYAN)
    env_icons={"day":"☀","night":"🌙","rain":"🌧","fog":"🌫","space":"🚀"}
    lv_panel=pygame.Rect(WIDTH//2-130,8,260,50)
    draw_neon_rect(win,lv_col,lv_panel,radius=10,glow_width=2,glow_alpha=70,fill_alpha=25)

    lv_str=f"{env_icons.get(env,'●')}  LEVEL {current_level}  —  {get_level_def(current_level)[5]}"
    lt=hud_font.render(lv_str,True,lv_col)
    win.blit(lt,(lv_panel.centerx-lt.get_width()//2,lv_panel.y+6))

    # ── progress bar toward next level
    if current_level<len(LEVEL_DEFINITIONS):
        curr_thresh=LEVEL_DEFINITIONS[current_level-1][0]
        next_thresh=LEVEL_DEFINITIONS[current_level][0]
        progress=max(0.0,min(1.0,(score-curr_thresh)/(next_thresh-curr_thresh)))
        bar_rect=pygame.Rect(WIDTH//2-130,lv_panel.bottom+4,260,10)
        pygame.draw.rect(win,(30,30,60),bar_rect,border_radius=5)
        fill_w=int(260*progress)
        if fill_w>0:
            pygame.draw.rect(win,lv_col,(bar_rect.x,bar_rect.y,fill_w,10),border_radius=5)
        pygame.draw.rect(win,lv_col,bar_rect,1,border_radius=5)
        pct=int(progress*100)
        pt=tiny_font.render(f"Next Level: {pct}%",True,lv_col)
        win.blit(pt,(bar_rect.x+2,bar_rect.bottom+2))
    else:
        max_t=tiny_font.render("MAX LEVEL",True,NEON_GOLD)
        win.blit(max_t,(lv_panel.centerx-max_t.get_width()//2,lv_panel.bottom+4))

    # ── power-up bars
    bar_y=118
    if jetpack_active:
        pygame.draw.rect(win,(30,30,60),(18,bar_y,160,14),border_radius=5)
        fw=int(160*jetpack_fuel/jetpack_max_fuel)
        fc=NEON_GREEN if jetpack_fuel>60 else (NEON_GOLD if jetpack_fuel>30 else NEON_RED)
        pygame.draw.rect(win,fc,(18,bar_y,fw,14),border_radius=5)
        pygame.draw.rect(win,fc,(18,bar_y,160,14),2,border_radius=5)
        win.blit(tiny_font.render(f"✈ FUEL {int(jetpack_fuel)}%",True,fc),(185,bar_y)); bar_y+=20
    if shield_active:
        tl=(shield_duration-shield_timer)//60
        pygame.draw.rect(win,(30,30,60),(18,bar_y,160,14),border_radius=5)
        fw=int(160*((shield_duration-shield_timer)/shield_duration))
        pygame.draw.rect(win,NEON_CYAN,(18,bar_y,fw,14),border_radius=5)
        pygame.draw.rect(win,NEON_CYAN,(18,bar_y,160,14),2,border_radius=5)
        win.blit(tiny_font.render(f"⬡ SHIELD {tl}s",True,NEON_CYAN),(185,bar_y)); bar_y+=20
    if magnet_active:
        tl=(magnet_duration-magnet_timer)//60
        pygame.draw.rect(win,(30,30,60),(18,bar_y,160,14),border_radius=5)
        fw=int(160*((magnet_duration-magnet_timer)/magnet_duration))
        pygame.draw.rect(win,NEON_RED,(18,bar_y,fw,14),border_radius=5)
        pygame.draw.rect(win,NEON_RED,(18,bar_y,160,14),2,border_radius=5)
        win.blit(tiny_font.render(f"⬤ MAGNET {tl}s",True,NEON_RED),(185,bar_y))

# ══════════════════════════════════════════════════════════════════════════════
#  CAMERA PANEL
# ══════════════════════════════════════════════════════════════════════════════
def draw_camera_panel(cam_surf,label_ready=True):
    cam_x,cam_y,cam_w,cam_h=648,312,228,168
    outer=pygame.Rect(cam_x-4,cam_y-26,cam_w+8,cam_h+30)
    draw_neon_rect(win,NEON_CYAN,outer,radius=10,glow_width=2,glow_alpha=60,fill_alpha=20)
    head_bg=pygame.Surface((outer.width,22),pygame.SRCALPHA)
    pygame.draw.rect(head_bg,(*NEON_CYAN,60),head_bg.get_rect(),border_radius=8)
    win.blit(head_bg,(outer.x,outer.y))
    win.blit(tiny_font.render("◉  CAMERA",True,NEON_CYAN),(outer.x+8,outer.y+4))
    rdy=tiny_font.render("● GESTURE READY" if label_ready else "● NO SIGNAL",
                          True,NEON_GREEN if label_ready else NEON_RED)
    win.blit(rdy,(outer.right-rdy.get_width()-8,outer.y+4))
    if cam_surf: win.blit(cam_surf,(cam_x,cam_y))
    else:
        ns=pygame.Surface((cam_w,cam_h),pygame.SRCALPHA); ns.fill((10,14,30,200))
        win.blit(ns,(cam_x,cam_y))
        nt=font.render("NO SIGNAL",True,(80,80,100))
        win.blit(nt,(cam_x+cam_w//2-nt.get_width()//2,cam_y+cam_h//2-nt.get_height()//2))

# ══════════════════════════════════════════════════════════════════════════════
#  DRAW GAME (main scene)
# ══════════════════════════════════════════════════════════════════════════════
def draw_game():
    global leg_animation, _game_tick, jetpack_particles, space_rock_timer

    _game_tick+=1

    # ── 1. Background
    draw_environment_background()

    # Night city silhouettes (must be after bg, before obstacles)
    draw_night_city_lights()

    # ── 2. Ground
    draw_environment_ground()

    # ── 3. Jetpack particles
    if jetpack_active:
        for _ in range(3): jetpack_particles.append(JetpackParticle(px+12,py-26))
    for jp in jetpack_particles[:]:
        jp.update(); jp.draw(win)
        if jp.life<=0: jetpack_particles.remove(jp)

    # ── 4. Shield / magnet effects
    if shield_active: draw_shield_effect(win,px,py)
    if magnet_active: draw_magnet_effect(win,px,py)

    # ── 5. Player
    if on_ground: leg_animation+=0.3
    draw_running_player(win,px,py,leg_animation)

    # Jetpack invincibility glow
    if jetpack_landing_invincibility:
        glow_pulse=abs(math.sin(jetpack_invincibility_timer*0.2))
        glow_radius=int(55+glow_pulse*10)
        for i in range(3):
            alpha=int((50-i*15)*glow_pulse)
            s=pygame.Surface((glow_radius*2+i*10,glow_radius*2+i*10),pygame.SRCALPHA)
            pygame.draw.circle(s,(255,215,0,alpha),(glow_radius+i*5,glow_radius+i*5),glow_radius+i*5)
            win.blit(s,(px+12-glow_radius-i*5,py-35-glow_radius-i*5))

    # ── 6. Coins / powerups / obstacles
    for coin in coins: coin.draw(win)
    for shield in shields: shield.draw(win)
    for magnet in magnets: magnet.draw(win)
    for jetpack in jetpacks: jetpack.draw(win)

    for s in stones:
        pygame.draw.rect(win,(60,60,60),s.move(3,3))
        pygame.draw.rect(win,(100,100,100),s)
        pygame.draw.rect(win,(140,140,140),(s.x,s.y,s.width-5,s.height-5))
        pygame.draw.rect(win,(0,0,0),s,2)

    env=get_environment()
    bird_color=(220,220,255) if env in ("night","space") else (0,0,0)
    bird_shadow=(150,150,180) if env in ("night","space") else (50,50,50)
    for b in birds:
        wing_flap=math.sin(score*0.2)*5
        pygame.draw.ellipse(win,bird_shadow,b.move(2,2))
        pygame.draw.ellipse(win,bird_color,b)
        pygame.draw.arc(win,bird_color,(b.x-10,b.y-5+wing_flap,20,15),0,3.14,3)
        pygame.draw.arc(win,bird_color,(b.x+b.width-10,b.y-5+wing_flap,20,15),0,3.14,3)

    # Space asteroids
    if env=="space":
        space_rock_timer+=1
        if space_rock_timer>90: spawn_space_rock(); space_rock_timer=0
        draw_space_rocks(win)

    # ── 7. Environment overlay (rain / fog on top of scene)
    draw_environment_overlay()

    # ── 8. HUD
    draw_hud()

# ══════════════════════════════════════════════════════════════════════════════
#  MENU
# ══════════════════════════════════════════════════════════════════════════════
def draw_menu():
    global _menu_tick
    _menu_tick+=1
    neon_star_bg(win,_stars,_menu_tick)
    # grid lines
    for i in range(0,WIDTH+40,80):
        off=(_menu_tick*0.4)%80; x_=(i-off)%(WIDTH+80)-40
        s=pygame.Surface((2,HEIGHT),pygame.SRCALPHA); s.fill((0,180,255,10)); win.blit(s,(x_,0))
    for j in range(0,HEIGHT+40,60):
        off=(_menu_tick*0.25)%60; y_=(j-off)%(HEIGHT+60)-30
        s=pygame.Surface((WIDTH,1),pygame.SRCALPHA); s.fill((0,180,255,8)); win.blit(s,(0,y_))
    draw_glow_text(win,"HUMAN RACING GAME",title_font,NEON_CYAN,(WIDTH//2,28),glow_color=NEON_BLUE,glow_radius=6,center=True)
    draw_glow_text(win,"— Level Edition —",small_font,(180,220,255),(WIDTH//2,90),glow_color=NEON_PURPLE,glow_radius=2,center=True)
    ip=pygame.Rect(WIDTH//2-180,108,360,30)
    draw_neon_rect(win,NEON_CYAN,ip,radius=8,glow_width=1,glow_alpha=40,fill_alpha=15)
    inst=small_font.render("☝ Jump  ✌ High Jump  ✋ Paper = Restart",True,(200,240,255))
    win.blit(inst,(ip.centerx-inst.get_width()//2,ip.y+7))
    dl=hud_font.render("SELECT DIFFICULTY",True,NEON_CYAN)
    win.blit(dl,(60,170)); pygame.draw.line(win,NEON_CYAN,(60,192),(302,192),1)
    pos=pygame.mouse.get_pos()
    for btn in [easy_btn,normal_btn,hard_btn]: btn.check_hover(pos); btn.draw(win)
    ll=hud_font.render("CHOOSE LEVEL",True,NEON_PURPLE)
    win.blit(ll,(338,150)); pygame.draw.line(win,NEON_PURPLE,(338,172),(860,172),1)
    for i,card in enumerate(level_cards): card.check_hover(pos); card.draw(win,selected_level_card==i)
    bar_bg=pygame.Surface((WIDTH,58),pygame.SRCALPHA); bar_bg.fill((5,8,20,220))
    win.blit(bar_bg,(0,HEIGHT-58)); pygame.draw.line(win,NEON_CYAN,(0,HEIGHT-58),(WIDTH,HEIGHT-58),1)
    shop_btn.check_hover(pos); shop_btn.draw(win)
    cust_btn.check_hover(pos); cust_btn.draw(win)
    cb=pygame.Rect(WIDTH-185,HEIGHT-52,170,40)
    draw_neon_rect(win,NEON_GOLD,cb,radius=10,glow_width=2,glow_alpha=50,fill_alpha=20)
    win.blit(hud_font.render(f"◈  {total_coins_ever}",True,NEON_GOLD),(cb.x+12,cb.y+10))
    if high_score>0:
        hb=pygame.Rect(415,HEIGHT-52,200,40)
        draw_neon_rect(win,NEON_PURPLE,hb,radius=10,glow_width=2,glow_alpha=40,fill_alpha=15)
        win.blit(hud_font.render(f"⬡ Best: {high_score}",True,(200,160,255)),(hb.x+12,hb.y+10))
    draw_scanline_overlay(win)

# ══════════════════════════════════════════════════════════════════════════════
#  GAME OVER
# ══════════════════════════════════════════════════════════════════════════════
def draw_game_over(cam):
    overlay=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA); overlay.fill((0,0,10,180)); win.blit(overlay,(0,0))
    draw_glow_text(win,"GAME OVER",title_font,NEON_RED,(WIDTH//2,80),glow_color=NEON_RED,glow_radius=8,center=True)
    panel=pygame.Rect(WIDTH//2-210,145,420,200)
    draw_neon_rect(win,NEON_BLUE,panel,radius=16,glow_width=2,glow_alpha=80,fill_alpha=30)
    win.blit(menu_font.render(f"SCORE  {score}",True,NEON_CYAN),
             (panel.centerx-menu_font.size(f"SCORE  {score}")[0]//2, panel.y+15))
    # Level reached
    lv_t=small_font.render(f"Reached Level {current_level}  —  {get_level_def(current_level)[5]}",True,NEON_PURPLE)
    win.blit(lv_t,(panel.centerx-lv_t.get_width()//2,panel.y+62))
    ct=font.render(f"◈  Coins: {coins_collected}",True,NEON_GOLD)
    win.blit(ct,(panel.centerx-ct.get_width()//2,panel.y+92))
    if score>high_score:
        nt=menu_font.render("✦  NEW HIGH SCORE!",True,NEON_GOLD)
        win.blit(nt,(panel.centerx-nt.get_width()//2,panel.y+128))
    else:
        ht=font.render(f"Best: {high_score}",True,(140,140,180))
        win.blit(ht,(panel.centerx-ht.get_width()//2,panel.y+140))
    pygame.draw.rect(win,NEON_BLUE,(panel.x+20,panel.y+168,panel.width-40,1))
    rt=small_font.render("✋ Show PAPER hand to restart",True,(180,200,255))
    win.blit(rt,(panel.centerx-rt.get_width()//2,panel.y+174))
    et=small_font.render("ESC  →  Main Menu",True,(130,140,180))
    win.blit(et,(panel.centerx-et.get_width()//2,panel.bottom+12))
    draw_scanline_overlay(win)

# ══════════════════════════════════════════════════════════════════════════════
#  SHOP / CUSTOMIZE (compact)
# ══════════════════════════════════════════════════════════════════════════════
def draw_shop():
    global _menu_tick; _menu_tick+=1
    neon_star_bg(win,_stars,_menu_tick)
    draw_glow_text(win,"SHOP",title_font,NEON_GOLD,(WIDTH//2,22),glow_color=NEON_GOLD,glow_radius=6,center=True)
    cb2=pygame.Rect(WIDTH//2-90,84,180,36)
    draw_neon_rect(win,NEON_GOLD,cb2,radius=10,glow_width=2,glow_alpha=60,fill_alpha=25)
    win.blit(hud_font.render(f"◈  {total_coins_ever}",True,NEON_GOLD),(cb2.centerx-hud_font.size(f"◈  {total_coins_ever}")[0]//2,cb2.y+8))
    y_pos=130; x_pos=28
    win.blit(hud_font.render("CHARACTERS",True,NEON_CYAN),(28,y_pos))
    pygame.draw.line(win,NEON_CYAN,(28,y_pos+22),(870,y_pos+22),1)
    y_pos+=32
    for name,data in character_skins.items():
        box=pygame.Rect(x_pos,y_pos,124,80)
        col=NEON_GREEN if (data["unlocked"] and name==current_skin) else (NEON_BLUE if data["unlocked"] else (60,60,90))
        draw_neon_rect(win,col,box,radius=8,glow_width=1,glow_alpha=40,fill_alpha=20)
        pc=get_rainbow_color(rainbow_offset) if name=="Rainbow" else data["color"]
        pygame.draw.circle(win,pc,(x_pos+32,y_pos+28),13)
        win.blit(tiny_font.render(name,True,(220,220,255)),(x_pos+8,y_pos+50))
        st=tiny_font.render("EQUIPPED" if name==current_skin else "OWNED",True,NEON_GREEN if name==current_skin else (180,180,200)) if data["unlocked"] else tiny_font.render(f"◈ {data['cost']}",True,NEON_GOLD)
        win.blit(st,(x_pos+8,y_pos+64))
        x_pos+=132
        if x_pos>780: x_pos=28; y_pos+=88
    y_pos+=100
    win.blit(hud_font.render("HATS",True,NEON_PURPLE),(28,y_pos))
    pygame.draw.line(win,NEON_PURPLE,(28,y_pos+22),(870,y_pos+22),1)
    y_pos+=32; x_pos=28
    for name,data in hats.items():
        box=pygame.Rect(x_pos,y_pos,124,68)
        col=NEON_GREEN if (data["unlocked"] and name==current_hat) else (NEON_PURPLE if data["unlocked"] else (60,60,90))
        draw_neon_rect(win,col,box,radius=8,glow_width=1,glow_alpha=40,fill_alpha=20)
        if name!="None": draw_hat(win,x_pos+18,y_pos+40,name)
        win.blit(tiny_font.render(name,True,(220,220,255)),(x_pos+8,y_pos+46))
        st=tiny_font.render("EQUIPPED" if name==current_hat else "OWNED",True,NEON_GREEN if name==current_hat else (180,180,200)) if data["unlocked"] else tiny_font.render(f"◈ {data['cost']}",True,NEON_GOLD)
        win.blit(st,(x_pos+8,y_pos+57))
        x_pos+=132
        if x_pos>780: x_pos=28; y_pos+=76
    bk=small_font.render("ESC  →  Back",True,(140,160,200))
    win.blit(bk,(WIDTH//2-bk.get_width()//2,HEIGHT-28))
    draw_scanline_overlay(win)

def draw_customize():
    global _menu_tick; _menu_tick+=1
    neon_star_bg(win,_stars,_menu_tick)
    draw_glow_text(win,"CUSTOMIZE",title_font,NEON_PURPLE,(WIDTH//2,22),glow_color=NEON_PURPLE,glow_radius=6,center=True)
    y_pos=110; x_pos=28
    win.blit(hud_font.render("COLOR THEMES",True,NEON_CYAN),(28,y_pos))
    pygame.draw.line(win,NEON_CYAN,(28,y_pos+22),(870,y_pos+22),1)
    y_pos+=32
    for name,data in color_themes.items():
        box=pygame.Rect(x_pos,y_pos,158,90)
        col=NEON_CYAN if name==current_theme else ((60,80,120) if data["unlocked"] else (50,50,70))
        draw_neon_rect(win,col,box,radius=10,glow_width=2 if name==current_theme else 1,glow_alpha=60,fill_alpha=20)
        pygame.draw.rect(win,data["sky"],(x_pos+10,y_pos+10,138,28),border_radius=4)
        pygame.draw.rect(win,data["ground"],(x_pos+10,y_pos+42,138,16),border_radius=4)
        win.blit(small_font.render(name,True,(220,230,255)),(x_pos+12,y_pos+64))
        st=tiny_font.render("ACTIVE" if name==current_theme else "OWNED",True,NEON_GREEN if name==current_theme else (160,180,200)) if data["unlocked"] else tiny_font.render(f"◈ {data['cost']}",True,NEON_GOLD)
        win.blit(st,(x_pos+100,y_pos+66))
        x_pos+=166
        if x_pos>780: x_pos=28; y_pos+=100
    y_pos+=110
    win.blit(hud_font.render("PREVIEW",True,NEON_CYAN),(WIDTH//2-hud_font.size("PREVIEW")[0]//2,y_pos-28))
    pr=pygame.Rect(WIDTH//2-145,y_pos,290,140)
    pygame.draw.rect(win,color_themes[current_theme]["sky"],pr,border_radius=10)
    pygame.draw.rect(win,color_themes[current_theme]["ground"],(WIDTH//2-145,y_pos+92,290,48),border_radius=10)
    draw_neon_rect(win,NEON_CYAN,pr,radius=10,glow_width=2,glow_alpha=60,fill=False)
    draw_running_player(win,WIDTH//2-12,y_pos+90,0)
    win.blit(small_font.render("ESC  →  Back",True,(140,160,200)),(WIDTH//2-small_font.size("ESC  →  Back")[0]//2,HEIGHT-28))
    draw_scanline_overlay(win)

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════
run=True; jump_cooldown=0

while run:
    clock.tick(60)

    for e in pygame.event.get():
        if e.type==pygame.QUIT: run=False
        if e.type==pygame.KEYDOWN:
            if e.key==pygame.K_ESCAPE:
                if game_state in [GAME_OVER,SHOP,CUSTOMIZE]: game_state=MENU
        if e.type==pygame.MOUSEBUTTONDOWN:
            pos=pygame.mouse.get_pos()
            if game_state==MENU:
                if easy_btn.is_clicked(pos):   difficulty="EASY";   reset_game()
                elif normal_btn.is_clicked(pos): difficulty="NORMAL"; reset_game()
                elif hard_btn.is_clicked(pos):  difficulty="HARD";   reset_game()
                elif shop_btn.is_clicked(pos):  game_state=SHOP
                elif cust_btn.is_clicked(pos):  game_state=CUSTOMIZE
                for i,card in enumerate(level_cards):
                    if card.is_clicked(pos) and not card.data["locked"]:
                        selected_level_card=i
            elif game_state==SHOP:
                y_pos=162; x_pos=28
                for name,data in character_skins.items():
                    if pygame.Rect(x_pos,y_pos,124,80).collidepoint(pos):
                        if not data["unlocked"] and total_coins_ever>=data["cost"]:
                            total_coins_ever-=data["cost"]; data["unlocked"]=True
                        if data["unlocked"]: current_skin=name
                    x_pos+=132
                    if x_pos>780: x_pos=28; y_pos+=88
                y_pos+=135; x_pos=28
                for name,data in hats.items():
                    if pygame.Rect(x_pos,y_pos,124,68).collidepoint(pos):
                        if not data["unlocked"] and total_coins_ever>=data["cost"]:
                            total_coins_ever-=data["cost"]; data["unlocked"]=True
                        if data["unlocked"]: current_hat=name
                    x_pos+=132
                    if x_pos>780: x_pos=28; y_pos+=76
            elif game_state==CUSTOMIZE:
                y_pos=142; x_pos=28
                for name,data in color_themes.items():
                    if pygame.Rect(x_pos,y_pos,158,90).collidepoint(pos):
                        if not data["unlocked"] and total_coins_ever>=data["cost"]:
                            total_coins_ever-=data["cost"]; data["unlocked"]=True
                        if data["unlocked"]: current_theme=name
                    x_pos+=166
                    if x_pos>780: x_pos=28; y_pos+=100

    jump_type,restart,cam=detect_hand_gesture()

    # ── MENU ──────────────────────────────────────────────────────────────────
    if game_state==MENU:
        draw_menu()
        if cam: draw_camera_panel(cam,label_ready=True)

    elif game_state==SHOP:     draw_shop()
    elif game_state==CUSTOMIZE: draw_customize()

    # ── PLAYING + LEVEL_COMPLETE (game continues behind popup) ────────────────
    elif game_state in (PLAYING, LEVEL_COMPLETE):

        # Don't update physics during popup
        if game_state==PLAYING:
            if shield_active:
                shield_timer+=1
                if shield_timer>=shield_duration: shield_active=False; shield_timer=0
            if jetpack_active:
                jetpack_fuel-=0.5; jetpack_was_active=True
                if jetpack_fuel<=0: jetpack_active=False; jetpack_fuel=0
                else: vel+=jetpack_thrust; vel=max(vel,-8); on_ground=False
            if jetpack_landing_invincibility:
                jetpack_invincibility_timer+=1
                if jetpack_invincibility_timer>=jetpack_invincibility_duration:
                    jetpack_landing_invincibility=False; jetpack_invincibility_timer=0
            if magnet_active:
                magnet_timer+=1
                if magnet_timer>=magnet_duration: magnet_active=False; magnet_timer=0
            if jump_cooldown>0: jump_cooldown-=1
            if jump_type and on_ground and jump_cooldown==0 and not jetpack_active:
                if jump_type=="normal": vel=jump_power; on_ground=False; jump_cooldown=15
                elif jump_type=="high":
                    vel=high_jump_power; on_ground=False; jump_cooldown=15
                    for _ in range(15): particle_systems.append(Particle(px,py,(100,200,255)))
            if not jetpack_active: vel+=gravity
            py+=vel
            if py<max_player_height: py=max_player_height; vel=max(0,vel)
            if py>=ground: py=ground; vel=0; on_ground=True
            timer+=1
            if timer>spawn_rate: stones.append(pygame.Rect(WIDTH,ground-5,35,35)); timer=0
            bird_timer+=bird_freq
            if bird_timer>random.randint(150,250): birds.append(pygame.Rect(WIDTH,random.randint(150,260),40,25)); bird_timer=0
            coin_timer+=1
            if coin_timer>random.randint(60,120): coins.append(Coin(WIDTH,random.randint(ground-100,ground-30))); coin_timer=0
            powerup_timer+=1
            if powerup_timer>random.randint(400,600):
                if random.random()<0.5: shields.append(Shield(WIDTH,random.randint(ground-80,ground-20)))
                else: magnets.append(Magnet(WIDTH,random.randint(ground-80,ground-20)))
                powerup_timer=0
            jetpack_spawn_timer+=1
            if jetpack_spawn_timer>random.randint(500,800):
                jetpacks.append(Jetpack(WIDTH,random.randint(ground-100,ground-30))); jetpack_spawn_timer=0
            player=pygame.Rect(px-5,py-65,40,70)
            for coin in coins[:]:
                coin.update(stone_speed)
                if magnet_active:
                    dx=(px+12)-(coin.x+12); dy=(py-35)-(coin.y+12)
                    distance=math.sqrt(dx**2+dy**2)
                    if distance<magnet_range: coin.x+=dx*0.15; coin.y+=dy*0.15; coin.rect.x=coin.x; coin.rect.y=coin.y
                if player.colliderect(coin.rect):
                    coins_collected+=1; total_coins_ever+=1; coins.remove(coin)
                    for _ in range(10): particle_systems.append(Particle(coin.x,coin.y,(255,215,0)))
                elif coin.x<-50: coins.remove(coin)
            for shield in shields[:]:
                shield.update(stone_speed)
                if player.colliderect(shield.rect):
                    shield_active=True; shield_timer=0; shields.remove(shield)
                    for _ in range(15): particle_systems.append(Particle(shield.x,shield.y,(100,200,255)))
                elif shield.x<-50: shields.remove(shield)
            for magnet in magnets[:]:
                magnet.update(stone_speed)
                if player.colliderect(magnet.rect):
                    magnet_active=True; magnet_timer=0; magnets.remove(magnet)
                    for _ in range(15): particle_systems.append(Particle(magnet.x,magnet.y,(255,100,100)))
                elif magnet.x<-50: magnets.remove(magnet)
            for jetpack in jetpacks[:]:
                jetpack.update(stone_speed)
                if player.colliderect(jetpack.rect):
                    jetpack_active=True; jetpack_fuel=jetpack_max_fuel; jetpack_timer=0; jetpacks.remove(jetpack)
                    for _ in range(20): particle_systems.append(Particle(jetpack.x,jetpack.y,(255,150,0)))
                elif jetpack.x<-50: jetpacks.remove(jetpack)
            for s in stones:
                s.x-=stone_speed
                if player.colliderect(s) and not shield_active and not jetpack_landing_invincibility:
                    game_state=GAME_OVER
                    if score>high_score: high_score=score
                    for _ in range(20): particle_systems.append(Particle(s.x,s.y,(255,100,100)))
            for b in birds:
                b.x-=stone_speed+1.5
                if player.colliderect(b) and not shield_active and not jetpack_landing_invincibility:
                    game_state=GAME_OVER
                    if score>high_score: high_score=score
                    for _ in range(20): particle_systems.append(Particle(b.x,b.y,(255,100,100)))
            stones=[s for s in stones if s.x>-50]
            birds=[b for b in birds if b.x>-50]
            score+=1

        # Always draw game scene
        draw_game()
        for p in particle_systems[:]:
            p.update(); p.draw(win)
            if p.life<=0: particle_systems.remove(p)

        # Level check & popup
        update_level_progression()
        if game_state==LEVEL_COMPLETE:
            draw_level_complete_popup()

        if cam: draw_camera_panel(cam,label_ready=True)
        draw_scanline_overlay(win)

    # ── GAME OVER ─────────────────────────────────────────────────────────────
    elif game_state==GAME_OVER:
        draw_game()
        for p in particle_systems[:]:
            p.update(); p.draw(win)
            if p.life<=0: particle_systems.remove(p)
        draw_game_over(cam)
        if cam: draw_camera_panel(cam,label_ready=True)
        if restart: reset_game()

    pygame.display.update()

pygame.quit()
cap.release()
cv2.destroyAllWindows()