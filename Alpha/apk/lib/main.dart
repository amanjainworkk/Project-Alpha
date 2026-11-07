// Project Alpha Mobile APK — Main Application Entrypoint
// Architecture: MultiProvider State Orchestration + OLED Dark Mode Theme
// Master Design Spec §10-§11 & 12-Task Implementation Plan (Task 10)

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'theme/alpha_colors.dart';
import 'theme/alpha_theme.dart';

import 'services/api_client.dart';
import 'services/websocket_service.dart';
import 'services/audio_service.dart';

import 'providers/connection_provider.dart';
import 'providers/project_provider.dart';
import 'providers/agent_provider.dart';
import 'providers/task_provider.dart';

import 'screens/canvas_screen.dart';
import 'screens/tasks_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/boardroom_screen.dart';
import 'screens/vault_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AlphaApp());
}

/// Root Application Widget for Project Alpha Mobile.
class AlphaApp extends StatelessWidget {
  const AlphaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        // ---------------------------------------------------------------------
        // 1. Core Network & Telemetry Services
        // ---------------------------------------------------------------------
        Provider<AlphaApiClient>(
          create: (_) => AlphaApiClient(
            baseUrl: 'https://blogging-paths-worth-lending.trycloudflare.com',
          ),
          dispose: (_, client) => client.dispose(),
        ),
        Provider<AlphaWebSocketService>(
          create: (_) => AlphaWebSocketService(
            host: 'blogging-paths-worth-lending.trycloudflare.com',
          ),
          dispose: (_, ws) => ws.dispose(),
        ),

        // ---------------------------------------------------------------------
        // 2. State Management Providers
        // ---------------------------------------------------------------------
        ChangeNotifierProvider<ConnectionProvider>(
          create: (context) {
            final provider = ConnectionProvider(
              apiClient: context.read<AlphaApiClient>(),
              wsService: context.read<AlphaWebSocketService>(),
            );
            scheduleMicrotask(() => provider.initialize());
            return provider;
          },
        ),
        ChangeNotifierProvider<ProjectProvider>(
          create: (context) {
            final provider = ProjectProvider(
              apiClient: context.read<AlphaApiClient>(),
              wsService: context.read<AlphaWebSocketService>(),
            );
            scheduleMicrotask(() => provider.loadProjects());
            return provider;
          },
        ),
        ChangeNotifierProvider<AgentProvider>(
          create: (context) {
            final provider = AgentProvider(
              apiClient: context.read<AlphaApiClient>(),
              wsService: context.read<AlphaWebSocketService>(),
            );
            scheduleMicrotask(() => provider.loadAgents());
            return provider;
          },
        ),
        ChangeNotifierProvider<TaskProvider>(
          create: (context) => TaskProvider(
            wsService: context.read<AlphaWebSocketService>(),
          ),
        ),
      ],
      child: MaterialApp(
        title: 'Project Alpha',
        debugShowCheckedModeBanner: false,
        theme: AlphaTheme.darkTheme,
        darkTheme: AlphaTheme.darkTheme,
        themeMode: ThemeMode.dark,
        home: const AlphaMainScreen(),
      ),
    );
  }
}

/// Main Navigation Shell with 5 Core Command Tabs.
class AlphaMainScreen extends StatefulWidget {
  const AlphaMainScreen({super.key});

  @override
  State<AlphaMainScreen> createState() => _AlphaMainScreenState();
}

class _AlphaMainScreenState extends State<AlphaMainScreen> {
  int _currentIndex = 0;

