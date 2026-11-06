import { ChevronDown, Sparkles, ArrowRight } from 'lucide-react'
import sadEmoji from '../../assets/images/sad-emoji-on-logged-out.png'

export default function LoggedOutHero({ onOpenLogin }) {
  const scrollToHowItWorks = () => {
    const el = document.getElementById('how-it-works-section')
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <div className="relative flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center px-4 py-12 text-center">
      {/* Background radial gradient glow */}
      <div className="pointer-events-none absolute inset-0 -z-10 flex items-center justify-center overflow-hidden">
        <div className="h-100 w-[500px] rounded-full bg-purple-900/15 blur-[120px]" />
      </div>

      <div className="flex max-w-xl flex-col items-center gap-6">
        {/* Sad emoji at center */}
        <div className="relative group">
          <div className="absolute -inset-2 rounded-full bg-linear-to-r from-purple-600/30 to-pink-600/30 blur-xl opacity-75 group-hover:opacity-100 transition duration-500" />
          <img
            src={sadEmoji}
            alt="Seems you are not logged in"
            className="relative h-44 w-44 sm:h-52 sm:w-52 object-contain drop-shadow-2xl transition-transform duration-300 hover:scale-105"
          />
        </div>

        {/* Funky Heading */}
        <div className="space-y-2">
          <h1 className="font-heading text-3xl sm:text-5xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-b from-gray-100 via-gray-200 to-gray-400">
            seems you are not logged in
          </h1>
          <p className="text-sm sm:text-base text-gray-400 max-w-md mx-auto">
            Unlock head-to-head developer comparisons, track solving streaks, and compete with friends on the leaderboard.
          </p>
        </div>

        <button
          type="button"
          onClick={onOpenLogin}
          className="group inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 px-7 py-3 text-sm font-semibold text-white shadow-lg shadow-purple-600/25 transition-all hover:from-purple-500 hover:to-indigo-500 hover:shadow-purple-600/40 hover:scale-[1.02] active:scale-[0.98]"
        >
          <Sparkles className="h-4 w-4 text-purple-200" />
          <span>Connect Profile & Log In</span>
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>

      {/* Scroll Down Indicator */}
      <button
        type="button"
        onClick={scrollToHowItWorks}
        className="mt-16 flex flex-col items-center gap-1.5 text-xs text-gray-400 hover:text-purple-300 transition-colors animate-bounce cursor-pointer"
        aria-label="Scroll to how it works"
      >
        <span>How it works</span>
        <ChevronDown className="h-4 w-4" />
      </button>
    </div>
  )
}
