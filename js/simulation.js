/**
 * Physics, Math and Simulation Engine for 3D Black Hole Web Application.
 */

export const G = 6.67430e-11;
export const C = 299792458.0;

export class Vec3 {
    constructor(x = 0.0, y = 0.0, z = 0.0) {
        this.x = Number(x);
        this.y = Number(y);
        this.z = Number(z);
    }

    add(v) { return new Vec3(this.x + v.x, this.y + v.y, this.z + v.z); }
    sub(v) { return new Vec3(this.x - v.x, this.y - v.y, this.z - v.z); }
    mul(s) { return new Vec3(this.x * s, this.y * s, this.z * s); }
    div(s) { return new Vec3(this.x / s, this.y / s, this.z / s); }
    dot(v) { return this.x * v.x + this.y * v.y + this.z * v.z; }
    
    cross(v) {
        return new Vec3(
            this.y * v.z - this.z * v.y,
            this.z * v.x - this.x * v.z,
            this.x * v.y - this.y * v.x
        );
    }

    length() { return Math.sqrt(this.dot(this)); }
    
    normalized() {
        const len = this.length();
        return len === 0 ? new Vec3() : this.div(len);
    }

    clone() { return new Vec3(this.x, this.y, this.z); }
}

export class ObjectData {
    constructor(position, radius, color, mass) {
        this.position = position; // Vec3
        this.radius = Number(radius);
        this.color = color; // [r, g, b, a] normalized 0-1
        this.mass = Number(mass);
        this.velocity = new Vec3();
    }
}

export class GravitySimulation {
    constructor(objects = []) {
        this.objects = objects;
    }

    step(enableGravity = true, timeStep = 1.0) {
        if (!enableGravity || this.objects.length === 0) return;

        const accelerations = this.objects.map(() => new Vec3());
        let anchorIndex = 0;
        let maxMass = -1;

        for (let i = 0; i < this.objects.length; i++) {
            if (this.objects[i].mass > maxMass) {
                maxMass = this.objects[i].mass;
                anchorIndex = i;
            }
        }

        for (let i = 0; i < this.objects.length; i++) {
            const objA = this.objects[i];
            for (let j = 0; j < this.objects.length; j++) {
                if (i === j) continue;
                const objB = this.objects[j];

                const offset = objB.position.sub(objA.position);
                const dist = Math.max(offset.length(), 1e9);
                const dir = offset.div(dist);
                const force = (G * objA.mass * objB.mass) / (dist * dist);
                accelerations[i] = accelerations[i].add(dir.mul((force / objA.mass) * timeStep));
            }
        }

        for (let i = 0; i < this.objects.length; i++) {
            if (i === anchorIndex) {
                this.objects[i].velocity = new Vec3();
                continue;
            }
            const obj = this.objects[i];
            obj.velocity = obj.velocity.add(accelerations[i]);
            obj.position = obj.position.add(obj.velocity.mul(timeStep));
        }
    }
}

/**
 * 3D Spacetime Grid deformed by gravity well (Flamm's paraboloid embedding diagram approximation)
 */
export class SpacetimeGrid {
    static generateMesh(objects, gridSize = 48, spacing = 2.0e10) {
        const vertices = [];
        const indices = [];

        const half = gridSize / 2;
        const gridPoints = [];

        // Identify central black hole (highest mass object)
        let centralObj = objects[0] || new ObjectData(new Vec3(), 1e9, [0,0,0,1], 4e30);
        for (const obj of objects) {
            if (obj.mass > centralObj.mass) centralObj = obj;
        }

        const bhRs = (2.0 * G * centralObj.mass) / (C * C) * 1.5e5;

        for (let z = 0; z <= gridSize; z++) {
            const row = [];
            for (let x = 0; x <= gridSize; x++) {
                let wx = (x - half) * spacing;
                let wz = (z - half) * spacing;

                // Central Black Hole Gravitational Funnel & Radial Pinching
                const dx = wx - centralObj.position.x;
                const dz = wz - centralObj.position.z;
                const dist = Math.sqrt(dx * dx + dz * dz);
                const normDist = dist / Math.max(bhRs, 1.0);

                // Deep aggressive plunge: scales directly with Black Hole mass (bhRs)
                let height = -Math.min(24.0 * bhRs, (18.0 * bhRs) / (Math.pow(normDist, 0.82) + 0.12));

                // Radial mesh contraction toward the singularity
                const pullFactor = Math.min(0.38, (0.45 * bhRs) / (dist + 0.5 * bhRs));
                wx -= dx * pullFactor;
                wz -= dz * pullFactor;

                // Secondary gravity wells for orbiting planets/masses
                for (const obj of objects) {
                    if (obj === centralObj) continue;
                    const pdx = wx - obj.position.x;
                    const pdz = wz - obj.position.z;
                    const pdist = Math.sqrt(pdx * pdx + pdz * pdz);
                    const massRatio = Math.min(1.0, obj.mass / centralObj.mass);
                    const pWell = - (4.0 * bhRs * massRatio) / (Math.sqrt(pdist / Math.max(bhRs, 1.0) + 0.15));
                    height += pWell;
                }

                row.push([wx, height, wz]);
            }
            gridPoints.push(row);
        }

        // Build vertex buffer & line indices
        for (let z = 0; z <= gridSize; z++) {
            for (let x = 0; x <= gridSize; x++) {
                const pt = gridPoints[z][x];
                vertices.push(pt[0], pt[1], pt[2]);

                const currIdx = z * (gridSize + 1) + x;
                if (x < gridSize) {
                    indices.push(currIdx, currIdx + 1);
                }
                if (z < gridSize) {
                    indices.push(currIdx, currIdx + (gridSize + 1));
                }
            }
        }

        return {
            vertices: new Float32Array(vertices),
            indices: new Uint16Array(indices)
        };
    }
}

/**
 * Geodesic Light Ray trajectory step calculator
 */
export class LightGeodesicIntegrator {
    static traceRayPath(startPos, startDir, schwarzschildRadius, steps = 180, stepSize = 1.2e8) {
        const path = [startPos.clone()];
        let pos = startPos.clone();
        let dir = startDir.normalized();

        for (let i = 0; i < steps; i++) {
            const r2 = pos.dot(pos);
            const r = Math.sqrt(r2);
            if (r <= schwarzschildRadius * 1.02) break; // Trapped in event horizon

            // Schwarzschild bending acceleration: a = - (1.5 * Rs / r^3) * (dir - pos*(pos.dot(dir)/r2))
            const impactDir = pos.div(r);
            const perp = dir.sub(impactDir.mul(dir.dot(impactDir)));
            const bendFactor = (1.8 * schwarzschildRadius) / (r2 + 1e-5);

            dir = dir.sub(impactDir.mul(bendFactor)).normalized();
            pos = pos.add(dir.mul(stepSize));
            path.push(pos.clone());

            if (r > schwarzschildRadius * 50) break; // Escaped into deep space
        }
        return path;
    }
}
