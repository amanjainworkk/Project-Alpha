// Project Alpha Mobile Living Canvas & Command Center
// Design System: OLED Dark Mode Color Tokens & Decoration Helpers
// Master Design Spec §11.3 & CDO Job Description §4.1

import 'package:flutter/material.dart';

/// Authentic Project Alpha OLED Design Tokens.
/// Specially calibrated for high-contrast pitch-black battery-saving OLED screens,
/// with electric cyan and blue neon highlights and WCAG AAA compliance.
abstract class AlphaColors {
  // ---------------------------------------------------------------------------
  // 1. OLED Pitch Black Backgrounds
  // ---------------------------------------------------------------------------

  /// Pure OLED pitch-black background (#0A0A0F) — true black for zero-power pixels.
  static const Color backgroundOled = Color(0xFF0A0A0F);

  /// Deep secondary background (#07070A) for canvas backdrop or letterboxing.
  static const Color backgroundDark = Color(0xFF07070A);

  // ---------------------------------------------------------------------------
  // 2. High-Contrast Dark Surfaces
  // ---------------------------------------------------------------------------

  /// Surface Level 1 (#12121A) — App bars, bottom nav bar, dialogs, drawers.
  static const Color surfaceLevel1 = Color(0xFF12121A);

  /// Surface Level 2 / Card (#1A1A24) — Elevated cards, list tiles, containers.
  static const Color surfaceLevel2 = Color(0xFF1A1A24);

  /// Surface Level 3 (#222230) — Active states, nested containers, hover items.
  static const Color surfaceLevel3 = Color(0xFF222230);

  /// Surface Variant (#161622) — Subtle variant for executive cards.
  static const Color surfaceVariant = Color(0xFF161622);

  /// Surface Canvas Node (#1E1E2E) — Archify vector node background.
  static const Color surfaceCanvas = Color(0xFF1E1E2E);

  // ---------------------------------------------------------------------------
  // 3. Borders & Dividers
  // ---------------------------------------------------------------------------

  /// Primary Structural Border (#2A2A38) — Card boundaries, dialog edges.
  static const Color border = Color(0xFF2A2A38);

  /// Subtle Border / Divider (#1E293B) — List item separators, inner outlines.
  static const Color borderSubtle = Color(0xFF1E293B);

  /// Bright / Highlight Border (#3B4261) — Focused or active selection ring.
  static const Color borderBright = Color(0xFF3B4261);

  // ---------------------------------------------------------------------------
  // 4. Primary Accents — Electric Cyan
  // ---------------------------------------------------------------------------

  /// Primary Accent Cyan (#06B6D4) — Action buttons, active progress, live flow.
  static const Color primaryCyan = Color(0xFF06B6D4);

  /// Electric Neon Cyan (#00F0FF) — Glow halo, pulsing data packet highlight.
  static const Color primaryCyanNeon = Color(0xFF00F0FF);

  /// Muted / Dark Cyan (#0891B2) — Pressed buttons, disabled accents.
  static const Color primaryCyanDark = Color(0xFF0891B2);

  /// 40% Opacity Cyan Glow (#6606B6D4).
  static const Color primaryCyanGlow = Color(0x6606B6D4);

  // ---------------------------------------------------------------------------
  // 5. Secondary Accents — Electric Blue
  // ---------------------------------------------------------------------------

  /// Secondary Accent Blue (#3B82F6) — Executive roles, links, secondary action.
  static const Color secondaryBlue = Color(0xFF3B82F6);

  /// Bright Blue (#2563EB) — Interactive hover and focus highlight.
  static const Color secondaryBlueBright = Color(0xFF2563EB);

  /// Dark Blue (#1D4ED8) — Pressed states and subtle secondary backgrounds.
  static const Color secondaryBlueDark = Color(0xFF1D4ED8);

  /// 40% Opacity Blue Glow (#663B82F6).
  static const Color secondaryBlueGlow = Color(0x663B82F6);

  // ---------------------------------------------------------------------------
  // 6. Tertiary Accents — Royal Purple
  // ---------------------------------------------------------------------------

  /// Tertiary Royal Purple (#8B5CF6) — Strategy, OKRs, and special indicators.
  static const Color accentPurple = Color(0xFF8B5CF6);

  /// Violet / Audit Accent (#A855F7) — CAO audit review markers.
  static const Color accentViolet = Color(0xFFA855F7);

  // ---------------------------------------------------------------------------
  // 7. Status & Telemetry Accents
  // ---------------------------------------------------------------------------

  /// Success Emerald (#10B981) — Completed tasks, healthy nodes, connected backend.
  static const Color successEmerald = Color(0xFF10B981);

  /// Success Glow (#6610B981).
  static const Color successEmeraldGlow = Color(0x6610B981);

  /// Warning Amber (#F59E0B) — Thinking state, review requested, token alert.
  static const Color warningAmber = Color(0xFFF59E0B);

  /// Warning Glow (#66F59E0B).
  static const Color warningAmberGlow = Color(0x66F59E0B);

  /// Error / Breach Rose (#EF4444) — Blocked tasks, CAO audit flag, disconnection.
  static const Color errorRose = Color(0xFFEF4444);

  /// Neon Bright Breach (#F43F5E) — High-severity breach pulse.
  static const Color errorRoseBright = Color(0xFFF43F5E);

  /// Error Glow (#66EF4444).
  static const Color errorRoseGlow = Color(0x66EF4444);

