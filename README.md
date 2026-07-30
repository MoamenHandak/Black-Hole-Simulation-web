# 🌌 3D Black Hole Raytracer & Gravity Simulator (Web & Python)

An interactive, GPU-accelerated **3D Schwarzschild Black Hole Raytracer and N-Body Gravity Simulator** built for modern web browsers (WebGL2 / HTML5 / ES Modules) and Python/OpenGL.

![Event Horizon 3D Banner](https://img.shields.io/badge/WebGL2-Realtime--Raytracing-ffaa32?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

---

## 🚀 Web Application Version

The Web version runs in any modern web browser with zero installation.

### Features
- **GPU Schwarzschild Light Raytracing**: Real-time gravitational deflection of light ($R_s = 2GM/c^2$), event horizon shadow ($R_{shadow} \approx 2.65 R_s$), and glowing photon sphere.
- **Accretion Disk with Relativistic Doppler Shift**: Relativistic beaming effect (approaching material is brighter & blueshifted; receding material is dimmed & redshifted) with custom color palettes (*Gargantua Gold*, *Cyber Cyan*, *Plasma Violet*, *Inferno Red*).
- **Gravitational Lensing**: Real-time warping of background starfields, procedural nebulae, and orbiting celestial planets.
- **3D Spacetime Grid Overlay**: View deformed spacetime geometry around the central mass.
- **N-Body Gravity Engine**: Real-time Newtonian orbital physics for celestial bodies surrounding the black hole.
- **Web Audio API Synth**: Procedural sub-bass cosmic drone detuned dynamically by black hole mass.
- **Photo Mode**: High-resolution PNG screenshot exporter.

### How to Run Locally
Simply open `index.html` in any web browser, or serve it using Python:
```bash
python -m http.server 8080
```
Then navigate to `http://localhost:8080/`.

---

## 🐍 Python Version

The repository also includes standalone Python/PyOpenGL ports:
- `black_hole_demo.py`: Interactive `pygame` + `PyOpenGL` 3D raytracer window.
- `cpu_geodesic.py`: Schwarzschild light geodesic step integrator.
- `lensing_2d.py`: 2D gravitational lensing simulator.
- `ray_tracing.py`: Raytracing experiment renderer.

### How to Run Python Scripts
```bash
python -m pip install pygame PyOpenGL
python black_hole_demo.py --width 1280 --height 720
```
