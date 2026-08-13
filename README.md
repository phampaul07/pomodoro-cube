# Smart Pomodoro Cube

<p align="center">
  <img src="images/hero.gif" width="500">
</p>

<h3 align="center">
A fully custom embedded productivity cube featuring a Pomodoro timer, digital clock, virtual pet, productivity tracker, and magnetic charging dock.
</h3>

<p align="center">
CircuitPython • ESP32-C3 • Embedded Systems • CAD • 3D Printing • Analog Electronics • KiCad
</p>

---

# README Contents
- [Overview](#overview)
- [Demonstrations](#demonstrations)
- [Features](#features)
- [Hardware](#hardware)
- [Getting Started](#getting-started)
- [Mechanical Design](#mechanical-design)
- [Engineering Deep Dive](#engineering-deep-dive)
- [Software Highlights](#software-highlights)
- [Challenges](#challenges)
- [Lessons Learned](#lessons-learned)
- [Future Improvements](#future-improvements)
- [Gallery](#gallery)
- [Acknowledgements](#acknowledgements)
- [Contact](#contact)

---

# Overview

The Smart Pomodoro Cube is a handheld productivity device that combines embedded systems, hardware engineering, and industrial design into a compact form factor no larger than a standard Rubik's Cube.

Instead of navigating through menus or using a touchscreen, the cube uses its physical orientation to select timer durations. Once docked onto its custom magnetic charging station, it transforms into an entirely different interface featuring an interactive virtual pet, productivity tracker, and quick-access study tools.

Every major component—including the enclosure, charging dock, firmware, custom KiCad PCB, and user interface—was designed specifically for this project.

The goal was not only to create a useful studying companion, but also to explore embedded systems, custom electronics, CAD, and hardware-software integration while fitting everything inside an extremely limited volume.

---

# Demonstrations

The Pomodoro Cube has two primary modes of operation.

---

## Standalone Cube

<p align="center">
<a href="https://youtube.com/shorts/b-1S72bGzG8?feature=share">
<img src="https://img.youtube.com/vi/b-1S72bGzG8/maxresdefault.jpg" width="700">
</a>
</p>

<p align="center">
<b>Click the thumbnail above to watch the standalone demonstration.</b>
</p>

### Demonstrated Features

- Real-time clock
- Battery percentage
- Temperature monitoring
- Cube orientation timer selection
- Pause / Resume
- Timer reset
- Countdown progress bar
- Portable battery operation

---

## Interactive Charging Dock

<p align="center">
<a href="https://youtube.com/shorts/HYNcFR9NDS4?feature=share">
<img src="https://img.youtube.com/vi/HYNcFR9NDS4/maxresdefault.jpg" width="700">
</a>
</p>

<p align="center">
<b>Click the thumbnail above to watch the dock demonstration.</b>
</p>

### Demonstrated Features

- Magnetic docking
- Automatic dock detection
- Charging indicator
- Clock Mode
- 15-minute Quick Timer
- Interactive Tamagotchi Pet
- Petting animation
- Productivity Stats

---

# Features

## Digital Clock

When idle, the cube functions as a portable desk clock displaying:

- Current time
- Battery percentage
- Temperature
- Charging status

using an external RTC module and onboard sensors.

---

## Pomodoro Timer

The cube's primary function is a distraction-free Pomodoro timer.

Simply rotate the cube onto one of its faces to instantly choose a timer duration.

Features include:

- Multiple timer durations
- Pause / Resume
- Reset
- Bar progress visualization
- Completion notification via beeps
- Battery-powered portability

---

## Magnetic Charging Dock

One of the biggest design goals was eliminating cables during normal use.

The cube charges magnetically using pogo pins while simultaneously detecting dock states and reading dock button presses. 

The charging dock was hand-built using a custom perfboard and soldered circuitry, while the internal electronics of the cube itself are mounted on a custom-designed PCB routed in KiCad.

---

## Dock Modes

Docking the cube unlocks four additional operating modes.

### Clock

Displays the standard clock while charging.

---

### Quick Timer

Instantly adds study time in 15-minute increments without rotating the cube.

---

### Tamagotchi

An interactive Tamagotchi-inspired virtual pet.

Features include:

- Idle animations
- Random blinking
- Petting animation
- Smooth sprite animation
- Physical interaction using dock buttons

---

### Productivity Statistics

Tracks long-term study habits including:

- Daily focus time
- Focus sessions
- Daily streak
- Lifetime sessions

---

# Hardware

| Component | Purpose |
|------------|---------|
| Seeed Studio XIAO ESP32-C3 | Main Microcontroller |
| Custom KiCad PCB | Main Board / Cube Electronics |
| 1.28" Round GC9A01 IPS Display | User Interface |
| MPU6050 | Orientation Detection |
| RTC Module | Timekeeping |
| 3.7V LiPo Battery | Portable Power |
| Magnetic Pogo Pins | Charging & Communication |
| Custom Perfboard | Dock Electronics |

---

# Getting Started

This runs on CircuitPython rather than compiled firmware, so there's no build/flash toolchain — the board mounts as a USB drive and files are copied directly onto it.

1. Flash the [CircuitPython UF2](https://circuitpython.org/board/seeed_xiao_esp32c3/) for the Seeed Studio XIAO ESP32-C3 (hold BOOT while plugging in, drag the `.uf2` onto the `ESP32C3` drive).
2. Once it reboots into CircuitPython, it'll appear as a `CIRCUITPY` drive. Copy the entire `firmware/` folder's contents onto it: `code.py`, `animation.py`, `dock.py`, the `.bmp` sprite assets, and the `lib/` folder of vendored Adafruit libraries.
3. `code.py` is the entry point — CircuitPython auto-runs it on boot. `firmware/legacy/standalone_cube.py` is an earlier, dock-less iteration kept for reference only; it isn't used.
4. The board reloads automatically any time `code.py` is saved. [Thonny](https://thonny.org/) (or any serial-capable editor) works well for live editing and viewing the serial console.

---

# Mechanical Design

A major objective of this project was fitting an entire embedded system inside the volume of a standard Rubik's Cube.

This required careful consideration of:

- Internal component placement
- Custom PCB dimensions and mounting
- Cable routing
- Battery placement
- Display clearance
- Magnet positioning
- Dock alignment

---

# Engineering Deep Dive

## Analog Button Multiplexing

Because the magnetic pogo pin interface between the cube and the dock only has four physical connections (5V, GND, 3.3V, and a single data line), it was physically impossible to dedicate separate GPIO pins for each of the four dock buttons.

To overcome this hardware constraint, every dock interaction is transmitted through the single available analog pin using a resistor ladder. Each button routes current through a different resistor, producing a unique voltage.

The ESP32 reads this incoming voltage through its ADC and determines which button was pressed based on predefined threshold ranges.

```
Button 1 → Home Clock
Button 2 → Quick Timer
Button 3 → Tomo
Button 4 → Productivity Stats
```

---

## Battery Monitoring

A fully charged LiPo battery outputs approximately 4.2V, exceeding the ESP32's safe analog input voltage.

To safely monitor the battery, a voltage divider using two identical 10kΩ resistors cuts the voltage in half before it reaches the ADC.

Hardware Flow:
```
Battery
↓
Voltage Divider
↓
ESP32 ADC
```

Software Logic:
```
ADC Reading
↓
Measured Voltage
↓
×2
↓
Actual Battery Voltage
↓
Battery Percentage
```

This approach allows safe and accurate battery monitoring without risking damage to the microcontroller.

<img width="246" height="199" alt="2021031915491336" src="https://github.com/user-attachments/assets/c6e70b51-e8f2-4de6-a553-96331f9b9741" />

---

## Firmware Architecture

The firmware is built around a finite state machine.

```
Standalone
 └── Clock
      │
      ▼
    Timer

Docked
 └── Clock
      ├── Quick Timer
      ├── Tomo
      └── Productivity Stats
```

Separating functionality into individual states simplified transitions, animations, and memory management.

---

# Software Highlights

- CircuitPython firmware
- SPI-driven GC9A01 display
- TileGrid sprite animations
- Memory-efficient bitmap loading
- Real-time battery monitoring
- Dock state detection
- ADC signal filtering
- Finite State Machine architecture

---

# Challenges

This project introduced me to several engineering disciplines simultaneously.

## Mechanical

- First complete CAD enclosure
- Designing around extremely limited internal space
- Dock alignment tolerances

---

## Electrical

- Designing a custom PCB in KiCad for the cube's internal layout
- Designing analog resistor ladder circuits
- Designing a voltage divider
- Magnetic pogo-pin charging
- Battery management
- Dock signal integrity

---

## Embedded Software

- Memory optimization
- Bitmap management
- Animation timing
- Display flickering
- ADC calibration
- State machine architecture

---

## Debugging

Some of the most time-consuming issues included:

- ESP32 memory limitations
- Magnetic charging reliability
- Analog threshold calibration
- Battery percentage accuracy
- Dock signal filtering
- Sprite memory fragmentation

Many of these required custom diagnostic firmware, multimeter testing, and extensive trial-and-error before arriving at stable solutions.

---

# Lessons Learned

This project taught me far more than simply building a productivity timer.

Some of the biggest skills I developed include:

- Embedded Systems
- CircuitPython
- Analog Circuit Design
- PCB Design (KiCad)
- Hardware Debugging
- CAD
- 3D Printing
- Battery Management
- SPI Displays
- Embedded UI Design
- Firmware Optimization
- State Machine Architecture

---

# Future Improvements

Although the current prototype is fully functional, there are several improvements I would like to explore.

- Custom PCB for the charging dock to replace the perfboard prototype
- Improved magnetic charging reliability
- Lower-power sleep mode
- Configurable timer durations
- Improved charging dock alignment
- Historical productivity graphs
- Rotating screen animation to make the interface fixed

---

# Gallery

| Cube | Dock |
|------|------|
| <img width="2217" height="2295" alt="IMG_2750" src="https://github.com/user-attachments/assets/47c5d93c-9311-4f70-925c-c8ca01058350" />| <img width="3024" height="4032" alt="IMG_2749" src="https://github.com/user-attachments/assets/2d7062d3-feac-4b3a-922d-83b6af8a94fb" /> |

| Real-Time Clock | Iterated Timer |
|------|------|
|<img width="4032" height="3024" alt="IMG_2753" src="https://github.com/user-attachments/assets/7f6579c9-9c8a-4ac8-bc8b-8f16c355ab3e" /> | <img width="4032" height="3024" alt="IMG_2754" src="https://github.com/user-attachments/assets/7ebef5c4-1801-4718-a616-3413b40726a2" /> |


| Tamagotchi | Stats |
|------|------|
|<img width="3024" height="4032" alt="IMG_2757" src="https://github.com/user-attachments/assets/083e92cf-9342-4e21-a807-ed936aab5156" /> |<img width="3024" height="4032" alt="IMG_2756" src="https://github.com/user-attachments/assets/bf3a9c01-6fa3-46c4-bbdb-243c60f5bd75" /> |

| PCB | Wiring |
|------|------|
| <img width="1911" height="2139" alt="front_pcb" src="https://github.com/user-attachments/assets/8b14f7b8-9f3f-4de5-b548-ce51dcfeb479" /> | <img width="3024" height="4032" alt="components" src="https://github.com/user-attachments/assets/bb55650d-d55b-4280-af41-0574d795a18d" />|

---

# Acknowledgements

This project was independently designed and built using CircuitPython on the Seeed Studio XIAO ESP32-C3.

It combines concepts from embedded systems, analog electronics, firmware development, mechanical design, PCB design, and human-centered interaction into a single portable productivity device.

---

# Contact

- **Paul Pham** — [phampp07@gmail.com](mailto:phampp07@gmail.com) • [linkedin.com/in/paul-pham07](https://www.linkedin.com/in/paul-pham07)

---

## If you enjoyed this project, consider leaving a star!
