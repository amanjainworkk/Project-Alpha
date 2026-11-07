// Project Alpha Mobile APK — Master Mobile Screens & Command Center Test Suite
// File Target: Alpha/apk/test/widget/screens_test.dart
// Milestone 11: Features 70, 72, 73, 74, 75, 76, 77
// Verifies genuine mounting and interaction with all 5 screens, ProgressBarCard, and AudioService.
// Zero detached dummy mockup classes — imports genuine production widgets.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:alpha_mobile/main.dart';
import 'package:alpha_mobile/theme/theme.dart';
import 'package:alpha_mobile/theme/alpha_colors.dart';
import 'package:alpha_mobile/theme/alpha_theme.dart';
import 'package:alpha_mobile/models/models.dart';
import 'package:alpha_mobile/providers/providers.dart';
import 'package:alpha_mobile/services/services.dart';
import 'package:alpha_mobile/widgets/widgets.dart';
import 'package:alpha_mobile/screens/screens.dart';

void main() {
  setUp(() {
    AlphaAudioService.instance.resetForTesting();
  });

  tearDown(() {
    AlphaAudioService.instance.resetForTesting();
  });

  // ===========================================================================
  // 1. ProgressBarCard Component Suite (Feature 72)
  // ===========================================================================
  group('ProgressBarCard Widget Suite (Feature 72)', () {
    testWidgets('renders task name, assigned agent chip, status badge, and ASCII progress bar', (WidgetTester tester) async {
      final task = TaskProgress(
        taskId: 'task_apk_compile',
        taskName: 'Compile Android APK',
        progressPercent: 80,
        currentStep: 'Optimizing Proguard R8 bytecode',
        assignedAgent: 'CTO',
        status: 'running',
      );

      bool tapped = false;

      await tester.pumpWidget(
        MaterialApp(
          theme: AlphaTheme.darkTheme,
          home: Scaffold(
            body: Center(
              child: ProgressBarCard(
                task: task,
                onTap: () {
                  tapped = true;
                },
              ),
            ),
          ),
        ),
      );

      // Verify task name, agent chip, and status badge
      expect(find.text('Compile Android APK'), findsOneWidget);
      expect(find.text('CTO'), findsOneWidget);
      expect(find.text('RUNNING'), findsOneWidget);
      expect(find.text('Optimizing Proguard R8 bytecode'), findsOneWidget);

      // Verify ASCII progress bar string
      expect(find.textContaining('[████████░░] 80%'), findsOneWidget);

      // Verify LinearProgressIndicator fraction
      final indicator = tester.widget<LinearProgressIndicator>(find.byType(LinearProgressIndicator));
      expect(indicator.value, equals(0.8));

      // Simulate card tap
      await tester.tap(find.byType(ProgressBarCard));
      expect(tapped, isTrue);
    });

    testWidgets('renders completed state with success emerald styling and 100% progress', (WidgetTester tester) async {
      final completedTask = TaskProgress(
        taskId: 'task_audit_verify',
        taskName: 'CAO Audit Verification',
        progressPercent: 100,
        currentStep: 'Verification Tribunal Verdict: APPROVE',
        assignedAgent: 'CAO-Claude',
        status: 'done',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AlphaTheme.darkTheme,
          home: Scaffold(
            body: ProgressBarCard(task: completedTask),
          ),
        ),
      );

      expect(find.text('CAO Audit Verification'), findsOneWidget);
      expect(find.text('CAO-Claude'), findsOneWidget);
      expect(find.text('DONE'), findsOneWidget);
      expect(find.textContaining('[██████████] 100%'), findsOneWidget);

      final indicator = tester.widget<LinearProgressIndicator>(find.byType(LinearProgressIndicator));
      expect(indicator.value, equals(1.0));
    });

    testWidgets('renders blocked/breach state with error rose badge and checklist items', (WidgetTester tester) async {
      final blockedTask = TaskProgress(
        taskId: 'task_sec_review',
        taskName: 'Security Perimeter Audit',
        progressPercent: 40,
        currentStep: 'Escalation cap reached on round 2',
        assignedAgent: 'CLO',
        status: 'blocked',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AlphaTheme.darkTheme,
          home: Scaffold(
            body: ProgressBarCard(
              task: blockedTask,
              subtasks: const [
                'Token Boundary Audit',
                'Escalation Cap Check',
                'Dual CAO Sign-off',
              ],
            ),
          ),
        ),
      );

      expect(find.text('Security Perimeter Audit'), findsOneWidget);
      expect(find.text('BLOCKED'), findsOneWidget);
      expect(find.text('CLO'), findsOneWidget);
      expect(find.text('Token Boundary Audit'), findsOneWidget);
      expect(find.text('Escalation Cap Check'), findsOneWidget);
      expect(find.text('Dual CAO Sign-off'), findsOneWidget);
    });
  });

  // ===========================================================================
  // 2. Tactile Audio Feedback Service (Feature 77)
  // ===========================================================================
  group('AlphaAudioService Tactile & SFX Suite (Feature 77)', () {
    test('instance returns persistent singleton instance', () {
      final s1 = AlphaAudioService.instance;
      final s2 = AudioService.instance;
      final s3 = AlphaAudioService();
      expect(identical(s1, s2), isTrue);
      expect(identical(s1, s3), isTrue);
    });

    test('sound triggers record events and increment counters', () async {
      final service = AlphaAudioService.instance;

      AudioEvent? triggeredHookEvent;
      service.onSoundTriggered = (e) => triggeredHookEvent = e;

      expect(service.taskCompletedCount, equals(0));
      await service.playTaskCompleted();
      expect(service.taskCompletedCount, equals(1));
      expect(service.lastEvent, equals(AudioEvent.taskCompleted));
      expect(triggeredHookEvent, equals(AudioEvent.taskCompleted));

      await service.playAuditBreachAlert();
      expect(service.auditBreachCount, equals(1));
      expect(service.lastEvent, equals(AudioEvent.auditBreachAlert));

      await service.playPulseFlowActive();
      expect(service.pulseFlowCount, equals(1));
      expect(service.lastEvent, equals(AudioEvent.pulseFlowActive));

      await service.playMessageSent();
      expect(service.messageSentCount, equals(1));
      expect(service.lastEvent, equals(AudioEvent.messageSent));

      await service.playNavigationTick();
      expect(service.navigationTickCount, equals(1));
      expect(service.lastEvent, equals(AudioEvent.navigationTick));

      expect(service.totalEventsCount, equals(5));
      expect(service.eventHistory.length, equals(5));
    });

    test('settings mutators toggle audio, haptics, and volume gracefully', () async {
      final service = AlphaAudioService.instance;

      int notifyCount = 0;
      service.addListener(() => notifyCount++);

      service.setAudioEnabled(false);
      expect(service.isAudioEnabled, isFalse);
      expect(notifyCount, equals(1));

      service.setHapticsEnabled(false);
      expect(service.isHapticsEnabled, isFalse);
      expect(notifyCount, equals(2));

      service.setVolume(0.5);
      expect(service.volume, equals(0.5));
      expect(notifyCount, equals(3));

      // Test clamping boundary
      service.setVolume(2.5);
      expect(service.volume, equals(1.0));

      service.setVolume(-0.5);
      expect(service.volume, equals(0.0));

      // Trigger while muted records muted state in history
      await service.playNavigationTick();
      expect(service.eventHistory.first.isAudioMuted, isTrue);
      expect(service.eventHistory.first.isHapticsMuted, isTrue);

      service.clearHistory();
      expect(service.eventHistory, isEmpty);
    });

    test('silent fallback handles headless environment without exceptions', () async {
      final service = AlphaAudioService.instance;
      service.setAudioEnabled(true);
      service.setHapticsEnabled(true);

      // In a flutter test runner, SystemSound / HapticFeedback fail silently or execute no-op.
      // Must not throw unhandled exceptions.
      expect(() async => await service.playTaskCompleted(), returnsNormally);
      expect(() async => await service.playAuditBreachAlert(), returnsNormally);
      expect(() async => await service.playPulseFlowActive(), returnsNormally);
      expect(() async => await service.playMessageSent(), returnsNormally);
      expect(() async => await service.playNavigationTick(), returnsNormally);
    });
  });

  // ===========================================================================
  // 3. 5-Screen Command Center Component Tests (Features 70, 73, 74, 75, 76)
  // ===========================================================================
  group('5-Screen Command Center Component Suites', () {
    testWidgets('CanvasScreen mounts ArchifyCanvas, toolbar controls, and node inspector', (WidgetTester tester) async {
      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<ConnectionProvider>(create: (_) => ConnectionProvider()),
            ChangeNotifierProvider<ProjectProvider>(create: (_) => ProjectProvider()),
            ChangeNotifierProvider<AgentProvider>(create: (_) => AgentProvider()),
            ChangeNotifierProvider<TaskProvider>(create: (_) => TaskProvider()),
            ChangeNotifierProvider<AlphaAudioService>(create: (_) => AlphaAudioService.instance),
          ],
          child: MaterialApp(
            theme: AlphaTheme.darkTheme,
            home: const Scaffold(
              body: CanvasScreen(),
            ),
          ),
        ),
      );
      await tester.pump();

      // Screen Header
      expect(find.text('Archify+ Living Canvas'), findsOneWidget);
      expect(find.text('Interactive Node Graph & Pulsing Telemetry Flow'), findsOneWidget);

      // Interactive Canvas & Toolbar Buttons
      expect(find.byType(ArchifyCanvas), findsOneWidget);
      expect(find.byIcon(Icons.zoom_in), findsOneWidget);
      expect(find.byIcon(Icons.zoom_out), findsOneWidget);
      expect(find.byIcon(Icons.center_focus_strong), findsOneWidget);
      expect(find.byIcon(Icons.bolt), findsOneWidget);

      // Tap Zoom In and verify no exceptions
      await tester.tap(find.byIcon(Icons.zoom_in));
      await tester.pump();
    });

    testWidgets('TasksScreen renders filter chips and lists active ProgressBarCard items', (WidgetTester tester) async {
      final taskProvider = TaskProvider();
      taskProvider.updateTask(
        TaskProgress(
          taskId: 'task_001',
          taskName: 'Initialize SQLite Vault',
          progressPercent: 90,
          currentStep: 'Running migrations',
          assignedAgent: 'CTO',
          status: 'running',
        ),
      );
      taskProvider.updateTask(
        TaskProgress(
          taskId: 'task_002',
          taskName: 'Draft Marketing Copy',
          progressPercent: 100,
          currentStep: 'Copy finalized',
          assignedAgent: 'CMO',
          status: 'done',
        ),
      );

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<TaskProvider>.value(value: taskProvider),
            ChangeNotifierProvider<AlphaAudioService>(create: (_) => AlphaAudioService.instance),
          ],
          child: MaterialApp(
            theme: AlphaTheme.darkTheme,
            home: const Scaffold(
              body: TasksScreen(),
            ),
          ),
        ),
      );
      await tester.pump();

      // Screen Header
      expect(find.text('Task Command Center'), findsOneWidget);
      expect(find.text('Granular Progress Bars & Execution Ticker'), findsOneWidget);

      // Filter chips
      expect(find.text('All'), findsOneWidget);
      expect(find.text('Running'), findsOneWidget);
      expect(find.text('Done'), findsOneWidget);

      // Task cards rendered
      expect(find.text('Initialize SQLite Vault'), findsOneWidget);
      expect(find.text('Draft Marketing Copy'), findsOneWidget);
      expect(find.byType(ProgressBarCard), findsNWidgets(2));

      // Filter by 'Running'
      await tester.tap(find.text('Running'));
      await tester.pump();
      expect(find.text('Initialize SQLite Vault'), findsOneWidget);
    });

    testWidgets('ChatScreen renders message stream, tool execution cards, input bar, and triggers audio', (WidgetTester tester) async {
      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<AgentProvider>(create: (_) => AgentProvider()),
            ChangeNotifierProvider<AlphaAudioService>(create: (_) => AlphaAudioService.instance),
          ],
          child: MaterialApp(
            theme: AlphaTheme.darkTheme,
            home: const Scaffold(
              body: ChatScreen(),
            ),
          ),
        ),
      );
      await tester.pump();

      // Screen Header
      expect(find.text('CEO Command Console'), findsOneWidget);
      expect(find.text('Goal Intake, Plan Approval & Synthesis Stream'), findsOneWidget);

      // Input field and send button
      expect(find.byType(TextField), findsOneWidget);
      expect(find.byIcon(Icons.send), findsOneWidget);

      // Enter directive and tap send
      await tester.enterText(find.byType(TextField), 'Launch Autonomous Sprint 12');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pump();

      // Verify audio feedback triggered
      expect(AlphaAudioService.instance.messageSentCount, equals(1));
    });

    testWidgets('BoardroomScreen renders 13 executive C-Suite agent cards, status pills, and token metrics', (WidgetTester tester) async {
      final agentProvider = AgentProvider();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<AgentProvider>.value(value: agentProvider),
            ChangeNotifierProvider<AlphaAudioService>(create: (_) => AlphaAudioService.instance),
          ],
          child: MaterialApp(
            theme: AlphaTheme.darkTheme,
            home: const Scaffold(
              body: BoardroomScreen(),
            ),
          ),
        ),
      );
      await tester.pump();

      // Screen Header
      expect(find.text('The Boardroom'), findsOneWidget);
      expect(find.text('13 C-Suite Agents Roster & Telemetry Cards'), findsOneWidget);

      // Verify core C-Suite roster cards
      expect(find.text('CEO'), findsOneWidget);
      expect(find.text('CTO'), findsOneWidget);
      expect(find.text('CMO'), findsOneWidget);
      expect(find.text('CFO'), findsOneWidget);
      expect(find.text('CAO-Claude'), findsOneWidget);
      expect(find.text('CAO-ChatGPT'), findsOneWidget);
    });

    testWidgets('VaultScreen renders document tree hierarchy, vector search bar, and episodic memories', (WidgetTester tester) async {
      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<ProjectProvider>(create: (_) => ProjectProvider()),
            ChangeNotifierProvider<AlphaAudioService>(create: (_) => AlphaAudioService.instance),
          ],
          child: MaterialApp(
            theme: AlphaTheme.darkTheme,
            home: const Scaffold(
              body: VaultScreen(),
            ),
          ),
        ),
      );
      await tester.pump();

      // Screen Header
      expect(find.text("Alpha's Vault"), findsOneWidget);
      expect(find.text('Persistent Knowledge, Architecture & Schemas'), findsOneWidget);

      // Document folders
      expect(find.text('projects/'), findsOneWidget);
      expect(find.text('audit/'), findsOneWidget);
      expect(find.text('system/'), findsOneWidget);

      // Search input
      expect(find.byType(TextField), findsOneWidget);
    });
  });

  // ===========================================================================
  // 4. AlphaMainScreen Master Shell & IndexedStack Navigation
  // ===========================================================================
  group('AlphaMainScreen Shell & Navigation Integration', () {
    testWidgets('switches views across all 5 command tabs and triggers navigation tick audio', (WidgetTester tester) async {
      await tester.pumpWidget(const AlphaApp());
      await tester.pump();

      expect(AlphaAudioService.instance.navigationTickCount, equals(0));

      // Tab 0 (Initial): Canvas
      expect(find.text('Archify+ Living Canvas'), findsOneWidget);
      expect(find.byType(CanvasScreen), findsOneWidget);

      // Switch to Tab 1: Tasks
      await tester.tap(find.text('Tasks'));
      await tester.pump();
      expect(find.text('Task Command Center'), findsOneWidget);
      expect(find.byType(TasksScreen), findsOneWidget);
      expect(AlphaAudioService.instance.navigationTickCount, equals(1));

      // Switch to Tab 2: CEO Chat
      await tester.tap(find.text('CEO Chat'));
      await tester.pump();
      expect(find.text('CEO Command Console'), findsOneWidget);
      expect(find.byType(ChatScreen), findsOneWidget);
      expect(AlphaAudioService.instance.navigationTickCount, equals(2));

      // Switch to Tab 3: Boardroom
      await tester.tap(find.text('Boardroom'));
      await tester.pump();
      expect(find.text('The Boardroom'), findsOneWidget);
      expect(find.byType(BoardroomScreen), findsOneWidget);
      expect(AlphaAudioService.instance.navigationTickCount, equals(3));

      // Switch to Tab 4: Vault
      await tester.tap(find.text('Vault'));
      await tester.pump();
      expect(find.text("Alpha's Vault"), findsOneWidget);
      expect(find.byType(VaultScreen), findsOneWidget);
      expect(AlphaAudioService.instance.navigationTickCount, equals(4));
    });
  });
}
