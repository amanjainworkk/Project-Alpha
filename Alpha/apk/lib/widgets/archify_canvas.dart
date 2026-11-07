// Project Alpha Mobile APK â€” Archify+ Living Visual Canvas
// Conforms to Feature 70: Archify+ Vector Node Graph & Custom Painter

import 'package:flutter/material.dart';
import '../models/models.dart';
import '../theme/theme.dart';
import 'pulsing_flow.dart';

/// Callback signature when a graph node is tapped on the canvas.
typedef OnNodeSelectedCallback = void Function(GraphNode node);

/// Interactive Living Visual Canvas widget wrapping CustomPainter in InteractiveViewer.
/// Renders OLED grid, node cards for 4 archetypes (founder, agent, service, store),
/// and delegates animated Bézier spline drawing to PulsingFlow or CustomPainter.
class ArchifyCanvas extends StatelessWidget {
  final List<GraphNode> nodes;
  final List<GraphEdge> edges;
  final TransformationController? transformationController;
  final double pulseValue;
  final bool flowsActive;
  final String? selectedNodeId;
  final OnNodeSelectedCallback? onNodeSelected;
  final double canvasWidth;
  final double canvasHeight;

  const ArchifyCanvas({
    super.key,
    required this.nodes,
    required this.edges,
    this.transformationController,
    this.pulseValue = 0.0,
    this.flowsActive = true,
    this.selectedNodeId,
    this.onNodeSelected,
    this.canvasWidth = 800.0,
    this.canvasHeight = 1000.0,
  });

  static Color getNodeColor(String type) {
    switch (type.toLowerCase()) {
      case 'founder':
        return AlphaColors.successEmerald;
      case 'agent':
        return AlphaColors.accentPurple;
      case 'store':
      case 'storage':
        return AlphaColors.warningAmber;
      case 'service':
      default:
        return AlphaColors.primaryCyan;
    }
  }

  @override
  Widget build(BuildContext context) {
    return InteractiveViewer(
      transformationController: transformationController,
      minScale: 0.4,
      maxScale: 3.0,
      boundaryMargin: const EdgeInsets.all(600),
      constrained: false,
      child: SizedBox(
        width: canvasWidth,
        height: canvasHeight,
        child: CustomPaint(
          painter: ArchifyCanvasPainter(
            nodes: nodes,
            edges: edges,
            pulseValue: pulseValue,
            flowsActive: flowsActive,
            selectedNodeId: selectedNodeId,
          ),
          child: Stack(
            children: nodes.map((node) {
              final nodeColor = getNodeColor(node.type);
              final isSelected = selectedNodeId == node.id;

              return Positioned(
                left: node.dx - 60,
                top: node.dy - 30,
                child: GestureDetector(
                  onTap: () => onNodeSelected?.call(node),
                  child: Container(
                    width: 120,
                    height: 60,
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: AlphaColors.surfaceCanvas,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isSelected ? AlphaColors.primaryCyanNeon : nodeColor,
                        width: isSelected ? 2.0 : 1.0,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: (isSelected ? AlphaColors.primaryCyanNeon : nodeColor)
                              .withOpacity(0.3),
                          blurRadius: isSelected ? 16 : 8,
                          spreadRadius: 1,
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
                          node.type.toUpperCase(),
                          style: TextStyle(
                            fontSize: 9,
                            color: nodeColor,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        ),
      ),
    );
  }
}

/// Standalone CustomPainter for ArchifyCanvas rendering background grid,
/// cubic Bézier curve connections, and moving glow packets.
class ArchifyCanvasPainter extends CustomPainter {
  final List<GraphNode> nodes;
  final List<GraphEdge> edges;
  final double pulseValue;
  final bool flowsActive;
  final String? selectedNodeId;

  ArchifyCanvasPainter({
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

      // Draw pulse packet along spline
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
  bool shouldRepaint(covariant ArchifyCanvasPainter oldDelegate) {
    return oldDelegate.pulseValue != pulseValue ||
        oldDelegate.flowsActive != flowsActive ||
        oldDelegate.selectedNodeId != selectedNodeId;
  }
}
