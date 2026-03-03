"""
Demo script showing VoiceHelpDeskAI audio system capabilities.

This script demonstrates:
1. AudioProcessor with real-time recording and processing
2. VoiceActivityDetector with multiple algorithms
3. AudioStreamManager for WebSocket streaming
4. AudioQueue system for buffering and processing
5. Error handling and recovery
"""

import asyncio
import time
import numpy as np
from pathlib import Path

from voicehelpdeskai.core.audio import (
    AudioProcessor,
    AudioStreamManager,
    VoiceActivityDetector,
    AudioQueue,
    PriorityAudioQueue,
)
from voicehelpdeskai.core.audio.queue_system import Priority, AudioQueueManager
from voicehelpdeskai.core.audio.vad import VADConfig, VADMode
from voicehelpdeskai.core.audio.error_handler import with_error_handling, get_error_handler
from voicehelpdeskai.core.audio.utils import AudioAnalyzer, AudioNormalizer, save_audio_safely
from voicehelpdeskai.config.manager import get_config_manager


def demo_audio_processor():
    """Demonstrate AudioProcessor capabilities."""
    print("\n=== AudioProcessor Demo ===")
    
    try:
        # Initialize processor
        processor = AudioProcessor()
        
        # Get audio device info
        processor.initialize_pyaudio()
        print(f"Default input device: {processor.get_default_input_device()}")
        print(f"Default output device: {processor.get_default_output_device()}")
        
        # Test audio processing
        print("\n1. Testing audio format conversion...")
        test_audio = np.random.normal(0, 0.1, 16000).astype(np.float32)  # 1 second of noise
        
        # Convert to different formats
        wav_data = processor.convert_format(test_audio, "wav")
        print(f"WAV conversion: {len(wav_data)} bytes")
        
        # Test resampling
        print("\n2. Testing audio resampling...")
        resampled = processor.resample_audio(test_audio, 16000, 8000)
        print(f"Resampled from 16kHz to 8kHz: {len(test_audio)} -> {len(resampled)} samples")
        
        # Test audio processing
        print("\n3. Testing audio processing pipeline...")
        processed = processor.process_audio_chunk(test_audio)
        print(f"Processed audio: {len(processed)} samples")
        
        # Get statistics
        stats = processor.get_stats()
        print(f"Processor stats: {stats}")
        
        processor.cleanup()
        print("AudioProcessor demo completed successfully!")
        
    except Exception as e:
        print(f"AudioProcessor demo failed: {e}")


def demo_voice_activity_detection():
    """Demonstrate VoiceActivityDetector capabilities."""
    print("\n=== Voice Activity Detection Demo ===")
    
    try:
        # Test different VAD modes
        vad_configs = [
            VADConfig(mode=VADMode.ENERGY_BASED),
            VADConfig(mode=VADMode.WEBRTC),
            VADConfig(mode=VADMode.HYBRID),
            VADConfig(mode=VADMode.SILENCE_BASED),
        ]
        
        for config in vad_configs:
            print(f"\nTesting {config.mode.value} VAD...")
            
            try:
                vad = VoiceActivityDetector(config)
                
                # Test with different audio types
                silence = np.zeros(8000, dtype=np.float32)  # 0.5s silence
                noise = np.random.normal(0, 0.01, 8000).astype(np.float32)  # Low noise
                speech = np.random.normal(0, 0.1, 8000).astype(np.float32)  # Simulated speech
                
                # Test VAD
                silence_result = vad.detect(silence)
                noise_result = vad.detect(noise) 
                speech_result = vad.detect(speech)
                
                print(f"  Silence: {silence_result.is_speech} (confidence: {silence_result.confidence:.2f})")
                print(f"  Noise: {noise_result.is_speech} (confidence: {noise_result.confidence:.2f})")
                print(f"  Speech: {speech_result.is_speech} (confidence: {speech_result.confidence:.2f})")
                
                # Get statistics
                stats = vad.get_statistics()
                print(f"  VAD stats: {stats['total_detections']} detections, {stats['speech_ratio']:.2f} speech ratio")
                
            except Exception as e:
                print(f"  {config.mode.value} VAD failed: {e}")
        
        print("Voice Activity Detection demo completed!")
        
    except Exception as e:
        print(f"VAD demo failed: {e}")