  void _showServerConfigDialog(BuildContext context) {
    final connection = context.read<ConnectionProvider>();
    final controller = TextEditingController(text: connection.backendBaseUrl);

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AlphaColors.surfaceLevel2,
        title: const Text('Backend Server Connection', style: TextStyle(color: AlphaColors.textPrimary, fontSize: 16)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Enter your PC IP address (e.g. http://192.168.1.18:8765):',
              style: TextStyle(color: AlphaColors.textSecondary, fontSize: 13),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              style: AlphaTheme.monoStyle.copyWith(color: AlphaColors.primaryCyanNeon, fontSize: 14),
              decoration: const InputDecoration(
                hintText: 'http://192.168.1.18:8765',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.wifi, color: AlphaColors.primaryCyan),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              final newUrl = controller.text.trim();
              if (newUrl.isNotEmpty) {
                final wsUrl = newUrl.replaceFirst('http://', 'ws://').replaceFirst('https://', 'wss://') + '/ws';
                connection.updateEndpoints(baseUrl: newUrl, wsUrl: wsUrl);
                connection.checkHealth();
                Navigator.pop(ctx);
              }
            },
            child: const Text('Connect'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AlphaColors.backgroundOled,
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                gradient: AlphaColors.primaryGradient,
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Text(
                'ALPHA',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                  color: AlphaColors.backgroundOled,
                  letterSpacing: 1.0,
                ),
              ),
            ),
            const SizedBox(width: 8),
            const Text(
              'OS',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AlphaColors.textPrimary,
              ),
            ),
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: AlphaColors.surfaceLevel3,
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Text(
                'v1.0.0',
                style: TextStyle(
                  fontSize: 10,
                  color: AlphaColors.textMuted,
                  fontFamily: 'Courier',
                ),
              ),
            ),
          ],
        ),
        actions: [
          // Real-time Connection State Pill
          Consumer<ConnectionProvider>(
            builder: (context, connection, _) {
              final isConnected = connection.isConnected;
              final isConnecting = connection.isConnecting;
              final Color statusColor = isConnected
                  ? AlphaColors.successEmerald
                  : isConnecting
                      ? AlphaColors.warningAmber
                      : AlphaColors.errorRose;
              final String statusText = isConnected
                  ? 'ONLINE'
                  : isConnecting
                      ? 'CONNECTING'
                      : 'OFFLINE';

              return GestureDetector(
                onTap: () => _showServerConfigDialog(context),
                child: Container(
                margin: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: statusColor.withOpacity(0.4)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 7,
                      height: 7,
                      decoration: BoxDecoration(
                        color: statusColor,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: statusColor.withOpacity(0.6),
                            blurRadius: 6,
                            spreadRadius: 1,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      statusText,
                      style: TextStyle(
                        color: statusColor,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
              ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh, size: 20, color: AlphaColors.textSecondary),
            tooltip: 'Sync Telemetry',
            onPressed: () {
              context.read<ProjectProvider>().loadProjects();
              context.read<AgentProvider>().loadAgents();
            },
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: const [
          CanvasScreen(),
          TasksScreen(),
          ChatScreen(),
          BoardroomScreen(),
          VaultScreen(),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.hub_outlined),
            activeIcon: Icon(Icons.hub),
            label: 'Canvas',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.checklist_rtl_rounded),
            activeIcon: Icon(Icons.checklist_rounded),
            label: 'Tasks',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.chat_bubble_outline),
            activeIcon: Icon(Icons.chat_bubble),
            label: 'CEO Chat',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.groups_outlined),
            activeIcon: Icon(Icons.groups),
            label: 'Boardroom',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.storage_outlined),
            activeIcon: Icon(Icons.storage),
            label: 'Vault',
          ),
        ],
      ),
    );
  }
}

/// Fallback preview widget illustrating OLED theme and telemetry cards.
class TabPlaceholder extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final Color accentColor;

  const TabPlaceholder({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.accentColor,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AlphaColors.surfaceLevel1,
                shape: BoxShape.circle,
                border: Border.all(color: accentColor.withOpacity(0.5), width: 1.5),
                boxShadow: [
                  BoxShadow(
                    color: accentColor.withOpacity(0.25),
                    blurRadius: 24,
                    spreadRadius: 2,
                  ),
                ],
              ),
              child: Icon(icon, size: 48, color: accentColor),
            ),
            const SizedBox(height: 24),
            Text(
              title,
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: AlphaColors.textPrimary,
                letterSpacing: -0.3,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              subtitle,
              style: const TextStyle(
                fontSize: 14,
                color: AlphaColors.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: AlphaColors.oledCardDecoration(
                surfaceColor: AlphaColors.surfaceLevel2,
                borderColor: AlphaColors.border,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'OLED STATUS PREVIEW',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: AlphaColors.textMuted,
                          letterSpacing: 0.5,
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: AlphaColors.statusBadgeDecoration(
                          statusColor: accentColor,
                        ),
                        child: Text(
                          'ACTIVE',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: accentColor,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  const LinearProgressIndicator(
                    value: 0.85,
                    backgroundColor: AlphaColors.borderSubtle,
                    valueColor: AlwaysStoppedAnimation<Color>(AlphaColors.primaryCyan),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Pulsing telemetry stream connected to desktop:8765',
                    style: TextStyle(fontSize: 12, color: AlphaColors.textSecondary),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Backward compatibility alias for main navigation shell.
typedef _TabPlaceholder = TabPlaceholder;
