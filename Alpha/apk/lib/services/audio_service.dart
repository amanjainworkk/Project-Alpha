// Project Alpha Mobile APK — Tactile Audio & Haptic Feedback Service
// Conforms to Feature 77 (Tactile Audio Feedback & SFX System)
// Architecture: Singleton + ChangeNotifier for reactive UI settings and system-sound fallback

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Enumeration of all discrete audio telemetry feedback events in Project Alpha.
enum AudioEvent {
  /// Triggered upon task completion (e.g. goal reached, subtask verified).
  taskCompleted,

  /// High-priority alert triggered when CAO auditor rejects plan or security breach occurs.
  auditBreachAlert,

  /// Ambient pulse feedback triggered when live telemetry flows or websocket frames stream.
  pulseFlowActive,

  /// Confirmation sound triggered when Founder sends a directive to CEO agent.
  messageSent,

  /// Subtle tactile click triggered on bottom bar command navigation or tab switch.
  navigationTick,
}

/// Audit record of an emitted audio event for diagnostics, settings verification, and unit tests.
class AudioEventRecord {
  final AudioEvent event;
  final DateTime timestamp;
  final double volume;
  final bool isAudioMuted;
  final bool isHapticsMuted;

  const AudioEventRecord({
    required this.event,
    required this.timestamp,
    required this.volume,
    required this.isAudioMuted,
    required this.isHapticsMuted,
  });

  @override
  String toString() =>
      'AudioEventRecord(event: $event, vol: $volume, audioMuted: $isAudioMuted, hapticsMuted: $isHapticsMuted)';
}

/// Tactile Audio & SFX Feedback Service for Project Alpha Mobile.
/// Provides safe platform-agnostic fallbacks when hardware audio or system sound is unavailable.
class AlphaAudioService extends ChangeNotifier {
  static final AlphaAudioService instance = AlphaAudioService._internal();

  bool _isAudioEnabled = true;
  bool _isHapticsEnabled = true;
  double _volume = 1.0;

  int _taskCompletedCount = 0;
  int _auditBreachCount = 0;
  int _pulseFlowCount = 0;
  int _messageSentCount = 0;
  int _navigationTickCount = 0;

  AudioEvent? _lastEvent;
  final List<AudioEventRecord> _eventHistory = [];

  /// Optional listener hook for custom audio adapters, SFX engines, or test spies.
  void Function(AudioEvent event)? onSoundTriggered;

  AlphaAudioService._internal();

  factory AlphaAudioService({
    bool isAudioEnabled = true,
    bool isHapticsEnabled = true,
    double volume = 1.0,
  }) {
    instance._isAudioEnabled = isAudioEnabled;
    instance._isHapticsEnabled = isHapticsEnabled;
    instance._volume = volume.clamp(0.0, 1.0);
    return instance;
  }

  // ---------------------------------------------------------------------------
  // Getters
  // ---------------------------------------------------------------------------

  /// Whether sound playback is enabled.
  bool get isAudioEnabled => _isAudioEnabled;

  /// Whether haptic vibration feedback is enabled.
  bool get isHapticsEnabled => _isHapticsEnabled;

  /// Audio playback volume (0.0 to 1.0).
  double get volume => _volume;

  int get taskCompletedCount => _taskCompletedCount;
  int get auditBreachCount => _auditBreachCount;
  int get pulseFlowCount => _pulseFlowCount;
  int get messageSentCount => _messageSentCount;
  int get navigationTickCount => _navigationTickCount;
  int get totalEventsCount =>
      _taskCompletedCount +
      _auditBreachCount +
      _pulseFlowCount +
      _messageSentCount +
      _navigationTickCount;

  AudioEvent? get lastEvent => _lastEvent;
  List<AudioEventRecord> get eventHistory => List.unmodifiable(_eventHistory);

  // ---------------------------------------------------------------------------
  // Settings Mutators
  // ---------------------------------------------------------------------------

  void setAudioEnabled(bool enabled) {
    if (_isAudioEnabled != enabled) {
      _isAudioEnabled = enabled;
      notifyListeners();
    }
  }

  void setHapticsEnabled(bool enabled) {
    if (_isHapticsEnabled != enabled) {
      _isHapticsEnabled = enabled;
      notifyListeners();
    }
  }

  void setVolume(double vol) {
    final clamped = vol.clamp(0.0, 1.0);
    if (_volume != clamped) {
      _volume = clamped;
      notifyListeners();
    }
  }

  // ---------------------------------------------------------------------------
  // Feature 77: Tactile Sound Triggers with Platform-Agnostic Fallback
  // ---------------------------------------------------------------------------

