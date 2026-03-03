import { io } from 'socket.io-client'
import type { Socket } from 'socket.io-client'

class SocketManager {
  private socket: Socket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5

  connect() {
    if (this.socket?.connected) return this.socket

    this.socket = io(import.meta.env.VITE_WS_URL || 'ws://localhost:8000', {
      transports: ['websocket'],
      autoConnect: true,
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: this.maxReconnectAttempts,
    })

    this.socket.on('connect', () => {
      console.log('Socket connected')
      this.reconnectAttempts = 0
    })

    this.socket.on('disconnect', (reason: string) => {
      console.log('Socket disconnected:', reason)
    })

    this.socket.on('connect_error', (error: Error) => {
      console.error('Socket connection error:', error)
      this.reconnectAttempts++
    })

    return this.socket
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }
  }

  getSocket() {
    return this.socket
  }

  isConnected() {
    return this.socket?.connected || false
  }
}

export const socketManager = new SocketManager()
export default socketManager