def demo_audio_queue_system():
    """Demonstrate AudioQueue system capabilities."""
    print("\n=== Audio Queue System Demo ===")
    
    try:
        # Create different types of queues
        print("\n1. Testing basic AudioQueue...")
        basic_queue = AudioQueue(max_size=100)
        
        # Add some test data
        test_data = [np.random.random(1024).astype(np.float32) for _ in range(10)]
        
        for i, data in enumerate(test_data):
            chunk_id = basic_queue.put(
                data, 
                priority=Priority.NORMAL,
                source=f"test_source_{i}"
            )
            print(f"  Added chunk {i}: {chunk_id[:8]}")
        
        print(f"  Queue size: {basic_queue.size()}")
        
        # Process some chunks
        for _ in range(5):
            chunk = basic_queue.get(block=False)
            if chunk:
                basic_queue.mark_completed(chunk.metadata.chunk_id)
                print(f"  Processed chunk: {chunk.metadata.chunk_id[:8]}")
        
        stats = basic_queue.get_statistics()
        print(f"  Queue stats: {stats}")
        
        # Test priority queue
        print("\n2. Testing PriorityAudioQueue...")
        priority_queue = PriorityAudioQueue(max_size=50)
        
        # Add chunks with different priorities
        priorities = [Priority.LOW, Priority.NORMAL, Priority.HIGH, Priority.CRITICAL]
        for i, priority in enumerate(priorities):
            data = np.random.random(512).astype(np.float32)
            chunk_id = priority_queue.put(data, priority=priority, source=f"priority_test_{i}")
            print(f"  Added {priority.name} priority chunk: {chunk_id[:8]}")
        
        # Get chunks (should come out in priority order)
        print("  Processing by priority:")
        while not priority_queue.is_empty():
            chunk = priority_queue.get(block=False)
            if chunk:
                print(f"    Got {chunk.metadata.priority.name} priority chunk")
        
        # Test AudioQueueManager
        print("\n3. Testing AudioQueueManager...")
        manager = AudioQueueManager()
        
        # Create additional queues
        manager.create_queue("processing_queue", max_size=200)
        manager.create_priority_queue("urgent_queue", max_size=100)
        manager.create_circular_buffer("stream_buffer", max_size=1000)
        
        # Get statistics
        all_stats = manager.get_all_statistics()
        print(f"  Manager stats: {all_stats['total_queues']} total queues")
        
        manager.shutdown()
        basic_queue.shutdown()
        
        print("Audio Queue System demo completed!")
        
    except Exception as e:
        print(f"Queue system demo failed: {e}")


async def demo_audio_stream_manager():
    """Demonstrate AudioStreamManager capabilities."""
    print("\n=== Audio Stream Manager Demo ===")
    
    try:
        # Create stream manager
        stream_manager = AudioStreamManager()
        await stream_manager.start()
        
        print("Stream manager started")
        
        # Simulate WebSocket connections
        class MockWebSocket:
            def __init__(self, name):
                self.name = name
                self.messages = []
            
            async def send_text(self, message):
                self.messages.append(message)
                print(f"  {self.name} sent: {len(message)} bytes")
        
        # Create mock connections
        ws1 = MockWebSocket("Client1")
        ws2 = MockWebSocket("Client2")
        
        # Create streams
        stream1_id = await stream_manager.create_stream(ws1)
        stream2_id = await stream_manager.create_stream(ws2)
        
        print(f"Created streams: {stream1_id[:8]}, {stream2_id[:8]}")
        
        # Connect streams
        await stream_manager.connect_stream(stream1_id)
        await stream_manager.connect_stream(stream2_id)
        
        # Send test audio data
        test_audio = np.random.normal(0, 0.1, 1024).astype(np.float32)
        
        success_count = await stream_manager.broadcast_audio(test_audio)
        print(f"Broadcast to {success_count} streams")
        
        # Get metrics
        global_metrics = stream_manager.get_global_metrics()
        print(f"Stream metrics: {global_metrics}")
        
        stream1_metrics = stream_manager.get_stream_metrics(stream1_id)
        if stream1_metrics:
            print(f"Stream 1 metrics: {stream1_metrics}")
        
        # Disconnect streams
        await stream_manager.disconnect_stream(stream1_id)
        await stream_manager.disconnect_stream(stream2_id)
        
        await stream_manager.stop()
        print("Audio Stream Manager demo completed!")
        
    except Exception as e:
        print(f"Stream manager demo failed: {e}")


