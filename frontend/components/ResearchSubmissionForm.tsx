'use client'

import { useState, useEffect } from 'react'
import { X } from 'lucide-react'

interface FormData {
    name: string
    email: string
    researchTopic: string
    whyInterested: string
    documentsUrls: string[]
    datasetUrl: string
    subscribeToBlog: boolean
}

export default function ResearchSubmissionForm() {
    const [isOpen, setIsOpen] = useState(false)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [submitted, setSubmitted] = useState(false)
    const [urlInput, setUrlInput] = useState('')
    const [errors, setErrors] = useState<Record<string, string>>({})

    const [formData, setFormData] = useState<FormData>({
        name: '',
        email: '',
        researchTopic: '',
        whyInterested: '',
        documentsUrls: [],
        datasetUrl: '',
        subscribeToBlog: false,
    })

    // Show popup after 10 seconds
    useEffect(() => {
        const timer = setTimeout(() => {
            setIsOpen(true)
        }, 10000)
        return () => clearTimeout(timer)
    }, [])

    const validateForm = (): boolean => {
        const newErrors: Record<string, string> = {}

        if (!formData.name.trim()) newErrors.name = 'Name is required'
        if (!formData.email.trim()) newErrors.email = 'Email is required'
        if (!formData.email.includes('@')) newErrors.email = 'Valid email required'
        if (!formData.researchTopic.trim()) newErrors.researchTopic = 'Research topic is required'
        if (!formData.whyInterested.trim()) newErrors.whyInterested = 'Please explain your interest'

        setErrors(newErrors)
        return Object.keys(newErrors).length === 0
    }

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        const { name, value } = e.target
        setFormData(prev => ({
            ...prev,
            [name]: value
        }))
        if (errors[name]) {
            setErrors(prev => ({
                ...prev,
                [name]: ''
            }))
        }
    }

    const handleCheckbox = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData(prev => ({
            ...prev,
            subscribeToBlog: e.target.checked
        }))
    }

    const addUrl = () => {
        if (urlInput.trim()) {
            setFormData(prev => ({
                ...prev,
                documentsUrls: [...prev.documentsUrls, urlInput.trim()]
            }))
            setUrlInput('')
        }
    }

    const removeUrl = (index: number) => {
        setFormData(prev => ({
            ...prev,
            documentsUrls: prev.documentsUrls.filter((_, i) => i !== index)
        }))
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        if (!validateForm()) return

        setIsSubmitting(true)

        try {
            const response = await fetch('/api/submissions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData),
            })

            if (!response.ok) throw new Error('Submission failed')

            const data = await response.json()
            console.log('✅ Submission successful:', data)

            setSubmitted(true)
            setTimeout(() => {
                setIsOpen(false)
                setSubmitted(false)
                setFormData({
                    name: '',
                    email: '',
                    researchTopic: '',
                    whyInterested: '',
                    documentsUrls: [],
                    datasetUrl: '',
                    subscribeToBlog: false,
                })
            }, 3000)
        } catch (error) {
            console.error('❌ Error:', error)
            setErrors(prev => ({
                ...prev,
                submit: 'Failed to submit. Please try again.'
            }))
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <>
            {/* Trigger Button */}
            <button
                onClick={() => setIsOpen(true)}
                className="px-4 py-2 bg-[#E05240] text-white rounded-lg hover:bg-[#D04130] transition-colors"
            >
                Submit Research Topic
            </button>

            {/* Modal */}
            {isOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
                    onClick={() => setIsOpen(false)}
                >
                    <div
                        className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
                        onClick={e => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="sticky top-0 bg-white border-b border-gray-200 p-6 flex items-center justify-between">
                            <div>
                                <h2 className="text-2xl font-bold text-gray-900">Submit Your Research Topic</h2>
                                <p className="text-gray-600 text-sm mt-1">
                                    Join our research community. Get selected daily for autonomous research.
                                </p>
                            </div>
                            <button
                                onClick={() => setIsOpen(false)}
                                className="text-gray-400 hover:text-gray-600"
                            >
                                <X size={24} />
                            </button>
                        </div>

                        {/* Success State */}
                        {submitted ? (
                            <div className="p-8 text-center">
                                <div className="w-16 h-16 bg-green-100 border-2 border-green-500 rounded-full flex items-center justify-center mx-auto mb-4">
                                    <span className="text-2xl">✓</span>
                                </div>
                                <h3 className="text-xl font-bold text-gray-900 mb-2">Submission Received!</h3>
                                <p className="text-gray-600 mb-6">
                                    Your research topic has been submitted. We'll evaluate it nightly.
                                </p>
                            </div>
                        ) : (
                            /* Form */
                            <form onSubmit={handleSubmit} className="p-8 space-y-6">
                                {/* Name */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-900 mb-2">
                                        Name *
                                    </label>
                                    <input
                                        type="text"
                                        name="name"
                                        value={formData.name}
                                        onChange={handleChange}
                                        placeholder="Your name"
                                        className={`w-full px-4 py-2 rounded-lg border ${errors.name ? 'border-red-500' : 'border-gray-300'
                                            } text-gray-900 placeholder-gray-500 focus:outline-none focus:border-[#E05240]`}
                                    />
                                    {errors.name && <p className="text-red-500 text-sm mt-1">{errors.name}</p>}
                                </div>

                                {/* Email */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-900 mb-2">
                                        Email *
                                    </label>
                                    <input
                                        type="email"
                                        name="email"
                                        value={formData.email}
                                        onChange={handleChange}
                                        placeholder="your.email@example.com"
                                        className={`w-full px-4 py-2 rounded-lg border ${errors.email ? 'border-red-500' : 'border-gray-300'
                                            } text-gray-900 placeholder-gray-500 focus:outline-none focus:border-[#E05240]`}
                                    />
                                    {errors.email && <p className="text-red-500 text-sm mt-1">{errors.email}</p>}
                                </div>

                                {/* Research Topic */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-900 mb-2">
                                        Research Topic *
                                    </label>
                                    <textarea
                                        name="researchTopic"
                                        value={formData.researchTopic}
                                        onChange={handleChange}
                                        placeholder="e.g., Quantum computing applications in drug discovery"
                                        rows={3}
                                        className={`w-full px-4 py-2 rounded-lg border ${errors.researchTopic ? 'border-red-500' : 'border-gray-300'
                                            } text-gray-900 placeholder-gray-500 focus:outline-none focus:border-[#E05240] resize-none`}
                                    />
                                    {errors.researchTopic && <p className="text-red-500 text-sm mt-1">{errors.researchTopic}</p>}
                                </div>

                                {/* Why Interested */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-900 mb-2">
                                        Why are you interested in this topic? *
                                    </label>
                                    <textarea
                                        name="whyInterested"
                                        value={formData.whyInterested}
                                        onChange={handleChange}
                                        placeholder="Tell us about your interest and background..."
                                        rows={3}
                                        className={`w-full px-4 py-2 rounded-lg border ${errors.whyInterested ? 'border-red-500' : 'border-gray-300'
                                            } text-gray-900 placeholder-gray-500 focus:outline-none focus:border-[#E05240] resize-none`}
                                    />
                                    {errors.whyInterested && <p className="text-red-500 text-sm mt-1">{errors.whyInterested}</p>}
                                </div>

                                {/* Document URLs */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-900 mb-2">
                                        Document or URL Links
                                    </label>
                                    <div className="flex gap-2 mb-3">
                                        <input
                                            type="url"
                                            value={urlInput}
                                            onChange={e => setUrlInput(e.target.value)}
                                            placeholder="https://example.com/paper.pdf"
                                            className="flex-1 px-4 py-2 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-500 focus:outline-none focus:border-[#E05240]"
                                            onKeyPress={e => {
                                                if (e.key === 'Enter') {
                                                    e.preventDefault()
                                                    addUrl()
                                                }
                                            }}
                                        />
                                        <button
                                            type="button"
                                            onClick={addUrl}
                                            className="px-4 py-2 bg-[#E05240]/20 border border-[#E05240] text-[#E05240] rounded-lg hover:bg-[#E05240]/30"
                                        >
                                            Add
                                        </button>
                                    </div>
                                    {formData.documentsUrls.length > 0 && (
                                        <div className="space-y-2">
                                            {formData.documentsUrls.map((url, index) => (
                                                <div
                                                    key={index}
                                                    className="flex items-center justify-between bg-gray-100 p-2 rounded border border-gray-300 text-sm"
                                                >
                                                    <span className="text-gray-700 truncate">{url}</span>
                                                    <button
                                                        type="button"
                                                        onClick={() => removeUrl(index)}
                                                        className="text-red-500 hover:text-red-700"
                                                    >
                                                        ✕
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Dataset URL */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-900 mb-2">
                                        Dataset (if available)
                                    </label>
                                    <input
                                        type="url"
                                        name="datasetUrl"
                                        value={formData.datasetUrl}
                                        onChange={handleChange}
                                        placeholder="https://example.com/dataset"
                                        className="w-full px-4 py-2 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-500 focus:outline-none focus:border-[#E05240]"
                                    />
                                </div>

                                {/* Subscribe Checkbox */}
                                <div className="flex items-center gap-3 p-4 bg-[#E05240]/10 border border-[#E05240]/30 rounded-lg">
                                    <input
                                        type="checkbox"
                                        id="subscribeToBlog"
                                        checked={formData.subscribeToBlog}
                                        onChange={handleCheckbox}
                                        className="w-4 h-4 rounded border-[#E05240] cursor-pointer"
                                    />
                                    <label htmlFor="subscribeToBlog" className="flex-1 text-gray-900 cursor-pointer">
                                        <div className="font-medium">Subscribe to our blog posts</div>
                                        <div className="text-sm text-gray-600">
                                            Get notified when research papers are published
                                        </div>
                                    </label>
                                </div>

                                {/* Error Message */}
                                {errors.submit && (
                                    <div className="p-3 bg-red-100 border border-red-300 rounded text-red-700 text-sm">
                                        {errors.submit}
                                    </div>
                                )}

                                {/* Submit Button */}
                                <button
                                    type="submit"
                                    disabled={isSubmitting}
                                    className="w-full py-3 bg-[#E05240] text-white font-semibold rounded-lg hover:bg-[#D04130] transition-all disabled:opacity-50"
                                >
                                    {isSubmitting ? 'Submitting...' : 'Submit Research Topic'}
                                </button>

                                <p className="text-gray-500 text-xs text-center">
                                    Your submission will be evaluated nightly. If selected, autonomous research will begin at midnight.
                                </p>
                            </form>
                        )}
                    </div>
                </div>
            )}
        </>
    )
}