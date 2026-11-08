// Project Alpha Mobile APK — Archify+ Living Visual Canvas Screen
// File Target: Alpha/apk/lib/screens/canvas_screen.dart
// Conforms to Task 11: Archify+ Canvas Host, Floating Toolbar & Node Inspector

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../theme/theme.dart';
import '../services/services.dart';
import '../providers/providers.dart';

/// Interactive Canvas Screen hosting the Archify+ living vector node graph,
/// floating zoom/flow controls, live telemetry HUD, and bottom sheet node inspector.
class CanvasScreen extends StatefulWidget {
  const CanvasScreen({super.key});

  @override
  State<CanvasScreen> createState() => _CanvasScreenState();
}

class _CanvasScreenState extends State<CanvasScreen>
    with SingleTickerProviderStateMixin {
  final TransformationController _transformController = TransformationController();
  late AnimationController _pulseController;

  GraphNode? _selectedNode;
  bool _flowsActive = true;
  bool _showLegend = false;

  final List<GraphNode> _nodes = [
    GraphNode(id: 'founder', label: 'Founder Terminal', type: 'founder', status: 'active', dx: 300, dy: 100),
    GraphNode(id: 'ceo', label: 'CEO Orchestrator', type: 'agent', status: 'active', dx: 300, dy: 220),
    GraphNode(id: 'cto', label: 'CTO Architect', type: 'agent', status: 'active', dx: 140, dy: 350),
    GraphNode(id: 'cao_engine', label: 'Dual CAO Gate', type: 'agent', status: 'active', dx: 460, dy: 350),
    GraphNode(id: 'api_gateway', label: 'FastAPI Desktop', type: 'service', status: 'healthy', dx: 300, dy: 480),
    GraphNode(id: 'model_router', label: 'Model Router', type: 'service', status: 'healthy', dx: 140, dy: 610),
    GraphNode(id: 'vault_sqlite', label: 'Vault SQLite', type: 'store', status: 'healthy', dx: 460, dy: 610),
    GraphNode(id: 'vault_chroma', label: 'Vault ChromaDB', type: 'store', status: 'healthy', dx: 460, dy: 730),
  ];

  final List<GraphEdge> _edges = [
    GraphEdge(sourceId: 'founder', targetId: 'ceo', label: 'Directives', isPulsing: true, latencyMs: 4),
    GraphEdge(sourceId: 'ceo', targetId: 'cto', label: 'Delegation', isPulsing: true, latencyMs: 6),
    GraphEdge(sourceId: 'ceo', targetId: 'cao_engine', label: 'Audit Gate', isPulsing: true, latencyMs: 8),
    GraphEdge(sourceId: 'cto', targetId: 'api_gateway', label: 'Execution', isPulsing: true, latencyMs: 12),
    GraphEdge(sourceId: 'api_gateway', targetId: 'model_router', label: 'Inference', isPulsing: true, latencyMs: 18),
    GraphEdge(sourceId: 'api_gateway', targetId: 'vault_sqlite', label: 'KV Read/Write', isPulsing: true, latencyMs: 5),
    GraphEdge(sourceId: 'api_gateway', targetId: 'vault_chroma', label: 'Vector Search', isPulsing: true, latencyMs: 22),
  ];

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _transformController.dispose();
    super.dispose();
  }

  void _zoomIn() {
    final Matrix4 current = _transformController.value;
    final Matrix4 next = current.clone()..scale(1.25);
    _transformController.value = next;
  }

  void _zoomOut() {
    final Matrix4 current = _transformController.value;
    final Matrix4 next = current.clone()..scale(0.8);
    _transformController.value = next;
  }

  void _resetZoom() {
    _transformController.value = Matrix4.identity();
  }

  Color _getNodeColor(String type) {
    switch (type.toLowerCase()) {
      case 'founder':
        return AlphaColors.successEmerald;
      case 'agent':
        return AlphaColors.accentPurple;
      case 'store':
        return AlphaColors.warningAmber;
      case 'service':
      default:
        return AlphaColors.primaryCyan;
    }
  }

  void _showNodeInspector(GraphNode node) {
    setState(() {
      _selectedNode = node;
    });

    final nodeColor = _getNodeColor(node.type);

    showModalBottomSheet(
      context: context,
      backgroundColor: AlphaColors.surfaceLevel1,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        side: BorderSide(color: AlphaColors.border),
      ),
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.all(20),
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
              const SizedBox(height: 14),
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: nodeColor.withOpacity(0.15),
                      shape: BoxShape.circle,
                      border: Border.all(color: nodeColor),
                    ),
                    child: Icon(Icons.hub, size: 20, color: nodeColor),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          node.label,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: AlphaColors.textPrimary,
                          ),
                        ),
                        Text(
                          'ID: ${node.id} • Type: ${node.type}',
                          style: AlphaTheme.monoStyle.copyWith(fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: AlphaColors.statusBadgeDecoration(
                      statusColor: AlphaColors.successEmerald,
                    ),
                    child: Text(
                      node.status.toUpperCase(),
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: AlphaColors.successEmerald,
                      ),
                    ),
                  ),
                ],
              ),
              const Divider(color: AlphaColors.borderSubtle, height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _buildInspectorStat('Coordinates', '(${node.dx.toInt()}, ${node.dy.toInt()})'),
                  _buildInspectorStat('Connected Edges', '3 Active'),
                  _buildInspectorStat('Telemetry Stream', 'Live 60fps'),
                ],
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  icon: const Icon(Icons.check, size: 16),
                  label: const Text('Close Inspector'),
                  onPressed: () => Navigator.pop(context),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildInspectorStat(String label, String value) {
    return Column(
      children: [
        Text(
          value,
          style: AlphaTheme.monoStyle.copyWith(
            fontSize: 12,
            fontWeight: FontWeight.bold,
            color: AlphaColors.textPrimary,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(fontSize: 10, color: AlphaColors.textMuted),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AlphaColors.backgroundOled,
      body: Consumer<TaskProvider>(
        builder: (context, taskProvider, _) {
          final runningTasks = taskProvider.runningTasks;
          final auditingTasks = taskProvider.auditingTasks;
          final bool isSystemActive = runningTasks.isNotEmpty || auditingTasks.isNotEmpty;

          // Compute dynamic node status & active workstreams
          final activeAgents = <String>{};
          for (final t in runningTasks) {
            activeAgents.add(t.assignedAgent.toLowerCase());
          }
          for (final t in auditingTasks) {
            activeAgents.add(t.assignedAgent.toLowerCase());
          }

          // Build dynamic edges: ONLY pulse when system has active work and matching workstreams!
          final dynamicEdges = [
            GraphEdge(
              sourceId: 'founder',
              targetId: 'ceo',
              label: 'Directives',
              isPulsing: isSystemActive,
              latencyMs: 4,
            ),
            GraphEdge(
              sourceId: 'ceo',
              targetId: 'cto',
              label: 'Delegation',
              isPulsing: isSystemActive && (activeAgents.contains('cto') || activeAgents.contains('cpo') || activeAgents.contains('cdo')),
              latencyMs: 6,
            ),
            GraphEdge(
              sourceId: 'ceo',
              targetId: 'cao_engine',
              label: 'Audit Gate',
              isPulsing: isSystemActive && (activeAgents.contains('cao') || activeAgents.contains('cao-claude') || activeAgents.contains('cao-chatgpt') || auditingTasks.isNotEmpty),
              latencyMs: 8,
            ),
            GraphEdge(
              sourceId: 'cto',
              targetId: 'api_gateway',
              label: 'Execution',
              isPulsing: isSystemActive && (activeAgents.contains('cto') || activeAgents.contains('coo')),
              latencyMs: 12,
            ),
            GraphEdge(
              sourceId: 'api_gateway',
              targetId: 'model_router',
              label: 'Inference',
              isPulsing: isSystemActive,
              latencyMs: 18,
            ),
            GraphEdge(
              sourceId: 'api_gateway',
              targetId: 'vault_sqlite',
              label: 'KV Read/Write',
              isPulsing: isSystemActive,
              latencyMs: 5,
            ),
            GraphEdge(
              sourceId: 'api_gateway',
              targetId: 'vault_chroma',
              label: 'Vector Search',
              isPulsing: isSystemActive,
              latencyMs: 22,
            ),
          ];

          String activeTaskName = 'Standby';
          int activeProgress = 0;
          if (runningTasks.isNotEmpty) {
            activeTaskName = runningTasks.first.taskName;
            activeProgress = runningTasks.first.progressPercent;
          } else if (auditingTasks.isNotEmpty) {
            activeTaskName = auditingTasks.first.taskName;
            activeProgress = auditingTasks.first.progressPercent;
          }

          return Stack(
            children: [
              // 1. Interactive Living Canvas
              InteractiveViewer(
                transformationController: _transformController,
                minScale: 0.4,
                maxScale: 3.0,
                boundaryMargin: const EdgeInsets.all(600),
                constrained: false,
                child: SizedBox(
                  width: 700,
                  height: 900,
                  child: AnimatedBuilder(
                    animation: _pulseController,
                    builder: (context, _) {
                      return CustomPaint(
                        painter: _LivingCanvasPainter(
                          nodes: _nodes,
                          edges: dynamicEdges,
                          pulseValue: _pulseController.value,
                          flowsActive: _flowsActive && isSystemActive,
                          selectedNodeId: _selectedNode?.id,
                        ),
                        child: Stack(
                          children: _nodes.map((node) {
                            final nodeColor = _getNodeColor(node.type);
                            final isSelected = _selectedNode?.id == node.id;

                            // Determine dynamic activity label for this node
                            String nodeStatusText = node.type.toUpperCase();
                            bool isNodeWorking = false;
                            if (node.id == 'cto' && (activeAgents.contains('cto') || activeAgents.contains('cpo') || activeAgents.contains('cdo'))) {
                              isNodeWorking = true;
                              nodeStatusText = 'WORKING ($activeProgress%)';
                            } else if (node.id == 'cao_engine' && (activeAgents.contains('cao') || activeAgents.contains('cao-claude') || auditingTasks.isNotEmpty)) {
                              isNodeWorking = true;
                              nodeStatusText = 'AUDITING ($activeProgress%)';
                            } else if (node.id == 'ceo' && isSystemActive) {
                              isNodeWorking = true;
                              nodeStatusText = 'DISPATCHING';
                            } else if (!isSystemActive && (node.type == 'agent' || node.type == 'service')) {
                              nodeStatusText = 'IDLE';
                            }

                            final Color activeColor = isNodeWorking
                                ? AlphaColors.primaryCyanNeon
                                : nodeColor;

                            return Positioned(
                              left: node.dx - 60,
                              top: node.dy - 30,
                              child: GestureDetector(
                                onTap: () => _showNodeInspector(node),
                                child: Container(
                                  width: 120,
                                  height: 60,
                                  padding: const EdgeInsets.all(6),
                                  decoration: BoxDecoration(
                                    color: AlphaColors.surfaceCanvas,
                                    borderRadius: BorderRadius.circular(8),
                                    border: Border.all(
                                      color: isSelected
                                          ? AlphaColors.primaryCyanNeon
                                          : (isNodeWorking ? AlphaColors.primaryCyanNeon : nodeColor),
                                      width: (isSelected || isNodeWorking) ? 2.0 : 1.0,
                                    ),
                                    boxShadow: [
                                      BoxShadow(
                                        color: (isSelected ? AlphaColors.primaryCyanNeon : activeColor)
                                            .withOpacity(isNodeWorking ? 0.6 : 0.2),
                                        blurRadius: (isSelected || isNodeWorking) ? 16 : 8,
                                        spreadRadius: isNodeWorking ? 2 : 1,
                                      ),
                                    ],
                                  ),
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Text(
                                        node.label,
                                        style: const TextStyle(
                                          fontSize: 11,
                                          fontWeight: FontWeight.bold,
                                          color: AlphaColors.textPrimary,
                                        ),
                                        textAlign: TextAlign.center,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        nodeStatusText,
                                        style: TextStyle(
                                          fontSize: 9,
                                          color: isNodeWorking ? AlphaColors.primaryCyanNeon : nodeColor,
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      );
                    },
                  ),
                ),
              ),

              // 2. Top Live Telemetry HUD Bar
              Positioned(
                top: 16,
                left: 16,
                right: 16,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: AlphaColors.oledCardDecoration(
                    surfaceColor: AlphaColors.surfaceLevel1.withOpacity(0.92),
                    borderColor: isSystemActive ? AlphaColors.primaryCyanNeon.withOpacity(0.5) : AlphaColors.border,
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Container(
                            width: 8,
                            height: 8,
                            decoration: BoxDecoration(
                              color: isSystemActive ? AlphaColors.primaryCyanNeon : AlphaColors.textMuted,
                              shape: BoxShape.circle,
                              boxShadow: isSystemActive
                                  ? [
                                      BoxShadow(
                                        color: AlphaColors.primaryCyanNeon.withOpacity(0.8),
                                        blurRadius: 8,
                                        spreadRadius: 2,
                                      ),
                                    ]
                                  : null,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            isSystemActive
                                ? 'ARCHIFY LIVE • ${runningTasks.length + auditingTasks.length} RUNNING'
                                : 'ARCHIFY STANDBY',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: isSystemActive ? AlphaColors.primaryCyanNeon : AlphaColors.textMuted,
                            ),
                          ),
                        ],
                      ),
                      Text(
                        isSystemActive
                            ? '$activeTaskName ($activeProgress%)'
                            : '${_nodes.length} Nodes • ${_edges.length} Flows',
                        style: AlphaTheme.monoStyle.copyWith(
                          fontSize: 11,
                          color: isSystemActive ? AlphaColors.textPrimary : AlphaColors.textSecondary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: AlphaColors.statusBadgeDecoration(
                          statusColor: isSystemActive ? AlphaColors.primaryCyan : AlphaColors.successEmerald,
                        ),
                        child: Text(
                          isSystemActive ? 'EXECUTING' : 'IDLE',
                          style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.bold,
                            color: isSystemActive ? AlphaColors.primaryCyan : AlphaColors.successEmerald,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // 3. Floating Control Toolbar
              Positioned(
                bottom: 24,
                right: 16,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _buildFloatingButton(Icons.add, _zoomIn, 'Zoom In'),
                    const SizedBox(height: 8),
                    _buildFloatingButton(Icons.remove, _zoomOut, 'Zoom Out'),
                    const SizedBox(height: 8),
                    _buildFloatingButton(Icons.center_focus_strong, _resetZoom, 'Reset View'),
                    const SizedBox(height: 8),
                    _buildFloatingButton(
                      _flowsActive ? Icons.waves : Icons.waves_outlined,
                      () {
                        setState(() {
                          _flowsActive = !_flowsActive;
                        });
                      },
                      'Toggle Flows',
                      active: _flowsActive,
                    ),
                    const SizedBox(height: 8),
                    _buildFloatingButton(
                      Icons.layers,
                      () {
                        setState(() {
                          _showLegend = !_showLegend;
                        });
                      },
                      'Legend',
                      active: _showLegend,
                    ),
                  ],
                ),
              ),

              // 4. Node Archetype Legend Overlay
              if (_showLegend)
                Positioned(
                  bottom: 24,
                  left: 16,
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: AlphaColors.oledCardDecoration(
                      surfaceColor: AlphaColors.surfaceLevel1.withOpacity(0.95),
                      borderColor: AlphaColors.border,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text(
                          'NODE ARCHETYPES',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: AlphaColors.textMuted,
                          ),
                        ),
                        const SizedBox(height: 8),
                        _buildLegendItem('Founder Terminal', AlphaColors.successEmerald),
                        _buildLegendItem('Executive Agent', AlphaColors.accentPurple),
                        _buildLegendItem('Core Service', AlphaColors.primaryCyan),
                        _buildLegendItem('Vault Storage', AlphaColors.warningAmber),
                      ],
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildLegendItem  Widget _buildLegendItem(String label, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 8),
          Text(label, style: const TextStyle(fontSize: 11, color: AlphaColors.textSecondary)),
        ],
      ),
    );
  }

  Widget _buildFloatingButton(IconData icon, VoidCallback onTap, String tooltip, {bool active = false}) {
    return FloatingActionButton.small(
      heroTag: tooltip,
      backgroundColor: active ? AlphaColors.primaryCyan : AlphaColors.surfaceLevel2,
      foregroundColor: active ? AlphaColors.backgroundOled : AlphaColors.textPrimary,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(
          color: active ? AlphaColors.primaryCyan : AlphaColors.border,
        ),
      ),
      tooltip: tooltip,
      onPressed: onTap,
      child: Icon(icon, size: 18),
    );
  }
}

/// Canvas Painter rendering OLED grid, cubic Bezier splines, and pulsing glowing packets.
class _LivingCanvasPainter extends CustomPainter {
  final List<GraphNode> nodes;
  final List<GraphEdge> edges;
  final double pulseValue;
  final bool flowsActive;
  final String? selectedNodeId;

  _LivingCanvasPainter({
    required this.nodes,
    required this.edges,
    required this.pulseValue,
    required this.flowsActive,
    this.selectedNodeId,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // 1. Draw subtle OLED grid lines
    final gridPaint = Paint()
      ..color = AlphaColors.borderSubtle.withOpacity(0.4)
      ..strokeWidth = 0.5;

    const double step = 40.0;
    for (double x = 0; x < size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (double y = 0; y < size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    final Map<String, GraphNode> nodeMap = {for (var n in nodes) n.id: n};

    // 2. Draw Splines & Animated Flow Packets
    for (final edge in edges) {
      final src = nodeMap[edge.sourceId];
      final dst = nodeMap[edge.targetId];
      if (src == null || dst == null) continue;

      final start = Offset(src.dx, src.dy);
      final end = Offset(dst.dx, dst.dy);

      final path = Path()..moveTo(start.dx, start.dy);
      final midY = (start.dy + end.dy) / 2;
      path.cubicTo(start.dx, midY, end.dx, midY, end.dx, end.dy);

      final linePaint = Paint()
        ..color = AlphaColors.primaryCyan.withOpacity(0.3)
        ..strokeWidth = 1.5
        ..style = PaintingStyle.stroke;

      canvas.drawPath(path, linePaint);

      // Traveling pulse packet
      if (flowsActive && edge.isPulsing) {
        final pathMetrics = path.computeMetrics().toList();
        if (pathMetrics.isNotEmpty) {
          final metric = pathMetrics.first;
          final tangent = metric.getTangentForOffset(metric.length * pulseValue);
          if (tangent != null) {
            final packetPaint = Paint()
              ..color = AlphaColors.primaryCyanNeon
              ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4.0);

            canvas.drawCircle(tangent.position, 4.0, packetPaint);

            final corePaint = Paint()..color = Colors.white;
            canvas.drawCircle(tangent.position, 2.0, corePaint);
          }
        }
      }
    }
  }

  @override
  bool shouldRepaint(covariant _LivingCanvasPainter oldDelegate) {
    return oldDelegate.pulseValue != pulseValue ||
        oldDelegate.flowsActive != flowsActive ||
        oldDelegate.selectedNodeId != selectedNodeId;
  }
}
