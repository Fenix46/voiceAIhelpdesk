import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { StatusIndicator } from '@/components/StatusIndicator'
import { 
  Mic, 
  Headphones, 
  MessageSquare, 
  ArrowRight,
  CheckCircle,
  Zap,
  Shield,
  BarChart3
} from 'lucide-react'

const features = [
  {
    icon: Mic,
    title: 'Voice Recognition',
    description: 'Advanced speech-to-text with real-time transcription and noise reduction'
  },
  {
    icon: MessageSquare,
    title: 'Smart Conversations',
    description: 'AI-powered responses that understand context and provide helpful solutions'
  },
  {
    icon: CheckCircle,
    title: 'Ticket Generation',
    description: 'Automatically create and manage support tickets from conversations'
  },
  {
    icon: BarChart3,
    title: 'Analytics Dashboard',
    description: 'Real-time metrics and insights into system performance and user satisfaction'
  }
]

const benefits = [
  { icon: Zap, text: 'Instant voice-to-text processing' },
  { icon: Shield, text: 'Secure and private conversations' },
  { icon: Headphones, text: '24/7 AI support assistant' },
  { icon: BarChart3, text: 'Comprehensive analytics' }
]

export function HomePage() {
  const navigate = useNavigate()

  const handleStartConversation = () => {
    navigate('/conversation')
  }

  return (
    <div className="max-w-6xl mx-auto space-y-16 py-8">
      {/* Hero Section */}
      <div className="text-center space-y-8">
        <div className="space-y-4">
          <h1 className="text-4xl md:text-6xl font-bold tracking-tight">
            Voice-Powered
            <span className="text-primary block">Help Desk AI</span>
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            Transform customer support with intelligent voice recognition, 
            real-time transcription, and automated ticket generation.
          </p>
        </div>

        {/* Status and CTA */}
        <div className="space-y-6">
          <div className="flex justify-center">
            <div className="bg-card border rounded-full px-4 py-2">
              <StatusIndicator />
            </div>
          </div>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button 
              size="lg" 
              onClick={handleStartConversation}
              className="text-lg px-8 py-6 h-auto"
            >
              <Mic className="mr-2" size={20} />
              Start Conversation
              <ArrowRight className="ml-2" size={20} />
            </Button>
            <Button 
              size="lg" 
              variant="outline"
              onClick={() => navigate('/dashboard')}
              className="text-lg px-8 py-6 h-auto"
            >
              <BarChart3 className="mr-2" size={20} />
              View Dashboard
            </Button>
          </div>
        </div>
      </div>

      {/* Features Grid */}
      <div className="space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold mb-4">Powerful Features</h2>
          <p className="text-muted-foreground text-lg">
            Everything you need for modern voice-powered customer support
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {features.map((feature, index) => {
            const Icon = feature.icon
            return (
              <div 
                key={index}
                className="bg-card border rounded-lg p-6 hover:shadow-lg transition-shadow"
              >
                <div className="flex items-start space-x-4">
                  <div className="p-3 bg-primary/10 rounded-lg">
                    <Icon size={24} className="text-primary" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-lg mb-2">{feature.title}</h3>
                    <p className="text-muted-foreground leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Benefits Section */}
      <div className="bg-muted/50 rounded-2xl p-8 md:p-12">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-4">Why Choose VoiceHelpDesk?</h2>
          <p className="text-muted-foreground text-lg">
            Built for modern support teams who value efficiency and customer satisfaction
          </p>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          {benefits.map((benefit, index) => {
            const Icon = benefit.icon
            return (
              <div key={index} className="flex items-center space-x-3">
                <div className="p-2 bg-primary/10 rounded-full">
                  <Icon size={16} className="text-primary" />
                </div>
                <span className="font-medium">{benefit.text}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 text-center">
        <div className="space-y-2">
          <div className="text-3xl font-bold text-primary">99.9%</div>
          <div className="text-sm text-muted-foreground">Uptime Guarantee</div>
        </div>
        <div className="space-y-2">
          <div className="text-3xl font-bold text-primary">&lt;2s</div>
          <div className="text-sm text-muted-foreground">Response Time</div>
        </div>
        <div className="space-y-2">
          <div className="text-3xl font-bold text-primary">24/7</div>
          <div className="text-sm text-muted-foreground">AI Support</div>
        </div>
      </div>

      {/* Getting Started */}
      <div className="text-center space-y-6 bg-primary/5 rounded-2xl p-8 md:p-12">
        <h2 className="text-2xl font-bold">Ready to Get Started?</h2>
        <p className="text-muted-foreground">
          Join thousands of teams already using VoiceHelpDesk to revolutionize their customer support.
        </p>
        <Button 
          size="lg" 
          onClick={handleStartConversation}
          className="text-lg px-8 py-6 h-auto"
        >
          Start Your First Conversation
          <ArrowRight className="ml-2" size={20} />
        </Button>
      </div>
    </div>
  )
}