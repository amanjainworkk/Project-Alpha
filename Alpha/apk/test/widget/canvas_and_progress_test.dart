// Project Alpha Mobile APK — Genuine Widget Test Suite
// Verifies OLED Dark Mode Theme, AlphaApp Shell, Navigation, and Tab Previews.
// Conforms to PROJECT.md Feature 66 (OLED Dark Mode Theme System) and Feature 65 (Flutter App Shell).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:alpha_mobile/main.dart';
import 'package:alpha_mobile/theme/theme.dart';
import 'package:alpha_mobile/theme/alpha_colors.dart';
import 'package:alpha_mobile/theme/alpha_theme.dart';
import 'package:alpha_mobile/providers/connection_provider.dart';
import 'package:alpha_mobile/providers/project_provider.dart';
import 'package:alpha_mobile/providers/agent_provider.dart';
import 'package:alpha_mobile/providers/task_provider.dart';

void main() {
  group('AlphaTheme.darkTheme Master Design & OLED Tokens', () {
    testWidgets('propagates high-contrast OLED black, electric cyan, and Material 3 design tokens', (WidgetTester tester) async {
      late BuildContext capturedContext;

      await tester.pumpWidget(
        MaterialApp(
          theme: AlphaTheme.darkTheme,
          home: Builder(
            builder: (context) {
              capturedContext = context;
              return const Scaffold(
                body: Center(child: Text('Theme Diagnostic Probe')),
              );
            },
          ),
        ),
      );

      final theme = Theme.of(capturedContext);

      // Core Material 3 & OLED Pitch Black assertions
      expect(theme.useMaterial3, isTrue);
      expect(theme.brightness, equals(Brightness.dark));
      expect(theme.scaffoldBackgroundColor, equals(AlphaColors.backgroundOled));
      expect(theme.canvasColor, equals(AlphaColors.backgroundOled));
      expect(theme.cardColor, equals(AlphaColors.surfaceLevel2));
      expect(theme.primaryColor, equals(AlphaColors.primaryCyan));

      // ColorScheme assertions
      expect(theme.colorScheme.primary, equals(AlphaColors.primaryCyan));
      expect(theme.colorScheme.onPrimary, equals(AlphaColors.backgroundOled));
      expect(theme.colorScheme.secondary, equals(AlphaColors.secondaryBlue));
      expect(theme.colorScheme.surface, equals(AlphaColors.surfaceLevel1));
      expect(theme.colorScheme.surfaceContainer, equals(AlphaColors.surfaceLevel2));
      expect(theme.colorScheme.surfaceContainerHigh, equals(AlphaColors.surfaceLevel3));
      expect(theme.colorScheme.error, equals(AlphaColors.errorRose));

      // BottomNavigationBar assertions
      expect(theme.bottomNavigationBarTheme.backgroundColor, equals(AlphaColors.surfaceLevel1));
      expect(theme.bottomNavigationBarTheme.selectedItemColor, equals(AlphaColors.primaryCyan));
      expect(theme.bottomNavigationBarTheme.unselectedItemColor, equals(AlphaColors.textMuted));
      expect(theme.bottomNavigationBarTheme.type, equals(BottomNavigationBarType.fixed));

      // Typography helper assertions
      expect(AlphaTheme.monoStyle.fontFamily, equals('Courier'));
      expect(AlphaTheme.monoStyle.color, equals(AlphaColors.textSecondary));
      final pillStyle = AlphaTheme.statusPillStyle(AlphaColors.primaryCyan);
      expect(pillStyle.color, equals(AlphaColors.primaryCyan));
      expect(pillStyle.fontWeight, equals(FontWeight.bold));
    });

    testWidgets('enforces card, button, and input decoration styling', (WidgetTester tester) async {
      late BuildContext capturedContext;

      await tester.pumpWidget(
        MaterialApp(
          theme: AlphaTheme.darkTheme,
          home: Builder(
            builder: (context) {
              capturedContext = context;
              return Scaffold(
                body: Column(
                  children: [
                    const Card(child: Text('Card Content')),
                    ElevatedButton(onPressed: () {}, child: const Text('Action')),
                    OutlinedButton(onPressed: () {}, child: const Text('Secondary')),
                    const TextField(decoration: InputDecoration(hintText: 'Search...')),
                  ],
                ),
              );
            },
          ),
        ),
      );

      final theme = Theme.of(capturedContext);

      // Card theme
      expect(theme.cardTheme.color, equals(AlphaColors.surfaceLevel2));
      expect(theme.cardTheme.elevation, equals(0));
      expect(theme.cardTheme.shape, isA<RoundedRectangleBorder>());

      // Elevated button style
      final elevatedStyle = theme.elevatedButtonTheme.style;
      expect(elevatedStyle?.backgroundColor?.resolve({}), equals(AlphaColors.primaryCyan));
      expect(elevatedStyle?.foregroundColor?.resolve({}), equals(AlphaColors.backgroundOled));

      // Outlined button style
      final outlinedStyle = theme.outlinedButtonTheme.style;
      expect(outlinedStyle?.foregroundColor?.resolve({}), equals(AlphaColors.primaryCyan));

      // Input decoration theme
      final inputTheme = theme.inputDecorationTheme;
      expect(inputTheme.filled, isTrue);
      expect(inputTheme.fillColor, equals(AlphaColors.surfaceLevel1));
      expect(inputTheme.prefixIconColor, equals(AlphaColors.primaryCyan));
    });
  });

  group('AlphaApp Root Application Shell', () {
    testWidgets('builds successfully with MultiProvider hierarchy and OLED dark theme', (WidgetTester tester) async {
      await tester.pumpWidget(const AlphaApp());
      await tester.pump();

      expect(find.byType(AlphaApp), findsOneWidget);
      expect(find.byType(AlphaMainScreen), findsOneWidget);
      expect(find.byType(MaterialApp), findsOneWidget);

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.title, equals('Project Alpha'));
      expect(materialApp.themeMode, equals(ThemeMode.dark));
      expect(materialApp.debugShowCheckedModeBanner, isFalse);

      // AppBar brand components
      expect(find.text('ALPHA'), findsOneWidget);
      expect(find.text('OS'), findsOneWidget);
      expect(find.text('v1.0.0'), findsOneWidget);

      // Default offline connection pill
      expect(find.text('OFFLINE'), findsOneWidget);

      // Sync telemetry refresh button
      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });
  });

  group('AlphaMainScreen Navigation & Tab Shell', () {
    testWidgets('renders all 5 command tabs in BottomNavigationBar with icons and labels', (WidgetTester tester) async {
      await tester.pumpWidget(const AlphaApp());
      await tester.pump();

      expect(find.byType(BottomNavigationBar), findsOneWidget);
      expect(find.text('Canvas'), findsOneWidget);
      expect(find.text('Tasks'), findsOneWidget);
      expect(find.text('CEO Chat'), findsOneWidget);
      expect(find.text('Boardroom'), findsOneWidget);
      expect(find.text('Vault'), findsOneWidget);

      expect(find.byIcon(Icons.hub_outlined), findsOneWidget);
      expect(find.byIcon(Icons.checklist_rtl_rounded), findsOneWidget);
      expect(find.byIcon(Icons.chat_bubble_outline), findsOneWidget);
      expect(find.byIcon(Icons.groups_outlined), findsOneWidget);
      expect(find.byIcon(Icons.storage_outlined), findsOneWidget);
    });

    testWidgets('switches active views across all 5 command tabs upon bottom bar interaction', (WidgetTester tester) async {
      await tester.pumpWidget(const AlphaApp());
      await tester.pump();

      // Tab 0 (Initial): Canvas
      expect(find.text('Archify+ Living Canvas'), findsOneWidget);
      expect(find.text('Interactive Node Graph & Pulsing Telemetry Flow'), findsOneWidget);

      // Switch to Tab 1: Tasks
      await tester.tap(find.text('Tasks'));
      await tester.pump();
      expect(find.text('Task Command Center'), findsOneWidget);
      expect(find.text('Granular Progress Bars & Execution Ticker'), findsOneWidget);

      // Switch to Tab 2: CEO Chat
      await tester.tap(find.text('CEO Chat'));
      await tester.pump();
      expect(find.text('CEO Command Console'), findsOneWidget);
      expect(find.text('Goal Intake, Plan Approval & Synthesis Stream'), findsOneWidget);

      // Switch to Tab 3: Boardroom
      await tester.tap(find.text('Boardroom'));
      await tester.pump();
      expect(find.text('The Boardroom'), findsOneWidget);
      expect(find.text('13 C-Suite Agents Roster & Telemetry Cards'), findsOneWidget);

      // Switch to Tab 4: Vault
      await tester.tap(find.text('Vault'));
      await tester.pump();
      expect(find.text("Alpha's Vault"), findsOneWidget);
      expect(find.text('Persistent Knowledge, Architecture & Schemas'), findsOneWidget);
    });

    testWidgets('updates connection status pill dynamically across state transitions', (WidgetTester tester) async {
      final connectionProvider = ConnectionProvider();
      final projectProvider = ProjectProvider();
      final agentProvider = AgentProvider();
      final taskProvider = TaskProvider();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<ConnectionProvider>.value(value: connectionProvider),
            ChangeNotifierProvider<ProjectProvider>.value(value: projectProvider),
            ChangeNotifierProvider<AgentProvider>.value(value: agentProvider),
            ChangeNotifierProvider<TaskProvider>.value(value: taskProvider),
          ],
          child: MaterialApp(
            theme: AlphaTheme.darkTheme,
            home: const AlphaMainScreen(),
          ),
        ),
      );
      await tester.pump();

      // Initial state: Disconnected -> OFFLINE
      expect(find.text('OFFLINE'), findsOneWidget);

      // State transition: Connecting -> CONNECTING
      connectionProvider.setStatus(ConnectionStatus.connecting);
      await tester.pump();
      expect(find.text('CONNECTING'), findsOneWidget);

      // State transition: Connected -> ONLINE
      connectionProvider.setStatus(ConnectionStatus.connected);
      await tester.pump();
      expect(find.text('ONLINE'), findsOneWidget);
    });
  });

  group('TabPlaceholder Preview Component', () {
    testWidgets('renders OLED preview card with LinearProgressIndicator and active telemetry status', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AlphaTheme.darkTheme,
          home: const Scaffold(
            body: TabPlaceholder(
              title: 'Task Command Center',
              subtitle: 'Granular Progress Bars & Execution Ticker',
              icon: Icons.checklist_rtl_rounded,
              accentColor: AlphaColors.secondaryBlue,
            ),
          ),
        ),
      );

      expect(find.text('Task Command Center'), findsOneWidget);
      expect(find.text('Granular Progress Bars & Execution Ticker'), findsOneWidget);
      expect(find.byIcon(Icons.checklist_rtl_rounded), findsOneWidget);
      expect(find.text('OLED STATUS PREVIEW'), findsOneWidget);
      expect(find.text('ACTIVE'), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      expect(find.text('Pulsing telemetry stream connected to desktop:8765'), findsOneWidget);

      final progressIndicator = tester.widget<LinearProgressIndicator>(find.byType(LinearProgressIndicator));
      expect(progressIndicator.value, equals(0.85));
      expect(progressIndicator.backgroundColor, equals(AlphaColors.borderSubtle));
    });
  });
}
