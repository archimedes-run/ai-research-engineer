'use client'

import { useEffect, useRef } from 'react'

interface Ripple {
    x: number
    y: number
    radius: number
    maxRadius: number
    speed: number
}

export default function AsciiOverlay() {
    const canvasRef = useRef<HTMLCanvasElement>(null)

    useEffect(() => {
        const canvas = canvasRef.current
        if (!canvas) return
        const ctx = canvas.getContext('2d')
        if (!ctx) return

        let width = canvas.width = window.innerWidth
        let height = canvas.height = window.innerHeight

        const fontSize = 11
        let columns = Math.floor(width / fontSize)
        let rows = Math.floor(height / fontSize)

        const specialChars = ['2', '?', '=', '+', '*', '-', '-', '-', '-', '-']
        const hiddenWords = [
            "AUTONOMY IS THE FUTURE",
            "INTO THE DISTANCE",
            "RESEARCH AHEAD",
            "ARCHIMEDES LABS"
        ]

        let grid: string[][] = []

        const generateGrid = () => {
            columns = Math.floor(width / fontSize)
            rows = Math.floor(height / fontSize)
            grid = Array.from({ length: rows }, () =>
                Array.from({ length: columns }, () =>
                    Math.random() > 0.08 ? '-' : specialChars[Math.floor(Math.random() * specialChars.length)]
                )
            )

            // Inject hidden words
            for (let i = 0; i < 8; i++) {
                const word = hiddenWords[Math.floor(Math.random() * hiddenWords.length)]
                const row = Math.floor(Math.random() * rows)
                const col = Math.floor(Math.random() * (columns - word.length))
                for (let j = 0; j < word.length; j++) {
                    if (grid[row] && grid[row][col + j]) {
                        grid[row][col + j] = word[j]
                    }
                }
            }
        }

        generateGrid()

        window.addEventListener('resize', () => {
            width = canvas.width = window.innerWidth
            height = canvas.height = window.innerHeight
            generateGrid()
        })

        let ripples: Ripple[] = []

        const draw = () => {
            ctx.clearRect(0, 0, width, height)
            ctx.font = `600 ${fontSize}px monospace`
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'

            // Spawn slow ripples
            if (Math.random() < 0.005 && ripples.length < 3) {
                ripples.push({
                    x: Math.random() * columns,
                    y: Math.random() * rows,
                    radius: 0,
                    // 🎛️ TWEAK HERE: Ripple Max Size (5% of screen is roughly 8-12 columns)
                    maxRadius: 8 + Math.random() * 4,
                    // 🎛️ TWEAK HERE: Ripple expansion speed (lower is slower)
                    speed: 0.08
                })
            }

            // Update ripples
            ripples.forEach(r => (r.radius += r.speed))
            ripples = ripples.filter(r => r.radius < r.maxRadius)

            for (let y = 0; y < rows; y++) {
                for (let x = 0; x < columns; x++) {
                    const char = grid[y]?.[x]
                    if (!char) continue

                    let waveAlpha = 0

                    // 🎛️ TWEAK HERE: How thick the ripple "wake" is. 
                    // Since the max radius is ~10, the wake should only be ~5 cells thick.
                    const wakeWidth = 5;

                    for (const r of ripples) {
                        const dist = Math.hypot(x - r.x, y - r.y)
                        const distFromEdge = r.radius - dist

                        if (distFromEdge > 0 && distFromEdge < wakeWidth) {
                            // Cosine wave for tight concentric rings. 
                            // Higher multiplier (e.g., 2.5) means tighter rings inside the small wake.
                            const ring = (Math.cos(distFromEdge * 2.5) + 1) / 2
                            const fade = 1.0 - (distFromEdge / wakeWidth)
                            waveAlpha = Math.max(waveAlpha, ring * fade)
                        }
                    }

                    // 🎛️ TWEAK HERE: DEFAULT VISIBILITY
                    // Change baseOpacity to make the numbers/-'s brighter overall!
                    // 0.1 = nearly invisible, 0.3 = nicely visible, 0.6 = very bright
                    const baseOpacity = 0.25;

                    // 🎛️ TWEAK HERE: How much the ripple brightens the text
                    const rippleIntensity = 0.65;

                    const finalAlpha = baseOpacity + (waveAlpha * rippleIntensity);

                    ctx.fillStyle = `rgba(255, 255, 255, ${finalAlpha})`
                    ctx.fillText(char, x * fontSize + fontSize / 2, y * fontSize + fontSize / 2)
                }
            }

            requestAnimationFrame(draw)
        }

        draw()

        return () => {
            window.removeEventListener('resize', generateGrid)
        }
    }, [])

    return (
        <canvas
            ref={canvasRef}
            className="absolute inset-0 z-10 pointer-events-none mix-blend-overlay opacity-90"
        />
    )
}