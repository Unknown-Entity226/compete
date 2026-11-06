import { useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { Layers, Info } from 'lucide-react'

const TOPIC_PALETTE = [
  '#a855f7', // purple-500
  '#ec4899', // pink-500
  '#6366f1', // indigo-500
  '#3b82f6', // blue-500
  '#06b6d4', // cyan-500
  '#10b981', // emerald-500
  '#f59e0b', // amber-500
  '#8b5cf6', // violet-500
]

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload
    return (
      <div className="rounded-xl border border-[#2a2d35] bg-[#1a1c23] p-3 shadow-xl">
        <p className="font-heading text-xs font-semibold text-gray-200">
          {data.topic}
        </p>
        <p className="font-mono text-sm font-bold text-purple-400 mt-0.5">
          {data.count} <span className="text-[11px] font-normal text-gray-400">problems solved</span>
        </p>
      </div>
    )
  }
  return null
}

export default function TopicBreakdownChart({ topicStats }) {
  const [activeTopic, setActiveTopic] = useState(null)

  const data = (Array.isArray(topicStats) ? topicStats : [])
    .filter((item) => item && typeof item === 'object')
    .slice(0, 8)
    .map((item) => ({
      topic: item.topic || item.tagName || 'Unknown',
      count: Number(item.count ?? item.problemsSolved ?? 0),
    }))
    .filter((item) => Number.isFinite(item.count) && item.count >= 0)

  return (
    <div className="rounded-2xl border border-[#2a2d35] bg-[#16181c] p-6 shadow-xl flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between pb-3 border-b border-[#2a2d35]/60 mb-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-950/60 text-purple-400 border border-purple-800/30">
              <Layers className="h-4 w-4" />
            </div>
            <div>
              <h3 className="font-heading text-base font-bold text-white">
                Solved Questions by Topic
              </h3>
              <p className="text-xs text-gray-400">
                Hover bars to inspect algorithmic mastery
              </p>
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-1 text-[11px] text-gray-500">
            <Info className="h-3.5 w-3.5" />
            <span>Top Categories</span>
          </div>
        </div>

        {/* Interactive Chart Container */}
        <div className="h-[270px] w-full pt-2">
          {data.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                onMouseMove={(state) => {
                  if (state?.activePayload?.[0]) {
                    setActiveTopic(state.activePayload[0].payload.topic)
                  }
                }}
                onMouseLeave={() => setActiveTopic(null)}
              >
                <XAxis
                  type="number"
                  stroke="#6b7280"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="topic"
                  stroke="#9ca3af"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  width={120}
                />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(168, 85, 247, 0.08)' }} />
                <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                  {data.map((entry, index) => {
                    const isHovered = activeTopic === entry.topic
                    const fill = TOPIC_PALETTE[index % TOPIC_PALETTE.length]
                    return (
                      <Cell
                        key={`${entry.topic}-${index}`}
                        fill={fill}
                        opacity={activeTopic && !isHovered ? 0.45 : 1}
                        className="transition-opacity duration-200"
                      />
                    )
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-[#2a2d35] bg-[#121316]/60 px-6 text-center text-sm text-gray-500">
              Topic breakdown is not available for this profile yet.
            </div>
          )}
        </div>
      </div>

      {/* Pill summary footer */}
      {data.length > 0 && <div className="mt-2 pt-3 border-t border-[#2a2d35]/40 flex flex-wrap gap-1.5">
        {data.slice(0, 4).map((d) => (
          <span
            key={d.topic}
            className="rounded-md bg-[#20222a] px-2 py-0.5 text-[10px] text-gray-300 font-medium border border-[#2a2d35]"
          >
            {d.topic}: <strong className="text-purple-300">{d.count}</strong>
          </span>
        ))}
      </div>}
    </div>
  )
}
