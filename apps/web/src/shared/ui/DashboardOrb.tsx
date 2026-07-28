import { useEffect, useRef } from "react"
import * as THREE from "three"

/** Soft teal 3D accent for the dashboard hero — keeps brand colors. */
export function DashboardOrb({ className }: { className?: string }) {
  const mountRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    const width = mount.clientWidth || 360
    const height = mount.clientHeight || 280

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100)
    camera.position.set(0, 0.2, 4.2)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(width, height)
    renderer.setClearColor(0x000000, 0)
    mount.appendChild(renderer.domElement)

    const group = new THREE.Group()
    scene.add(group)

    const icosa = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.05, 1),
      new THREE.MeshStandardMaterial({
        color: new THREE.Color("#2dd4bf"),
        metalness: 0.35,
        roughness: 0.28,
        flatShading: true,
      }),
    )
    group.add(icosa)

    const wire = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.28, 0),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color("#5eead4"),
        wireframe: true,
        transparent: true,
        opacity: 0.35,
      }),
    )
    group.add(wire)

    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(1.55, 0.035, 16, 96),
      new THREE.MeshStandardMaterial({
        color: new THREE.Color("#0d9488"),
        metalness: 0.6,
        roughness: 0.25,
        emissive: new THREE.Color("#115e59"),
        emissiveIntensity: 0.35,
      }),
    )
    ring.rotation.x = Math.PI / 2.4
    group.add(ring)

    const particles = new THREE.Points(
      (() => {
        const geo = new THREE.BufferGeometry()
        const count = 80
        const pos = new Float32Array(count * 3)
        for (let i = 0; i < count; i++) {
          const r = 1.8 + Math.random() * 1.4
          const theta = Math.random() * Math.PI * 2
          const phi = Math.acos(2 * Math.random() - 1)
          pos[i * 3] = r * Math.sin(phi) * Math.cos(theta)
          pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
          pos[i * 3 + 2] = r * Math.cos(phi)
        }
        geo.setAttribute("position", new THREE.BufferAttribute(pos, 3))
        return geo
      })(),
      new THREE.PointsMaterial({
        color: new THREE.Color("#99f6e4"),
        size: 0.035,
        transparent: true,
        opacity: 0.85,
        sizeAttenuation: true,
      }),
    )
    group.add(particles)

    scene.add(new THREE.AmbientLight(0xffffff, 0.55))
    const key = new THREE.DirectionalLight(0xccfbf1, 1.1)
    key.position.set(3, 4, 5)
    scene.add(key)
    const fill = new THREE.PointLight(0x2dd4bf, 1.4, 12)
    fill.position.set(-2.5, -1, 2)
    scene.add(fill)

    let frame = 0
    let raf = 0
    const tick = () => {
      frame += 0.008
      icosa.rotation.y += 0.006
      icosa.rotation.x = Math.sin(frame) * 0.15
      wire.rotation.y -= 0.004
      wire.rotation.z += 0.002
      ring.rotation.z += 0.01
      particles.rotation.y += 0.0015
      group.rotation.y = Math.sin(frame * 0.35) * 0.12
      renderer.render(scene, camera)
      raf = requestAnimationFrame(tick)
    }
    tick()

    const onResize = () => {
      const w = mount.clientWidth
      const h = mount.clientHeight
      if (!w || !h) return
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    const ro = new ResizeObserver(onResize)
    ro.observe(mount)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      renderer.dispose()
      icosa.geometry.dispose()
      ;(icosa.material as THREE.Material).dispose()
      wire.geometry.dispose()
      ;(wire.material as THREE.Material).dispose()
      ring.geometry.dispose()
      ;(ring.material as THREE.Material).dispose()
      particles.geometry.dispose()
      ;(particles.material as THREE.Material).dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
    }
  }, [])

  return <div ref={mountRef} className={className} aria-hidden />
}
