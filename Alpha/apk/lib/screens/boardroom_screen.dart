// Project Alpha Mobile APK — Executive Boardroom Screen
// File Target: Alpha/apk/lib/screens/boardroom_screen.dart
// Conforms to Feature 74: 13 C-Suite Agent Cards, Live Telemetry & Model Tier Badges

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../theme/theme.dart';
import '../providers/providers.dart';

/// Executive Boardroom Screen displaying all 13 canonical C-Suite agents,
/// live status pills, token metrics, model tiers, and deep inspection modal.
class BoardroomScreen extends StatefulWidget {
  const BoardroomScreen({super.key});

  @override
  State<BoardroomScreen> createState() => _BoardroomScreenState();
}

class _BoardroomScreenState extends State<BoardroomScreen> {
  String _selectedFilter = 'All';

  final List<String> _filters = [
    'All',
    'Active',
    'Auditing',
    'Idle',
    'Audit Officers',
  ];

  Color _getAgentStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'active':
        return AlphaColors.successEmerald;
      case 'auditing':
        return AlphaColors.accentViolet;
      case 'blocked':
        return AlphaColors.errorRose;
      case 'idle':
      default:
        return AlphaColors.textMuted;
    }
  }

  void _showAgentDetails(BuildContext context, Agent agent) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AlphaColors.surfaceLevel1,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        side: BorderSide(color: AlphaColors.border),
      ),
      builder: (context) {
        final statusColor = _getAgentStatusColor(agent.status);

        return Padding(
          padding: const EdgeInsets.all(20),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
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
                const SizedBox(height: 16),
                Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        color: AlphaColors.surfaceLevel2,
                        shape: BoxShape.circle,
                        border: Border.all(color: AlphaColors.primaryCyan, width: 2),
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        agent.agentId.replaceAll('CAO-', 'C-'),
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                          color: AlphaColors.primaryCyan,
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            agent.fullTitle.isNotEmpty ? agent.fullTitle : agent.role,
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: AlphaColors.textPrimary,
                            ),
                          ),
                          Text(
                            'Agent ID: ${agent.agentId}',
                            style: AlphaTheme.monoStyle.copyWith(fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: AlphaColors.statusBadgeDecoration(statusColor: statusColor),
                      child: Text(
                        agent.status.toUpperCase(),
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: statusColor,
                        ),
                      ),
                    ),
                  ],
                ),
                const Divider(height: 24, color: AlphaColors.borderSubtle),
                const Text(
                  'MODEL CONFIGURATION & METRICS',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: AlphaColors.textMuted,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: _buildMetricTile('Assigned Model', agent.model, Icons.memory),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _buildMetricTile('Cost Today', agent.formattedCost, Icons.attach_money),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: _buildMetricTile('Tokens Used', '${agent.tokensUsed}', Icons.token),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _buildMetricTile('Style', agent.communicationStyle, Icons.chat),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                const Text(
                  'ACTIVE TASK',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: AlphaColors.textMuted,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 6),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AlphaColors.surfaceLevel2,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AlphaColors.borderSubtle),
                  ),
                  child: Text(
                    agent.currentTask,
                    style: const TextStyle(fontSize: 13, color: AlphaColors.textPrimary),
                  ),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    icon: const Icon(Icons.send_rounded, size: 16),
                    label: Text('Direct Message ${agent.agentId}'),
                    onPressed: () {
                      Navigator.pop(context);
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildMetricTile(String label, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AlphaColors.surfaceLevel2,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AlphaColors.borderSubtle),
      ),
      child: Row(
        children: [
          Icon(icon, size: 18, color: AlphaColors.primaryCyan),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(fontSize: 10, color: AlphaColors.textMuted),
                ),
                Text(
                  value,
                  style: AlphaTheme.monoStyle.copyWith(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: AlphaColors.textPrimary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAgentCard(Agent agent) {
    final statusColor = _getAgentStatusColor(agent.status);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      decoration: AlphaColors.oledCardDecoration(
        surfaceColor: AlphaColors.surfaceLevel2,
        borderColor: agent.isActive ? AlphaColors.borderBright : AlphaColors.border,
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _showAgentDetails(context, agent),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: AlphaColors.surfaceLevel3,
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: agent.agentId.contains('CAO')
                            ? AlphaColors.accentViolet
                            : AlphaColors.primaryCyan,
                        width: 1.5,
                      ),
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      agent.agentId.replaceAll('CAO-', 'C-'),
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: agent.agentId.contains('CAO')
                            ? AlphaColors.accentViolet
                            : AlphaColors.primaryCyan,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          agent.fullTitle.isNotEmpty ? agent.fullTitle : agent.role,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: AlphaColors.textPrimary,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        Text(
                          agent.agentId,
                          style: AlphaTheme.monoStyle.copyWith(fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: AlphaColors.statusBadgeDecoration(statusColor: statusColor),
                    child: Text(
                      agent.status.toUpperCase(),
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: statusColor,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: AlphaColors.backgroundOled,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  agent.currentTask,
                  style: const TextStyle(fontSize: 12, color: AlphaColors.textSecondary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: AlphaColors.surfaceLevel3,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      agent.model,
                      style: AlphaTheme.monoStyle.copyWith(fontSize: 10),
                    ),
                  ),
                  Text(
                    '${agent.tokensUsed} toks • ${agent.formattedCost}',
                    style: AlphaTheme.monoStyle.copyWith(fontSize: 11),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AgentProvider>(
      builder: (context, agentProvider, _) {
        final agents = agentProvider.allAgents;
        final filteredAgents = agents.where((a) {
          if (_selectedFilter == 'All') return true;
          if (_selectedFilter == 'Active') return a.isActive;
          if (_selectedFilter == 'Auditing') return a.isAuditing;
          if (_selectedFilter == 'Idle') return a.isIdle;
          if (_selectedFilter == 'Audit Officers') return a.agentId.contains('CAO');
          return true;
        }).toList();

        return Scaffold(
          backgroundColor: AlphaColors.backgroundOled,
          body: Column(
            children: [
              // Boardroom Executive Overview Card
              Container(
                margin: const EdgeInsets.all(16),
                padding: const EdgeInsets.all(16),
                decoration: AlphaColors.oledCardDecoration(
                  surfaceColor: AlphaColors.surfaceLevel1,
                  borderColor: AlphaColors.border,
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildHeaderMetric('13', 'Executives', AlphaColors.primaryCyan),
                    _buildHeaderMetric('${agentProvider.activeCount}', 'Active', AlphaColors.successEmerald),
                    _buildHeaderMetric('${agentProvider.totalTokensToday}', 'Tokens', AlphaColors.secondaryBlue),
                    _buildHeaderMetric(agentProvider.formattedTotalCost, 'Cost Today', AlphaColors.warningAmber),
                  ],
                ),
              ),

              // Filter Chips
              SizedBox(
                height: 36,
                child: ListView.builder(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: _filters.length,
                  itemBuilder: (context, index) {
                    final filter = _filters[index];
                    final isSelected = _selectedFilter == filter;

                    return Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                        label: Text(
                          filter,
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
                              _selectedFilter = filter;
                            });
                          }
                        },
                      ),
                    );
                  },
                ),
              ),

              const SizedBox(height: 8),

              // Executive Agents List
              Expanded(
                child: ListView.builder(
                  padding: const EdgeInsets.only(bottom: 16),
                  itemCount: filteredAgents.length,
                  itemBuilder: (context, index) => _buildAgentCard(filteredAgents[index]),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildHeaderMetric(String value, String label, Color color) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(fontSize: 11, color: AlphaColors.textMuted),
        ),
      ],
    );
  }
}