  /// Plays a triumphant audio chime and tactile medium pulse upon task completion.
  Future<void> playTaskCompleted() async {
    _recordEvent(AudioEvent.taskCompleted);
    _taskCompletedCount++;
    _lastEvent = AudioEvent.taskCompleted;

    if (_isAudioEnabled && _volume > 0.0) {
      try {
        await SystemSound.play(SystemSoundType.alert);
      } catch (e) {
        debugPrint('AlphaAudioService: playTaskCompleted sound fallback ($e)');
      }
    }

    if (_isHapticsEnabled) {
      try {
        await HapticFeedback.mediumImpact();
      } catch (e) {
        debugPrint('AlphaAudioService: playTaskCompleted haptic fallback ($e)');
      }
    }

    onSoundTriggered?.call(AudioEvent.taskCompleted);
    notifyListeners();
  }

  /// Plays an urgent warning alert and heavy haptic vibration on CAO audit breach.
  Future<void> playAuditBreachAlert() async {
    _recordEvent(AudioEvent.auditBreachAlert);
    _auditBreachCount++;
    _lastEvent = AudioEvent.auditBreachAlert;

    if (_isAudioEnabled && _volume > 0.0) {
      try {
        await SystemSound.play(SystemSoundType.alert);
      } catch (e) {
        debugPrint('AlphaAudioService: playAuditBreachAlert sound fallback ($e)');
      }
    }

    if (_isHapticsEnabled) {
      try {
        await HapticFeedback.heavyImpact();
      } catch (e) {
        debugPrint('AlphaAudioService: playAuditBreachAlert haptic fallback ($e)');
      }
    }

    onSoundTriggered?.call(AudioEvent.auditBreachAlert);
    notifyListeners();
  }

  /// Plays a subtle ambient click and light pulse when Archify+ live flow pulses.
  Future<void> playPulseFlowActive() async {
    _recordEvent(AudioEvent.pulseFlowActive);
    _pulseFlowCount++;
    _lastEvent = AudioEvent.pulseFlowActive;

    if (_isAudioEnabled && _volume > 0.0) {
      try {
        await SystemSound.play(SystemSoundType.click);
      } catch (e) {
        debugPrint('AlphaAudioService: playPulseFlowActive sound fallback ($e)');
      }
    }

    if (_isHapticsEnabled) {
      try {
        await HapticFeedback.lightImpact();
      } catch (e) {
        debugPrint('AlphaAudioService: playPulseFlowActive haptic fallback ($e)');
      }
    }

    onSoundTriggered?.call(AudioEvent.pulseFlowActive);
    notifyListeners();
  }

  /// Plays an affirmative transmission click when Founder dispatches a chat message.
  Future<void> playMessageSent() async {
    _recordEvent(AudioEvent.messageSent);
    _messageSentCount++;
    _lastEvent = AudioEvent.messageSent;

    if (_isAudioEnabled && _volume > 0.0) {
      try {
        await SystemSound.play(SystemSoundType.click);
      } catch (e) {
        debugPrint('AlphaAudioService: playMessageSent sound fallback ($e)');
      }
    }

    if (_isHapticsEnabled) {
      try {
        await HapticFeedback.lightImpact();
      } catch (e) {
        debugPrint('AlphaAudioService: playMessageSent haptic fallback ($e)');
      }
    }

    onSoundTriggered?.call(AudioEvent.messageSent);
    notifyListeners();
  }

  /// Plays a crisp selection tick on bottom navigation tab switches.
  Future<void> playNavigationTick() async {
    _recordEvent(AudioEvent.navigationTick);
    _navigationTickCount++;
    _lastEvent = AudioEvent.navigationTick;

    if (_isAudioEnabled && _volume > 0.0) {
      try {
        await SystemSound.play(SystemSoundType.click);
      } catch (e) {
        debugPrint('AlphaAudioService: playNavigationTick sound fallback ($e)');
      }
    }

    if (_isHapticsEnabled) {
      try {
        await HapticFeedback.selectionClick();
      } catch (e) {
        debugPrint('AlphaAudioService: playNavigationTick haptic fallback ($e)');
      }
    }

    onSoundTriggered?.call(AudioEvent.navigationTick);
    notifyListeners();
  }

  void _recordEvent(AudioEvent event) {
    _eventHistory.insert(
      0,
      AudioEventRecord(
        event: event,
        timestamp: DateTime.now(),
        volume: _volume,
        isAudioMuted: !_isAudioEnabled || _volume == 0.0,
        isHapticsMuted: !_isHapticsEnabled,
      ),
    );
    if (_eventHistory.length > 100) {
      _eventHistory.removeLast();
    }
  }

  void clearHistory() {
    _eventHistory.clear();
    notifyListeners();
  }

  /// Hermetic state reset helper for automated widget and unit test suites.
  void resetForTesting() {
    _isAudioEnabled = true;
    _isHapticsEnabled = true;
    _volume = 1.0;
    _taskCompletedCount = 0;
    _auditBreachCount = 0;
    _pulseFlowCount = 0;
    _messageSentCount = 0;
    _navigationTickCount = 0;
    _lastEvent = null;
    _eventHistory.clear();
    onSoundTriggered = null;
    notifyListeners();
  }
}

/// Ergonomic alias conforming to Project Alpha mobile services conventions.
typedef AudioService = AlphaAudioService;
