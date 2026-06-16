'use client'

import { motion } from 'framer-motion'
import Image from 'next/image'
import { Terminal as TerminalIcon, Cpu, CheckCircle2, FlaskConical, Database } from 'lucide-react'

// --- Data Pulse Component: The moving "blinking light" ---
const DataPulse = ({ path, delay = 0 }: { path: string; delay?: number }) => (
    <motion.path
        d={path}
        fill="none"
        stroke="rgba(224, 82, 64, 0.8)"
        strokeWidth="2"
        strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{
            pathLength: [0, 1],
            opacity: [0, 1, 0]
        }}
        transition={{
            duration: 2,
            repeat: Infinity,
            delay,
            ease: "easeInOut"
        }}
    />
)

const IntegrationHub = () => {
    // Paths calculated relative to the center (0,0)
    const paths = {
        arxiv: "M -140, -50 Q -70, -50 0, 0",
        semantic: "M -140, 50 Q -70, 50 0, 0",
        flask: "M 0, 0 Q 70, -45 140, -45",
        db: "M 0, 0 Q 70, 45 140, 45"
    }

    return (
        <div className="relative w-full h-full min-h-[300px] flex items-center justify-center py-12">

            {/* LEFT: SOURCES */}
            <div className="absolute left-[15%] md:left-[20%] flex flex-col gap-12 items-end z-20">
                <motion.div
                    whileHover={{ scale: 1.05 }}
                    className="bg-white w-[100px] h-[50px] flex items-center justify-center p-2 rounded-xl shadow-lg border border-black/5 overflow-hidden"
                >
                    <Image src="/arxiv.png" alt="ArXiv" width={80} height={30} className="object-contain grayscale contrast-125" />
                </motion.div>
                <motion.div
                    whileHover={{ scale: 1.05 }}
                    className="bg-white w-[100px] h-[50px] flex items-center justify-center p-2 rounded-xl shadow-lg border border-black/5 overflow-hidden"
                >
                    <Image src="/semantic-scholar.png" alt="Semantic Scholar" width={80} height={30} className="object-contain grayscale" />
                </motion.div>
            </div>

            {/* CENTER: ARCHIMEDES HUB */}
            <div className="relative z-30">
                <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
                    className="absolute -inset-6 border border-dashed border-[#E05240]/30 rounded-full"
                />
                <motion.div
                    animate={{ scale: [1, 1.05, 1] }}
                    transition={{ duration: 4, repeat: Infinity }}
                    className="w-16 h-16 bg-gradient-to-br from-[#E05240] to-[#FF8C7A] rounded-2xl flex items-center justify-center shadow-[0_0_30px_rgba(224,82,64,0.4)] relative border border-white/20"
                >
                    <span className="font-brand font-bold text-white text-2xl">A</span>
                </motion.div>
            </div>

            {/* RIGHT: OUTPUTS */}
            <div className="absolute right-[15%] md:right-[20%] flex flex-col gap-10 items-start z-20">
                <motion.div
                    animate={{
                        boxShadow: ["0 0 0px rgba(224,82,64,0)", "0 0 20px rgba(224,82,64,0.3)", "0 0 0px rgba(224,82,64,0)"]
                    }}
                    transition={{ duration: 2, repeat: Infinity, delay: 1 }}
                    className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/20"
                >
                    <FlaskConical className="w-6 h-6 text-white" />
                </motion.div>
                <motion.div
                    animate={{
                        boxShadow: ["0 0 0px rgba(224,82,64,0)", "0 0 20px rgba(224,82,64,0.3)", "0 0 0px rgba(224,82,64,0)"]
                    }}
                    transition={{ duration: 2, repeat: Infinity, delay: 1.2 }}
                    className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/20"
                >
                    <Database className="w-6 h-6 text-white" />
                </motion.div>
            </div>

            {/* SVG CONNECTOR SYSTEM */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none overflow-visible" viewBox="0 0 400 400" preserveAspectRatio="xMidYMid meet">
                <g transform="translate(200, 200)">
                    {/* Static Background Paths */}
                    <path d={paths.arxiv} fill="none" stroke="white" strokeWidth="1" strokeDasharray="4 4" opacity="0.15" />
                    <path d={paths.semantic} fill="none" stroke="white" strokeWidth="1" strokeDasharray="4 4" opacity="0.15" />
                    <path d={paths.flask} fill="none" stroke="white" strokeWidth="1" strokeDasharray="4 4" opacity="0.15" />
                    <path d={paths.db} fill="none" stroke="white" strokeWidth="1" strokeDasharray="4 4" opacity="0.15" />

                    {/* Animated Light Pulses */}
                    <DataPulse path={paths.arxiv} delay={0} />
                    <DataPulse path={paths.semantic} delay={0.5} />
                    <DataPulse path={paths.flask} delay={1} />
                    <DataPulse path={paths.db} delay={1.3} />
                </g>
            </svg>
        </div>
    )
}

const Terminal = ({ logs, title }: { logs: string[]; title: string }) => (
    <div className="w-full max-w-2xl mx-auto bg-[#1E1E1E]/90 backdrop-blur-xl rounded-lg overflow-hidden shadow-2xl border border-white/10 font-mono text-[11px] leading-relaxed">
        <div className="bg-[#323232] px-4 py-2 flex items-center gap-2 border-b border-white/5">
            <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-[#FF5F56]" />
                <div className="w-2.5 h-2.5 rounded-full bg-[#FFBD2E]" />
                <div className="w-2.5 h-2.5 rounded-full bg-[#27C93F]" />
            </div>
            <div className="flex-1 text-center text-white/40 text-[10px] uppercase tracking-widest">{title}</div>
        </div>
        <div className="p-5 h-52 overflow-y-auto custom-scrollbar">
            {logs.map((log, i) => (
                <div key={i} className="mb-1.5 flex gap-3">
                    <span className="text-green-400 opacity-50 select-none">➜</span>
                    <span className="text-white/80">{log}</span>
                </div>
            ))}
            <motion.div
                animate={{ opacity: [0, 1, 0] }}
                transition={{ repeat: Infinity, duration: 1 }}
                className="inline-block w-1.5 h-3 bg-[#E05240] ml-1 shadow-[0_0_8px_#E05240]"
            />
        </div>
    </div>
)

const features = [
    {
        id: '01',
        title: 'Literature Synthesis',
        tag: 'GOOGLE AGENT SDK • MULTI-MODAL DISCOVERY',
        desc: 'Archimedes uses the Google Agent SDK to orchestrate an autonomous ideation loop . It surveys ArXiv and Semantic Scholar to identify unexploited research frontiers and mathematically novel hypotheses.',
        img: '/mit-dome.jpg',
        customVisual: <IntegrationHub />
    },
    {
        id: '02',
        title: 'Neural Architecture',
        tag: 'CLAUDE CODE • SONNET 4.5 • PYTORCH',
        desc: 'Leveraging Claude Code for surgical refactoring, the agent implements complex neural networks from scratch. It utilizes structural code intelligence to perform AST inspections, ensuring mathematical correctness.',
        img: '/stanford-tower.jpg',
        logs: [
            "CODING_MODEL=claude-sonnet-4-5-20250929",
            "Surgical Inspection: identify bottleneck in Wavelet-KAN...",
            "Environment: active /uv/ deterministic environment",
            "Implementing custom CUDA kernels for spline expansion...",
            "Epoch 12/100 | Loss: 0.0412 | LR: 1.5e-4"
        ]
    },
    {
        id: '03',
        title: 'Empirical Validation',
        tag: 'SUCCESS CRITERIA • ADAPTIVE PI',
        desc: 'The Stage Reflector acts as an autonomous Principal Investigator, adapting the research plan in real-time based on training logs and convergence metrics. Results are synthesized into a publication-ready LaTeX manuscript.',
        img: '/drexel-main.jpg',
        logs: [
            "[CriteriaChecker] Criterion 0: ✅ MET (Zero Data Leakage)",
            "[CriteriaChecker] Criterion 2: ✅ MET (IDWT Perfect Reconstruction)",
            "[StageReflector] Adapting Stage 4: Add HPO for spline grid...",
            "Building: final_manuscript.pdf (LaTeX Compiler)",
            "✓ ALL SUCCESS CRITERIA MET. Session Archived."
        ]
    }
]

export default function Pipeline() {
    return (
        <section id="about" className="py-24 px-6 relative bg-[#FCF1EB] paper-grain">
            <div className="max-w-7xl mx-auto space-y-32">
                {features.map((f, i) => (
                    <div
                        key={f.id}
                        className={`flex flex-col md:flex-row items-center gap-12 md:gap-20 ${i % 2 === 1 ? 'md:flex-row-reverse' : ''
                            }`}
                    >
                        {/* Text Side */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: "-100px" }}
                            className="flex-1 space-y-6"
                        >
                            <div className="space-y-2">
                                <span className="font-mono text-[9px] tracking-[0.4em] text-[#E05240] uppercase font-bold">
                                    Phase {f.id} // {f.tag}
                                </span>
                                <h2 className="font-display text-4xl md:text-6xl text-[#3C2F2A] leading-tight italic">
                                    {f.title}
                                </h2>
                            </div>
                            <p className="font-body text-base text-[#3C2F2A]/70 leading-relaxed max-w-md">
                                {f.desc}
                            </p>
                        </motion.div>

                        {/* Visual Side */}
                        <div className="flex-[1.2] relative group w-full">
                            <motion.div
                                initial={{ opacity: 0 }}
                                whileInView={{ opacity: 1 }}
                                viewport={{ once: true }}
                                className="relative aspect-[16/10] rounded-2xl overflow-hidden shadow-2xl border border-black/5"
                            >
                                <Image
                                    src={f.img}
                                    alt={f.title}
                                    fill
                                    className="object-cover blur-[4px] scale-105 contrast-[0.85] brightness-[0.6] sepia-[15%]"
                                />

                                <div className="absolute inset-0 bg-[#3C2F2A]/30 mix-blend-multiply opacity-50" />
                                <div className="absolute inset-0 bg-gradient-to-t from-[#3C2F2A] via-transparent to-transparent opacity-70" />

                                <div className="absolute inset-0 flex items-center justify-center px-8">
                                    <motion.div
                                        initial={{ scale: 0.9, opacity: 0 }}
                                        whileInView={{ scale: 1, opacity: 1 }}
                                        transition={{ delay: 0.2 }}
                                        className="w-full h-full flex items-center justify-center"
                                    >
                                        {f.customVisual ? f.customVisual : <Terminal logs={f.logs || []} title={f.title} />}
                                    </motion.div>
                                </div>
                            </motion.div>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    )
}