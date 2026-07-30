"""Python port of `2D_lensing.cpp` using Tkinter for visualization."""

from __future__ import annotations

import argparse
import math
import tkinter as tk

from common import BlackHole, Vec3


class Ray2D:
    def __init__(self, position: tuple[float, float], direction: tuple[float, float], black_hole: BlackHole) -> None:
        self.x = float(position[0])
        self.y = float(position[1])
        self.r = math.hypot(self.x, self.y)
        self.phi = math.atan2(self.y, self.x)

        dx, dy = direction
        self.dr = dx * math.cos(self.phi) + dy * math.sin(self.phi)
        self.dphi = (-dx * math.sin(self.phi) + dy * math.cos(self.phi)) / max(self.r, 1e-9)

        factor = 1.0 - black_hole.schwarzschild_radius / max(self.r, black_hole.schwarzschild_radius * 1.001)
        dt_dlambda = math.sqrt((self.dr * self.dr) / (factor * factor) + (self.r * self.r * self.dphi * self.dphi) / factor)
        self.energy = factor * dt_dlambda
        self.trail = [(self.x, self.y)]

    def step(self, delta_lambda: float, schwarzschild_radius: float) -> None:
        if self.r <= schwarzschild_radius:
            return

        state = [self.r, self.phi, self.dr, self.dphi]
        k1 = geodesic_rhs(self, schwarzschild_radius)
        k2 = geodesic_rhs(state_to_ray(self, add_state(state, k1, delta_lambda / 2.0)), schwarzschild_radius)
        k3 = geodesic_rhs(state_to_ray(self, add_state(state, k2, delta_lambda / 2.0)), schwarzschild_radius)
        k4 = geodesic_rhs(state_to_ray(self, add_state(state, k3, delta_lambda)), schwarzschild_radius)

        increments = [
            (delta_lambda / 6.0) * (a + 2 * b + 2 * c + d)
            for a, b, c, d in zip(k1, k2, k3, k4)
        ]
        self.r += increments[0]
        self.phi += increments[1]
        self.dr += increments[2]
        self.dphi += increments[3]
        self.x = self.r * math.cos(self.phi)
        self.y = self.r * math.sin(self.phi)
        self.trail.append((self.x, self.y))


def geodesic_rhs(ray: Ray2D, schwarzschild_radius: float) -> list[float]:
    radius = max(ray.r, schwarzschild_radius * 1.0001)
    factor = 1.0 - schwarzschild_radius / radius
    dt_dlambda = ray.energy / factor

    return [
        ray.dr,
        ray.dphi,
        -((schwarzschild_radius / (2 * radius * radius)) * factor * dt_dlambda * dt_dlambda)
        + ((schwarzschild_radius / (2 * radius * radius * factor)) * ray.dr * ray.dr)
        + (radius - schwarzschild_radius) * ray.dphi * ray.dphi,
        -2.0 * ray.dr * ray.dphi / radius,
    ]


def add_state(values: list[float], derivatives: list[float], factor: float) -> list[float]:
    return [value + derivative * factor for value, derivative in zip(values, derivatives)]


def state_to_ray(template: Ray2D, values: list[float]) -> Ray2D:
    copy = Ray2D((template.x, template.y), (1.0, 0.0), BlackHole(Vec3(), 8.54e36))
    copy.energy = template.energy
    copy.r, copy.phi, copy.dr, copy.dphi = values
    copy.trail = template.trail
    return copy


class LensingApp:
    def __init__(self, width: int, height: int, ray_count: int, steps_per_frame: int) -> None:
        self.width = width
        self.height = height
        self.steps_per_frame = steps_per_frame
        self.scale = width / 2.4e11
        self.black_hole = BlackHole(Vec3(), 8.54e36)

        self.root = tk.Tk()
        self.root.title("2D Black Hole Lensing")
        self.canvas = tk.Canvas(self.root, width=width, height=height, bg="black")
        self.canvas.pack()

        start_y = [(-3.0e10 + i * (6.0e10 / max(ray_count - 1, 1))) for i in range(ray_count)]
        self.rays = [Ray2D(position=(-1.2e11, y), direction=(3.0e8, 0.0), black_hole=self.black_hole) for y in start_y]

    def world_to_screen(self, x: float, y: float) -> tuple[float, float]:
        return self.width / 2 + x * self.scale, self.height / 2 - y * self.scale

    def draw(self) -> None:
        self.canvas.delete("all")

        radius = self.black_hole.schwarzschild_radius * self.scale
        cx, cy = self.world_to_screen(0.0, 0.0)
        self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill="red", outline="")

        for ray in self.rays:
            for _ in range(self.steps_per_frame):
                ray.step(1.0, self.black_hole.schwarzschild_radius)

            if len(ray.trail) > 1:
                flattened = [coord for point in ray.trail[-200:] for coord in self.world_to_screen(*point)]
                self.canvas.create_line(*flattened, fill="white")

        self.root.after(16, self.draw)

    def run(self) -> None:
        self.draw()
        self.root.mainloop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize 2D lensing in the Python port.")
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--rays", type=int, default=12)
    parser.add_argument("--steps-per-frame", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.width <= 0 or args.height <= 0 or args.rays <= 0 or args.steps_per_frame <= 0:
        raise ValueError("All CLI values must be positive integers.")

    app = LensingApp(args.width, args.height, args.rays, args.steps_per_frame)
    app.run()


if __name__ == "__main__":
    main()
