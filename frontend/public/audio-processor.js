// AudioWorklet processor for real-time audio processing
class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    
    // Processing parameters
    this.noiseGateThreshold = -50 // dB
    this.compressionRatio = 4
    this.compressionThreshold = -20 // dB
    this.gainLevel = 1.0
    
    // Buffer for echo cancellation
    this.echoBuffer = new Float32Array(4096)
    this.echoBufferIndex = 0
    
    // Noise gate state
    this.gateOpen = false
    this.gateHysteresis = 3 // dB
    
    // Compressor state
    this.compressorGain = 1.0
    this.attackTime = 0.003 // 3ms
    this.releaseTime = 0.1 // 100ms
    
    // Spectrum analysis
    this.fftSize = 512
    this.fftBuffer = new Float32Array(this.fftSize)
    this.fftIndex = 0
    this.spectrum = new Float32Array(this.fftSize / 2)
    
    // Listen for parameter changes
    this.port.onmessage = (event) => {
      const { type, data } = event.data
      
      switch (type) {
        case 'setNoiseGate':
          this.noiseGateThreshold = data.threshold
          break
        case 'setCompression':
          this.compressionRatio = data.ratio
          this.compressionThreshold = data.threshold
          break
        case 'setGain':
          this.gainLevel = data.level
          break
        case 'setEchoCancellation':
          this.echoCancellationEnabled = data.enabled
          break
      }
    }
  }
  
  // Convert linear amplitude to dB
  linearToDb(linear) {
    return 20 * Math.log10(Math.max(linear, 1e-10))
  }
  
  // Convert dB to linear amplitude
  dbToLinear(db) {
    return Math.pow(10, db / 20)
  }
  
  // RMS calculation for level detection
  calculateRMS(samples) {
    let sum = 0
    for (let i = 0; i < samples.length; i++) {
      sum += samples[i] * samples[i]
    }
    return Math.sqrt(sum / samples.length)
  }
  
  // Noise gate processing
  processNoiseGate(samples) {
    const rms = this.calculateRMS(samples)
    const levelDb = this.linearToDb(rms)
    
    // Hysteresis for smooth gate operation
    const openThreshold = this.noiseGateThreshold
    const closeThreshold = this.noiseGateThreshold - this.gateHysteresis
    
    if (levelDb > openThreshold) {
      this.gateOpen = true
    } else if (levelDb < closeThreshold) {
      this.gateOpen = false
    }
    
    // Apply gate
    if (!this.gateOpen) {
      for (let i = 0; i < samples.length; i++) {
        samples[i] *= 0.01 // -40dB attenuation
      }
    }
    
    return samples
  }
  
  // Dynamic range compression
  processCompressor(samples) {
    const rms = this.calculateRMS(samples)
    const inputLevelDb = this.linearToDb(rms)
    
    if (inputLevelDb > this.compressionThreshold) {
      // Calculate gain reduction
      const overshoot = inputLevelDb - this.compressionThreshold
      const gainReductionDb = overshoot * (1 - 1/this.compressionRatio)
      const targetGain = this.dbToLinear(-gainReductionDb)
      
      // Smooth gain changes
      const alpha = 1 - Math.exp(-1 / (sampleRate * this.attackTime))
      this.compressorGain += alpha * (targetGain - this.compressorGain)
    } else {
      // Release
      const alpha = 1 - Math.exp(-1 / (sampleRate * this.releaseTime))
      this.compressorGain += alpha * (1.0 - this.compressorGain)
    }
    
    // Apply compression
    for (let i = 0; i < samples.length; i++) {
      samples[i] *= this.compressorGain
    }
    
    return samples
  }
  
  // Simple echo cancellation using adaptive filter
  processEchoCancellation(samples) {
    if (!this.echoCancellationEnabled) return samples
    
    for (let i = 0; i < samples.length; i++) {
      // Store current sample in echo buffer
      this.echoBuffer[this.echoBufferIndex] = samples[i]
      
      // Apply echo cancellation (simplified)
      let echoEstimate = 0
      for (let j = 1; j < Math.min(this.echoBuffer.length, 1024); j++) {
        const delayIndex = (this.echoBufferIndex - j + this.echoBuffer.length) % this.echoBuffer.length
        echoEstimate += this.echoBuffer[delayIndex] * 0.3 * Math.exp(-j * 0.001)
      }
      
      // Subtract echo estimate
      samples[i] -= echoEstimate * 0.5
      
      this.echoBufferIndex = (this.echoBufferIndex + 1) % this.echoBuffer.length
    }
    
    return samples
  }
  
  // Apply gain control
  processGain(samples) {
    for (let i = 0; i < samples.length; i++) {
      samples[i] *= this.gainLevel
      // Soft clipping to prevent distortion
      if (samples[i] > 1.0) {
        samples[i] = Math.tanh(samples[i])
      } else if (samples[i] < -1.0) {
        samples[i] = Math.tanh(samples[i])
      }
    }
    
    return samples
  }
  
  // Calculate FFT for spectrum analysis (simplified)
  updateSpectrum(samples) {
    // Add samples to FFT buffer
    for (let i = 0; i < samples.length; i++) {
      if (this.fftIndex < this.fftSize) {
        this.fftBuffer[this.fftIndex] = samples[i]
        this.fftIndex++
      }
    }
    
    // When buffer is full, calculate spectrum
    if (this.fftIndex >= this.fftSize) {
      // Simple magnitude spectrum (not actual FFT, but approximation)
      for (let i = 0; i < this.spectrum.length; i++) {
        let real = 0
        let imag = 0
        
        for (let j = 0; j < this.fftSize; j++) {
          const angle = -2 * Math.PI * i * j / this.fftSize
          real += this.fftBuffer[j] * Math.cos(angle)
          imag += this.fftBuffer[j] * Math.sin(angle)
        }
        
        this.spectrum[i] = Math.sqrt(real * real + imag * imag) / this.fftSize
      }
      
      // Send spectrum data
      this.port.postMessage({
        type: 'spectrum',
        data: Array.from(this.spectrum)
      })
      
      this.fftIndex = 0
    }
  }
  
  process(inputs, outputs, parameters) {
    const input = inputs[0]
    const output = outputs[0]
    
    if (input.length > 0) {
      const inputChannel = input[0]
      const outputChannel = output[0]
      
      // Copy input to output for processing
      let samples = new Float32Array(inputChannel)
      
      // Apply audio processing chain
      samples = this.processNoiseGate(samples)
      samples = this.processCompressor(samples)
      samples = this.processEchoCancellation(samples)
      samples = this.processGain(samples)
      
      // Update spectrum analysis
      this.updateSpectrum(samples)
      
      // Copy processed samples to output
      for (let i = 0; i < samples.length; i++) {
        outputChannel[i] = samples[i]
      }
      
      // Send processed audio data
      const rms = this.calculateRMS(samples)
      this.port.postMessage({
        type: 'audioLevel',
        data: {
          rms,
          peak: Math.max(...samples.map(Math.abs)),
          gateOpen: this.gateOpen,
          compressionGain: this.compressorGain
        }
      })
    }
    
    return true
  }
}

registerProcessor('audio-processor', AudioProcessor)