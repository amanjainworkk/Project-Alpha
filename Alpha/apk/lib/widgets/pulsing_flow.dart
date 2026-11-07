// Project Alpha Mobile APK â€” Pulsing Data Flow Widget
// Conforms to Feature 71: Live Pulsing Data Flows & Bézier Splines

import 'package:flutter/material.dart';
import '../models/models.dart';
import '../theme/theme.dart';

/// Standalone Animated Pulsing Flow widget rendering cubic Bézier curves,
/// glowing traveling pulse particles, and optional latency badges between nodes.
class PulsingFlow extends StatefulWidget {
  final Offset sourceOffset;
  final Offset targetOffset;
  final GraphEdge edge;
  final bool isPulsing;
  final Color pulseColor;
  final bool showLatencyBadge;

  const PulsingFlow({
    super.key,
    required this.sourceOffset,
    required this.targetOffset,
    required this.edge,
    this.isPulsing = true,
    this.pulseColor = AlphaColors.primaryCyanNeon,
    this.showLatencyBadge = true,
  });

  @override
  State<PulsingFlow> createState() => _PulsingFlowState();
}

class _PulsingFlowState extends State<PulsingFlow>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    );
    if (widget.isPulsing) {
      _controller.repeat();
    }
  }

  @override
  void didUpdateWidget(covariant PulsingFlow oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isPulsing != oldWidget.isPulsing) {
      if (widget.isPulsing) {
        _controller.repeat();
      } else {
        _controller.stop();
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return CustomPaint(
          painter: PulsingFlowPainter(
            source: widget.sourceOffset,
            target: widget.targetOffset,
            pulseValue: _controller.value,
            isPulsing: widget.isPulsing,
            pulseColor: widget.pulseColor,
            latencyMs: widget.showLatencyBadge ? widget.edge.latencyMs : null,
          ),
        );
      },
    );
  }
}

/// CustomPainter rendering a single cubic Bézier spline with animated glow particle
class PulsingFlowPainter extends CustomPainter {
  final Offset source;
  final Offset target;
  final double pulseValue;
  final bool isPulsing;
  final Color pulseColor;
  final int? latencyMs;

  PulsingFlowPainter({
    required this.source,
    required this.target,
    required this.pulseValue,
    required this.isPulsing,
    required this.pulseColor,
    this.latencyMs,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final path = Path()..moveTo(source.dx, source.dy);
    final midY = (source.dy + target.dy) / 2;
    path.cubicTo(source.dx, midY, target.dx, midY, target.dx, target.dy);

    final linePaint = Paint()
      ..color = pulseColor.withOpacity(0.35)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    canvas.drawPath(path, linePaint);

    if (isPulsing) {
      final metrics = path.computeMetrics().toList();
      if (metrics.isNotEmpty) {
        final metric = metrics.first;
        final tangent = metric.getTangentForOffset(metric.length * pulseValue);
        if (tangent != null) {
          final glowPaint = Paint()
            ..color = pulseColor
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4.0);

          canvas.drawCircle(tangent.position, 4.0, glowPaint);

          final corePaint = Paint()..color = Colors.white;
          canvas.drawCircle(tangent.position, 2.0, corePaint);
        }
      }
    }
  }

  @override
  bool shouldRepaint(covariant PulsingFlowPainter oldDelegate) {
    return oldDelegate.pulseValue != pulseValue ||
        oldDelegate.isPulsing != isPulsing ||
        oldDelegate.source != source ||
        oldDelegate.target != target;
  }
}
