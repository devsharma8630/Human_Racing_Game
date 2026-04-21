# 🏃 Human Racing Game

A **hand-gesture controlled endless runner** built entirely in Python using Pygame and MediaPipe. No keyboard needed — your webcam reads your hand gestures in real time to control the character.

## 🎮 Gameplay Preview

> Run endlessly, dodge obstacles, collect coins, grab power-ups — all using your hand!

| Gesture | Action |
| 1 Finger (index up) | Normal Jump |
| 2 Fingers (index + middle up) | High Jump |
| Open Palm (all fingers up) | Restart Game |

---

## 🌍 Level Progression System

The game features **5 unique environments** that unlock automatically as your score increases:
Modes---
| 1 |  ☀️ Day | City Streets — Morning Run |
| 2 | 🌙 Night | Night City — Watch Your Step |
| 3 | 🌧️ Rain | Rainy Roads — Slippery Ground |
| 4 | 🌫️ Fog | Foggy Dawn — Low Visibility |
| 5 | 🚀 Space | Space Colony — Zero Gravity |

Each level increases obstacle speed, spawn rate, and introduces unique visual effects.

---

## ✨ Features

-  **Real-time hand gesture control** via webcam (MediaPipe)
-  **5 dynamic environments** — Day, Night, Rain, Fog, Space
-  **Level completion popup** with animated celebration particles
-  **Rain system** — animated drops + ground splash ripples
-  **Fog system** — layered parallax drifting fog banks
-  **Space level** — parallax starfield, nebula, floating asteroids
-  **Night mode** — city silhouettes with lit building windows
-  **Power-ups** — Shield, Magnet, Jetpack
-  **Coin economy** — collect coins, unlock characters and hats in the Shop
-  **11 character skins** — Classic, Robot, Astronaut, Rainbow and more
-  **12 hats** — Crown, Wizard Hat, Viking Helmet, Santa Hat and more
-  **Futuristic neon UI** — glassmorphism panels, neon glow, CRT scanlines
-  **HUD with level progress bar** — see exactly how close the next level is
-  **High score tracking**
-  **difficulty modes** — Easy, Normal, Hard

---

## 🛠️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/human-racing-game.git
cd human-racing-game
```

### 2. Install dependencies

```bash
pip install pygame opencv-python mediapipe numpy
```

> ⚠️ Python **3.8 – 3.11** is recommended. MediaPipe may have issues on Python 3.12+.

### 3. Run the game

```bash
python human_racing_game_levels.py
```

---
