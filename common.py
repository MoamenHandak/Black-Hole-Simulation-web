"""Shared math and utility helpers for the Python port."""

from __future__ import annotations

import math


C = 299_792_458.0
G = 6.67430e-11


class Vec3:
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> "Vec3":
        if scalar == 0:
            raise ZeroDivisionError("Cannot divide a vector by zero.")
        return Vec3(self.x / scalar, self.y / scalar, self.z / scalar)

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length(self) -> float:
        return math.sqrt(self.dot(self))

    def normalized(self) -> "Vec3":
        length = self.length()
        if length == 0:
            return Vec3()
        return self / length

    def as_tuple(self) -> tuple[float, float, float]:
        return self.x, self.y, self.z


class BlackHole:
    def __init__(self, position: Vec3, mass: float) -> None:
        self.position = position
        self.mass = float(mass)
        self.schwarzschild_radius = 2.0 * G * self.mass / (C * C)

    def intercepts(self, point: Vec3) -> bool:
        offset = point - self.position
        return offset.dot(offset) < self.schwarzschild_radius**2


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def write_ppm(path: str, width: int, height: int, pixels: list[tuple[int, int, int]]) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive.")
    if len(pixels) != width * height:
        raise ValueError("Pixel buffer size does not match the image dimensions.")

    with open(path, "w", encoding="ascii") as handle:
        handle.write(f"P3\n{width} {height}\n255\n")
        for red, green, blue in pixels:
            handle.write(f"{red} {green} {blue}\n")