  // ---------------------------------------------------------------------------
  // 8. Typography Tokens
  // ---------------------------------------------------------------------------

  /// Primary Text (#F8FAFC) — High-contrast white for headings and critical text.
  static const Color textPrimary = Color(0xFFF8FAFC);

  /// Secondary Text (#94A3B8) — Medium-contrast cool gray for body and subheads.
  static const Color textSecondary = Color(0xFF94A3B8);

  /// Muted Text (#64748B) — Low-contrast slate for captions, metadata, timestamps.
  static const Color textMuted = Color(0xFF64748B);

  /// Inverse Text (#0A0A0F) — Dark text on bright neon chips and badges.
  static const Color textInverse = Color(0xFF0A0A0F);

  // ---------------------------------------------------------------------------
  // 9. Neon Glow Shadow Helpers
  // ---------------------------------------------------------------------------

  /// Returns a glowing cyan BoxShadow for active cards and pulsing nodes.
  static BoxShadow cyanGlowShadow({
    double blurRadius = 16.0,
    double spreadRadius = 1.0,
    double opacity = 0.4,
  }) {
    return BoxShadow(
      color: primaryCyan.withOpacity(opacity),
      blurRadius: blurRadius,
      spreadRadius: spreadRadius,
    );
  }

  /// Returns a glowing blue BoxShadow for executive cards and secondary items.
  static BoxShadow blueGlowShadow({
    double blurRadius = 16.0,
    double spreadRadius = 1.0,
    double opacity = 0.4,
  }) {
    return BoxShadow(
      color: secondaryBlue.withOpacity(opacity),
      blurRadius: blurRadius,
      spreadRadius: spreadRadius,
    );
  }

  /// Returns an emerald BoxShadow for healthy nodes and completion badges.
  static BoxShadow emeraldGlowShadow({
    double blurRadius = 12.0,
    double spreadRadius = 1.0,
    double opacity = 0.4,
  }) {
    return BoxShadow(
      color: successEmerald.withOpacity(opacity),
      blurRadius: blurRadius,
      spreadRadius: spreadRadius,
    );
  }

  /// Returns an amber BoxShadow for warnings and thinking states.
  static BoxShadow amberGlowShadow({
    double blurRadius = 12.0,
    double spreadRadius = 1.0,
    double opacity = 0.4,
  }) {
    return BoxShadow(
      color: warningAmber.withOpacity(opacity),
      blurRadius: blurRadius,
      spreadRadius: spreadRadius,
    );
  }

  /// Returns a rose BoxShadow for errors and blocked tasks.
  static BoxShadow roseGlowShadow({
    double blurRadius = 14.0,
    double spreadRadius = 1.0,
    double opacity = 0.4,
  }) {
    return BoxShadow(
      color: errorRose.withOpacity(opacity),
      blurRadius: blurRadius,
      spreadRadius: spreadRadius,
    );
  }

  // ---------------------------------------------------------------------------
  // 10. BoxDecoration Helpers
  // ---------------------------------------------------------------------------

  /// Standard OLED Card decoration with subtle border and optional glow.
  static BoxDecoration oledCardDecoration({
    Color surfaceColor = surfaceLevel2,
    Color borderColor = border,
    double borderRadius = 12.0,
    List<BoxShadow>? shadows,
  }) {
    return BoxDecoration(
      color: surfaceColor,
      borderRadius: BorderRadius.circular(borderRadius),
      border: Border.all(color: borderColor, width: 1.0),
      boxShadow: shadows,
    );
  }

  /// Neon-bordered decoration for active nodes, focused cards, and interactive canvas.
  static BoxDecoration neonBorderDecoration({
    required Color accentColor,
    Color surfaceColor = surfaceLevel2,
    double borderRadius = 12.0,
    double width = 1.5,
    bool hasGlow = true,
  }) {
    return BoxDecoration(
      color: surfaceColor,
      borderRadius: BorderRadius.circular(borderRadius),
      border: Border.all(color: accentColor, width: width),
      boxShadow: hasGlow
          ? [
              BoxShadow(
                color: accentColor.withOpacity(0.35),
                blurRadius: 14.0,
                spreadRadius: 1.0,
              ),
            ]
          : null,
    );
  }

  /// Status chip / pill badge decoration (e.g. RUNNING, BLOCKED, AUDITING, DONE).
  static BoxDecoration statusBadgeDecoration({
    required Color statusColor,
    double bgOpacity = 0.15,
    double borderRadius = 6.0,
  }) {
    return BoxDecoration(
      color: statusColor.withOpacity(bgOpacity),
      borderRadius: BorderRadius.circular(borderRadius),
      border: Border.all(color: statusColor.withOpacity(0.5), width: 1.0),
    );
  }

  /// Archify vector node box decoration.
  static BoxDecoration canvasNodeDecoration({
    required Color nodeColor,
    bool isSelected = false,
  }) {
    return BoxDecoration(
      color: surfaceCanvas,
      borderRadius: BorderRadius.circular(8.0),
      border: Border.all(
        color: isSelected ? primaryCyanNeon : nodeColor,
        width: isSelected ? 2.0 : 1.0,
      ),
      boxShadow: isSelected
          ? [
              BoxShadow(
                color: primaryCyanNeon.withOpacity(0.5),
                blurRadius: 16.0,
                spreadRadius: 2.0,
              ),
            ]
          : null,
    );
  }

  /// Standard brand linear gradient from Cyan to Blue.
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [primaryCyan, secondaryBlue],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}
