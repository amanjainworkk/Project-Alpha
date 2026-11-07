// Project Alpha Mobile APK — Granular Tasks Screen
// File Target: Alpha/apk/lib/screens/tasks_screen.dart
// Conforms to Feature 75: Filterable Tasks, ASCII Progress Bars & Execution Ticker

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../theme/theme.dart';
import '../providers/providers.dart';
import '../widgets/progress_bar_card.dart';

/// Granular Tasks Screen with status filters, overall progress gauge,
/// real-time task cards, and expandable execution log stream.
class TasksScreen extends StatefulWidget {
  const TasksScreen({super.key});

  @override
  State<TasksScreen> createState() => _TasksScreenState();
}

class _TasksScreenState extends State<TasksScreen> {
  String _activeFilter = 'all'; // 'all', 'running', 'auditing', 'blocked', 'done'
  String _searchQuery = '';
  final TextEditingController _searchController = TextEditingController();

  final List<Map<String, String>> _filterOptions = [
    {'id': 'all', 'label': 'All Tasks'},
    {'id': 'running', 'label': 'Running'},
    {'id': 'auditing', 'label': 'Auditing'},
    {'id': 'blocked', 'label': 'Blocked'},
    {'id': 'done', 'label': 'Completed'},
  ];

  @override
  void initState() {
    super.initState();
    _populateDefaultTasksIfEmpty();
  }