@with_error_handling(max_retries=3, fallback_result="Error handled gracefully")
def demo_error_handling():
    """Demonstrate error handling capabilities."""
    print("\n=== Error Handling Demo ===")
    
    # Simulate various errors
    error_handler = get_error_handler()
    
    print("1. Testing retry mechanism...")
    
    @with_error_handling(max_retries=2, fallback_result="Fallback used")
    def flaky_function(fail_count=1):
        flaky_function.call_count = getattr(flaky_function, 'call_count', 0) + 1
        if flaky_function.call_count <= fail_count:
            raise ConnectionError(f"Simulated failure #{flaky_function.call_count}")
        return "Success after retry"
    
    result = flaky_function(fail_count=1)
    print(f"  Result: {result}")
    
    print("\n2. Testing circuit breaker...")
    
    # Generate multiple errors to trigger circuit breaker
    for i in range(3):
        try:
            raise AudioProcessingError(f"Test error #{i+1}")
        except Exception as e:
            from voicehelpdeskai.core.audio.error_handler import ErrorContext
            context = ErrorContext(
                function_name="demo_function",
                module=__name__,
                args=(),
                kwargs={},
                timestamp=time.time(),
                attempt_count=1,
                max_attempts=1,
            )
            error_handler.record_error(e, context)
    
    # Check circuit breaker status
    print(f"  Circuit breaker open: {error_handler.is_circuit_breaker_open()}")
    
    # Get error statistics
    stats = error_handler.get_error_statistics()
    print(f"  Error stats: {stats}")
    
    # Reset for demo
    error_handler.reset_circuit_breaker()
    
    print("Error Handling demo completed!")


def demo_audio_utilities():
    """Demonstrate audio utilities."""
    print("\n=== Audio Utilities Demo ===")
    
    try:
        # Create test audio
        sample_rate = 16000
        duration = 2.0  # seconds
        test_audio = np.sin(2 * np.pi * 440 * np.linspace(0, duration, int(sample_rate * duration))).astype(np.float32)
        
        print("1. Audio analysis...")
        
        # Analyze audio
        rms = AudioAnalyzer.calculate_rms(test_audio)
        peak = AudioAnalyzer.calculate_peak(test_audio)
        clipping = AudioAnalyzer.detect_clipping(test_audio)
        
        print(f"  RMS: {rms:.4f}")
        print(f"  Peak: {peak:.4f}")
        print(f"  Clipping: {clipping}")
        
        print("\n2. Audio normalization...")
        
        # Test normalization
        normalized_peak = AudioNormalizer.normalize_peak(test_audio, target_peak=0.5)
        normalized_rms = AudioNormalizer.normalize_rms(test_audio, target_rms=0.1)
        
        print(f"  Original peak: {AudioAnalyzer.calculate_peak(test_audio):.4f}")
        print(f"  Normalized peak: {AudioAnalyzer.calculate_peak(normalized_peak):.4f}")
        print(f"  Original RMS: {AudioAnalyzer.calculate_rms(test_audio):.4f}")
        print(f"  Normalized RMS: {AudioAnalyzer.calculate_rms(normalized_rms):.4f}")
        
        print("\n3. Audio validation...")
        
        # Test validation
        from voicehelpdeskai.core.audio.utils import AudioValidator
        validation = AudioValidator.validate_audio_data(test_audio)
        quality = AudioValidator.check_audio_quality(test_audio, sample_rate)
        
        print(f"  Validation: {validation['valid']}")
        print(f"  Quality: {quality['overall_quality']}")
        
        print("\n4. File operations...")
        
        # Test saving audio
        output_path = Path("temp_audio_test.wav")
        success = save_audio_safely(test_audio, output_path, sample_rate)
        print(f"  Save result: {success}")
        
        if output_path.exists():
            output_path.unlink()  # Clean up
            print("  Cleaned up test file")
        
        print("Audio Utilities demo completed!")
        
    except Exception as e:
        print(f"Audio utilities demo failed: {e}")


async def main():
    """Run all demos."""
    print("VoiceHelpDeskAI Audio System Demo")
    print("=" * 50)
    
    # Run demos
    demo_audio_processor()
    demo_voice_activity_detection()
    demo_audio_queue_system()
    await demo_audio_stream_manager()
    demo_error_handling()
    demo_audio_utilities()
    
    print("\n" + "=" * 50)
    print("All demos completed! 🎉")
    
    # Show final system stats
    error_handler = get_error_handler()
    final_stats = error_handler.get_error_statistics()
    print(f"\nFinal error statistics: {final_stats}")


if __name__ == "__main__":
    # Create examples directory if it doesn't exist
    Path("examples").mkdir(exist_ok=True)
    
    # Run the demo
    asyncio.run(main())