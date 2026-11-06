import { User, FileText, Link2, CheckCircle2, ArrowRight } from 'lucide-react'

const steps = [
  {
    step: '01',
    title: 'Click on Profile',
    desc: 'Tap the profile icon in the top right corner of the navigation bar.',
    icon: User,
  },
  {
    step: '02',
    title: http://localhost:5173/'Enter your details',
    desc: 'Add your display name so friends can recognize you on the leaderboard.',
    icon: FileText,
  },
  {
    step: '03',
    title: "Enter your competitive site's profile link",
    subtitle: '(For now we only support LeetCode)',
    desc: 'Paste your LeetCode profile URL (e.g. leetcode.com/username) or handle.',
    icon: Link2,
  },
  {
    step: '04',
    title: 'Done!',
    desc: 'Your stats, difficulty breakdown, and friends ranking sync automatically.',
    icon: CheckCircle2,
  },
]

export default function HowItWorks({ onOpenLogin }) {
  return (
    <section
      id="how-it-works-section"
      className="relative border-t border-[#2a2d35] bg-[#121316]/50 py-24 px-4 sm:px-6 lg:px-8"
    >
      <div className="mx-auto max-w-5xl">
        {/* Section Header */}
        <div className="text-center space-y-3 mb-16">
          <span className="inline-block rounded-full bg-purple-950/80 px-3.5 py-1 text-xs font-semibold text-purple-300 border border-purple-800/40 uppercase tracking-wider">
            Quick Start Guide
          </span>
          <h2 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-white">
            How Login & Profile Creation Works
          </h2>
          <p className="text-sm sm:text-base text-gray-400 max-w-2xl mx-auto">
            Get up and running in less than 30 seconds. No password or complex setup required.
          </p>
        </div>

        {/* Step Flow Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 relative">
          {steps.map((item, idx) => {
            const Icon = item.icon
            return (
              <div
                key={item.step}
                className="group relative flex flex-col justify-between rounded-2xl border border-[#2a2d35] bg-[#16181c] p-6 shadow-md transition-all duration-300 hover:border-purple-500/50 hover:bg-[#1a1c22] hover:-translate-y-1"
              >
                <div>
                  {/* Step Badge & Icon */}
                  <div className="flex items-center justify-between mb-5">
                    <span className="font-heading text-xs font-extrabold text-purple-400 bg-purple-950/60 px-2.5 py-1 rounded-md border border-purple-800/30">
                      STEP {item.step}
                    </span>
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#20222a] text-purple-300 group-hover:bg-purple-600 group-hover:text-white transition-colors">
                      <Icon className="h-5 w-5" />
                    </div>
                  </div>

                  {/* Title & Desc */}
                  <h3 className="font-heading text-lg font-semibold text-gray-100 mb-1">
                    {item.title}
                  </h3>
                  {item.subtitle && (
                    <p className="text-xs font-medium text-amber-400/90 mb-2">
                      {item.subtitle}
                    </p>
                  )}
                  <p className="text-xs text-gray-400 leading-relaxed">
                    {item.desc}
                  </p>
                </div>

                {/* Arrow Connector on desktop */}
                {idx < steps.length - 1 && (
                  <div className="hidden lg:block absolute -right-3 top-1/2 -translate-y-1/2 z-10 text-gray-600">
                    →
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Action Button after the steps */}
        <div className="mt-16 text-center">
          <button
            type="button"
            onClick={onOpenLogin}
            className="group inline-flex items-center gap-3 rounded-xl bg-linear-to-r from-purple-600 via-fuchsia-600 to-indigo-600 px-8 py-3.5 text-base font-semibold text-white shadow-xl shadow-purple-600/30 hover:opacity-95 hover:scale-[1.02] active:scale-[0.98] transition-all"
          >
            <span>Log In & Connect LeetCode</span>
            <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
          </button>
          <p className="mt-3 text-xs text-gray-500">
            Supports both public LeetCode handles and full profile URLs.
          </p>
        </div>
      </div>
    </section>
  )
}