  void _populateDefaultTasksIfEmpty() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final taskProvider = context.read<TaskProvider>();
      if (taskProvider.allTasks.isEmpty) {
        taskProvider.updateTask(
          TaskProgress(
            taskId: 'task_001',
            taskName: 'Generate Tech Spec & Canvas Schemas',
            progressPercent: 80,
            currentStep: 'Resolving CAO audit flags',
            assignedAgent: 'CTO',
            status: 'auditing',
          ),
        );
        taskProvider.updateTask(
          TaskProgress(
            taskId: 'task_002',
            taskName: 'Dual CAO Compliance Verification',
            progressPercent: 90,
            currentStep: 'Running Claude & GPT consensus check',
            assignedAgent: 'CAO-Claude',
            status: 'running',
          ),
        );
        taskProvider.updateTask(
          TaskProgress(
            taskId: 'task_003',
            taskName: 'Design System & OLED Token Calibration',
            progressPercent: 100,
            currentStep: 'OLED tokens and themes verified',
            assignedAgent: 'CDO',
            status: 'done',
          ),
        );
        taskProvider.updateTask(
          TaskProgress(
            taskId: 'task_004',
            taskName: 'FastAPI WebSocket Stream Telemetry',
            progressPercent: 65,
            currentStep: 'Streaming node pulse packets',
            assignedAgent: 'COO',
            status: 'running',
          ),
        );
      }
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _showExecutionLogs(BuildContext context, TaskProvider taskProvider) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AlphaColors.surfaceLevel1,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        side: BorderSide(color: AlphaColors.border),
      ),
      builder: (context) {
        final logs = taskProvider.executionLogs;

        return Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AlphaColors.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'LIVE EXECUTION LOGS',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: AlphaColors.textPrimary,
                    ),
                  ),
                  TextButton(
                    onPressed: () {
                      taskProvider.clearLogs();
                      Navigator.pop(context);
                    },
                    child: const Text('Clear', style: TextStyle(color: AlphaColors.primaryCyan)),
                  ),
                ],
              ),
              const Divider(color: AlphaColors.borderSubtle),
              Expanded(
                child: logs.isEmpty
                    ? const Center(
                        child: Text(
                          'No logs recorded yet.',
                          style: TextStyle(color: AlphaColors.textMuted),
                        ),
                      )
                    : ListView.builder(
                        itemCount: logs.length,
                        itemBuilder: (context, index) => Padding(
                          padding: const EdgeInsets.symmetric(vertical: 2),
                          child: Text(
                            logs[index],
                            style: AlphaTheme.monoStyle.copyWith(fontSize: 11),
                          ),
                        ),
                      ),
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<TaskProvider>(
      builder: (context, taskProvider, _) {
        final allTasks = taskProvider.allTasks;
        final filteredTasks = allTasks.where((task) {
          if (_activeFilter != 'all') {
            if (_activeFilter == 'running' && !task.isRunning) return false;
            if (_activeFilter == 'auditing' && !task.isAuditing) return false;
            if (_activeFilter == 'blocked' && !task.isBlocked) return false;
            if (_activeFilter == 'done' && !task.isDone) return false;
          }
          if (_searchQuery.isNotEmpty) {
            final query = _searchQuery.toLowerCase();
            final matchesName = task.taskName.toLowerCase().contains(query);
            final matchesAgent = task.assignedAgent.toLowerCase().contains(query);
            final matchesStep = task.currentStep.toLowerCase().contains(query);
            if (!matchesName && !matchesAgent && !matchesStep) return false;
          }
          return true;
        }).toList();

        return Scaffold(
          backgroundColor: AlphaColors.backgroundOled,
          body: Column(
            children: [
              // 1. Overall Progress Header Card
              Container(
                margin: const EdgeInsets.all(16),
                padding: const EdgeInsets.all(16),
                decoration: AlphaColors.oledCardDecoration(
                  surfaceColor: AlphaColors.surfaceLevel1,
                  borderColor: AlphaColors.border,
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'OVERALL PROGRESS',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: AlphaColors.textMuted,
                            letterSpacing: 0.5,
                          ),
                        ),
                        Text(
                          '${(taskProvider.overallProgress * 100).round()}%',
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: AlphaColors.primaryCyan,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: taskProvider.overallProgress,
                        minHeight: 6,
                        backgroundColor: AlphaColors.borderSubtle,
                        valueColor: const AlwaysStoppedAnimation<Color>(AlphaColors.primaryCyan),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        _buildCounter('Total', '${taskProvider.totalCount}', AlphaColors.textPrimary),
                        _buildCounter('Running', '${taskProvider.runningCount}', AlphaColors.primaryCyan),
                        _buildCounter('Blocked', '${taskProvider.blockedCount}', AlphaColors.errorRose),
                        _buildCounter('Done', '${taskProvider.doneCount}', AlphaColors.successEmerald),
                      ],
                    ),
                  ],
                ),
              ),

              // 2. Search & Log Button Row
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  children: [
                    Expanded(
                      child: SizedBox(
                        height: 38,
                        child: TextField(
                          controller: _searchController,
                          style: const TextStyle(fontSize: 13, color: AlphaColors.textPrimary),
                          decoration: InputDecoration(
                            hintText: 'Filter tasks or agents...',
                            hintStyle: const TextStyle(color: AlphaColors.textMuted, fontSize: 12),
                            prefixIcon: const Icon(Icons.search, size: 16, color: AlphaColors.textMuted),
                            contentPadding: EdgeInsets.zero,
                            fillColor: AlphaColors.surfaceLevel2,
                            filled: true,
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(8),
                              borderSide: const BorderSide(color: AlphaColors.border),
                            ),
                            enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(8),
                              borderSide: const BorderSide(color: AlphaColors.border),
                            ),
                          ),
                          onChanged: (val) {
                            setState(() {
                              _searchQuery = val;
                            });
                          },
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton(
                      icon: const Icon(Icons.terminal, color: AlphaColors.primaryCyan),
                      tooltip: 'View Execution Logs',
                      onPressed: () => _showExecutionLogs(context, taskProvider),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 8),

              // 3. Filter Chips
              SizedBox(
                height: 34,
                child: ListView.builder(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: _filterOptions.length,
                  itemBuilder: (context, index) {
                    final opt = _filterOptions[index];
                    final isSelected = _activeFilter == opt['id'];

                    return Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                        label: Text(
                          opt['label']!,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                            color: isSelected
                                ? AlphaColors.backgroundOled
                                : AlphaColors.textSecondary,
                          ),
                        ),
                        selected: isSelected,
                        selectedColor: AlphaColors.primaryCyan,
                        backgroundColor: AlphaColors.surfaceLevel2,
                        side: BorderSide(
                          color: isSelected ? AlphaColors.primaryCyan : AlphaColors.border,
                        ),
                        onSelected: (selected) {
                          if (selected) {
                            setState(() {
                              _activeFilter = opt['id']!;
                            });
                          }
                        },
                      ),
                    );
                  },
                ),
              ),

              const SizedBox(height: 8),

              // 4. Tasks List
              Expanded(
                child: filteredTasks.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.task_alt, size: 48, color: AlphaColors.textMuted.withOpacity(0.5)),
                            const SizedBox(height: 12),
                            const Text(
                              'No matching tasks found',
                              style: TextStyle(color: AlphaColors.textSecondary, fontSize: 14),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.only(bottom: 16),
                        itemCount: filteredTasks.length,
                        itemBuilder: (context, index) => ProgressBarCard(
                          task: filteredTasks[index],
                        ),
                      ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildCounter(String label, String value, Color color) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: const TextStyle(fontSize: 10, color: AlphaColors.textMuted),
        ),
      ],
    );
  }
}
