"use client";

import { Suspense, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { ContactShadows, Float, RoundedBox, Sparkles } from "@react-three/drei";
import { useReducedMotion } from "framer-motion";
import * as THREE from "three";

const INK = "#1b2029";
const AMBER = "#f59e0b";
const RED = "#e11d48";

function DocumentSheet() {
  const lines = [0.72, 0.52, 0.62, 0.44, 0.68, 0.36];
  return (
    <group rotation={[-0.06, 0.16, -0.025]}>
      <RoundedBox args={[2.25, 2.95, 0.09]} radius={0.07} smoothness={4} position={[0, 0, 0]}>
        <meshStandardMaterial color="#ffffff" roughness={0.32} metalness={0.04} />
      </RoundedBox>
      <RoundedBox args={[2.05, 0.16, 0.02]} radius={0.03} smoothness={3} position={[0, 1.16, 0.06]}>
        <meshStandardMaterial color={INK} roughness={0.5} />
      </RoundedBox>
      {lines.map((width, index) => (
        <mesh key={index} position={[-0.92 + width / 2, 0.78 - index * 0.3, 0.06]}>
          <boxGeometry args={[width, 0.035, 0.012]} />
          <meshStandardMaterial
            color={index === 2 ? AMBER : index === 4 ? RED : "#cbd5e1"}
            roughness={0.6}
          />
        </mesh>
      ))}
      <mesh position={[0.62, -1.08, 0.1]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.26, 0.26, 0.05, 40]} />
        <meshStandardMaterial color={RED} roughness={0.35} />
      </mesh>
      <mesh position={[0.62, -1.08, 0.14]}>
        <torusGeometry args={[0.16, 0.018, 12, 40]} />
        <meshStandardMaterial color="#ffffff" roughness={0.4} />
      </mesh>
      <mesh position={[-0.72, -1.1, 0.08]}>
        <boxGeometry args={[0.7, 0.03, 0.012]} />
        <meshStandardMaterial color="#94a3b8" />
      </mesh>
    </group>
  );
}

function Scales() {
  const beam = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (beam.current) {
      beam.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.9) * 0.055;
    }
  });
  return (
    <group position={[-1.85, 0.15, 0.1]} scale={0.62}>
      <mesh position={[0, -0.15, 0]}>
        <cylinderGeometry args={[0.035, 0.05, 1.9, 20]} />
        <meshStandardMaterial color="#b45309" metalness={0.55} roughness={0.3} />
      </mesh>
      <mesh position={[0, -1.05, 0]}>
        <cylinderGeometry args={[0.34, 0.4, 0.08, 32]} />
        <meshStandardMaterial color="#92400e" metalness={0.5} roughness={0.35} />
      </mesh>
      <group ref={beam} position={[0, 0.78, 0]}>
        <mesh>
          <boxGeometry args={[1.7, 0.045, 0.045]} />
          <meshStandardMaterial color="#b45309" metalness={0.6} roughness={0.28} />
        </mesh>
        {[-0.78, 0.78].map((x) => (
          <group key={x} position={[x, 0, 0]}>
            <mesh position={[0, -0.32, 0]}>
              <cylinderGeometry args={[0.008, 0.008, 0.64, 8]} />
              <meshStandardMaterial color="#d97706" metalness={0.5} roughness={0.4} />
            </mesh>
            <mesh position={[0, -0.66, 0]}>
              <cylinderGeometry args={[0.24, 0.18, 0.05, 28]} />
              <meshStandardMaterial color="#b45309" metalness={0.55} roughness={0.3} />
            </mesh>
          </group>
        ))}
      </group>
    </group>
  );
}

function SceneContent() {
  return (
    <>
      <ambientLight intensity={0.75} />
      <directionalLight position={[4, 6, 5]} intensity={1.5} castShadow />
      <directionalLight position={[-5, 2, 3]} intensity={0.55} color="#bfdbfe" />
      <pointLight position={[0, -2, 4]} intensity={0.8} color="#e0e7ff" />
      <Float speed={1.4} rotationIntensity={0.18} floatIntensity={0.55} floatingRange={[-0.08, 0.08]}>
        <DocumentSheet />
      </Float>
      <Float speed={1.1} rotationIntensity={0.12} floatIntensity={0.4} floatingRange={[-0.06, 0.06]}>
        <Scales />
      </Float>
      <Sparkles count={38} scale={[5.5, 4.5, 3]} size={1.6} speed={0.25} color="#93c5fd" opacity={0.7} />
      <ContactShadows position={[0, -2.05, 0]} opacity={0.32} scale={9} blur={2.6} far={4.5} />
    </>
  );
}

function Fallback() {
  return (
    <div className="flex h-full w-full items-center justify-center [perspective:1200px]">
      <div className="relative h-64 w-48 rounded-2xl bg-white shadow-2xl [transform:rotateY(-16deg)_rotateX(6deg)]">
        <div className="absolute left-5 top-6 h-2 w-24 rounded bg-ink-900" />
        {[0, 1, 2, 3, 4].map((row) => (
          <div
            key={row}
            className="absolute left-5 h-1 rounded bg-slate-300"
            style={{ top: 64 + row * 18, width: `${[80, 60, 70, 45, 65][row]}%` }}
          />
        ))}
        <div className="absolute bottom-6 right-6 h-10 w-10 rounded-full bg-rose-600/90" />
      </div>
    </div>
  );
}

export default function HeroScene({ className }: { className?: string }) {
  const reduce = useReducedMotion();
  if (reduce) {
    return (
      <div className={className} aria-hidden>
        <Fallback />
      </div>
    );
  }
  return (
    <div className={className} aria-hidden>
      <Canvas
        camera={{ position: [0, 0.15, 6.2], fov: 38 }}
        dpr={[1, 1.8]}
        gl={{ antialias: true, alpha: true }}
        fallback={<Fallback />}
        onCreated={({ gl }) => gl.setClearColor(0x000000, 0)}
      >
        <Suspense fallback={null}>
          <SceneContent />
        </Suspense>
      </Canvas>
    </div>
  );
}