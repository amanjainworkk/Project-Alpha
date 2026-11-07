// Project Alpha Mobile APK — Granular Task Progress Bar Card
// File Target: Alpha/apk/lib/widgets/progress_bar_card.dart
// Conforms to Feature 72, Task 11, and Milestone 10 Model Specifications

import 'package:flutter/material.dart';
import '../models/models.dart';
import '../theme/theme.dart';

/// Granular Task Progress Card featuring textual ASCII progress bar,
/// animated OLED gradient indicator, assigned C-Suite agent chip, and subtask checklist.
class ProgressBarCard extends StatefulWidget {
  final TaskProgress task;
  final VoidCallback? onTap;
  final bool initiallyExpanded;
  final ValueChanged<int>? onSubtaskToggled;

  const ProgressBarCard({
    super.key,
    required this.task,
    this.onTap,
    this.initiallyExpanded = false,
    this.onSubtaskToggled,
  });

  @override
  State<ProgressBarCard> createState() => _ProgressBarCardState();
}

class _ProgressBarCardState extends State<ProgressBarCard>
    with SingleTickerProviderStateMixin {
  late bool _isExpanded;
  late AnimationController _pulseController;
  late Animation<double> _glowAnimation;

  @override
  void initState() {
    super.initState();
    _isExpanded = widget.initiallyExpanded;
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    );
    _glowAnimation = Tween<double>(begin: 0.3, end: 0.8).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );

    if (widget.task.isRunning) {
      _pulseController.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(covariant ProgressBarCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.task.isRunning && !_pulseController.isAnimating) {
      _pulseController.repeat(reverse: true);
    } else if (!widget.task.isRunning && _pulseController.isAnimating) {
      _pulseController.stop();
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Color _getStatusColor() {
    if (widget.task.isDone) return AlphaColors.successEmerald;
    if (widget.task.isBlocked) return AlphaColors.errorRose;
    if (widget.task.isFailed) return AlphaColors.errorRose;
    if (widget.task.isAuditing) return AlphaColors.accentViolet;
    return AlphaColors.primaryCyan;
  }

  String _getStatusLabel() {
    final s = widget.task.status.toUpperCase();
    if (widget.task.isDone) return 'DONE';
    if (widget.task.isBlocked) return 'BLOCKED';
    if (widget.task.isFailed) return 'FAILED';
    if (widget.task.isAuditing) return 'AUDITING';
    return s.isNotEmpty ? s : 'RUNNING';
  }

  List<String> _generateSubtasks() {
    final step = widget.task.currentStep;
    final pct = widget.task.progressPercent;
    return [
      'Initialize context & Vault parameters',
      'Execute model generation ($step)',
      'Dual CAO compliance review',
      'Persist deliverables to Vault store',
    ];
  }

  @override
  Widget build(BuildContext context) {
    final statusColor = _getStatusColor();
    final statusLabel = _getStatusLabel();
    final subtasks = _generateSubtasks();

    return AnimatedBuilder(
      animation: _glowAnimation,
      builder: (context, child) {
        return Container(
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: AlphaColors.surfaceLevel2,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: widget.task.isRunning
                  ? statusColor.withOpacity(_glowAnimation.value)
                  : AlphaColors.border,
              width: widget.task.isRunning ? 1.5 : 1.0,
            ),
            boxShadow: widget.task.isRunning
                ? [
                    BoxShadow(
                      color: statusColor.withOpacity(0.25 * _glowAnimation.value),
                      blurRadius: 14,
                      spreadRadius: 1,
                    )
                  ]
                : null,
          ),
          child: InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: widget.onTap ?? () {
              setState(() {
                _isExpanded = !_isExpanded;
              });
            },
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 1. Header Row: Task Name + Status Badge + Agent Chip
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Agent Chip
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AlphaColors.surfaceLevel3,
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: AlphaColors.secondaryBlue.withOpacity(0.5)),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.psychology, size: 14, color: AlphaColors.secondaryBlue),
                            const SizedBox(width: 4),
                            Text(
                              widget.task.assignedAgent.isNotEmpty
                                  ? widget.task.assignedAgent
                                  : 'CEO',
                              style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                color: AlphaColors.textPrimary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 10),
                      // Task Name
                      Expanded(
                        child: Text(
                          widget.task.taskName.isNotEmpty
                              ? widget.task.taskName
                              : widget.task.taskId,
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: AlphaColors.textPrimary,
                            letterSpacing: -0.2,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Status Badge
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: AlphaColors.statusBadgeDecoration(statusColor: statusColor),
                        child: Text(
                          statusLabel,
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: statusColor,
                            letterSpacing: 0.5,
                          ),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 12),

                  // 2. Monospace ASCII Progress Bar
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: AlphaColors.backgroundOled,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: AlphaColors.borderSubtle),
                    ),
                    child: Text(
                      widget.task.formatProgressBar(),
                      style: AlphaTheme.monoStyle.copyWith(
                        color: statusColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                        letterSpacing: 1.0,
                      ),
                    ),
                  ),

                  const SizedBox(height: 10),

                  // 3. High-Contrast Gradient Visual Progress Indicator
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: Stack(
                      children: [
                        // Track
                        Container(
                          height: 6,
                          width: double.infinity,
                          color: AlphaColors.borderSubtle,
                        ),
                        // Fill bar with gradient
                        FractionallySizedBox(
                          widthFactor: widget.task.progressFraction,
                          child: Container(
                            height: 6,
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: [
                                  AlphaColors.primaryCyan,
                                  statusColor,
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 10),

                  // 4. Current Step Ticker
                  Row(
                    children: [
                      Icon(
                        widget.task.isDone
                            ? Icons.check_circle_outline
                            : widget.task.isBlocked
                                ? Icons.warning_amber_rounded
                                : Icons.sync,
                        size: 14,
                        color: statusColor,
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          widget.task.currentStep.isNotEmpty
                              ? widget.task.currentStep
                              : 'Awaiting execution instruction',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AlphaColors.textSecondary,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Icon(
                        _isExpanded ? Icons.expand_less : Icons.expand_more,
                        size: 18,
                        color: AlphaColors.textMuted,
                      ),
                    ],
                  ),

                  // 5. Expandable Subtask Checklist
                  if (_isExpanded) ...[
                    const Divider(height: 20, color: AlphaColors.borderSubtle),
                    const Text(
                      'SUBTASK EXECUTION CHECKLIST',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: AlphaColors.textMuted,
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(height: 8),
                    ...List.generate(subtasks.length, (index) {
                      final isStepDone = (index + 1) * 25 <= widget.task.progressPercent ||
                          widget.task.isDone;
                      final isCurrent = !isStepDone &&
                          (index * 25 < widget.task.progressPercent);

                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Row(
                          children: [
                            Icon(
                              isStepDone
                                  ? Icons.check_circle
                                  : isCurrent
                                      ? Icons.radio_button_checked
                                      : Icons.radio_button_unchecked,
                              size: 16,
                              color: isStepDone
                                  ? AlphaColors.successEmerald
                                  : isCurrent
                                      ? AlphaColors.primaryCyan
                                      : AlphaColors.textMuted,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                subtasks[index],
                                style: TextStyle(
                                  fontSize: 12,
                                  color: isStepDone
                                      ? AlphaColors.textSecondary
                                      : isCurrent
                                          ? AlphaColors.textPrimary
                                          : AlphaColors.textMuted,
                                  decoration: isStepDone
                                      ? TextDecoration.lineThrough
                                      : null,
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    }),
                  ],
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
