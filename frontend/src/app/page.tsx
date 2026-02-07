'use client'

import { useState } from 'react'

export default function Home() {
  const [activeView, setActiveView] = useState('overview')

  const stats = [
    { label: 'Active Data Sources', value: '12', change: '+2', trend: 'up' },
    { label: 'Processing Rate', value: '1.2M/s', change: '+15%', trend: 'up' },
    { label: 'System Health', value: '98.5%', change: '-0.2%', trend: 'down' },
    { label: 'Active Alerts', value: '3', change: '-5', trend: 'up' },
  ]

  const recentActivity = [
    { id: 1, type: 'ingestion', message: 'New data batch processed from Sensor Array A', time: '2 min ago' },
    { id: 2, type: 'alert', message: 'Anomaly detected in temperature readings', time: '5 min ago' },
    { id: 3, type: 'system', message: 'Model retraining completed successfully', time: '12 min ago' },
    { id: 4, type: 'ingestion', message: 'Historical data import finished', time: '1 hour ago' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Data Fusion Dashboard</h1>
          <p className="text-muted-foreground">
            Monitor and manage your data fusion operations in real-time
          </p>
        </div>
        <div className="flex gap-2">
          <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors">
            New Data Source
          </button>
          <button className="px-4 py-2 border border-input bg-background hover:bg-accent rounded-md transition-colors">
            Export Report
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, index) => (
          <div key={index} className="p-6 rounded-lg border bg-card card-hover">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-muted-foreground">{stat.label}</span>
              <span className={
                stat.trend === 'up' ? 'text-xs px-2 py-1 rounded-full bg-green-100 text-green-700' : 'text-xs px-2 py-1 rounded-full bg-red-100 text-red-700'
              }>
                {stat.change}
              </span>
            </div>
            <div className="mt-2 text-3xl font-bold">{stat.value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 rounded-lg border bg-card p-6">
          <h2 className="text-lg font-semibold mb-4">Recent Activity</h2>
          <div className="space-y-4">
            {recentActivity.map((activity) => (
              <div key={activity.id} className="flex items-start gap-4 p-3 rounded-md hover:bg-muted/50 transition-colors">
                <div className={
                  activity.type === 'alert' ? 'w-2 h-2 mt-2 rounded-full bg-red-500' :
                  activity.type === 'ingestion' ? 'w-2 h-2 mt-2 rounded-full bg-blue-500' : 'w-2 h-2 mt-2 rounded-full bg-green-500'
                } />
                <div className="flex-1">
                  <p className="text-sm">{activity.message}</p>
                  <span className="text-xs text-muted-foreground">{activity.time}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
          <div className="space-y-3">
            <button className="w-full p-3 text-left rounded-md border hover:bg-muted/50 transition-colors">
              <div className="font-medium">Run Data Pipeline</div>
              <div className="text-sm text-muted-foreground">Process pending data batches</div>
            </button>
            <button className="w-full p-3 text-left rounded-md border hover:bg-muted/50 transition-colors">
              <div className="font-medium">View Analytics</div>
              <div className="text-sm text-muted-foreground">Open detailed analytics view</div>
            </button>
            <button className="w-full p-3 text-left rounded-md border hover:bg-muted/50 transition-colors">
              <div className="font-medium">Configure Alerts</div>
              <div className="text-sm text-muted-foreground">Manage alert thresholds</div>
            </button>
            <button className="w-full p-3 text-left rounded-md border hover:bg-muted/50 transition-colors">
              <div className="font-medium">System Settings</div>
              <div className="text-sm text-muted-foreground">Adjust system configuration</div>
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">Data Sources Status</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left p-3 font-medium">Source Name</th>
                <th className="text-left p-3 font-medium">Type</th>
                <th className="text-left p-3 font-medium">Status</th>
                <th className="text-left p-3 font-medium">Last Update</th>
                <th className="text-left p-3 font-medium">Records/min</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b hover:bg-muted/50">
                <td className="p-3">Sensor Array A</td>
                <td className="p-3">IoT Stream</td>
                <td className="p-3"><span className="status-online">Online</span></td>
                <td className="p-3">Just now</td>
                <td className="p-3">12,450</td>
              </tr>
              <tr className="border-b hover:bg-muted/50">
                <td className="p-3">Database Sync</td>
                <td className="p-3">PostgreSQL</td>
                <td className="p-3"><span className="status-online">Online</span></td>
                <td className="p-3">30 sec ago</td>
                <td className="p-3">8,320</td>
              </tr>
              <tr className="border-b hover:bg-muted/50">
                <td className="p-3">API Gateway</td>
                <td className="p-3">REST API</td>
                <td className="p-3"><span className="status-pending">Syncing</span></td>
                <td className="p-3">2 min ago</td>
                <td className="p-3">5,100</td>
              </tr>
              <tr className="hover:bg-muted/50">
                <td className="p-3">Legacy System</td>
                <td className="p-3">File Import</td>
                <td className="p-3"><span className="status-offline">Offline</span></td>
                <td className="p-3">1 hour ago</td>
                <td className="p-3">0</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
