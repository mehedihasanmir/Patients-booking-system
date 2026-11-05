"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useVoice } from "@/lib/voice";

function Tooth() {
  const ref = useRef<THREE.Mesh>(null);
  const level = useVoice((state) => state.level);
  const geometry = useMemo(() => {
    const points = [
      new THREE.Vector2(0, -1.15),
      new THREE.Vector2(0.28, -1.05),
      new THREE.Vector2(0.36, -0.35),
      new THREE.Vector2(0.52, 0.18),
      new THREE.Vector2(0.4, 0.74),
      new THREE.Vector2(0.14, 0.98),
      new THREE.Vector2(0, 1.05),
    ];
    return new THREE.LatheGeometry(points, 42);
  }, []);

  useFrame((_, delta) => {
    if (!ref.current) return;
    ref.current.rotation.y += delta * 0.35;
    const pulse = 1 + Math.sin(performance.now() / 480) * 0.012 + level * 0.08;
    ref.current.scale.setScalar(pulse);
  });

  return (
    <mesh ref={ref} geometry={geometry}>
      <meshPhysicalMaterial
        color="#f6fbff"
        roughness={0.16}
        metalness={0.05}
        clearcoat={1}
        clearcoatRoughness={0.12}
      />
    </mesh>
  );
}

function VoiceRings() {
  const group = useRef<THREE.Group>(null);
  const level = useVoice((state) => state.level);
  const active = useVoice((state) => state.active);
  useFrame((_, delta) => {
    if (group.current) group.current.rotation.z += delta * (active ? 0.45 : 0.15);
  });
  const scale = 1 + level * 0.28;
  return (
    <group ref={group} scale={scale}>
      <mesh rotation={[Math.PI / 2.35, 0.15, 0]}>
        <torusGeometry args={[1.48, 0.014, 16, 90]} />
        <meshBasicMaterial color="#149a96" transparent opacity={0.45 + level * 0.5} />
      </mesh>
      <mesh rotation={[1.15, 0.5, 0.35]}>
        <torusGeometry args={[1.78, 0.008, 12, 90]} />
        <meshBasicMaterial color="#8eb7ff" transparent opacity={0.28 + (active ? 0.2 : 0)} />
      </mesh>
    </group>
  );
}

export default function ToothCanvas() {
  return (
    <Canvas camera={{ position: [0, 0.15, 4.3], fov: 34 }} dpr={[1, 1.6]} gl={{ alpha: true, antialias: true }}>
      <ambientLight intensity={0.75} />
      <directionalLight position={[3.2, 4.2, 2.4]} intensity={1.5} color="#ffffff" />
      <pointLight position={[-2.2, 0.8, 2]} intensity={14} color="#8fd8d0" />
      <Tooth />
      <VoiceRings />
    </Canvas>
  );
}
