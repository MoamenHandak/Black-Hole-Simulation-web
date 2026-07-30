"""Python port of `CPU-geodesic.cpp`.

This version renders a CPU image of a black hole using either a fast sphere
intersection or a slower Schwarzschild geodesic march.
"""

from __future__ import annotations

import argparse
import math

from common import BlackHole, Vec3, clamp, write_ppm


class Camera:
    def __init__(
        self,
        position: Vec3 | None = None,
        target: Vec3 | None = None,
        fov_y: float = 60.0,
    ) -> None:
        self.position = position or Vec3(6.34194e10, 0.0, 0.0)
        self.target = target or Vec3()
        self.fov_y = float(fov_y)

    def basis(self) -> tuple[Vec3, Vec3, Vec3]:
        forward = (self.target - self.position).normalized()
        right = forward.cross(Vec3(0.0, 1.0, 0.0)).normalized()
        up = right.cross(forward).normalized()
        return forward, right, up


class Ray3D:
    def __init__(self, position: Vec3, direction: Vec3, black_hole: BlackHole) -> None:
        self.x = position.x
        self.y = position.y
        self.z = position.z

        self.r = math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)
        self.theta = math.acos(self.z / max(self.r, 1e-9))
        self.phi = math.atan2(self.y, self.x)

        dx, dy, dz = direction.normalized().as_tuple()
        self.dr = math.sin(self.theta) * math.cos(self.phi) * dx
        self.dr += math.sin(self.theta) * math.sin(self.phi) * dy
        self.dr += math.cos(self.theta) * dz

        self.dtheta = math.cos(self.theta) * math.cos(self.phi) * dx
        self.dtheta += math.cos(self.theta) * math.sin(self.phi) * dy
        self.dtheta -= math.sin(self.theta) * dz
        self.dtheta /= max(self.r, 1e-9)

        sin_theta = max(math.sin(self.theta), 1e-9)
        self.dphi = (-math.sin(self.phi) * dx + math.cos(self.phi) * dy) / (self.r * sin_theta)

        factor = 1.0 - black_hole.schwarzschild_radius / max(self.r, black_hole.schwarzschild_radius * 1.001)
        dt_dlambda = math.sqrt(
            (self.dr * self.dr) / factor
            + self.r * self.r * self.dtheta * self.dtheta
            + self.r * self.r * sin_theta * sin_theta * self.dphi * self.dphi
        )
        self.energy = factor * dt_dlambda

    def point(self) -> Vec3:
        return Vec3(self.x, self.y, self.z)

    def clone(self) -> "Ray3D":
        clone = object.__new__(Ray3D)
        clone.x = self.x
        clone.y = self.y
        clone.z = self.z
        clone.r = self.r
        clone.theta = self.theta
        clone.phi = self.phi
        clone.dr = self.dr
        clone.dtheta = self.dtheta
        clone.dphi = self.dphi
        clone.energy = self.energy
        return clone

    def step(self, delta_lambda: float, schwarzschild_radius: float) -> None:
        if self.r <= schwarzschild_radius:
            return

        state = [self.r, self.theta, self.phi, self.dr, self.dtheta, self.dphi]
        k1 = geodesic_rhs(self, schwarzschild_radius)
        k2 = geodesic_rhs(state_to_ray(self, add_state(state, k1, delta_lambda / 2.0)), schwarzschild_radius)
        k3 = geodesic_rhs(state_to_ray(self, add_state(state, k2, delta_lambda / 2.0)), schwarzschild_radius)
        k4 = geodesic_rhs(state_to_ray(self, add_state(state, k3, delta_lambda)), schwarzschild_radius)

        increments = [
            (delta_lambda / 6.0) * (a + 2 * b + 2 * c + d)
            for a, b, c, d in zip(k1, k2, k3, k4)
        ]

        self.r += increments[0]
        self.theta += increments[1]
        self.phi += increments[2]
        self.dr += increments[3]
        self.dtheta += increments[4]
        self.dphi += increments[5]

        self.x = self.r * math.sin(self.theta) * math.cos(self.phi)
        self.y = self.r * math.sin(self.theta) * math.sin(self.phi)
        self.z = self.r * math.cos(self.theta)


