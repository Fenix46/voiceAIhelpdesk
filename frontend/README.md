# VoiceHelpDesk AI - Frontend

A modern React frontend for the VoiceHelpDesk AI system, featuring real-time voice recording, AI-powered conversations, and intelligent ticket generation.

## 🚀 Features

### Core Functionality
- **Real-time Voice Recording**: High-quality audio capture with noise reduction
- **Live Transcription**: Real-time speech-to-text with visual feedback
- **AI Conversations**: Intelligent responses and context-aware assistance
- **Ticket Generation**: Automatic support ticket creation from conversations
- **Analytics Dashboard**: Comprehensive metrics and system monitoring

### Voice Features
- **Voice Activation Detection (VAD)**: Automatic recording when speech is detected
- **Push-to-Talk**: Hold spacebar to record, release to stop
- **Audio Visualization**: Real-time audio level indicators and pulse animations
- **Noise Reduction**: Built-in audio processing for clearer recordings

### User Experience
- **Dark Mode**: Full dark/light theme support with system preference detection
- **Responsive Design**: Mobile-first design that works on all devices
- **Keyboard Shortcuts**: Full keyboard navigation and shortcuts
- **Accessibility**: WCAG 2.1 AA compliant with screen reader support
- **Offline Support**: Local data storage and sync when connection is restored

### Technical Features
- **Real-time Updates**: WebSocket integration for live data
- **State Management**: Zustand for efficient state handling
- **Data Fetching**: React Query for server state management
- **Error Boundaries**: Graceful error handling and recovery
- **Loading States**: Smart loading indicators and progress tracking

## 🛠️ Tech Stack

- **React 18** with TypeScript
- **Vite** for build tooling and development server
- **TailwindCSS** for styling with shadcn/ui components
- **React Query** for server state management
- **Zustand** for client state management
- **React Router** for navigation
- **Socket.io** for real-time communication
- **Lucide React** for icons

## 🏃‍♂️ Getting Started

### Prerequisites
- Node.js 16+ and npm
- Backend server running on port 8000 (see backend README)

### Installation

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to configure API endpoints if needed.

3. **Start development server**:
   ```bash
   npm run dev
   ```

4. **Open browser**:
   Navigate to `http://localhost:3000`

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/           # Reusable UI components
│   │   ├── ui/              # shadcn/ui base components
│   │   ├── AudioRecorder.tsx # Voice recording interface
│   │   ├── ConversationHistory.tsx
│   │   ├── MetricsDashboard.tsx
│   │   └── ...
│   ├── pages/               # Page components
│   │   ├── HomePage.tsx
│   │   ├── ConversationPage.tsx
│   │   ├── DashboardPage.tsx
│   │   └── ...
│   ├── hooks/               # Custom React hooks
│   │   ├── useVoiceActivation.ts
│   │   ├── usePushToTalk.ts
│   │   ├── useKeyboardShortcuts.ts
│   │   └── ...
│   ├── store/               # Zustand stores
│   │   ├── conversationStore.ts
│   │   └── appStore.ts
│   ├── lib/                 # Utilities and config
│   │   ├── utils.ts
│   │   ├── queryClient.ts
│   │   └── socket.ts
│   └── providers/           # React context providers
├── public/                  # Static assets
└── ...config files
```

## 🎯 Key Components

### AudioRecorder
The main voice input component featuring:
- Multiple recording modes (manual, push-to-talk, voice activation)
- Real-time audio visualization
- WebSocket streaming to backend
- Error handling and user feedback

### ConversationHistory
Chat-like interface displaying:
- User messages and AI responses
- Audio playback for recorded messages
- Message actions (copy, replay audio)
- Session statistics

### MetricsDashboard
Real-time analytics showing:
- System performance metrics
- User engagement statistics
- Connection status and health checks
- Historical trend data

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + N` | Start new conversation |
| `Ctrl/Cmd + D` | Go to dashboard |
| `Ctrl/Cmd + T` | Go to tickets |
| `Ctrl/Cmd + ,` | Open settings |
| `Ctrl/Cmd + H` | Go to home |
| `R` | Start recording (on conversation page) |
| `Esc` | Stop recording |
| `Space` | Push-to-talk (when enabled) |
| `Shift + C` | Clear conversation |
| `?` | Show help |

## 🎨 Theming

The application supports full dark/light mode theming:

- **System**: Follows OS preference (default)
- **Light**: Light theme
- **Dark**: Dark theme

Themes are implemented using CSS custom properties and TailwindCSS classes.

## ♿ Accessibility

### Features Implemented
- **WCAG 2.1 AA** compliance
- **Screen reader** support with ARIA labels
- **Keyboard navigation** for all interactive elements
- **High contrast** mode support
- **Reduced motion** preference respect
- **Skip links** for main content and navigation
- **Focus management** with visible focus indicators

### Screen Reader Support
- Live regions for status updates
- Descriptive labels for all controls
- Proper heading hierarchy
- Alternative text for visual elements

## 📱 Responsive Design

The interface is fully responsive with breakpoints for:
- **Mobile**: 320px+
- **Tablet**: 768px+
- **Desktop**: 1024px+
- **Large**: 1280px+

Mobile-specific features:
- Touch-friendly controls
- Optimized navigation
- Gesture support for audio recording

## 🔌 API Integration

### REST Endpoints
- `GET /api/health` - System health check
- `GET /api/metrics` - Analytics data
- `GET /api/tickets` - Support tickets
- `POST /api/tickets` - Create ticket

### WebSocket Events
- `audio-chunk` - Streaming audio data
- `transcript-partial` - Live transcription
- `transcript-final` - Completed transcription
- `error` - Error notifications

## 🔧 Available Scripts

```bash
npm run dev          # Start development server
npm run build        # Build for production
npm run preview      # Preview production build
npm run lint         # Run ESLint
npm run type-check   # Run TypeScript checks
```

## 🌐 Browser Support

- **Chrome**: 90+
- **Firefox**: 88+
- **Safari**: 14+
- **Edge**: 90+

## 📋 Environment Variables

```bash
# API Configuration
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# Feature Flags
VITE_ENABLE_ANALYTICS=true
VITE_ENABLE_NOTIFICATIONS=true
VITE_ENABLE_OFFLINE_MODE=true

# Audio Settings
VITE_MAX_RECORDING_DURATION=300000
VITE_AUDIO_SAMPLE_RATE=16000
VITE_AUDIO_CHUNK_SIZE=1024

# Development
VITE_DEBUG_MODE=false
VITE_LOG_LEVEL=info
```

## 🚀 Production Deployment

1. **Build the application**:
   ```bash
   npm run build
   ```

2. **Serve static files**:
   The `dist/` folder contains all static assets ready for deployment.

3. **Configure server**:
   Ensure your web server supports SPA routing by redirecting all routes to `index.html`.

## 🤝 Contributing

1. Follow the existing code style and conventions
2. Add TypeScript types for all new code
3. Include accessibility attributes for UI components
4. Test responsive design on multiple screen sizes
5. Verify keyboard navigation works properly

## 📄 License

This project is part of the VoiceHelpDesk AI system. See the main project README for license information.
