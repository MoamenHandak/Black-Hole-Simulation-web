"""Readable Python port of `ray_tracing.cpp`.

This script renders a simple scene to a PPM image.
"""

from __future__ import annotations

import argparse
from math import inf, sqrt

from common import Vec3, write_ppm


class Material:
    def __init__(self, color: Vec3, specular: float = 0.5, emission: float = 0.0) -> None:
        self.color = color
        self.specular = float(specular)
        self.emission = float(emission)


class Ray:
    def __init__(self, origin: Vec3, direction: Vec3) -> None:
        self.origin = origin
        self.direction = direction.normalized()


class Sphere:
    def __init__(self, center: Vec3, radius: float, material: Material) -> None:
        self.center = center
        self.radius = float(radius)
        self.material = material

    def intersect(self, ray: Ray) -> float | None:
        offset = ray.origin - self.center
        a = ray.direction.dot(ray.direction)
        b = 2.0 * offset.dot(ray.direction)
        c = offset.dot(offset) - self.radius**2
        discriminant = b * b - 4.0 * a * c
        if discriminant < 0:
            return None

        root = sqrt(discriminant)
        near = (-b - root) / (2.0 * a)
        far = (-b + root) / (2.0 * a)
        for distance in (near, far):
            if distance > 0:
                return distance
        return None

    def normal_at(self, point: Vec3) -> Vec3:
        return (point - self.center).normalized()


class Scene:
    def __init__(self, objects: list[Sphere], light_position: Vec3 | None = None) -> None:
        self.objects = objects
        self.light_position = light_position or Vec3(5.0, 5.0, 5.0)

    def trace(self, ray: Ray) -> Vec3:
        closest_hit = inf
        hit_object = None

        for obj in self.objects:
            distance = obj.intersect(ray)
            if distance is not None and distance < closest_hit:
                closest_hit = distance
                hit_object = obj

        if hit_object is None:
            return Vec3(0.0, 0.0, 0.1)

        hit_point = ray.origin + ray.direction * closest_hit
        normal = hit_object.normal_at(hit_point)
        light_direction = (self.light_position - hit_point).normalized()
        light_distance = (self.light_position - hit_point).length()
        diffuse = max(normal.dot(light_direction), 0.0)
        shadow_origin = hit_point + normal * 0.001
        shadow_ray = Ray(shadow_origin, light_direction)
        in_shadow = any(
            (distance := obj.intersect(shadow_ray)) is not None and distance < light_distance
            for obj in self.objects
        )

        ambient = 0.1
        brightness = ambient if in_shadow else ambient + 0.9 * diffuse
        return hit_object.material.color * brightness


def color_to_rgb(color: Vec3) -> tuple[int, int, int]:
    return tuple(max(0, min(255, round(channel * 255))) for channel in color.as_tuple())


def render(scene: Scene, width: int, height: int) -> list[tuple[int, int, int]]:
    if width <= 0 or height <= 0:
        raise ValueError("Width and height must both be positive integers.")

    aspect_ratio = width / height
    pixels: list[tuple[int, int, int]] = []

    for y in range(height):
        row = [
            color_to_rgb(
                scene.trace(
                    Ray(
                        origin=Vec3(),
                        direction=Vec3(
                            (2.0 * ((x + 0.5) / width) - 1.0) * aspect_ratio,
                            -(2.0 * ((y + 0.5) / height) - 1.0),
                            -1.0,
                        ),
                    )
                )
            )
            for x in range(width)
        ]
        pixels.extend(row)

    return pixels


def build_default_scene() -> Scene:
    return Scene(
        objects=[
            Sphere(Vec3(0.0, 0.0, -5.0), 2.0, Material(Vec3(1.0, 0.2, 0.2))),
            Sphere(Vec3(3.0, 0.0, -7.0), 1.5, Material(Vec3(0.2, 1.0, 0.2))),
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the Python port of the simple ray tracer.")
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--output", default="ray_tracing.ppm")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pixels = render(build_default_scene(), args.width, args.height)
    write_ppm(args.output, args.width, args.height, pixels)
    print(f"Saved image to {args.output}")


if __name__ == "__main__":
    main()