def geodesic_rhs(ray: Ray3D, schwarzschild_radius: float) -> list[float]:
    radius = max(ray.r, schwarzschild_radius * 1.0001)
    sin_theta = max(math.sin(ray.theta), 1e-9)
    cos_theta = math.cos(ray.theta)
    factor = 1.0 - schwarzschild_radius / radius
    dt_dlambda = ray.energy / factor

    return [
        ray.dr,
        ray.dtheta,
        ray.dphi,
        -((schwarzschild_radius / (2 * radius * radius)) * factor * dt_dlambda * dt_dlambda)
        + ((schwarzschild_radius / (2 * radius * radius * factor)) * ray.dr * ray.dr)
        + radius * (ray.dtheta * ray.dtheta + sin_theta * sin_theta * ray.dphi * ray.dphi),
        -((2.0 / radius) * ray.dr * ray.dtheta) + sin_theta * cos_theta * ray.dphi * ray.dphi,
        -((2.0 / radius) * ray.dr * ray.dphi) - 2.0 * cos_theta * ray.dtheta * ray.dphi / sin_theta,
    ]


def add_state(values: list[float], derivatives: list[float], factor: float) -> list[float]:
    return [value + derivative * factor for value, derivative in zip(values, derivatives)]


def state_to_ray(template: Ray3D, values: list[float]) -> Ray3D:
    copy = template.clone()
    copy.r, copy.theta, copy.phi, copy.dr, copy.dtheta, copy.dphi = values
    return copy


def trace_pixel(
    x: int,
    y: int,
    width: int,
    height: int,
    black_hole: BlackHole,
    use_geodesics: bool,
    origin: Vec3,
    forward: Vec3,
    right: Vec3,
    up: Vec3,
    aspect: float,
    tan_half_fov: float,
    max_steps: int,
) -> tuple[int, int, int]:
    u = (2.0 * ((x + 0.5) / width) - 1.0) * aspect * tan_half_fov
    v = (1.0 - 2.0 * ((y + 0.5) / height)) * tan_half_fov
    direction = (right * u + up * v + forward).normalized()

    if not use_geodesics:
        camera_to_hole = origin - black_hole.position
        b_value = 2.0 * camera_to_hole.dot(direction)
        c_value = camera_to_hole.dot(camera_to_hole) - black_hole.schwarzschild_radius**2
        discriminant = b_value * b_value - 4.0 * c_value
        if discriminant <= 0.0:
            return 0, 0, 0

        root = math.sqrt(discriminant)
        near = (-b_value - root) / 2.0
        far = (-b_value + root) / 2.0
        return (255, 0, 0) if near > 0.0 or far > 0.0 else (0, 0, 0)

    ray = Ray3D(origin, direction, black_hole)
    for _ in range(max_steps):
        if black_hole.intercepts(ray.point()):
            return 255, 0, 0
        ray.step(1.0e7, black_hole.schwarzschild_radius)
        if ray.r > 1.0e14:
            break

    glow = clamp(1.0e12 / max(ray.r, 1.0), 0.0, 0.3)
    return round(glow * 120), round(glow * 120), round(glow * 255)


def render_frame(
    width: int,
    height: int,
    camera: Camera,
    black_hole: BlackHole,
    use_geodesics: bool,
    max_steps: int = 320,
) -> list[tuple[int, int, int]]:
    if width <= 0 or height <= 0:
        raise ValueError("Width and height must be positive.")
    if max_steps <= 0:
        raise ValueError("max_steps must be positive.")

    forward, right, up = camera.basis()
    aspect = width / height
    tan_half_fov = math.tan(math.radians(camera.fov_y) * 0.5)
    origin = camera.position

    return [
        trace_pixel(
            x,
            y,
            width,
            height,
            black_hole,
            use_geodesics,
            origin,
            forward,
            right,
            up,
            aspect,
            tan_half_fov,
            max_steps,
        )
        for y in range(height)
        for x in range(width)
    ]


def render(width: int, height: int, use_geodesics: bool) -> list[tuple[int, int, int]]:
    black_hole = BlackHole(Vec3(), 8.54e36)
    camera = Camera()
    return render_frame(width, height, camera, black_hole, use_geodesics)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the CPU geodesic Python port.")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--output", default="cpu_geodesic.ppm")
    parser.add_argument("--use-geodesics", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pixels = render(args.width, args.height, args.use_geodesics)
    write_ppm(args.output, args.width, args.height, pixels)
    mode = "full geodesics" if args.use_geodesics else "sphere approximation"
    print(f"Saved {mode} render to {args.output}")


if __name__ == "__main__":
    main()
